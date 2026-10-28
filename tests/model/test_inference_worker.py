import pytest

from harness.contracts import PortStatItem, PortStatsMessage
from model.inference_worker import InferenceWorker, watched_ports
from model.model import AnomalyModel
from model.synthetic_samples import build_labeled_dataset_csv


@pytest.fixture(scope="module")
def model(tmp_path_factory):
    csv_path = tmp_path_factory.mktemp("data") / "train.csv"
    build_labeled_dataset_csv(str(csv_path))
    return AnomalyModel().fit(str(csv_path))


class Counters:
    """Cumulative S1 port counters that advance by a given rate each 2-second poll."""

    def __init__(self) -> None:
        self.t = 1000.0
        self.pkts = {1: 0, 2: 0, 3: 0}
        self.bytes = {1: 0, 2: 0, 3: 0}

    def tick(self, rates):
        self.t += 2.0
        for port, (pps, size) in rates.items():
            self.pkts[port] += int(pps * 2)
            self.bytes[port] += int(pps * 2 * size)
        stats = [PortStatItem(dpid=1, port_no=p, rx_packets=self.pkts[p], tx_packets=0, rx_bytes=self.bytes[p],
                              tx_bytes=0, duration_sec=60) for p in self.pkts]
        return PortStatsMessage(timestamp=self.t, dpid=1, stats=stats)


NORMAL = {1: (20, 98), 2: (0, 0), 3: (20, 98)}
ATTACK = {1: (20, 98), 2: (1700, 54), 3: (1720, 55)}


def test_only_unprotected_access_ports_are_watched():
    assert watched_ports() == [(1, 2)]


def test_attack_is_confirmed_on_second_sample_and_keeps_alerting(model):
    worker, c = InferenceWorker(model), Counters()
    assert worker.process(c.tick(NORMAL)) == []  # baseline only
    assert worker.process(c.tick(NORMAL)) == []
    assert worker.process(c.tick(ATTACK)) == []  # first suspicious sample
    alerts = worker.process(c.tick(ATTACK))
    assert [(a.dpid, a.in_port) for a in alerts] == [(1, 2)]
    assert alerts[0].bpp == pytest.approx(54, abs=1) and alerts[0].score < 0
    assert len(worker.process(c.tick(ATTACK))) == 1  # heartbeat for the controller FSM
    assert worker.process(c.tick(NORMAL)) == []


def test_trunk_port_carrying_the_attack_never_alerts(model):
    worker, c = InferenceWorker(model), Counters()
    for rates in (NORMAL, ATTACK, ATTACK, ATTACK):
        alerts = worker.process(c.tick(rates))
        assert all(a.in_port != 3 for a in alerts)


def test_single_spike_and_low_rate_small_packets_do_not_alert(model):
    worker, c = InferenceWorker(model), Counters()
    worker.process(c.tick(NORMAL))
    for rates in (ATTACK, NORMAL, ATTACK, NORMAL):  # never two in a row
        assert worker.process(c.tick(rates)) == []
    trickle = {1: (20, 98), 2: (5, 60), 3: (25, 90)}  # small packets but far below flood rate
    for _ in range(3):
        assert worker.process(c.tick(trickle)) == []


class ErrorCounters(Counters):
    """Counters that can also advance a per-port rx_errors counter (for port-scan tests)."""

    def __init__(self) -> None:
        super().__init__()
        self.errors = {1: 0, 2: 0, 3: 0}

    def tick(self, rates, error_rates=None):  # noqa: D401 - small test helper
        self.t += 2.0
        for port, (pps, size) in rates.items():
            self.pkts[port] += int(pps * 2)
            self.bytes[port] += int(pps * 2 * size)
        for port, err_pps in (error_rates or {}).items():
            self.errors[port] += int(err_pps * 2)
        stats = [
            PortStatItem(dpid=1, port_no=p, rx_packets=self.pkts[p], tx_packets=0, rx_bytes=self.bytes[p],
                         tx_bytes=0, rx_errors=self.errors[p], duration_sec=60)
            for p in self.pkts
        ]
        return PortStatsMessage(timestamp=self.t, dpid=1, stats=stats)


