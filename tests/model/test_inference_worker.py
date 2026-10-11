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
