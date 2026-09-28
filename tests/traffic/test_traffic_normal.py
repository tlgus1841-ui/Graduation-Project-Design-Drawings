"""traffic_normal.py 단위 검증 (계획서 §5.1).

패킷 전송(send)은 root 권한/Mininet 환경이 필요하므로 다루지 않고,
패킷 생성·체크섬·비율·간격 로직만 검증한다.
"""

import random

from scapy.layers.inet import ICMP, IP, TCP

from traffic.traffic_normal import (
    BULK_BURST_RANGE,
    BULK_PAYLOAD_SIZE,
    BULK_PORT,
    HTTP_PAYLOAD_RANGE,
    HTTP_PORT,
    PATTERN_WEIGHTS,
    PacketProfile,
    build_bulk_packets,
    build_http_packet,
    build_icmp_ping,
    finalize_checksum,
    poisson_interval,
    weighted_pattern_choice,
)

PROFILE = PacketProfile(src="10.0.0.1", dst="10.0.0.4")


def test_http_packet_matches_spec():
    pkt = build_http_packet(PROFILE)
    assert pkt[IP].src == "10.0.0.1"
    assert pkt[IP].dst == "10.0.0.4"
    assert pkt[TCP].dport == HTTP_PORT
    payload_len = len(bytes(pkt[TCP].payload))
    assert HTTP_PAYLOAD_RANGE[0] <= payload_len <= HTTP_PAYLOAD_RANGE[1]


def test_bulk_packets_match_spec():
    packets = build_bulk_packets(PROFILE)
    assert BULK_BURST_RANGE[0] <= len(packets) <= BULK_BURST_RANGE[1]
    for pkt in packets:
        assert pkt[TCP].dport == BULK_PORT
        assert len(bytes(pkt[TCP].payload)) == BULK_PAYLOAD_SIZE


def test_icmp_ping_matches_spec():
    pkt = build_icmp_ping(PROFILE)
    assert pkt[IP].dst == "10.0.0.4"
    assert pkt.haslayer(ICMP)


def test_finalize_checksum_clears_fields():
    pkt = IP(src="10.0.0.1", dst="10.0.0.4") / TCP(sport=1234, dport=80)
    # Scapy가 계산한 체크섬 값을 임의로 주입한 뒤, 삭제되는지 검증한다.
    pkt = pkt.__class__(bytes(pkt))
    finalize_checksum(pkt)
    assert pkt[IP].chksum is None
    assert pkt[TCP].chksum is None


def test_weighted_pattern_choice_ratio_within_tolerance():
    rng = random.Random(42)
    samples = [weighted_pattern_choice(rng) for _ in range(20_000)]
    counts = {p: samples.count(p) / len(samples) for p in PATTERN_WEIGHTS}
    for pattern, expected in PATTERN_WEIGHTS.items():
        assert abs(counts[pattern] - expected) < 0.02


def test_poisson_interval_is_positive_and_scales_with_mean():
    random.seed(0)
    samples = [poisson_interval(0.2) for _ in range(5_000)]
    assert all(s > 0 for s in samples)
    mean = sum(samples) / len(samples)
    assert abs(mean - 0.2) < 0.02
