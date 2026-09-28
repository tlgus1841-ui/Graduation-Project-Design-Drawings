"""
Mock IPC Bus and Pydantic Contract Test Harness
Author: Sihyeon Park (22101489 / Tech Lead)
Phase 2 (Week 4) Milestone

Ensures 100% serialization integrity, schema validation, and bus pub/sub delivery
without requiring Mininet, Ryu controller, or a live Redis instance.
"""

import json
import queue
import time
import uuid
from typing import Callable, Dict, List
import pytest
from pydantic import ValidationError

from harness.contracts import (
    REDIS_CHANNEL_ANOMALY_ALERT,
    REDIS_CHANNEL_CONTROL_COMMAND,
    REDIS_CHANNEL_PORT_STATS,
    REDIS_CHANNEL_TOPOLOGY_SYNC,
    AnomalyAlertMessage,
    ControlCommandMessage,
    DefenseAction,
    PortStatItem,
    PortStatsMessage,
    ThreatType,
    TopologyLink,
    TopologyNode,
    TopologySyncMessage,
)


class MockRedisBus:
    """
    In-memory mock Redis Pub/Sub event bus.
    Enables instant (<0.1s) testing of IPC channels and consumer pipelines.
    """

    def __init__(self):
        self._subscribers: Dict[str, List[queue.Queue]] = {}

    def subscribe(self, channel: str) -> queue.Queue:
        """Register a subscriber queue for a specific channel."""
        q = queue.Queue()
        if channel not in self._subscribers:
            self._subscribers[channel] = []
        self._subscribers[channel].append(q)
        return q

    def publish(self, channel: str, message: str) -> int:
        """Deliver payload to all active subscriber queues on the channel."""
        if channel not in self._subscribers:
            return 0
        delivered = 0
        for q in self._subscribers[channel]:
            q.put(message)
            delivered += 1
        return delivered

    def clear(self):
        self._subscribers.clear()


@pytest.fixture
def mock_bus():
    """Provides a clean in-memory Redis event bus for each test."""
    bus = MockRedisBus()
    yield bus
    bus.clear()


# =====================================================================
# Test Suite 1: PortStatsMessage (Ryu -> AI / Web)
# =====================================================================
def test_port_stats_serialization():
    """Verify that Ryu port statistics serialize and deserialize with 100% fidelity."""
    stats = [
        PortStatItem(
            dpid=1,
            port_no=1,
            rx_packets=1250,
            tx_packets=1200,
            rx_bytes=102400,
            tx_bytes=98000,
            rx_errors=0,
            duration_sec=30,
        ),
        PortStatItem(
            dpid=1,
            port_no=2,
            rx_packets=50000,
            tx_packets=50,
            rx_bytes=3200000,
            tx_bytes=4000,
            rx_errors=0,
            duration_sec=30,
        ),
    ]
    message = PortStatsMessage(dpid=1, stats=stats)

    # Serialize to JSON string
    raw_json = message.model_dump_json()
    assert isinstance(raw_json, str)

    # Deserialize back into Pydantic model
    recovered = PortStatsMessage.model_validate_json(raw_json)
    assert recovered.dpid == 1
    assert len(recovered.stats) == 2
    assert recovered.stats[1].port_no == 2
    assert recovered.stats[1].rx_packets == 50000
    assert abs(recovered.timestamp - time.time()) < 5.0


def test_port_stats_invalid_types_rejected():
    """Ensure invalid port stats trigger ValidationError."""
    with pytest.raises(ValidationError):
        # Missing required port_no and duration_sec
        PortStatItem(dpid=1, rx_packets=10, tx_packets=10, rx_bytes=100, tx_bytes=100)


# =====================================================================
# Test Suite 2: AnomalyAlertMessage (AI Worker -> Ryu / Web)
# =====================================================================
def test_anomaly_alert_validation():
    """Verify that AI Worker anomaly alert correctly validates and serializes."""
    alert = AnomalyAlertMessage(
        dpid=1,
        in_port=2,
        threat_type=ThreatType.SYN_FLOOD_SPOOFING.value,
        score=-0.785,
        pps=4820.5,
        bps=3085120.0,
        bpp=64.0,
        metadata={"model": "IsolationForest-v1", "threshold": "-0.50"},
    )

    raw_json = alert.model_dump_json()
    recovered = AnomalyAlertMessage.model_validate_json(raw_json)

    assert recovered.dpid == 1
    assert recovered.in_port == 2
    assert recovered.threat_type == "SYN_FLOOD_SPOOFING"
    assert recovered.score == -0.785
    assert recovered.pps == 4820.5
    assert recovered.metadata["model"] == "IsolationForest-v1"


def test_anomaly_alert_missing_fields_rejected():
    """Ensure omission of critical AI features (score, pps, etc.) raises ValidationError."""
    with pytest.raises(ValidationError):
        # Missing pps, bps, bpp
        AnomalyAlertMessage(dpid=1, in_port=2, score=-0.6)


# =====================================================================
# Test Suite 3: ControlCommandMessage (AI/Web -> Ryu)
# =====================================================================
def test_control_command_actions():
    """Verify control command structures for autonomous defense and restoration."""
    cmd_id = str(uuid.uuid4())
    cmd = ControlCommandMessage(
        command_id=cmd_id,
        action=DefenseAction.ISOLATE.value,
        target_dpid=1,
        target_port=2,
        reason="Autonomous mitigation: SYN Flood detected on Ingress Port 2",
        priority=100,
    )

    raw_json = cmd.model_dump_json()
    recovered = ControlCommandMessage.model_validate_json(raw_json)

    assert recovered.command_id == cmd_id
    assert recovered.action == "ISOLATE"
    assert recovered.target_dpid == 1
    assert recovered.target_port == 2
    assert recovered.priority == 100


