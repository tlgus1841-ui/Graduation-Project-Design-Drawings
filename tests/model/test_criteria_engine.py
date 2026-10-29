import pytest

from harness.contracts import (FlowCountItem, FlowCountMessage, RiskStage, ServerConnItem, ServerConnMessage,
                               ServiceHealthMessage, ThreatType)
from model.criteria_engine import (
    Baseline,
    BaselineLearner,
    CriteriaConfig,
    CriteriaEngine,
    load_baselines,
    save_baselines,
)

KINDS = ("syn", "fin", "rst", "udp", "icmp", "rst_in", "unreach_in", "arp_fail")
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
    # 35/s unanswered SYNs: 15/s over the gap line (20) → +30 per 2 s report → CUSUM passes 50 on the 2nd report
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


def _health(t, loss, rtt=2.5):
    return ServiceHealthMessage(timestamp=t, target_ip="10.0.0.4", sent=10, received=round(10 - loss / 10),
                                loss_percent=loss, rtt_avg_ms=None if loss == 100 else rtt)


def test_weak_attack_with_service_degraded_twice_is_danger():
    engine, c = CriteriaEngine(CFG, BASE, ports=[PORT]), Counts()
    weak = {**NORMAL, "udp": 150}  # 3x the attack line: WARNING on its own
    out = run(engine, c, NORMAL, weak, weak)
    assert stages(out)[-1] == (RiskStage.WARNING, ThreatType.UDP_FLOOD.value)

    engine.update_health(_health(c.t + 1, loss=40))  # one bad report is not enough
    out = run(engine, c, weak)
    assert out[0][0].stage == RiskStage.WARNING
    engine.update_health(_health(c.t + 1, loss=30))
    out = run(engine, c, weak)
    assert out[0][0].stage == RiskStage.DANGER and out[0][0].threat_type == ThreatType.UDP_FLOOD.value
    assert any(r.startswith("service degraded: loss 30%") for r in out[0][0].reasons)

    engine.update_health(_health(c.t + 1, loss=0))  # service recovered: back to WARNING
    assert run(engine, c, weak)[0][0].stage == RiskStage.WARNING


def test_slow_replies_also_count_as_degraded():
    engine, c = CriteriaEngine(CFG, BASE, ports=[PORT]), Counts()
    weak = {**NORMAL, "udp": 150}
    run(engine, c, NORMAL, weak)
    for _ in range(2):
        engine.update_health(_health(c.t + 1, loss=0, rtt=CFG.health_rtt_ms + 1))
    assert run(engine, c, weak)[0][0].stage == RiskStage.DANGER


def test_degraded_service_alone_never_blames_a_port():
    engine, c = CriteriaEngine(CFG, BASE, ports=[PORT]), Counts()
    for _ in range(3):
        engine.update_health(_health(c.t + 1, loss=100))
    out = run(engine, c, NORMAL, NORMAL, NORMAL)
    assert all(d[0].stage == RiskStage.NORMAL for d in out[1:])


def test_stale_health_is_ignored():
    engine, c = CriteriaEngine(CFG, BASE, ports=[PORT]), Counts()
    weak = {**NORMAL, "udp": 150}
    for _ in range(2):
        engine.update_health(_health(c.t, loss=100))
    out = run(engine, c, *[weak] * 5)  # 10 s later the controller has stopped reporting
    assert out[-1][0].stage == RiskStage.WARNING


def _conns(t, slow, pending=0):
    return ServerConnMessage(timestamp=t, server_ip="10.0.0.4", port=80, clients=[
        ServerConnItem(client_ip="10.0.0.2", open=max(slow, pending, 1), slow=slow, pending=pending)])


def test_slow_http_from_server_side_connection_counts():
    engine, c = CriteriaEngine(CFG, BASE, ports=[PORT]), Counts()
    run(engine, c, NORMAL)
    engine.update_server_conns(_conns(c.t + 1, slow=3))  # a few slow connections: only WATCH
    assert run(engine, c, NORMAL)[0][0].stage == RiskStage.WATCH
    out = []
    for _ in range(2):
        engine.update_server_conns(_conns(c.t + 1, slow=30))  # 3x the line: WARNING after two reports
        out += run(engine, c, NORMAL)
    assert stages(out) == [(RiskStage.WATCH, None), (RiskStage.WARNING, ThreatType.SLOW_DDOS.value)]
    for _ in range(2):
        engine.update_server_conns(_conns(c.t + 1, slow=150))  # Slowloris default: 15x
        last = run(engine, c, NORMAL)
    assert stages(last) == [(RiskStage.DANGER, ThreatType.SLOW_DDOS.value)]


def test_unfinished_requests_catch_slow_http_before_20_seconds():
    engine, c = CriteriaEngine(CFG, BASE, ports=[PORT]), Counts()
    run(engine, c, NORMAL)
    out = []
    for _ in range(2):
        engine.update_server_conns(_conns(c.t + 1, slow=0, pending=150))  # 5 s in: none slow yet
        out += run(engine, c, NORMAL)
    assert stages(out) == [(RiskStage.WATCH, None), (RiskStage.DANGER, ThreatType.SLOW_DDOS.value)]
    assert "unfinished 150" in out[-1][0].reasons[-2]


