"""traffic_scan.py 단위 검증.

실제 패킷 전송(send)은 root 권한/Mininet 환경이 필요하므로 다루지 않고,
패킷 생성·포트 순환·PPS 주입 루프 로직만 검증한다 (send()는 모킹).
"""

from scapy.layers.inet import IP, TCP

import traffic.traffic_scan as scan

PROFILE = scan.ScanProfile(dst="10.0.0.4", src="10.0.0.2")


def test_scan_packet_does_not_spoof_source_ip():
    pkt = scan.build_scan_packet(PROFILE, dport=22)
    assert pkt[IP].src == "10.0.0.2"
    assert pkt[IP].dst == "10.0.0.4"
    assert pkt[TCP].dport == 22
    assert pkt[TCP].flags == "S"
    assert not pkt.haslayer("Raw")  # 페이로드 없음


def test_scan_packet_checksum_cleared():
    pkt = scan.build_scan_packet(PROFILE, dport=22)
    assert pkt[IP].chksum is None
    assert pkt[TCP].chksum is None


def test_scan_packet_wire_size_within_spec():
    for _ in range(50):
        pkt = scan.build_scan_packet(PROFILE, dport=22)
        wire_size = len(bytes(pkt)) + scan.WIRE_OVERHEAD
        assert 54 <= wire_size <= 74


def test_dport_cycle_covers_full_range_before_repeating():
    dports = scan.dport_cycle((1, 5))
    assert [next(dports) for _ in range(5)] == [1, 2, 3, 4, 5]
    assert next(dports) == 1  # 한 바퀴 돌면 다시 처음부터


def test_scan_second_sends_requested_count_and_cycles_ports(monkeypatch):
    captured = []
    monkeypatch.setattr(scan, "send", lambda pkts, verbose=False: captured.extend(pkts))

    dports = scan.dport_cycle((1, 3))
    sent = scan.scan_second(PROFILE, pps=6, dports=dports)

    assert sent == 6
    assert len(captured) == 6
    assert all(p[TCP].flags == "S" for p in captured)
    assert [p[TCP].dport for p in captured] == [1, 2, 3, 1, 2, 3]


def test_run_respects_duration_and_stays_below_flood_pps_range(monkeypatch):
    monkeypatch.setattr(scan, "send", lambda pkts, verbose=False: None)
    monkeypatch.setattr(scan.time, "sleep", lambda _seconds: None)

    result = scan.run(PROFILE, duration=0.05, pps_range=(10, 20))

    assert result["seconds"] >= 1
    assert all(10 <= rate <= 20 for rate in result["rate_log"])
    assert all(rate < 100 for rate in result["rate_log"])  # 플러드 임계치(100) 미달 유지
    assert result["sent"] == sum(result["rate_log"])
