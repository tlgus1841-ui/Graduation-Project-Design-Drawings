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
    """Cumulative S3 port counters that advance by a given rate each 2-second poll."""

    def __init__(self) -> None:
        self.t = 1000.0
        self.pkts = {1: 0, 2: 0, 99: 0}
        self.bytes = {1: 0, 2: 0, 99: 0}

    def tick(self, rates):
        self.t += 2.0
        for port, (pps, size) in rates.items():
            self.pkts[port] += int(pps * 2)
            self.bytes[port] += int(pps * 2 * size)
        stats = [PortStatItem(dpid=3, port_no=p, rx_packets=self.pkts[p], tx_packets=0, rx_bytes=self.bytes[p],
                              tx_bytes=0, duration_sec=60) for p in self.pkts]
        return PortStatsMessage(timestamp=self.t, dpid=3, stats=stats)


NORMAL = {1: (20, 98), 2: (0, 0), 99: (20, 98)}
ATTACK = {1: (20, 98), 2: (1700, 54), 99: (1720, 55)}


def test_only_unprotected_access_ports_are_watched():
    # users S3 · S4, sinkhole S8 and the external entrance S9; servers, DMZ and admin are protected
    assert watched_ports() == [(3, 1), (3, 2), (4, 1), (4, 2), (8, 1), (9, 1)]


def test_attack_is_confirmed_on_second_sample_and_keeps_alerting(model):
    worker, c = InferenceWorker(model), Counters()
    assert worker.process(c.tick(NORMAL)) == []  # baseline only
    assert worker.process(c.tick(NORMAL)) == []
    assert worker.process(c.tick(ATTACK)) == []  # first suspicious sample
    alerts = worker.process(c.tick(ATTACK))
    assert [(a.dpid, a.in_port) for a in alerts] == [(3, 2)]
    assert alerts[0].bpp == pytest.approx(54, abs=1) and alerts[0].score < 0
    assert len(worker.process(c.tick(ATTACK))) == 1  # heartbeat for the controller FSM
    assert worker.process(c.tick(NORMAL)) == []


def test_trunk_port_carrying_the_attack_never_alerts(model):
    worker, c = InferenceWorker(model), Counters()
    for rates in (NORMAL, ATTACK, ATTACK, ATTACK):
        alerts = worker.process(c.tick(rates))
        assert all(a.in_port != 99 for a in alerts)


def test_single_spike_and_low_rate_small_packets_do_not_alert(model):
    worker, c = InferenceWorker(model), Counters()
    worker.process(c.tick(NORMAL))
    for rates in (ATTACK, NORMAL, ATTACK, NORMAL):  # never two in a row
        assert worker.process(c.tick(rates)) == []
    trickle = {1: (20, 98), 2: (5, 60), 99: (25, 90)}  # small packets but far below flood rate
    for _ in range(3):
        assert worker.process(c.tick(trickle)) == []


def test_small_packet_burst_below_flood_threshold_is_confirmed_as_port_scan(model):
    """DDoS 외 공격 유형: 플러드 임계치(100 PPS)에는 못 미치지만, 평온한 기준선 대비
    튀는 소형 패킷(포트 순환 SYN 등) 버스트는 PORT_SCAN으로 확정되어야 한다."""
    worker, c = InferenceWorker(model), Counters()
    quiet = {1: (20, 98), 2: (5, 60), 99: (20, 98)}  # 포트 2: 조용한 기준선 (플러드 아님)
    scan = {1: (20, 98), 2: (80, 60), 99: (20, 98)}  # 포트 2: 여전히 플러드 임계치 미달이지만 급등

    for _ in range(6):
        worker.process(c.tick(quiet))  # EWMA 기준선 확보 (warmup)
    worker.process(c.tick(scan))  # 1st suspicious sample
    alerts = worker.process(c.tick(scan))  # 2nd -> confirmed

    assert len(alerts) == 1
    assert alerts[0].in_port == 2
    assert alerts[0].threat_type == "PORT_SCAN"


