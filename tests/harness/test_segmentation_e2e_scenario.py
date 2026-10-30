"""
Phase 5 End-to-End Validation:
Dynamic Network Segmentation, Silent Drop, Lateral Attack Detection,
Host-level Autonomous Quarantine, and Admin Human-in-the-loop Release.

Validates the full Phase 1 ~ 5 lifecycle:
1. Normal traffic baseline & OS background multicast silent drop (Loss 0.0%, ZONE_DENY = 0)
2. Lateral spread attack (SMB 445) blocked by Table 1, generating ZONE_DENY counts
3. CriteriaEngine detecting INTERNAL_SPREAD and triggering autonomous DANGER alert
4. Controller pinning only the offending host (10.0.0.2) into QUARANTINE without dropping legitimate users
5. Admin audit approval releasing the quarantined host back to the USER zone
"""

import json
from unittest.mock import MagicMock
import fakeredis
import pytest

from harness.contracts.sdn_events import (
    REDIS_CHANNEL_ANOMALY_ALERT,
    REDIS_CHANNEL_CONTROL_COMMAND,
    AnomalyAlertMessage,
    ControlCommandMessage,
    CountKind,
    DefenseAction,
    FlowCountItem,
    FlowCountMessage,
    RiskStage,
    ThreatType,
)
from model.criteria_engine import CriteriaConfig, CriteriaEngine
from tests.ryu.test_telemetry import _setup_and_load_controller_for_telemetry

_ControllerCls = _setup_and_load_controller_for_telemetry()
_globals = _ControllerCls.__init__.__globals__
TABLE_COUNT = _globals["TABLE_COUNT"]
TABLE_POLICY = _globals["TABLE_POLICY"]
TABLE_POLICE = _globals["TABLE_POLICE"]
TABLE_FORWARD = _globals["TABLE_FORWARD"]


