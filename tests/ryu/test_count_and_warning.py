"""Counting rules (table 0) and WARNING-stage rate limiting in the Ryu controller."""

import json
from unittest.mock import MagicMock

from harness.contracts.sdn_events import (
    REDIS_CHANNEL_ANOMALY_ALERT,
    WARNING_HOLD_SEC,
    AnomalyAlertMessage,
    DefenseAction,
)
from tests.ryu.test_controller_logic import SelfDefendingSDNController

_module = SelfDefendingSDNController.__init__.__globals__
count_cookie = _module["count_cookie"]
decode_count_cookie = _module["decode_count_cookie"]
count_rule_specs = _module["count_rule_specs"]
TABLE_COUNT, TABLE_POLICE, TABLE_FORWARD = _module["TABLE_COUNT"], _module["TABLE_POLICE"], _module["TABLE_FORWARD"]
police_matches = _module["police_matches"]


def test_police_matches_limit_only_the_attack_kind():
    udp, icmp = {"eth_type": 0x0800, "ip_proto": 17}, {"eth_type": 0x0800, "ip_proto": 1}
    assert police_matches("UDP_FLOOD") == [udp]
    assert police_matches("ICMP_FLOOD") == [icmp]
    [syn] = police_matches("SYN_FLOOD_SPOOFING")
    assert syn["tcp_flags"] == (0x002, 0x012)  # SYN without ACK: the host's own web traffic keeps flowing
    assert police_matches("PORT_SCAN") == [syn, udp]  # TCP and UDP scans
    assert police_matches("SLOW_DDOS") == [syn]  # Slow HTTP: no more new connections
    assert police_matches("INTERNAL_SPREAD") == [syn]
    assert police_matches("UNKNOWN") == [{}]  # whole port


def test_count_cookie_round_trip_and_foreign_cookie():
    for kind in ("syn", "fin", "rst", "udp", "icmp", "rst_in", "unreach_in"):
        assert decode_count_cookie(count_cookie(4, 1, kind)) == (4, 1, kind)
    assert decode_count_cookie(0) is None
    assert decode_count_cookie(0x1234) is None


def test_count_rules_cover_every_access_host():
    controller = SelfDefendingSDNController()
    specs = count_rule_specs(controller.arp_table)
    assert len(specs) == 7 * len(controller.arp_table)
    by_kind = {(dpid, port, kind): (prio, match) for dpid, port, kind, prio, match in specs}
    prio, match = by_kind[(1, 2, "syn")]
    assert match["in_port"] == 2 and match["ip_proto"] == 6
    assert match["tcp_flags"] == (0x002, 0x012)  # SYN set, ACK clear: requests only, not SYN-ACK replies
    rst_in_prio, rst_in = by_kind[(1, 2, "rst_in")]
    assert rst_in["ipv4_dst"] == "10.0.0.2" and "in_port" not in rst_in
    # What a host sends wins over what it receives when both match one packet (one rule per table)
    assert prio > rst_in_prio


def test_switch_features_installs_count_police_and_forward_tables():
    controller = SelfDefendingSDNController()
    controller.add_flow = MagicMock()
    ev = MagicMock()
    ev.msg.datapath.id = 1
    controller.switch_features_handler(ev)

    calls = [c.kwargs for c in controller.add_flow.call_args_list]
    tables = [c.get("table_id", TABLE_FORWARD) for c in calls]
    assert tables.count(TABLE_COUNT) == 1 + 14  # default goto + 7 rules for each of the 2 hosts on S1
    assert tables.count(TABLE_POLICE) == 1
    table_miss = [c for c in calls if c.get("table_id", TABLE_FORWARD) == TABLE_FORWARD]
    assert len(table_miss) == 1 and table_miss[0]["priority"] == 0
    assert all(c["cookie"] for c in calls if c.get("table_id") == TABLE_COUNT and c["priority"] > 0)


def _controller():
    controller = SelfDefendingSDNController()
    for name in ("isolate_port", "restore_port", "reroute_traffic", "restore_reroute_traffic",
                 "rate_limit_port", "unrate_limit_port", "_publish_control_command", "_publish_topology_sync"):
        setattr(controller, name, MagicMock())
    return controller


def _alert(stage):
    return AnomalyAlertMessage(dpid=1, in_port=2, threat_type="UDP_FLOOD", score=-0.2, pps=400.0, bps=1.0,
                               bpp=60.0, stage=stage).model_dump_json()


def _actions(controller):
    return [c.kwargs["action"] for c in controller._publish_control_command.call_args_list]


