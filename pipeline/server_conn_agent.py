"""Self-Defending SDN Tower - 서버 연결 상태 수집기 (Slow HTTP 판단용).

스위치 카운터는 패킷 개수만 세서 '연결 하나가 얼마나 오래, 얼마나 느리게 쓰이는지'를 볼 수 없다.
그래서 보호 서버에서 열린 HTTP 연결을 2초마다 `ss`로 읽어, 접속한 PC마다 '느린 요청' 연결 수를
sdn:stats:serverconn으로 발행한다. Apache mod_reqtimeout과 같은 기준이다:

* 느린 요청 = 연결된 지 SLOW_AGE_SEC(20초) 이상 지났는데 서버가 아직 응답을 한 바이트도 보내지 않았고
  (요청이 끝나지 않음), 받은 요청이 초당 SLOW_RATE_BPS(500B) 미만인 연결.

실행 (서버에서): python -m pipeline.server_conn_agent --port 80
테스트베드: Mininet 호스트의 네트워크 공간에서 ss를 실행하도록 --netns-pid <h_server의 PID>를 준다.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from harness.contracts import REDIS_CHANNEL_SERVER_CONNS, ServerConnItem, ServerConnMessage

SLOW_AGE_SEC = 20.0
SLOW_RATE_BPS = 500.0
_FIELD = re.compile(r"\b(bytes_received|bytes_acked):(\d+)")


@dataclass
class Conn:
    peer_ip: str
    peer_port: int
    bytes_received: int
    bytes_acked: int


def _split_addr(addr: str) -> Tuple[str, int]:
    host, _, port = addr.rpartition(":")
    host = host.strip("[]")
    if host.startswith("::ffff:"):
        host = host[len("::ffff:"):]
    return host, int(port)


def parse_ss(output: str) -> List[Conn]:
    """`ss -Htin state established '( sport = :80 )'` 출력 → 연결 목록 (주소 줄 + 들여 쓴 상세 줄)."""
    conns: List[Conn] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        if not line[0].isspace():
            parts = line.split()
            if len(parts) >= 4:
                ip, port = _split_addr(parts[3])
                conns.append(Conn(ip, port, 0, 0))
        elif conns:
            fields = dict(_FIELD.findall(line))
            conns[-1].bytes_received = int(fields.get("bytes_received", 0))
            conns[-1].bytes_acked = int(fields.get("bytes_acked", 0))
    return conns


class ConnTracker:
    """연결을 처음 본 시각을 기억해 나이(초)를 계산하고, 접속한 PC마다 열린 연결과 느린 요청 수를 센다."""

    def __init__(self, slow_age: float = SLOW_AGE_SEC, slow_rate: float = SLOW_RATE_BPS) -> None:
        self.slow_age = slow_age
        self.slow_rate = slow_rate
        self.first_seen: Dict[Tuple[str, int], float] = {}

    def update(self, conns: List[Conn], now: float) -> Dict[str, Tuple[int, int]]:
        alive = set()
        per_ip: Dict[str, List[int]] = {}
        for c in conns:
            key = (c.peer_ip, c.peer_port)
            alive.add(key)
            age = now - self.first_seen.setdefault(key, now)
            # 서버가 보낸 응답이 없다(bytes_acked ≤ 1: SYN-ACK만 확인됨) = 요청이 아직 끝나지 않았다
            slow = age >= self.slow_age and c.bytes_acked <= 1 and c.bytes_received / max(age, 1e-9) < self.slow_rate
            counts = per_ip.setdefault(c.peer_ip, [0, 0])
            counts[0] += 1
            counts[1] += int(slow)
        for key in list(self.first_seen):
            if key not in alive:
                del self.first_seen[key]
        return {ip: (n, slow) for ip, (n, slow) in per_ip.items()}


def ss_command(port: int, netns_pid: Optional[int]) -> List[str]:
    cmd = ["ss", "-Htin", "state", "established", f"( sport = :{port} )"]
    return (["nsenter", f"--net=/proc/{netns_pid}/ns/net"] + cmd) if netns_pid else cmd


def build_message(server_ip: str, port: int, per_ip: Dict[str, Tuple[int, int]], now: float) -> ServerConnMessage:
    return ServerConnMessage(timestamp=now, server_ip=server_ip, port=port, clients=[
        ServerConnItem(client_ip=ip, open=n, slow=slow) for ip, (n, slow) in sorted(per_ip.items())])


def main() -> None:
    p = argparse.ArgumentParser(description="서버 연결 상태 수집기 (Slow HTTP 판단용)")
    p.add_argument("--server-ip", default="10.0.0.4")
    p.add_argument("--port", type=int, default=80)
    p.add_argument("--interval", type=float, default=2.0)
    p.add_argument("--redis-url", default="redis://localhost:6379/0")
    p.add_argument("--netns-pid", type=int, help="이 프로세스의 네트워크 공간에서 ss 실행 (Mininet 호스트)")
    a = p.parse_args()

    import redis
    r = redis.Redis.from_url(a.redis_url)
    tracker = ConnTracker()
    cmd = ss_command(a.port, a.netns_pid)
    print(f"[server_conn_agent] watching {a.server_ip}:{a.port} every {a.interval}s", flush=True)
    while True:
        out = subprocess.run(cmd, capture_output=True, text=True).stdout
        now = time.time()
        msg = build_message(a.server_ip, a.port, tracker.update(parse_ss(out), now), now)
        r.publish(REDIS_CHANNEL_SERVER_CONNS, msg.model_dump_json())
        time.sleep(a.interval)


if __name__ == "__main__":
    main()
