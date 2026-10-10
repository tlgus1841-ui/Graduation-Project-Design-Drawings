"""
E2E Multi-Module Pipeline Integration Test (Week 8).
Author: Sihyeon Park (22101489 / Tech Lead)
Phase 3 Milestone

Simulates the end-to-end telemetry and alert pipeline:
Ryu PortStats -> Redis Bus -> Mock AI Inference -> Redis Alert -> Controller Autonomous Mitigation -> FSM
"""

from unittest.mock import MagicMock
import fakeredis
from harness.contracts.sdn_events import (
    REDIS_CHANNEL_ANOMALY_ALERT,
    REDIS_CHANNEL_PORT_STATS,
    AnomalyAlertMessage,
    PortStatItem,
    PortStatsMessage,
    ThreatType,
)
from harness.safety.flapping_fsm import DefenseState
from tests.ryu.test_telemetry import _setup_and_load_controller_for_telemetry


def test_e2e_telemetry_to_mitigation_pipeline():
    """
    Test E2E flow:
    1. PortStatsMessage published to Redis
    2. Simulated AI worker detects SYN Flood anomaly
    3. AnomalyAlertMessage received by Controller
    4. Controller executes In_port Drop, triggers Reroute, and FSM enters MITIGATED
    """
    fake_server = fakeredis.FakeServer()
    redis_client = fakeredis.FakeRedis(server=fake_server, decode_responses=True)

    ControllerCls = _setup_and_load_controller_for_telemetry()
    controller = ControllerCls()
    controller.redis_client = redis_client

    # Register switches S1, S2, S3, S4
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

    # Step 1: Telemetry publication
    stats_msg = PortStatsMessage(
        dpid=1,
        stats=[
            PortStatItem(
                dpid=1,
                port_no=2,
                rx_packets=5000,
                tx_packets=10,
                rx_bytes=320000,
                tx_bytes=640,
                rx_errors=0,
                duration_sec=2,
            )
        ],
    )
    redis_client.publish(REDIS_CHANNEL_PORT_STATS, stats_msg.model_dump_json())

    # Step 2: AI detects anomaly and publishes alert
    alert = AnomalyAlertMessage(
        dpid=1,
        in_port=2,
        threat_type=ThreatType.SYN_FLOOD_SPOOFING.value,
        score=-0.91,
        pps=2500.0,
        bps=160000.0,
        bpp=64.0,
    )
    alert_json = alert.model_dump_json()

    # Step 3: Controller handles alert message
    controller._handle_redis_message(REDIS_CHANNEL_ANOMALY_ALERT, alert_json)

    # Step 4: Verify defenses applied
    # 4.1 In_port 2 dropped on S1
    assert mock_dps[1].send_msg.called
    # 4.2 FSM transitioned to MITIGATED
    assert controller.fsm.get_state() == DefenseState.MITIGATED

    # Step 5: Advance heartbeat past cooldown to verify automatic self-healing
    t_end = controller.fsm.last_threat_time + 11.0
    controller.fsm.evaluate_heartbeat(current_time=t_end)
    assert controller.fsm.get_state() == DefenseState.NORMAL
