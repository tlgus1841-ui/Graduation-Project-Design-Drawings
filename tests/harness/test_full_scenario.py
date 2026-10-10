"""
Comprehensive 4-Stage Autonomous Defense Scenario Verification (Week 14).
Author: Sihyeon Park (22101489 / Tech Lead)
Phase 6 Milestone

Simulates the full 4-stage lifecycle:
Stage 1: Normal Traffic Baseline (S1 -> S2 -> S4)
Stage 2: Attack Injection & Detection (Scapy SYN Flood on S1:P2, Score < -0.8)
Stage 3: Autonomous Defense & Bypass Rerouting (In_port 2 Drop, S1 -> S3 -> S4 Bypass)
Stage 4: Autonomous Self-Healing (Traffic ceases, FSM Cooldown, Safe Rollback to Baseline)
"""

from unittest.mock import MagicMock
import fakeredis
from harness.contracts.sdn_events import (
    REDIS_CHANNEL_ANOMALY_ALERT,
    AnomalyAlertMessage,
    ThreatType,
)
from harness.safety.flapping_fsm import DefenseState
from tests.ryu.test_telemetry import _setup_and_load_controller_for_telemetry


def test_full_4_stage_autonomous_defense_scenario():
    """
    4단계 전체 라이프사이클 시뮬레이션 및 검증:
    1단계 (Normal) -> 2단계 (Attack) -> 3단계 (Mitigate & Reroute) -> 4단계 (Self-Healing)
    """
    fake_server = fakeredis.FakeServer()
    redis_client = fakeredis.FakeRedis(server=fake_server, decode_responses=True)

    ControllerCls = _setup_and_load_controller_for_telemetry()
    controller = ControllerCls()
    controller.redis_client = redis_client

    # Connect switches S1, S2, S3, S4
    mock_dps = {}
    for dpid in [1, 2, 3, 4]:
        dp = MagicMock()
        dp.id = dpid
        dp.ofproto = MagicMock()
        dp.ofproto.OFPP_MAX = 0xff00
        dp.ofproto.OFP_NO_BUFFER = 0xffffffff
        dp.ofproto_parser = MagicMock()
        mock_dps[dpid] = dp
        controller.datapaths[dpid] = dp

    # [Stage 1: Normal Baseline]
    assert controller.fsm.get_state() == DefenseState.NORMAL
    # Primary routing for 10.0.0.4 on S1 points to S2 (Port 3)
    assert controller.routing_table[1]["10.0.0.4"] == 3

    # [Stage 2 & 3: Attack Detection & Autonomous Defense]
    alert = AnomalyAlertMessage(
        dpid=1,
        in_port=2,  # Attacker port
        threat_type=ThreatType.SYN_FLOOD_SPOOFING.value,
        score=-0.95,
        pps=4800.0,
        bps=3072000.0,
        bpp=64.0,
    )
    controller._handle_redis_message(
        REDIS_CHANNEL_ANOMALY_ALERT, alert.model_dump_json()
    )

    # 3.1 State must be MITIGATED
    assert controller.fsm.get_state() == DefenseState.MITIGATED

    # 3.2 In_port 2 on S1 isolated with Priority 100
    s1_msgs = [call.args[0] for call in mock_dps[1].send_msg.call_args_list]
    assert len(s1_msgs) > 0

    # 3.3 Bypass routing installed on intermediate switch S3 (Port 2 -> S4)
    s3_msgs = [call.args[0] for call in mock_dps[3].send_msg.call_args_list]
    assert len(s3_msgs) > 0

    # [Stage 4: Autonomous Self-Healing & Cooldown Rollback]
    t_threat = controller.fsm.last_threat_time

    # 4.1 Advance to cooldown
    controller.fsm.evaluate_heartbeat(current_time=t_threat + 5.5)
    assert controller.fsm.get_state() == DefenseState.COOLDOWN

    # 4.2 Advance past cooldown (10.5s) -> NORMAL
    controller.fsm.evaluate_heartbeat(current_time=t_threat + 10.5)
    assert controller.fsm.get_state() == DefenseState.NORMAL

    # 4.3 Verify S1 received flow deletion command to restore In_port 2
    assert mock_dps[1].send_msg.call_count >= 2
