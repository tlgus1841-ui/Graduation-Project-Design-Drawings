import pytest

from harness.contracts import FlowCountItem, FlowCountMessage, RiskStage, ThreatType
from model.criteria_engine import (
    Baseline,
    BaselineLearner,
    CriteriaConfig,
    CriteriaEngine,
    load_baselines,
    save_baselines,
)

KINDS = ("syn", "fin", "rst", "udp", "icmp", "rst_in", "unreach_in")
PORT = (1, 2)
CFG = CriteriaConfig()  # the measured numbers: floors, N = 10, attack floor 50/s, M = 5
# A user making about one web request per second plus a little DNS and ping
NORMAL = {"syn": 1, "fin": 1, "udp": 0.5, "icmp": 1}
BASE = {PORT: {"syn": (1.0, 1.0), "udp": (0.5, 0.5), "icmp": (1.0, 0.1), "gap": (0.0, 1.0), "fail": (0.0, 0.1)}}


class Counts:
    """Cumulative counters for S1:2 advanced by per-second rates every 2-second report."""

    def __init__(self):
        self.t, self.n = 1000.0, {k: 0.0 for k in KINDS}

    def tick(self, rates):
        self.t += 2.0
        for k in KINDS:
            self.n[k] += rates.get(k, 0) * 2
        return FlowCountMessage(timestamp=self.t, dpid=1, counts=[
            FlowCountItem(port_no=2, kind=k, packets=int(v)) for k, v in self.n.items()])


def run(engine, counts, *rates_seq):
    return [engine.update(counts.tick(r)) for r in rates_seq]


def stages(results):
    return [(d[0].stage, d[0].threat_type) if d else None for d in results]


def test_normal_traffic_stays_normal():
    engine, c = CriteriaEngine(CFG, BASE, ports=[PORT]), Counts()
    out = run(engine, c, NORMAL, *[NORMAL] * 10)
    assert out[0] == []  # first report only sets the reference point
    assert all(d[0].stage == RiskStage.NORMAL for d in out[1:])


def test_single_spike_is_watch_only():
    engine, c = CriteriaEngine(CFG, BASE, ports=[PORT]), Counts()
    out = run(engine, c, NORMAL, NORMAL, {**NORMAL, "udp": 500}, NORMAL, NORMAL, NORMAL)
    assert [d[0].stage for d in out[1:]] == [RiskStage.NORMAL, RiskStage.WATCH, RiskStage.WATCH,
                                             RiskStage.NORMAL, RiskStage.NORMAL]


@pytest.mark.parametrize("kind, threat", [("udp", ThreatType.UDP_FLOOD.value), ("icmp", ThreatType.ICMP_FLOOD.value)])
def test_strong_flood_jumps_to_danger_on_second_report(kind, threat):
    engine, c = CriteriaEngine(CFG, BASE, ports=[PORT]), Counts()
    out = run(engine, c, NORMAL, {**NORMAL, kind: 1000}, {**NORMAL, kind: 1000})
    assert stages(out)[1:] == [(RiskStage.WATCH, None), (RiskStage.DANGER, threat)]


def test_moderate_flood_is_warning():
    engine, c = CriteriaEngine(CFG, BASE, ports=[PORT]), Counts()
    out = run(engine, c, NORMAL, {**NORMAL, "udp": 150}, {**NORMAL, "udp": 150})
    assert stages(out)[-1] == (RiskStage.WARNING, ThreatType.UDP_FLOOD.value)
    assert out[-1][0].strength == pytest.approx(3.0)


def test_syn_flood_strong_and_weak():
    engine, c = CriteriaEngine(CFG, BASE, ports=[PORT]), Counts()
    out = run(engine, c, NORMAL, {"syn": 1000}, {"syn": 1000})
    assert stages(out)[-1] == (RiskStage.DANGER, ThreatType.SYN_FLOOD_SPOOFING.value)

    engine, c = CriteriaEngine(CFG, BASE, ports=[PORT]), Counts()
    # 35/s unanswered SYNs: 25/s over the gap line → +50 per report → CUSUM reaches 100 on the 2nd report
    out = run(engine, c, NORMAL, *[{"syn": 35}] * 3)
    assert stages(out)[1:] == [(RiskStage.WATCH, None), (RiskStage.WATCH, None),
                               (RiskStage.WARNING, ThreatType.SYN_FLOOD_SPOOFING.value)]


