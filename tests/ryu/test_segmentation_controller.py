"""
Unit tests for Ryu Controller Table 1 Dynamic Network Segmentation & Quarantine.
Validates:
1. Table 1 Zone Policy flows installation in switch_features_handler
2. Ingress Trunk bypass (Pri 65535), ARP pass (Pri 500), and Probe pass (Pri 400)
3. Hard Whitelist protection preventing server/probe quarantine
4. Host quarantine: flow mods on TABLE_POLICY (delete normal, add admin HTTPS/DNS)
5. Host release: restoring normal USER flows on TABLE_POLICY
6. Redis command dispatcher handling QUARANTINE and RELEASE actions
"""

from unittest.mock import MagicMock
import pytest

from harness.contracts.sdn_events import (
    REDIS_CHANNEL_CONTROL_COMMAND,
    ControlCommandMessage,
    CountKind,
    DefenseAction,
)
from tests.ryu.test_controller_logic import SelfDefendingSDNController

_globals = SelfDefendingSDNController.__init__.__globals__
TABLE_COUNT = _globals["TABLE_COUNT"]
TABLE_POLICY = _globals["TABLE_POLICY"]
TABLE_POLICE = _globals["TABLE_POLICE"]
TABLE_FORWARD = _globals["TABLE_FORWARD"]


def _make_controller_with_dp(dpid=1):
    controller = SelfDefendingSDNController()
    dp = MagicMock()
    dp.id = dpid
    dp.ofproto.OFPP_ANY = 0xFFFFFFFF
    dp.ofproto.OFPG_ANY = 0xFFFFFFFF
    dp.ofproto.OFP_NO_BUFFER = 0xFFFFFFFF
    dp.ofproto.OFPP_CONTROLLER = 0xFFFFFFFD
    dp.ofproto.OFPCML_NO_BUFFER = 0xFFFF
    dp.ofproto_parser = MagicMock()
    controller.datapaths[dpid] = dp
    return controller, dp


def test_switch_features_installs_segmentation_rules():
    controller, dp = _make_controller_with_dp(dpid=1)
    controller.add_flow = MagicMock()
    ev = MagicMock()
    ev.msg.datapath = dp
    dp.id = 1

    controller.switch_features_handler(ev)

    policy_calls = [
        c.kwargs for c in controller.add_flow.call_args_list
        if c.kwargs.get("table_id") == TABLE_POLICY
    ]
    assert len(policy_calls) > 0

    priorities = [c["priority"] for c in policy_calls]
    # Trunk bypass
    assert 65535 in priorities
    # ARP pass
    assert 500 in priorities
    # Probe pass
    assert 400 in priorities
    # Silent drop
    assert 350 in priorities
    # USER -> SERVER allow rules
    assert 200 in priorities
    # ZONE_DENY table-miss per access port
    assert 0 in priorities

    # Check ZONE_DENY cookie on priority 0
    zone_deny_calls = [c for c in policy_calls if c["priority"] == 0]
    assert len(zone_deny_calls) >= 2  # S1 has Port 1 and Port 2
    for call in zone_deny_calls:
        assert call["cookie"] is not None
        assert call["actions"] == []


def test_quarantine_hard_whitelist_protection():
    controller, _ = _make_controller_with_dp(dpid=1)
    # Server and probe IP cannot be quarantined
    assert controller.quarantine_host("10.0.0.4") is False
    assert controller.quarantine_host("10.0.0.250") is False
    assert controller.quarantine_host("10.0.0.254") is False
    assert len(controller.quarantined_hosts) == 0


