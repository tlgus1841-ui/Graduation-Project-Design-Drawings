"""traffic_scan.py 단위 검증.

실제 패킷 전송(send)은 root 권한/Mininet 환경이 필요하므로 다루지 않고,
포트 파싱 · 패킷 생성 · 전송 루프(배치/속도) 로직만 검증한다 (send()는 모킹).
"""

from scapy.layers.inet import IP, TCP, UDP

import traffic.traffic_scan as scan


def test_parse_ports_handles_range_and_list():
    assert scan.parse_ports("1-5") == [1, 2, 3, 4, 5]
    assert scan.parse_ports("22,80,443") == [22, 80, 443]
    assert scan.parse_ports("22,100-102") == [22, 100, 101, 102]


def test_build_probe_tcp_does_not_spoof_source_ip():
    pkt = scan.build_probe("tcp", src="10.0.0.2", dst="10.0.0.4", port=22)
    assert pkt[IP].src == "10.0.0.2"
    assert pkt[IP].dst == "10.0.0.4"
    assert pkt[TCP].dport == 22
    assert pkt[TCP].flags == "S"
    assert pkt[IP].chksum is None
    assert pkt[TCP].chksum is None


def test_build_probe_udp_has_empty_payload():
    pkt = scan.build_probe("udp", src="10.0.0.2", dst="10.0.0.4", port=53)
    assert pkt[IP].src == "10.0.0.2"
    assert pkt[UDP].dport == 53
    assert pkt[IP].chksum is None
    assert pkt[UDP].chksum is None


def test_run_sends_each_port_once_and_cycles_batches(monkeypatch):
    captured = []
    monkeypatch.setattr(scan, "send", lambda pkts, verbose=False: captured.extend(pkts))
    monkeypatch.setattr(scan.time, "sleep", lambda _seconds: None)

    result = scan.run("tcp", "10.0.0.2", "10.0.0.4", [1, 2, 3, 4, 5], rate=2)

    assert result["sent"] == 5
    assert len(captured) == 5
    assert sorted(p[TCP].dport for p in captured) == [1, 2, 3, 4, 5]
    assert all(p[TCP].flags == "S" for p in captured)
