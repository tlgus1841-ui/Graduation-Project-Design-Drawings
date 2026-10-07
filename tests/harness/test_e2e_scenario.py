from harness.verification.e2e_defense_standin import flow_commands, standin_score
import pytest

from harness.verification.e2e_scenario import analyze, parse_ping_d, rule_packets, seq_times, window_loss

PING = "\n".join([
    "[100.000] 64 bytes from 10.0.0.4: icmp_seq=1 ttl=64 time=0.3 ms",
    "[100.050] 64 bytes from 10.0.0.4: icmp_seq=2 ttl=64 time=0.3 ms",
    "[100.150] 64 bytes from 10.0.0.4: icmp_seq=4 ttl=64 time=0.3 ms",
    "4 packets transmitted, 3 received, 25% packet loss, time 150ms",
])


def test_parse_ping_d_collects_received_sequence_numbers():
    assert parse_ping_d(PING) == {"transmitted": 4, "received_seqs": [1, 2, 4], "reply_ts": [100.0, 100.05, 100.15]}


def test_rule_packets_sums_matching_rules():
    dump = "\n".join([
        " cookie=0x0, n_packets=500, priority=100,in_port=2 actions=drop",
        " cookie=0x0, n_packets=40, priority=10,ip,nw_dst=10.0.0.4 actions=output:3",
    ])
    assert rule_packets(dump, "in_port=2 actions=drop") == 500
    assert rule_packets(dump, "priority=10,ip,nw_dst=10.0.0.4") == 40


def test_lost_ping_time_is_interpolated_between_replies():
    times = seq_times(4, [1, 2, 4], [100.0, 100.05, 100.15])
    assert times[3] == pytest.approx(100.10)
    assert window_loss(times, [1, 2, 4], 100.08, 100.2) == {"sent": 2, "lost": 1, "loss_percent": 50.0}


def test_standin_rule_matches_spec_thresholds():
    assert standin_score(3000, 54) < -0.5
    assert standin_score(3000, 800) > -0.5  # flash crowd with normal packet size
    assert standin_score(100, 54) > -0.5  # too little traffic


def test_reroute_installs_ingress_last_and_restore_removes_ingress_first():
    reroute = [" ".join(c) for c in flow_commands("REROUTE")]
    assert " s1 " in reroute[-1]
    restore = [" ".join(c) for c in flow_commands("RESTORE")]
    assert "in_port=2" in restore[0]
    assert all("--strict" in c for c in restore)
    assert "actions=drop" in " ".join(flow_commands("ISOLATE")[0])


def test_analyze_combines_run_and_events():
    run = {
        "ping": {"start": 0.0, "transmitted": 1200, "received_seqs": [n for n in range(1, 1201) if n != 100],
                 "reply_ts": [(n - 1) * 0.05 for n in range(1, 1201) if n != 100]},
        "attack_start": 20.0, "attack_end": 40.0, "attack_packets_at_s1_port2": 30000,
        "flow_samples": [{"t": 25.0, "s1_drop_in2": 100, "s1_dst_server_p10": 50},
                         {"t": 39.0, "s1_drop_in2": 25000, "s1_dst_server_p10": 50}],
    }
    events = [
        {"t": 23.0, "kind": "alert"},
        {"t": 24.48, "kind": "sample", "stats_ts": 24.47},
        {"t": 24.5, "kind": "command", "action": "REROUTE", "apply_ms": 20.0, "stats_ts": 24.47},
        {"t": 24.6, "kind": "command", "action": "ISOLATE", "apply_ms": 5.0, "stats_ts": 24.47},
        {"t": 52.0, "kind": "command", "action": "RESTORE", "apply_ms": 10.0},
    ]
    m = analyze(run, events)
    assert m["detect_after_attack_s"] == 3.0
    assert m["first_alert_to_isolate_ms"] == 1600.0
    assert m["decision_to_isolated_ms"] == 120.0
    assert m["isolate_count"] == 1 and m["restore_count"] == 1
    assert m["recovery_after_attack_s"] == 12.0
    assert m["dropped_at_s1_while_isolated"] == 24900
    assert m["leaked_to_server_while_isolated"] == 0
    assert m["normal_loss"]["whole_run"]["lost"] == 1
    assert m["normal_loss"]["before_attack"]["lost"] == 1  # seq 100 sent at 4.95 s
    assert m["normal_loss"]["attack_while_isolated"]["lost"] == 0
