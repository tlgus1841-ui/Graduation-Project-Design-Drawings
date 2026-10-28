import json

import pytest

from harness.verification.criteria_measure import analyze_e2e, phase_of, rate_samples, summarize


def _counts(t, **packets):
    kinds = ("syn", "fin", "rst", "udp", "icmp", "rst_in", "unreach_in")
    return {"ch": "sdn:stats:flowcount", "data": {"timestamp": t, "dpid": 1, "counts": [
        {"port_no": 2, "kind": k, "packets": packets.get(k, 0)} for k in kinds]}}


def _ports(t, rx):
    return {"ch": "sdn:stats:port", "data": {"timestamp": t, "dpid": 1, "stats": [
        {"dpid": 1, "port_no": 2, "rx_packets": rx, "tx_packets": 0, "rx_bytes": 0, "tx_bytes": 0,
         "duration_sec": 1}]}}


def test_rate_samples_per_second_with_derived_indicators():
    recs = [_counts(100.0), _ports(100.0, 0),
            _counts(102.0, syn=10, fin=4, rst=2, rst_in=6, unreach_in=2), _ports(102.0, 400)]
    v = {s["ind"]: s["v"] for s in rate_samples(recs)}
    assert v["syn"] == 5 and v["fin"] == 2 and v["rst"] == 1
    assert v["gap"] == 2  # 5 - (2 + 1)
    assert v["fail"] == 4  # (6 + 2) / 2 s
    assert v["pps"] == 200


def test_counter_reset_is_skipped():
    recs = [_counts(100.0, udp=500), _counts(102.0, udp=10)]
    assert [s for s in rate_samples(recs) if s["ind"] == "udp"] == []


def test_summarize_and_phase_of():
    s = summarize([1.0, 2.0, 3.0, 4.0])
    assert s["mean"] == 2.5 and s["max"] == 4.0 and s["n"] == 4
    assert summarize([]) == {"n": 0}
    phases = [{"name": "normal", "start": 0, "end": 100, "skip": 10}, {"name": "udp", "start": 130, "end": 150}]
    assert phase_of(5, phases) is None  # start-up skipped
    assert phase_of(50, phases) == "normal"
    assert phase_of(153, phases) == "udp"  # report arrives up to one cycle late
    assert phase_of(120, phases) is None


def test_phase_of_gives_a_short_attack_its_own_first_reports():
    phases = [{"name": "quiet", "start": 0, "end": 30, "skip": 6}, {"name": "scan", "start": 30, "end": 32},
              {"name": "quiet", "start": 32, "end": 62, "skip": 6}]
    assert phase_of(30.6, phases) == "scan"  # inside the scan, though within the earlier quiet's lag
    assert phase_of(34.0, phases) == "scan"  # late report: the most recently ended phase
    assert phase_of(37.0, phases) is None  # past the scan's lag, before the quiet's skip ends
    assert phase_of(40.0, phases) == "quiet"


def test_analyze_e2e_sees_the_last_attacks_late_alert(tmp_path):
    phases = [{"name": "normal", "start": 0.0, "end": 100.0, "skip": 10.0},
              {"name": "quiet", "start": 100.0, "end": 130.0, "skip": 6.0},
              {"name": "tcp_scan", "start": 130.0, "end": 132.0}]
    (tmp_path / "phases.json").write_text(json.dumps({"phases": phases}))
    events = [{"t": 134.3, "kind": "alert", "stage": "DANGER", "threat": "PORT_SCAN"},
              {"t": 134.3, "kind": "command", "action": "ISOLATE"}]
    (tmp_path / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events))
    (tmp_path / "ping_legit.txt").write_text(
        "".join(f"[{t:.3f}] 64 bytes from 10.0.0.4: icmp_seq={n} ttl=64 time=0.5 ms\n"
                for n, t in enumerate(range(1, 139), start=1)) + "138 packets transmitted, 138 received\n")
    report = analyze_e2e(tmp_path, tmp_path / "events.jsonl")
    scan = report["tcp_scan"]
    assert scan["first_alert_after_s"] == 4.3 and scan["first_stage"] == "DANGER"  # after the attack process ended
    assert scan["commands"] == ["ISOLATE"] and report["normal"]["alerts"] == 0


@pytest.mark.parametrize("value", [0.0])
def test_summarize_zero(value):
    assert summarize([value])["std"] == 0.0