def test_slow_http_report_goes_stale():
    engine, c = CriteriaEngine(CFG, BASE, ports=[PORT]), Counts()
    engine.update_server_conns(_conns(c.t, slow=150))
    out = run(engine, c, *[NORMAL] * 6)  # the collector stopped reporting
    assert out[-1][0].threat_type is None


def test_internal_spread_from_failed_arp_targets():
    engine, c = CriteriaEngine(CFG, BASE, ports=[PORT]), Counts()
    out = run(engine, c, NORMAL, *[{**NORMAL, "arp_fail": 5}] * 4)  # 10 new missing hosts per report
    assert [s[1] for s in stages(out)[1:]] == [None, None, None, ThreatType.INTERNAL_SPREAD.value]  # 30 ≥ 25
    out = run(engine, c, NORMAL, NORMAL)  # stopped looking for new hosts
    assert stages(out)[-1][1] is None


def test_a_few_missing_hosts_is_not_spread():
    engine, c = CriteriaEngine(CFG, BASE, ports=[PORT]), Counts()
    out = run(engine, c, NORMAL, *[{**NORMAL, "arp_fail": 0.5}] * 20)  # 20 in 40 s: under 25
    assert all(s is None or s[1] is None for s in stages(out))


def test_rst_burst_without_own_probes_is_not_a_scan():
    """The server resetting 150 of this host's old connections at once is not a port scan."""
    engine, c = CriteriaEngine(CFG, BASE, ports=[PORT]), Counts()
    out = run(engine, c, NORMAL, {**NORMAL, "rst_in": 75}, NORMAL, {**NORMAL, "rst_in": 0.5}, NORMAL)
    assert all(s is None or s[1] is None for s in stages(out))


def test_approved_relearn_follows_a_real_rise_then_reverts():
    engine, c = CriteriaEngine(CFG, BASE, ports=[PORT]), Counts()
    busy = {**NORMAL, "udp": 150}  # a genuine UDP-heavy event (e.g. a game launch): looks like a weak flood
    out = run(engine, c, NORMAL, busy, busy)
    assert stages(out)[-1] == (RiskStage.WARNING, ThreatType.UDP_FLOOD.value)

    assert engine.approve_relearn(until=c.t + 120) == [PORT]  # admin approves 2 minutes
    out = run(engine, c, *[busy] * 30)
    assert out[-1][0].threat_type is None and "relearning (approved)" in out[-1][0].reasons
    assert engine.baseline(PORT, "udp").mean > 100  # learned beyond the usual 2x cap
    assert engine.baseline(PORT, "gap").mean == pytest.approx(0.0, abs=0.1)  # attack signals are not relearned

    run(engine, c, *[busy] * 31)  # the approved period ends: back to the pre-learned value
    assert engine.baseline(PORT, "udp").mean == pytest.approx(0.5)
    out = run(engine, c, busy, busy)
    assert stages(out)[-1] == (RiskStage.WARNING, ThreatType.UDP_FLOOD.value)


def test_relearn_does_not_learn_from_a_danger_level_attack():
    engine, c = CriteriaEngine(CFG, BASE, ports=[PORT]), Counts()
    run(engine, c, NORMAL)
    engine.approve_relearn(until=c.t + 600)
    out = run(engine, c, *[{**NORMAL, "udp": 2000}] * 5)
    assert out[-1][0].stage == RiskStage.DANGER
    assert engine.baseline(PORT, "udp").mean < 1.0


class Counts1(Counts):
    """Same as Counts but the controller reports every second."""

    def tick(self, rates):
        self.t += 1.0
        for k in KINDS:
            self.n[k] += rates.get(k, 0)
        return FlowCountMessage(timestamp=self.t, dpid=1, counts=[
            FlowCountItem(port_no=2, kind=k, packets=int(v)) for k, v in self.n.items()])


def test_one_second_reports_confirm_in_two_seconds_with_the_same_windows():
    engine, c = CriteriaEngine(CFG, BASE, ports=[PORT]), Counts1()
    out = run(engine, c, NORMAL, {**NORMAL, "udp": 1000}, {**NORMAL, "udp": 1000})
    assert stages(out)[1:] == [(RiskStage.WATCH, None), (RiskStage.DANGER, ThreatType.UDP_FLOOD.value)]

    engine, c = CriteriaEngine(CFG, BASE, ports=[PORT]), Counts1()
    # 4 failures a second: 16 in the 4-second short window only once 4 reports are in it
    out = run(engine, c, NORMAL, *[{"syn": 4, "rst_in": 4}] * 5)
    assert [s[1] for s in stages(out)[1:]] == [None, None, None, None, ThreatType.PORT_SCAN.value]

    engine, c = CriteriaEngine(CFG, BASE, ports=[PORT]), Counts1()
    run(engine, c, NORMAL, *[{**NORMAL, "udp": 8}] * 12)  # learning resumes after 10 s: reports 10, 11, 12
    a = 2 / 601  # 10 minutes of one-second reports
    assert engine.baseline(PORT, "udp").mean == pytest.approx(8 - 7.5 * (1 - a) ** 3)
