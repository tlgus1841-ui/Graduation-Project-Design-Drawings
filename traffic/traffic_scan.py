"""Self-Defending SDN Tower - H_attacker(10.0.0.2) -> H_server(10.0.0.4) 포트 스캔/Slow 트래픽 생성기.

model/attack_classifier.py의 PORT_SCAN·SLOW_DRIFT 탐지(플러드 임계치 미달의 소형
패킷 트래픽 증가)를 실제 Mininet 패킷으로 검증·시연하기 위한 생성기다.
traffic_attack.py(SYN Flood)와 달리 출발지 IP는 스푸핑하지 않는다 — 실제 포트
스캐너는 SYN-ACK/RST 응답을 받아야 의미가 있으므로 자신의 실제 IP로 보낸다.

목적지 포트를 순환시키며 플러드 임계치(model/inference_worker.py의
MIN_ATTACK_PPS=100) 미달의 저속(기본 20~60 PPS)으로 SYN을 전송한다. 짧게
실행하면 포트 스캔, 길게(SUSTAINED_TICKS_FOR_SLOW_DDOS 이상, 기본 20초 이상)
지속 실행하면 Slow DDoS 전조 시연이 된다 — model/attack_classifier.py가 둘을
지속 시간으로만 구분하기 때문이다.

실행 예:
    sudo uv run python traffic/traffic_scan.py --dst 10.0.0.4 --duration 12  # 포트 스캔 데모
    sudo uv run python traffic/traffic_scan.py --dst 10.0.0.4 --duration 30  # Slow DDoS 데모
"""

from __future__ import annotations

import argparse
import itertools
import random
import time
from dataclasses import dataclass
from typing import Iterator, List, Tuple

from scapy.layers.inet import IP, TCP
from scapy.packet import Packet
from scapy.sendrecv import send

try:
    from traffic.checksum_utils import finalize_checksum
except ImportError:  # `python traffic/traffic_scan.py`로 직접 실행될 때 (패키지 컨텍스트 없음)
    from checksum_utils import finalize_checksum  # type: ignore[no-redef]

WIRE_OVERHEAD = 14
SPORT_RANGE = (1024, 65535)
# model/inference_worker.py의 MIN_ATTACK_PPS(100) 미달 유지 - 플러드 게이트(DetectionGuard)를
# 피해 model/attack_classifier.py의 PORT_SCAN/SLOW_DRIFT 경로로만 잡히게 한다.
PPS_RANGE = (20, 60)
DPORT_RANGE = (1, 1024)  # 흔한 서비스 포트 대역을 순환 스캔


@dataclass
class ScanProfile:
    dst: str
    src: str = "10.0.0.2"


def dport_cycle(dport_range: Tuple[int, int]) -> Iterator[int]:
    return itertools.cycle(range(dport_range[0], dport_range[1] + 1))


def build_scan_packet(profile: ScanProfile, dport: int) -> Packet:
    """출발지 IP는 스푸핑하지 않는, 페이로드 없는 SYN 패킷 생성 (목적지 포트만 순환)."""
    sport = random.randint(*SPORT_RANGE)
    pkt = IP(src=profile.src, dst=profile.dst) / TCP(sport=sport, dport=dport, flags="S")
    return finalize_checksum(pkt)


def scan_second(profile: ScanProfile, pps: int, dports: Iterator[int], verbose: bool = False) -> int:
    """목표 PPS만큼 포트를 순환하며 SYN 패킷을 전송하고 전송 개수를 반환한다."""
    packets: List[Packet] = [build_scan_packet(profile, next(dports)) for _ in range(pps)]
    send(packets, verbose=verbose)
    return len(packets)


def run(
    profile: ScanProfile,
    duration: float,
    pps_range: Tuple[int, int] = PPS_RANGE,
    dport_range: Tuple[int, int] = DPORT_RANGE,
    verbose: bool = False,
) -> dict:
    """duration(초) 동안 매초 pps_range 내 무작위 목표치로 포트를 순환 스캔한다."""
    dports = dport_cycle(dport_range)
    sent_total = 0
    rate_log: List[int] = []
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        tick_start = time.monotonic()
        target_pps = random.randint(*pps_range)
        sent_total += scan_second(profile, target_pps, dports, verbose=verbose)
        rate_log.append(target_pps)
        elapsed = time.monotonic() - tick_start
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
    return {"sent": sent_total, "seconds": len(rate_log), "rate_log": rate_log}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H_attacker -> H_server 포트 스캔/Slow 트래픽 생성기")
    parser.add_argument("--dst", default="10.0.0.4", help="목적지 호스트 IP (H_server)")
    parser.add_argument("--src", default="10.0.0.2", help="출발지 호스트 IP (H_attacker, 스푸핑하지 않음)")
    parser.add_argument(
        "--duration", type=float, default=12.0,
        help="총 실행 시간(초). 12초=포트 스캔 데모, 30초 이상=Slow DDoS 데모",
    )
    parser.add_argument("--min-pps", type=int, default=PPS_RANGE[0], help="초당 최소 패킷 수 (플러드 임계치 100 미달 유지)")
    parser.add_argument("--max-pps", type=int, default=PPS_RANGE[1], help="초당 최대 패킷 수 (플러드 임계치 100 미달 유지)")
    parser.add_argument("--dport-min", type=int, default=DPORT_RANGE[0], help="스캔 시작 포트")
    parser.add_argument("--dport-max", type=int, default=DPORT_RANGE[1], help="스캔 종료 포트")
    parser.add_argument("--verbose", action="store_true", help="Scapy 전송 로그 출력")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    profile = ScanProfile(dst=args.dst, src=args.src)
    result = run(
        profile, args.duration, (args.min_pps, args.max_pps), (args.dport_min, args.dport_max),
        verbose=args.verbose,
    )
    avg_pps = result["sent"] / result["seconds"] if result["seconds"] else 0
    print(f"[traffic_scan] 전송 완료: 총 {result['sent']}건, {result['seconds']}초간 평균 {avg_pps:.0f} PPS")


if __name__ == "__main__":
    main()
