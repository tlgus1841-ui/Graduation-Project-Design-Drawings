from harness.verification.flow_table_check import count_flows, rx_packets, summarize

DUMP_FLOWS = "\n".join([
    "OFPST_FLOW reply (OF1.3) (xid=0x2):",
    " cookie=0x0, duration=5.1s, table=0, n_packets=20000, n_bytes=1080000,"
    " idle_timeout=60, priority=10,ip,nw_dst=10.0.0.4 actions=output:3",
    " cookie=0x0, duration=9.8s, table=0, n_packets=12, n_bytes=840, priority=0 actions=CONTROLLER:65535",
])

DUMP_PORTS = """OFPST_PORT reply (OF1.3) (xid=0x2): 1 ports
  port  "s1-eth2": rx pkts=23130, bytes=1249492, drop=0, errs=0, frame=0, over=0, crc=0
           tx pkts=19, bytes=1528, drop=0, errs=0, coll=0
"""


def test_count_flows_skips_header():
    assert count_flows(DUMP_FLOWS) == 2
    assert count_flows("OFPST_FLOW reply (OF1.3) (xid=0x2):\n") == 0


def test_rx_packets_parses_counter():
    assert rx_packets(DUMP_PORTS) == 23130
    assert rx_packets("") == 0


def test_summarize_reports_growth_per_switch():
    samples = [
        {"s1": 7, "s2": 4, "s3": 1, "s4": 4},
        {"s1": 8, "s2": 4, "s3": 1, "s4": 4},
        {"s1": 7, "s2": 4, "s3": 1, "s4": 4},
    ]
    summary = summarize(samples)
    assert summary["s1"] == {"before": 7, "max": 8, "growth": 1}
    assert summary["s3"]["growth"] == 0
    assert summarize([]) == {}
