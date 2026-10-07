"""Self-Defending SDN Tower - H_legit(10.0.0.1) -> H_server(10.0.0.4) 정상 트래픽 생성기.

주간 계획: docs/writing/reports/weekly/week04_traffic_normal_plan.md
실행 예: sudo uv run python traffic/traffic_normal.py --src 10.0.0.1 --dst 10.0.0.4
"""

from __future__ import annotations

import argparse
import random
import string
import time
from dataclasses import dataclass

from scapy.layers.inet import ICMP, IP, TCP
from scapy.packet import Packet
from scapy.sendrecv import send

try:
    from traffic.checksum_utils import finalize_checksum
except ImportError:  # `python traffic/traffic_normal.py`로 직접 실행될 때 (패키지 컨텍스트 없음)
    from checksum_utils import finalize_checksum  # type: ignore[no-redef]

# 패턴 비율 (A: HTTP GET, B: 대용량 전송, C: ICMP Ping)
PATTERN_WEIGHTS = {"A": 0.70, "B": 0.20, "C": 0.10}

HTTP_PORT = 80
BULK_PORT = 443
HTTP_PAYLOAD_RANGE = (500, 1000)
BULK_PAYLOAD_SIZE = 1400
BULK_BURST_RANGE = (3, 5)


@dataclass
class PacketProfile:
    src: str
    dst: str
    sport: int = 0

    def __post_init__(self) -> None:
        if self.sport == 0:
            self.sport = random.randint(1024, 65535)


def _random_payload(size: int) -> bytes:
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choices(alphabet, k=size)).encode()


def build_http_packet(profile: PacketProfile) -> Packet:
    """패턴 A: HTTP GET 웹 서핑 모사 (페이로드 500~1000B)."""
    payload_size = random.randint(*HTTP_PAYLOAD_RANGE)
    pkt = (
        IP(src=profile.src, dst=profile.dst)
        / TCP(sport=profile.sport, dport=HTTP_PORT, flags="PA")
        / _random_payload(payload_size)
    )
    return finalize_checksum(pkt)


def build_bulk_packets(profile: PacketProfile) -> list[Packet]:
    """패턴 B: 대용량 전송 모사 (1,400B 풀사이즈 패킷 3~5개 버스트)."""
    burst_count = random.randint(*BULK_BURST_RANGE)
    packets = []
    for _ in range(burst_count):
        pkt = (
            IP(src=profile.src, dst=profile.dst)
            / TCP(sport=profile.sport, dport=BULK_PORT, flags="PA")
            / _random_payload(BULK_PAYLOAD_SIZE)
        )
        packets.append(finalize_checksum(pkt))
    return packets


def build_icmp_ping(profile: PacketProfile) -> Packet:
    """패턴 C: ICMP Echo Request (64B)."""
    pkt = IP(src=profile.src, dst=profile.dst) / ICMP()
    return finalize_checksum(pkt)


def weighted_pattern_choice(rng: random.Random | None = None) -> str:
    """70/20/10 비율로 패턴 A/B/C 중 하나를 선택한다."""
    patterns = list(PATTERN_WEIGHTS.keys())
    weights = list(PATTERN_WEIGHTS.values())
    chooser = rng.choices if rng is not None else random.choices
    return chooser(patterns, weights=weights, k=1)[0]


def poisson_interval(mean_interval: float) -> float:
    """지수 분포(Poisson process) 기반 발송 간격을 계산한다."""
    return random.expovariate(1 / mean_interval)


def send_pattern(pattern: str, profile: PacketProfile, verbose: bool = False) -> int:
    """패턴을 전송하고 전송된 패킷 수를 반환한다."""
    if pattern == "A":
        send(build_http_packet(profile), verbose=verbose)
        return 1
    if pattern == "B":
        packets = build_bulk_packets(profile)
        send(packets, verbose=verbose)
        return len(packets)
    if pattern == "C":
        send(build_icmp_ping(profile), verbose=verbose)
        return 1
    raise ValueError(f"알 수 없는 패턴: {pattern}")


def run(profile: PacketProfile, mean_interval: float, duration: float, verbose: bool = False) -> dict[str, int]:
    """duration(초) 동안 혼합 트래픽을 전송하고 패턴별 전송 횟수를 반환한다."""
    stats = {"A": 0, "B": 0, "C": 0}
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        pattern = weighted_pattern_choice()
        send_pattern(pattern, profile, verbose=verbose)
        stats[pattern] += 1
        time.sleep(poisson_interval(mean_interval))
    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H_legit -> H_server 정상 트래픽 생성기")
    parser.add_argument("--src", default="10.0.0.1", help="발신 호스트 IP (H_legit)")
    parser.add_argument("--dst", default="10.0.0.4", help="수신 호스트 IP (H_server)")
    parser.add_argument("--mean-interval", type=float, default=0.2, help="평균 발송 간격(초)")
    parser.add_argument("--duration", type=float, default=60.0, help="총 실행 시간(초)")
    parser.add_argument("--verbose", action="store_true", help="Scapy 전송 로그 출력")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    profile = PacketProfile(src=args.src, dst=args.dst)
    stats = run(profile, args.mean_interval, args.duration, verbose=args.verbose)
    total = sum(stats.values())
    print(f"[traffic_normal] 전송 완료: 총 {total}건 (A={stats['A']}, B={stats['B']}, C={stats['C']})")


if __name__ == "__main__":
    main()
