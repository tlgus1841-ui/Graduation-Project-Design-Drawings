"""Service-health probe: the controller pings the protected server from S1 and reports loss and delay."""

import time
from unittest.mock import MagicMock

from harness.contracts.sdn_events import (
    ACCESS_HOST_PORTS,
    REDIS_CHANNEL_SERVICE_HEALTH,
    SERVICE_PROBE_IP,
    SERVICE_PROBE_MAC,
    ServiceHealthMessage,
)
from tests.ryu.test_controller_logic import SelfDefendingSDNController

_module = SelfDefendingSDNController.__init__.__globals__
ProbeTracker = _module["ProbeTracker"]
PROBE_ICMP_ID = _module["PROBE_ICMP_ID"]


def test_tracker_counts_only_settled_probes():
    tracker = ProbeTracker(timeout=1.0)
    for i in range(10):
        tracker.next_seq(100.0 + 0.2 * i)  # 100.0 … 101.8
    for seq in range(1, 9):
        tracker.reply(seq, 100.0 + 0.2 * (seq - 1) + 0.004)  # 4 ms, except seq 9 and 10
    tracker.reply(9, 101.6 + 1.5)  # too late: counts as lost

    msg = tracker.summary(now=102.1)  # seq 1–6 sent at least 1 s ago
    assert (msg.sent, msg.received, msg.loss_percent) == (6, 6, 0.0)
    assert msg.rtt_avg_ms == 4.0 and msg.rtt_max_ms == 4.0

    msg = tracker.summary(now=103.0)
    assert (msg.sent, msg.received) == (4, 2) and msg.loss_percent == 50.0
    assert tracker.summary(now=104.0) is None  # nothing new settled


def test_all_probes_lost_has_no_rtt():
    tracker = ProbeTracker(timeout=1.0)
    tracker.next_seq(10.0)
    msg = tracker.summary(now=12.0)
    assert msg.loss_percent == 100.0 and msg.rtt_avg_ms is None


def test_arp_for_the_probe_address_is_answered_by_the_controller():
    controller = SelfDefendingSDNController()
    controller.send_arp_reply = MagicMock()
    datapath, eth, arp_pkt = MagicMock(), MagicMock(), MagicMock()
    datapath.id = 5
    eth.src = "00:00:00:00:00:11"
    arp_pkt.opcode, arp_pkt.dst_ip, arp_pkt.src_ip = 1, SERVICE_PROBE_IP, "10.0.0.11"
    controller.handle_arp(datapath, in_port=1, eth=eth, arp_pkt=arp_pkt)
    controller.send_arp_reply.assert_called_once_with(
        datapath, SERVICE_PROBE_MAC, SERVICE_PROBE_IP, "00:00:00:00:00:11", "10.0.0.11", 1)


def _reply_packet(seq, icmp_id=PROBE_ICMP_ID):
    icmp_pkt = MagicMock()
    icmp_pkt.type = 0
    icmp_pkt.data.id = icmp_id
    icmp_pkt.data.seq = seq
    pkt = MagicMock()
    pkt.get_protocol.return_value = icmp_pkt
    return pkt


def test_reply_is_sent_back_towards_s1_then_recorded_there():
    controller = SelfDefendingSDNController()
    controller.add_flow = MagicMock()
    s5 = MagicMock()
    s5.id = 5
    controller._handle_probe_reply(s5, in_port=1, pkt=_reply_packet(1), data=b"x")
    assert controller.add_flow.call_args.kwargs["actions"][0] is not None
    s5.ofproto_parser.OFPActionOutput.assert_called_with(controller.routing_table[5][controller.probe_route_ip])
    s5.send_msg.assert_called_once()

    seq = controller.probe.next_seq(time.time())
    s3 = MagicMock()
    s3.id = 3
    controller._handle_probe_reply(s3, in_port=99, pkt=_reply_packet(seq, icmp_id=0x1234), data=b"x")
    assert controller.probe.rtt_ms == {}  # someone else's ping
    controller._handle_probe_reply(s3, in_port=99, pkt=_reply_packet(seq), data=b"x")
    assert seq in controller.probe.rtt_ms
    s3.send_msg.assert_not_called()


def test_health_is_published_every_report():
    controller = SelfDefendingSDNController()
    controller.redis_client = MagicMock()
    controller.probe.next_seq(10.0)
    controller._publish_service_health(now=12.0)
    channel, body = controller.redis_client.publish.call_args.args
    assert channel == REDIS_CHANNEL_SERVICE_HEALTH
    assert ServiceHealthMessage.model_validate_json(body).loss_percent == 100.0
    controller.redis_client.publish.reset_mock()
    controller._publish_service_health(now=14.0)  # nothing settled: no message
    controller.redis_client.publish.assert_not_called()


def test_access_host_ports_match_the_controller():
    controller = SelfDefendingSDNController()
    assert ACCESS_HOST_PORTS == {ip: (h["dpid"], h["port"]) for ip, h in controller.arp_table.items()}