def test_port_scan_on_watched_port_is_confirmed_as_port_scan(model):
    """DDoS 외 공격 유형: 패킷량은 평범한데 에러율만 뚜렷하게 높은 포트 스캔류 트래픽."""
    worker, c = InferenceWorker(model), ErrorCounters()
    scan = {1: (20, 98), 2: (30, 90), 3: (20, 98)}  # H_attacker 포트: PPS는 평범
    scan_errors = {2: 20}  # 그런데 30개 중 20개가 에러(닫힌 포트 등) -> err_rate 매우 높음

    worker.process(c.tick(scan, scan_errors))  # baseline
    worker.process(c.tick(scan, scan_errors))  # 1st suspicious sample
    alerts = worker.process(c.tick(scan, scan_errors))  # 2nd -> confirmed

    assert len(alerts) == 1
    assert alerts[0].in_port == 2
    assert alerts[0].threat_type == "PORT_SCAN"


def test_normal_error_free_traffic_never_triggers_port_scan(model):
    worker, c = InferenceWorker(model), ErrorCounters()
    for _ in range(5):
        assert worker.process(c.tick(NORMAL)) == []


# ---------------------------------------------------------------------
# Criteria mode: alerts come from per-kind counts, port stats only fill pps/bpp
# ---------------------------------------------------------------------
from harness.contracts import FlowCountItem, FlowCountMessage, RiskStage  # noqa: E402
from model.criteria_engine import CriteriaEngine  # noqa: E402


def _counts(t, udp_total):
    return FlowCountMessage(timestamp=t, dpid=1, counts=[
        FlowCountItem(port_no=2, kind=k, packets=udp_total if k == "udp" else 0)
        for k in ("syn", "fin", "rst", "udp", "icmp", "rst_in", "unreach_in")])


def test_criteria_mode_alerts_with_stage_and_threat_type(model):
    worker, c = InferenceWorker(model, criteria=CriteriaEngine(ports=[(1, 2)])), Counters()
    assert worker.process(c.tick(NORMAL)) == [] and worker.process(c.tick(ATTACK)) == []  # no legacy alerts
    assert worker.process(c.tick(ATTACK)) == []
    assert worker.process_counts(_counts(1000.0, 0)) == []
    assert worker.process_counts(_counts(1002.0, 2000)) == []  # 1,000 UDP/s: first report → WATCH
    alerts = worker.process_counts(_counts(1004.0, 4000))
    assert [(a.in_port, a.threat_type, a.stage) for a in alerts] == [(2, "UDP_FLOOD", RiskStage.DANGER.value)]
    assert alerts[0].pps == pytest.approx(1700, rel=0.01)  # from the latest port stats


def test_legacy_mode_ignores_counts(model):
    worker = InferenceWorker(model)
    assert worker.process_counts(_counts(1000.0, 0)) == []


def test_criteria_mode_uses_service_health_for_danger(model):
    from harness.contracts import ServiceHealthMessage
    worker = InferenceWorker(model, criteria=CriteriaEngine(ports=[(1, 2)]))
    worker.process_counts(_counts(1000.0, 0))
    worker.process_counts(_counts(1002.0, 300))  # 150 UDP/s: 3x the line, WARNING on its own
    for t in (1003.0, 1005.0):
        worker.process_health(ServiceHealthMessage(timestamp=t, target_ip="10.0.0.4", sent=10, received=5,
                                                   loss_percent=50.0, rtt_avg_ms=3.0))
    [alert] = worker.process_counts(_counts(1006.0, 600))
    assert (alert.threat_type, alert.stage) == ("UDP_FLOOD", RiskStage.DANGER.value)
    assert "service degraded" in alert.metadata["reasons"]
    InferenceWorker(model).process_health(ServiceHealthMessage(target_ip="10.0.0.4", sent=1, received=0,
                                                               loss_percent=100.0))  # legacy: ignored


def test_relearn_command_reaches_the_criteria_engine(model):
    from harness.contracts import ControlCommandMessage
    worker = InferenceWorker(model, criteria=CriteriaEngine(ports=[(1, 2)]))
    cmd = ControlCommandMessage(command_id="manual-relearn-1", action="RELEARN", target_dpid=0, target_port=0,
                                reason="[MANUAL] admin: 수강신청", duration_sec=600.0)
    assert worker.process_command(cmd, now=1000.0) == [(1, 2)]
    isolate = ControlCommandMessage(command_id="manual-isolate-1", action="ISOLATE", target_dpid=1,
                                    target_port=2, reason="x")
    assert worker.process_command(isolate) == []
    assert InferenceWorker(model).process_command(cmd) == []  # legacy mode has no baselines to relearn