def test_sustained_small_packet_burst_escalates_to_slow_ddos(model):
    """같은 소형 패킷 버스트가 오래(SUSTAINED_TICKS_FOR_SLOW_DDOS 이상) 계속되면
    탐색성 버스트(포트 스캔)가 아니라 저속·장기 지속 공격(Slow DDoS)으로 승격한다."""
    worker, c = InferenceWorker(model), Counters()
    quiet = {1: (20, 98), 2: (5, 60), 99: (20, 98)}
    burst = {1: (20, 98), 2: (80, 60), 99: (20, 98)}

    for _ in range(6):
        worker.process(c.tick(quiet))

    threat_types = []
    for _ in range(15):
        alerts = worker.process(c.tick(burst))
        threat_types.extend(a.threat_type for a in alerts)

    assert "PORT_SCAN" in threat_types  # 처음엔 짧은 버스트로 분류됨
    assert threat_types[-1] == "SLOW_DDOS"  # 계속되니 Slow DDoS로 승격


def test_normal_steady_traffic_never_triggers_secondary_classifier(model):
    worker, c = InferenceWorker(model), Counters()
    for _ in range(20):
        assert worker.process(c.tick(NORMAL)) == []


# ---------------------------------------------------------------------
# Criteria mode: alerts come from per-kind counts, port stats only fill pps/bpp
# ---------------------------------------------------------------------
from harness.contracts import FlowCountItem, FlowCountMessage, RiskStage  # noqa: E402
from model.criteria_engine import CriteriaEngine  # noqa: E402


def _counts(t, udp_total):
    return FlowCountMessage(timestamp=t, dpid=3, counts=[
        FlowCountItem(port_no=2, kind=k, packets=udp_total if k == "udp" else 0)
        for k in ("syn", "fin", "rst", "udp", "icmp", "rst_in", "unreach_in")])


def test_criteria_mode_alerts_with_stage_and_threat_type(model):
    worker, c = InferenceWorker(model, criteria=CriteriaEngine(ports=[(3, 2)])), Counters()
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
    worker = InferenceWorker(model, criteria=CriteriaEngine(ports=[(3, 2)]))
    worker.process_counts(_counts(1000.0, 0))
    worker.process_counts(_counts(1002.0, 300))  # 150 UDP/s: 3x the line, WARNING on its own
    for t in (1003.0, 1005.0):
        worker.process_health(ServiceHealthMessage(timestamp=t, target_ip="10.0.0.11", sent=10, received=5,
                                                   loss_percent=50.0, rtt_avg_ms=3.0))
    [alert] = worker.process_counts(_counts(1006.0, 600))
    assert (alert.threat_type, alert.stage) == ("UDP_FLOOD", RiskStage.DANGER.value)
    assert "service degraded" in alert.metadata["reasons"]
    InferenceWorker(model).process_health(ServiceHealthMessage(target_ip="10.0.0.11", sent=1, received=0,
                                                               loss_percent=100.0))  # legacy: ignored


def test_relearn_command_reaches_the_criteria_engine(model):
    from harness.contracts import ControlCommandMessage
    worker = InferenceWorker(model, criteria=CriteriaEngine(ports=[(3, 2)]))
    cmd = ControlCommandMessage(command_id="manual-relearn-1", action="RELEARN", target_dpid=0, target_port=0,
                                reason="[MANUAL] admin: 수강신청", duration_sec=600.0)
    assert worker.process_command(cmd, now=1000.0) == [(3, 2)]
    isolate = ControlCommandMessage(command_id="manual-isolate-1", action="ISOLATE", target_dpid=3,
                                    target_port=2, reason="x")
    assert worker.process_command(isolate) == []
    assert InferenceWorker(model).process_command(cmd) == []  # legacy mode has no baselines to relearn
