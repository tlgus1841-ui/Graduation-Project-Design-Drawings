"""Self-Defending SDN Tower - 내부 확산 공격기 (랜섬웨어·웜 방식, 판단 기준 측정용).

같은 망의 내부 주소를 차례로 돌며 파일 공유(445) 같은 포트로 연결을 시도한다. 대부분의 주소에는
PC가 없어서 ARP 질문에 아무도 답하지 않고(연결 실패), 있는 PC는 닫힌 포트로 RST를 돌려준다.
표준 라이브러리만 쓴다.

실행 예: python3 -m traffic.traffic_spread --subnet 10.0.0 --hosts 5-60 --port 445 --rate 10
"""

from __future__ import annotations

import argparse
import socket
import time
from typing import List


def parse_hosts(spec: str) -> List[int]:
    """'5-60' 또는 '1,4,9' 형식의 마지막 옥텟 목록."""
    out: List[int] = []
    for part in spec.split(","):
        if "-" in part:
            lo, hi = part.split("-")
            out += list(range(int(lo), int(hi) + 1))
        elif part:
            out.append(int(part))
    return out


def run(subnet: str, hosts: List[int], port: int, rate: float) -> dict:
    """초당 rate개 주소에 연결을 시도한다. 응답을 기다리지 않는다 (ARP · 연결은 커널이 계속 시도)."""
    tried = 0
    socks = []
    for last in hosts:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setblocking(False)
        s.connect_ex((f"{subnet}.{last}", port))
        tried += 1
        socks.append(s)
        time.sleep(1.0 / rate)
    time.sleep(3.0)  # 커널의 ARP 재시도(약 3초)가 끝날 때까지 기다린다
    for s in socks:
        s.close()
    return {"tried": tried}


def main() -> None:
    p = argparse.ArgumentParser(description="내부 확산 공격기")
    p.add_argument("--subnet", default="10.0.0")
    p.add_argument("--hosts", default="5-60", help="마지막 옥텟 범위")
    p.add_argument("--port", type=int, default=445)
    p.add_argument("--rate", type=float, default=10.0, help="초당 시도할 주소 수")
    a = p.parse_args()
    r = run(a.subnet, parse_hosts(a.hosts), a.port, a.rate)
    print(f"[traffic_spread] {a.subnet}.x:{a.port} 주소 {r['tried']}개 시도", flush=True)


if __name__ == "__main__":
    main()
