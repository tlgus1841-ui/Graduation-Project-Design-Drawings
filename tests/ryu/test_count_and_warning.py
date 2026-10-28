"""Counting rules (table 0) and WARNING-stage rate limiting in the Ryu controller."""

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
police_match = _module["police_match"]


def test_police_match_limits_only_the_attack_kind():
    assert police_match("UDP_FLOOD") == {"eth_type": 0x0800, "ip_proto": 17}
    assert police_match("ICMP_FLOOD") == {"eth_type": 0x0800, "ip_proto": 1}
    assert police_match("SYN_FLOOD_SPOOFING")["tcp_flags"] == (0x002, 0x012)
    assert police_match("PORT_SCAN") == police_match("SYN_FLOOD_SPOOFING")
    assert police_match("UNKNOWN") == {}


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
