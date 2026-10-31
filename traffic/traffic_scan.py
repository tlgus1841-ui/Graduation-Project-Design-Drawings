"""Self-Defending SDN Tower - 포트 스캔 공격기 (판단 기준 측정용).

공격자 자신의 IP로 서버의 포트를 차례로 두드린다. 닫힌 포트는 서버 커널이 RST(TCP)나
ICMP 도달 불가(UDP)를 돌려보내므로, 기준표의 '실패 응답 수'가 실제로 생긴다.
TCP는 SYN 스캔(nmap -sS와 같은 방식)이다: 열린 포트의 SYN-ACK에는 공격자 커널이 RST로 답한다.

실행 예: sudo .venv/bin/python -m traffic.traffic_scan --kind tcp --ports 1-1000 --rate 500
"""

from __future__ import annotations

import argparse
import random
import time
from typing import List

from scapy.layers.inet import IP, TCP, UDP
from scapy.packet import Packet
from scapy.sendrecv import send

try:
    from traffic.checksum_utils import finalize_checksum
except ImportError:  # 직접 실행될 때 (패키지 컨텍스트 없음)
    from checksum_utils import finalize_checksum  # type: ignore[no-redef]


def parse_ports(spec: str) -> List[int]:
    """'1-1000' 또는 '22,80,443' 형식."""
    ports: List[int] = []
    for part in spec.split(","):
        if "-" in part:
            lo, hi = part.split("-")
            ports += range(int(lo), int(hi) + 1)
        elif part.strip():
            ports.append(int(part))
    return ports


def build_probe(kind: str, src: str, dst: str, port: int) -> Packet:
    sport = random.randint(20000, 60000)
    if kind == "tcp":
        pkt = IP(src=src, dst=dst) / TCP(sport=sport, dport=port, flags="S")
    else:
        # scapy의 Packet.__truediv__는 Self 타입 변수를 속성 할당(__truediv__ = __div__)으로
        # 선언해 mypy가 2단 체이닝에서 타입을 못 풀어낸다(런타임 동작과는 무관한 스텁 한계).
        pkt = IP(src=src, dst=dst) / UDP(sport=sport, dport=port) / b""  # type: ignore[operator]
    return finalize_checksum(pkt)


def run(kind: str, src: str, dst: str, ports: List[int], rate: float) -> dict:
    """rate(초당 포트 수)로 ports를 한 번씩 두드린다. 1초 단위로 묶어 보낸다."""
    batch = max(1, int(rate))
    gap = batch / rate
    sent = 0
    t0 = time.monotonic()
    for i in range(0, len(ports), batch):
        tick = time.monotonic()
        send([build_probe(kind, src, dst, p) for p in ports[i:i + batch]], verbose=False)
        sent += len(ports[i:i + batch])
        elapsed = time.monotonic() - tick
        if elapsed < gap:
            time.sleep(gap - elapsed)
    return {"sent": sent, "seconds": round(time.monotonic() - t0, 1)}


def main() -> None:
    p = argparse.ArgumentParser(description="포트 스캔 공격기 (TCP SYN / UDP)")
    p.add_argument("--kind", choices=("tcp", "udp"), required=True)
    p.add_argument("--src", default="10.0.0.2", help="공격자 자신의 IP (응답을 받아야 하므로 변조하지 않음)")
    p.add_argument("--dst", default="10.0.0.11")
    p.add_argument("--ports", default="1-1000")
    p.add_argument("--rate", type=float, default=500.0, help="초당 두드리는 포트 수")
    a = p.parse_args()
    r = run(a.kind, a.src, a.dst, parse_ports(a.ports), a.rate)
    print(f"[traffic_scan] {a.kind}: {r['sent']}개 포트, {r['seconds']}초")


if __name__ == "__main__":
    main()