def test_quarantine_and_release_host_flows():
    controller, dp = _make_controller_with_dp(dpid=1)
    controller.delete_flow = MagicMock()
    controller.add_flow = MagicMock()

    # 1. Quarantine H_attacker (10.0.0.2 on S1:P2)
    ok = controller.quarantine_host("10.0.0.2")
    assert ok is True
    assert "10.0.0.2" in controller.quarantined_hosts

    # Verify normal Pri 200 rules deleted from TABLE_POLICY
    deleted = [
        c.kwargs for c in controller.delete_flow.call_args_list
        if c.kwargs.get("table_id") == TABLE_POLICY and c.kwargs.get("priority") == 200
    ]
    assert len(deleted) >= 3  # Web, DNS, ICMP

    # Verify Pri 300 quarantine rules added to TABLE_POLICY
    added_quarantine = [
        c.kwargs for c in controller.add_flow.call_args_list
        if c.kwargs.get("table_id") == TABLE_POLICY and c.kwargs.get("priority") == 300
    ]
    assert len(added_quarantine) == 2  # HTTPS 443, DNS 53 to ADMIN

    # 2. Release H_attacker
    controller.delete_flow.reset_mock()
    controller.add_flow.reset_mock()

    ok_rel = controller.release_host("10.0.0.2")
    assert ok_rel is True
    assert "10.0.0.2" not in controller.quarantined_hosts

    # Verify Pri 300 quarantine rules deleted
    deleted_q = [
        c.kwargs for c in controller.delete_flow.call_args_list
        if c.kwargs.get("table_id") == TABLE_POLICY and c.kwargs.get("priority") == 300
    ]
    assert len(deleted_q) == 2

    # Verify Pri 200 normal USER rules restored
    restored = [
        c.kwargs for c in controller.add_flow.call_args_list
        if c.kwargs.get("table_id") == TABLE_POLICY and c.kwargs.get("priority") == 200
    ]
    assert len(restored) >= 3


def test_redis_control_command_quarantine_and_release():
    controller, _ = _make_controller_with_dp(dpid=1)
    controller.quarantine_host = MagicMock()
    controller.release_host = MagicMock()
    controller._publish_topology_sync = MagicMock()

    # QUARANTINE command
    q_cmd = ControlCommandMessage(
        command_id="manual-q-1",
        action=DefenseAction.QUARANTINE.value,
        target_dpid=1,
        target_port=2,
        reason="Lateral spread detected",
        target_ip="10.0.0.2",
        target_mac="00:00:00:00:00:02",
    )
    controller._handle_redis_message(REDIS_CHANNEL_CONTROL_COMMAND, q_cmd.model_dump_json())
    controller.quarantine_host.assert_called_once_with(
        "10.0.0.2", "00:00:00:00:00:02", 1, 2
    )

    # RELEASE command
    r_cmd = ControlCommandMessage(
        command_id="manual-r-1",
        action=DefenseAction.RELEASE.value,
        target_dpid=1,
        target_port=2,
        reason="Host cleaned and verified",
        target_ip="10.0.0.2",
        target_mac="00:00:00:00:00:02",
    )
    controller._handle_redis_message(REDIS_CHANNEL_CONTROL_COMMAND, r_cmd.model_dump_json())
    controller.release_host.assert_called_once_with(
        "10.0.0.2", "00:00:00:00:00:02", 1, 2
    )


def test_anomaly_alert_threat_type_branching():
    from harness.contracts.sdn_events import REDIS_CHANNEL_ANOMALY_ALERT, AnomalyAlertMessage, RiskStage, ThreatType

    controller, _ = _make_controller_with_dp(dpid=1)
    controller.quarantine_host = MagicMock()
    controller.isolate_port = MagicMock()
    controller.reroute_traffic = MagicMock()
    controller._publish_control_command = MagicMock()
    controller._publish_topology_sync = MagicMock()

    # 1. INTERNAL_SPREAD alert -> triggers quarantine_host only, NOT isolate_port
    spread_alert = AnomalyAlertMessage(
        dpid=1, in_port=2, threat_type=ThreatType.INTERNAL_SPREAD.value,
        stage=RiskStage.DANGER.value, score=-2.5, pps=50.0, bps=1000.0, bpp=64.0
    )
    controller._handle_redis_message(REDIS_CHANNEL_ANOMALY_ALERT, spread_alert.model_dump_json())
    controller.quarantine_host.assert_called_once_with("10.0.0.2", dpid=1, port=2)
    controller.isolate_port.assert_not_called()
    controller.reroute_traffic.assert_not_called()

    # 2. Flood alert -> triggers isolate_port + reroute_traffic
    controller.quarantine_host.reset_mock()
    controller.isolate_port.reset_mock()
    controller.reroute_traffic.reset_mock()
    controller.fsm.force_restore()

    flood_alert = AnomalyAlertMessage(
        dpid=1, in_port=2, threat_type=ThreatType.SYN_FLOOD_SPOOFING.value,
        stage=RiskStage.DANGER.value, score=-5.0, pps=500.0, bps=10000.0, bpp=64.0
    )
    controller._handle_redis_message(REDIS_CHANNEL_ANOMALY_ALERT, flood_alert.model_dump_json())
    controller.quarantine_host.assert_not_called()
    controller.isolate_port.assert_called_once_with(1, 2, priority=100)
    controller.reroute_traffic.assert_called_once_with(source_dpid=1, target_dpid=4, dst_ip="10.0.0.4")