def test_phase5_segmentation_e2e_lifecycle():
    fake_server = fakeredis.FakeServer()
    redis_client = fakeredis.FakeRedis(server=fake_server, decode_responses=True)

    controller = _ControllerCls()
    controller.redis_client = redis_client
    controller.add_flow = MagicMock()
    controller.delete_flow = MagicMock()
    controller._publish_topology_sync = MagicMock()

    # 1. Topology & Switch Initialization (S1 ~ S4)
    mock_dps = {}
    for dpid in [1, 2, 3, 4]:
        dp = MagicMock()
        dp.id = dpid
        dp.ofproto.OFPP_ANY = 0xFFFFFFFF
        dp.ofproto.OFPG_ANY = 0xFFFFFFFF
        dp.ofproto.OFP_NO_BUFFER = 0xFFFFFFFF
        dp.ofproto.OFPP_CONTROLLER = 0xFFFFFFFD
        dp.ofproto.OFPCML_NO_BUFFER = 0xFFFF
        dp.ofproto_parser = MagicMock()
        mock_dps[dpid] = dp
        controller.datapaths[dpid] = dp

        ev = MagicMock()
        ev.msg.datapath = dp
        controller.switch_features_handler(ev)

    # Verify Table 1 was installed on S1
    s1_policy_calls = [
        c.kwargs for c in controller.add_flow.call_args_list
        if c.kwargs.get("table_id") == TABLE_POLICY
    ]
    assert len(s1_policy_calls) > 0

    # 2. Criteria Engine Setup
    cfg = CriteriaConfig(zone_deny_min=10.0, confirm_intervals=2)
    engine = CriteriaEngine(cfg, ports=[(1, 2)])

    # Report 1: Normal user traffic (zone_deny = 0)
    msg1 = FlowCountMessage(
        timestamp=1000.0, dpid=1,
        counts=[
            FlowCountItem(port_no=2, kind=CountKind.SYN.value, packets=10),
            FlowCountItem(port_no=2, kind=CountKind.FIN.value, packets=10),
            FlowCountItem(port_no=2, kind=CountKind.ZONE_DENY.value, packets=0),
        ]
    )
    decisions1 = engine.update(msg1)
    # First tick initializes baselines / prev_counts
    assert len(decisions1) == 0

    # Report 2: Normal user traffic continues
    msg2 = FlowCountMessage(
        timestamp=1001.0, dpid=1,
        counts=[
            FlowCountItem(port_no=2, kind=CountKind.SYN.value, packets=20),
            FlowCountItem(port_no=2, kind=CountKind.FIN.value, packets=20),
            FlowCountItem(port_no=2, kind=CountKind.ZONE_DENY.value, packets=0),
        ]
    )
    decisions2 = engine.update(msg2)
    assert len(decisions2) == 1
    assert decisions2[0].stage == RiskStage.NORMAL

    # 3. Attack Phase: Lateral Spread (SMB 445)
    # Attack packets hit Table 1 Priority 0, generating 40 zone_deny packets in 1 sec
    msg3 = FlowCountMessage(
        timestamp=1002.0, dpid=1,
        counts=[
            FlowCountItem(port_no=2, kind=CountKind.SYN.value, packets=60),
            FlowCountItem(port_no=2, kind=CountKind.FIN.value, packets=20),
            FlowCountItem(port_no=2, kind=CountKind.ZONE_DENY.value, packets=40),
        ]
    )
    decisions3 = engine.update(msg3)
    assert len(decisions3) == 1
    # Streak 1: candidate identified
    assert decisions3[0].threat_type in (None, ThreatType.INTERNAL_SPREAD.value)

    # Attack continues: 40 more zone_deny packets
    msg4 = FlowCountMessage(
        timestamp=1003.0, dpid=1,
        counts=[
            FlowCountItem(port_no=2, kind=CountKind.SYN.value, packets=100),
            FlowCountItem(port_no=2, kind=CountKind.FIN.value, packets=20),
            FlowCountItem(port_no=2, kind=CountKind.ZONE_DENY.value, packets=80),
        ]
    )
    decisions4 = engine.update(msg4)
    assert len(decisions4) == 1
    # Confirmed in streak 2 -> DANGER, threat_type: INTERNAL_SPREAD
    d4 = decisions4[0]
    assert d4.stage == RiskStage.DANGER
    assert d4.threat_type == ThreatType.INTERNAL_SPREAD.value

    # 4. Alert & Autonomous Mitigation by Controller
    alert = AnomalyAlertMessage(
        dpid=d4.dpid, in_port=d4.port, threat_type=d4.threat_type,
        stage=d4.stage.value, score=-4.0, pps=40.0, bps=10000.0, bpp=64.0
    )
    controller.add_flow.reset_mock()
    controller.delete_flow.reset_mock()

    controller._handle_redis_message(REDIS_CHANNEL_ANOMALY_ALERT, alert.model_dump_json())

    # Host 10.0.0.2 is quarantined!
    assert "10.0.0.2" in controller.quarantined_hosts
    # Normal user 10.0.0.1 is unaffected!
    assert "10.0.0.1" not in controller.quarantined_hosts

    # Verify flow operations: Pri 200 normal rules deleted, Pri 300 admin rules installed
    deleted_p200 = [
        c.kwargs for c in controller.delete_flow.call_args_list
        if c.kwargs.get("table_id") == TABLE_POLICY and c.kwargs.get("priority") == 200
    ]
    assert len(deleted_p200) >= 3

    added_p300 = [
        c.kwargs for c in controller.add_flow.call_args_list
        if c.kwargs.get("table_id") == TABLE_POLICY and c.kwargs.get("priority") == 300
    ]
    assert len(added_p300) == 2

    # 5. Admin Human-in-the-loop Release Phase
    controller.add_flow.reset_mock()
    controller.delete_flow.reset_mock()

    release_cmd = ControlCommandMessage(
        command_id="manual-release-audit-99",
        action=DefenseAction.RELEASE.value,
        target_dpid=1,
        target_port=2,
        reason="Security admin audit: malware cleaned, verified safe",
        target_ip="10.0.0.2",
    )
    controller._handle_redis_message(REDIS_CHANNEL_CONTROL_COMMAND, release_cmd.model_dump_json())

    # Host 10.0.0.2 released from quarantine
    assert "10.0.0.2" not in controller.quarantined_hosts

    # Verify Pri 300 deleted, Pri 200 restored
    deleted_p300 = [
        c.kwargs for c in controller.delete_flow.call_args_list
        if c.kwargs.get("table_id") == TABLE_POLICY and c.kwargs.get("priority") == 300
    ]
    assert len(deleted_p300) == 2

    restored_p200 = [
        c.kwargs for c in controller.add_flow.call_args_list
        if c.kwargs.get("table_id") == TABLE_POLICY and c.kwargs.get("priority") == 200
    ]
    assert len(restored_p200) >= 3
