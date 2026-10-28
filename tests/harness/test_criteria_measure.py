import pytest

from harness.verification.criteria_measure import phase_of, rate_samples, summarize


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


@pytest.mark.parametrize("value", [0.0])
def test_summarize_zero(value):
    assert summarize([value])["std"] == 0.0