def test_tcp_port_scan_is_not_mistaken_for_syn_flood():
    engine, c = CriteriaEngine(CFG, BASE, ports=[PORT]), Counts()
    scan = {"syn": 250, "rst_in": 250}
    out = run(engine, c, NORMAL, scan, scan)
    assert stages(out)[-1] == (RiskStage.DANGER, ThreatType.PORT_SCAN.value)


def test_slow_scan_caught_by_the_long_window():
    engine, c = CriteriaEngine(CFG, BASE, ports=[PORT]), Counts()
    slow = {"syn": 2, "rst_in": 2, "fin": 0}  # 2 closed ports a second: never 15 in 4 s
    out = run(engine, c, NORMAL, *[slow] * 9)
    assert all(s[1] is None for s in stages(out)[1:9])
    assert stages(out)[9] == (RiskStage.WARNING, ThreatType.PORT_SCAN.value)  # 32 failures after 8 reports
    # Once the failures stop, the 5-minute count alone no longer flags the host
    out = run(engine, c, *[NORMAL] * 3)
    assert [s[1] for s in stages(out)] == [ThreatType.PORT_SCAN.value, None, None]


def test_udp_scan_few_unreachables_still_count():
    engine, c = CriteriaEngine(CFG, BASE, ports=[PORT]), Counts()
    out = run(engine, c, NORMAL, {"udp": 150, "unreach_in": 3}, NORMAL, NORMAL)
    assert stages(out)[2][1] == ThreatType.PORT_SCAN.value  # 6 unreachables inside the short window

    engine, c = CriteriaEngine(CFG, BASE, ports=[PORT]), Counts()
    out = run(engine, c, NORMAL, {**NORMAL, "unreach_in": 1.5}, NORMAL, NORMAL)  # 3 in 4 s: under the threshold of 4
    assert all(s is None or s[1] is None for s in stages(out))


def test_occasional_closed_port_mistake_is_not_a_scan():
    engine, c = CriteriaEngine(CFG, BASE, ports=[PORT]), Counts()
    out = run(engine, c, NORMAL, *[{**NORMAL, "rst_in": 1}] * 5)
    assert all(d[0].threat_type is None for d in out[1:])


def test_learning_freezes_during_attack_and_stays_within_bounds():
    engine, c = CriteriaEngine(CFG, BASE, ports=[PORT]), Counts()
    run(engine, c, NORMAL, *[{**NORMAL, "udp": 1000}] * 5)
    assert engine.baseline(PORT, "udp").mean == pytest.approx(0.5)  # nothing learned from the flood
    run(engine, c, *[{**NORMAL, "udp": 8}] * 400)  # busier but normal: mean creeps up, capped at 2×
    b = engine.baseline(PORT, "udp")
    assert b.mean == pytest.approx(1.0) and b.std <= 1.0
    run(engine, c, *[{"udp": 0}] * 400)  # very quiet: never below the pre-learned value
    assert engine.baseline(PORT, "udp").mean == pytest.approx(0.5)


def test_without_baseline_floors_act_as_fixed_criteria():
    engine, c = CriteriaEngine(CFG, None, ports=[PORT]), Counts()
    out = run(engine, c, NORMAL, NORMAL, {"udp": 1000}, {"udp": 1000})
    assert stages(out)[-1] == (RiskStage.DANGER, ThreatType.UDP_FLOOD.value)
    assert engine.line(PORT, "udp") == 10


def test_baseline_update_bounds():
    b = Baseline(mean=2.0, var=1.0, base_mean=2.0, base_std=1.0)
    for _ in range(2000):
        b.update(100.0, 0.05, 2.0)
    assert b.mean == pytest.approx(4.0) and b.std == pytest.approx(2.0)


def test_learner_save_and_load_round_trip(tmp_path):
    learner, c = BaselineLearner(ports=[PORT]), Counts()
    for r in [NORMAL, NORMAL, {**NORMAL, "udp": 2.5}]:
        learner.update(c.tick(r))
    base = learner.baselines()
    assert base[PORT]["udp"] == (1.5, 1.0)
    path = tmp_path / "baseline.json"
    save_baselines(str(path), base, seconds=4)
    assert load_baselines(str(path)) == base
    assert load_baselines(str(tmp_path / "missing.json")) is None