def test_warning_rate_limits_once_and_lifts_after_hold():
    controller = _controller()
    controller._handle_redis_message(REDIS_CHANNEL_ANOMALY_ALERT, _alert("WARNING"))
    controller._handle_redis_message(REDIS_CHANNEL_ANOMALY_ALERT, _alert("WARNING"))
    controller.rate_limit_port.assert_called_once_with(1, 2, "UDP_FLOOD")
    controller.isolate_port.assert_not_called()
    assert _actions(controller) == [DefenseAction.RATE_LIMIT.value]

    controller._expire_rate_limits(now=controller.rate_limits["1:2"] + WARNING_HOLD_SEC - 1)
    controller.unrate_limit_port.assert_not_called()
    controller._expire_rate_limits(now=controller.rate_limits["1:2"] + WARNING_HOLD_SEC)
    controller.unrate_limit_port.assert_called_once_with(1, 2)
    assert controller.rate_limits == {}
    assert _actions(controller)[-1] == DefenseAction.UNLIMIT.value


def test_danger_after_warning_isolates_and_drops_the_rate_limit():
    controller = _controller()
    controller._handle_redis_message(REDIS_CHANNEL_ANOMALY_ALERT, _alert("WARNING"))
    controller._handle_redis_message(REDIS_CHANNEL_ANOMALY_ALERT, _alert("DANGER"))
    controller.unrate_limit_port.assert_called_once_with(1, 2)
    controller.isolate_port.assert_called_once()
    assert controller.rate_limits == {}


def test_warning_while_isolated_keeps_the_isolation():
    controller = _controller()
    controller._handle_redis_message(REDIS_CHANNEL_ANOMALY_ALERT, _alert("DANGER"))
    controller._handle_redis_message(REDIS_CHANNEL_ANOMALY_ALERT, _alert("WARNING"))
    controller.rate_limit_port.assert_not_called()
    assert "1:2" in controller.fsm.mitigated_targets


def test_alert_without_stage_still_isolates():
    """Senders that predate the stage field (old worker, API mock) mean DANGER."""
    controller = _controller()
    legacy = AnomalyAlertMessage(dpid=1, in_port=2, score=-0.3, pps=1500.0, bps=1.0, bpp=54.0).model_dump_json()
    controller._handle_redis_message(REDIS_CHANNEL_ANOMALY_ALERT, legacy)
    controller.isolate_port.assert_called_once()


def test_missing_internal_hosts_asked_by_arp_are_counted_per_access_port():
    controller = SelfDefendingSDNController()
    controller.send_arp_reply = MagicMock()
    controller.redis_client = MagicMock()
    datapath, eth = MagicMock(), MagicMock()
    datapath.id = 1
    for target in ("10.0.0.7", "10.0.0.8", "10.0.0.7", "10.0.0.4", "10.0.0.2"):
        arp_pkt = MagicMock()
        arp_pkt.opcode, arp_pkt.dst_ip, arp_pkt.src_ip = 1, target, "10.0.0.2"
        controller.handle_arp(datapath, in_port=2, eth=eth, arp_pkt=arp_pkt)
    # Existing hosts are answered, the asker itself is ignored, repeats count once
    assert controller.arp_fail_targets[(1, 2)] == {"10.0.0.7", "10.0.0.8"}

    stat = MagicMock()
    stat.cookie, stat.packet_count = count_cookie(1, 2, "syn"), 40
    ev = MagicMock()
    ev.msg.datapath.id = 1
    ev.msg.body = [stat]
    controller.flow_stats_reply_handler(ev)
    body = controller.redis_client.publish.call_args.args[1]
    counts = {(c["port_no"], c["kind"]): c["packets"] for c in json.loads(body)["counts"]}
    assert counts[(2, "syn")] == 40 and counts[(2, "arp_fail")] == 2 and counts[(1, "arp_fail")] == 0


def test_monitor_loop_counts_every_second_and_port_stats_every_two():
    controller = SelfDefendingSDNController()
    dp = MagicMock()
    dp.id = 1
    controller.datapaths = {1: dp}
    controller._request_stats = MagicMock()
    controller._request_count_stats = MagicMock()
    controller._publish_service_health = MagicMock()
    hub = _module["hub"]
    original = hub.sleep
    hub.sleep = MagicMock(side_effect=[None] * 4 + [StopIteration])
    try:
        controller._monitor_loop()
    except StopIteration:
        pass
    finally:
        hub.sleep = original
    assert hub.sleep is original
    assert controller._request_count_stats.call_count == 4  # 4 one-second ticks
    assert controller._request_stats.call_count == 2 and controller._publish_service_health.call_count == 2