# =====================================================================
# Test Suite 4: TopologySyncMessage (Ryu -> Web UI)
# =====================================================================
def test_topology_sync_message():
    """Verify topology synchronization message schema."""
    nodes = [
        TopologyNode(id="s1", label="Switch 1 (Ingress)", node_type="switch", dpid=1, status="ATTACKED"),
        TopologyNode(id="h_legit", label="Host Legit", node_type="host", ip="10.0.0.1", mac="00:00:00:00:00:01"),
    ]
    links = [
        TopologyLink(source="s1", target="h_legit", src_port=1, dst_port=1, is_trunk=False, status="ACTIVE"),
        TopologyLink(source="s1", target="s2", src_port=3, dst_port=1, is_trunk=True, status="ACTIVE"),
    ]
    topo_msg = TopologySyncMessage(nodes=nodes, links=links)

    raw_json = topo_msg.model_dump_json()
    recovered = TopologySyncMessage.model_validate_json(raw_json)

    assert len(recovered.nodes) == 2
    assert recovered.nodes[0].status == "ATTACKED"
    assert len(recovered.links) == 2
    assert recovered.links[1].is_trunk is True


# =====================================================================
# Test Suite 5: Mock Pub/Sub Pipeline Integration
# =====================================================================
def test_mock_pubsub_pipeline(mock_bus):
    """
    Simulate end-to-end communication via MockRedisBus:
    1. Ryu Controller subscribes to 'sdn:control:command'
    2. AI Worker publishes AnomalyAlert to 'sdn:anomaly:alert'
    3. Defense engine triggers ControlCommand to 'sdn:control:command'
    4. Ryu consumer validates and receives command without data corruption.
    """
    # Ryu subscribes to control commands
    ryu_command_sub = mock_bus.subscribe(REDIS_CHANNEL_CONTROL_COMMAND)
    # Web dashboard subscribes to anomaly alerts
    web_alert_sub = mock_bus.subscribe(REDIS_CHANNEL_ANOMALY_ALERT)

    # 1. AI Worker produces alert
    alert = AnomalyAlertMessage(
        dpid=1,
        in_port=2,
        threat_type=ThreatType.SYN_FLOOD_SPOOFING.value,
        score=-0.88,
        pps=4950.0,
        bps=3168000.0,
        bpp=64.0,
    )
    recipients = mock_bus.publish(REDIS_CHANNEL_ANOMALY_ALERT, alert.model_dump_json())
    assert recipients == 1

    # Web receives raw message and validates
    web_msg_raw = web_alert_sub.get_nowait()
    web_alert = AnomalyAlertMessage.model_validate_json(web_msg_raw)
    assert web_alert.score == -0.88

    # 2. Defense logic decides to isolate Port 2
    cmd = ControlCommandMessage(
        command_id="cmd-mitigate-001",
        action=DefenseAction.ISOLATE.value,
        target_dpid=web_alert.dpid,
        target_port=web_alert.in_port,
        reason=f"Auto Drop due to {web_alert.threat_type}",
        priority=100,
    )
    recipients = mock_bus.publish(REDIS_CHANNEL_CONTROL_COMMAND, cmd.model_dump_json())
    assert recipients == 1

    # Ryu receives raw command and parses
    ryu_cmd_raw = ryu_command_sub.get_nowait()
    ryu_cmd = ControlCommandMessage.model_validate_json(ryu_cmd_raw)
    assert ryu_cmd.action == "ISOLATE"
    assert ryu_cmd.target_dpid == 1
    assert ryu_cmd.target_port == 2
    assert ryu_cmd.priority == 100


def test_multiple_subscribers_broadcast(mock_bus):
    """Ensure a single PortStats publication reaches multiple subscribers (AI Worker + FastAPI)."""
    ai_sub = mock_bus.subscribe(REDIS_CHANNEL_PORT_STATS)
    web_sub = mock_bus.subscribe(REDIS_CHANNEL_PORT_STATS)

    msg = PortStatsMessage(
        dpid=1,
        stats=[
            PortStatItem(dpid=1, port_no=1, rx_packets=100, tx_packets=90, rx_bytes=8000, tx_bytes=7200, duration_sec=10)
        ],
    )
    recipients = mock_bus.publish(REDIS_CHANNEL_PORT_STATS, msg.model_dump_json())
    assert recipients == 2

    ai_data = PortStatsMessage.model_validate_json(ai_sub.get_nowait())
    web_data = PortStatsMessage.model_validate_json(web_sub.get_nowait())

    assert ai_data.dpid == web_data.dpid == 1
    assert ai_data.stats[0].rx_packets == 100


def test_corrupted_payload_handling(mock_bus):
    """Ensure malformed or non-JSON payloads are safely rejected upon validation."""
    sub = mock_bus.subscribe(REDIS_CHANNEL_ANOMALY_ALERT)
    mock_bus.publish(REDIS_CHANNEL_ANOMALY_ALERT, "{corrupted_json: true,")

    raw = sub.get_nowait()
    with pytest.raises(ValidationError):
        AnomalyAlertMessage.model_validate_json(raw)
