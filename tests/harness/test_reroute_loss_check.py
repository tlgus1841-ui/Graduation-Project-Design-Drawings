from harness.verification.reroute_loss_check import BYPASS_FLOWS, flow_add_cmd, flow_packets, parse_ping

PING_OK = """--- 10.0.0.4 ping statistics ---
1000 packets transmitted, 1000 received, 0% packet loss, time 10987ms
rtt min/avg/max/mdev = 0.050/0.210/3.100/0.150 ms
"""
PING_LOSS = "1000 packets transmitted, 993 received, 0.7% packet loss, time 10990ms\n"

DUMP_S1 = "\n".join([
    "OFPST_FLOW reply (OF1.3) (xid=0x2):",
    " cookie=0x0, table=0, n_packets=412, n_bytes=40376, priority=100,ip,nw_dst=10.0.0.4 actions=output:4",
    " cookie=0x0, table=0, n_packets=300, n_bytes=29400, idle_timeout=60,"
    " priority=10,ip,nw_dst=10.0.0.4 actions=output:3",
])


def test_parse_ping_reads_summary():
    assert parse_ping(PING_OK) == {"transmitted": 1000, "received": 1000, "loss_percent": 0.0}
    assert parse_ping(PING_LOSS)["received"] == 993
    assert parse_ping("garbage")["loss_percent"] == 100.0


def test_flow_packets_picks_rule_by_priority_and_dst():
    assert flow_packets(DUMP_S1, "10.0.0.4", 100) == 412
    assert flow_packets(DUMP_S1, "10.0.0.4", 10) == 300
    assert flow_packets(DUMP_S1, "10.0.0.1", 100) == 0


def test_ingress_switch_is_switched_last():
    # make-before-break: S1 must change only after S3/S4 already know the bypass.
    assert BYPASS_FLOWS[-1][0] == "s1"
    assert {sw for sw, _, _ in BYPASS_FLOWS[:-1]} == {"s3", "s4"}


def test_flow_add_cmd_uses_openflow13_and_priority():
    cmd = flow_add_cmd("s1", "10.0.0.4", 4)
    assert cmd.startswith("ovs-ofctl -O OpenFlow13 add-flow s1 ")
    assert "priority=100,ip,nw_dst=10.0.0.4,actions=output:4" in cmd
