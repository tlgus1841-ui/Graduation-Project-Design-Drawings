"""traffic_attack.py 단위 검증 (계획서 §5).

실제 패킷 전송(send)은 root 권한/Mininet 환경이 필요하므로 다루지 않고,
패킷 생성·IP 랜덤화·PPS 주입 루프 로직만 검증한다 (send()는 모킹).
"""

from scapy.layers.inet import IP, TCP

import traffic.traffic_attack as attack

PROFILE = attack.AttackProfile(dst="10.0.0.4", dport=80)


def test_syn_packet_matches_spec():
    pkt = attack.build_syn_packet(PROFILE)
    assert pkt[IP].dst == "10.0.0.4"
    assert pkt[TCP].dport == 80
    assert pkt[TCP].flags == "S"
    assert not pkt.haslayer("Raw")  # 페이로드 없음
    assert attack.SPORT_RANGE[0] <= pkt[TCP].sport <= attack.SPORT_RANGE[1]


def test_syn_packet_checksum_cleared():
    pkt = attack.build_syn_packet(PROFILE)
    assert pkt[IP].chksum is None
    assert pkt[TCP].chksum is None


def test_syn_packet_wire_size_within_spec():
    for _ in range(50):
        pkt = attack.build_syn_packet(PROFILE)
        wire_size = len(bytes(pkt)) + attack.WIRE_OVERHEAD
        assert 54 <= wire_size <= 74


def test_random_public_ip_excludes_private_and_reserved_ranges():
    for _ in range(5_000):
        ip = attack.random_public_ip()
        a, b, _, _ = (int(part) for part in ip.split("."))
        assert 1 <= a <= 223
        assert not attack._is_private_or_reserved(a, b)


def test_flood_second_sends_requested_count(monkeypatch):
    captured = []
    monkeypatch.setattr(attack, "send", lambda pkts, verbose=False: captured.extend(pkts))

    sent = attack.flood_second(PROFILE, pps=250)

    assert sent == 250
    assert len(captured) == 250
    assert all(p[TCP].flags == "S" for p in captured)


def test_run_respects_duration_and_pps_range(monkeypatch):
    monkeypatch.setattr(attack, "send", lambda pkts, verbose=False: None)
    monkeypatch.setattr(attack.time, "sleep", lambda _seconds: None)

    result = attack.run(PROFILE, duration=0.05, pps_range=(10, 20))

    assert result["seconds"] >= 1
    assert all(10 <= rate <= 20 for rate in result["rate_log"])
    assert result["sent"] == sum(result["rate_log"])
