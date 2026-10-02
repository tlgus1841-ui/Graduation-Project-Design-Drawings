"""
Redis -> WebSocket Bridge Test Harness
Author: Gwanwoo Kim (22102237 / PM & Tech Writer)
Phase 2 (Week 6) Milestone

Uses fakeredis, so no Redis server, Ryu or AI Worker is needed:
- contract validation (valid relayed, malformed / wrong-schema dropped)
- provisional FSM phase inference (spec §8 Q3)
- live subscription loop relays published messages to WebSocket clients
- FastAPI live mode reports Redis status
"""

import asyncio
import json
from typing import Any, List

import fakeredis
import fakeredis.aioredis
from fastapi.testclient import TestClient

from api.main import create_app
from api.mock_generator import SYSTEM_STATUS_TYPE, MockTelemetryGenerator, Phase
from api.redis_bridge import RedisBridge
from api.websocket_hub import ConnectionManager
from harness.contracts import (
    REDIS_CHANNEL_ANOMALY_ALERT,
    REDIS_CHANNEL_CONTROL_COMMAND,
    REDIS_CHANNEL_PORT_STATS,
    REDIS_CHANNEL_TOPOLOGY_SYNC,
    AnomalyAlertMessage,
    ControlCommandMessage,
    PortStatItem,
    PortStatsMessage,
)


class FakeWebSocket:
    def __init__(self) -> None:
        self.sent: List[Any] = []

    async def send_json(self, data: Any, mode: str = "text") -> None:
        self.sent.append(data)


def port_stats_json() -> str:
    item = PortStatItem(dpid=1, port_no=2, rx_packets=100, tx_packets=0, rx_bytes=6400,
                        tx_bytes=0, rx_errors=0, duration_sec=4)
    return PortStatsMessage(dpid=1, stats=[item]).model_dump_json()


def alert_json() -> str:
    return AnomalyAlertMessage(dpid=1, in_port=2, threat_type="SYN_FLOOD_SPOOFING", score=-0.8,
                               pps=3000.0, bps=192000.0, bpp=64.0, metadata={}).model_dump_json()


def command_json(action: str) -> str:
    return ControlCommandMessage(command_id=f"cmd-{action}", action=action, target_dpid=1,
                                 target_port=2, reason="test", priority=100).model_dump_json()


# =====================================================================
# Test Suite 1: validation and relay envelopes
# =====================================================================
def test_valid_payload_is_relayed_as_envelope():
    bridge = RedisBridge()
    envelopes = bridge.handle_message(REDIS_CHANNEL_PORT_STATS, port_stats_json().encode())
    assert envelopes[0]["type"] == REDIS_CHANNEL_PORT_STATS
    PortStatsMessage.model_validate(envelopes[0]["data"])
    assert bridge.dropped == 0


def test_malformed_and_wrong_schema_payloads_are_dropped():
    bridge = RedisBridge()
    assert bridge.handle_message(REDIS_CHANNEL_PORT_STATS, b"{not json") == []
    # Ryu-style payload with a misspelled field must not reach browsers
    wrong = json.dumps({"timestamp": 1.0, "dpid": 1, "stats": [{"dpid": 1, "port": 2}]})
    assert bridge.handle_message(REDIS_CHANNEL_PORT_STATS, wrong) == []
    assert bridge.handle_message("sdn:unknown", port_stats_json()) == []
    assert (bridge.received, bridge.dropped) == (3, 3)


def test_topology_sync_updates_snapshot():
    bridge = RedisBridge()
    assert {n.id for n in bridge.topology_snapshot().nodes} >= {"s1", "h_server"}  # static fallback
    topo = MockTelemetryGenerator().topology_snapshot(Phase.MITIGATED).model_dump_json()
    bridge.handle_message(REDIS_CHANNEL_TOPOLOGY_SYNC, topo)
    assert next(n for n in bridge.topology_snapshot().nodes if n.id == "s1").status == "MITIGATED"


# =====================================================================
# Test Suite 2: provisional phase inference
# =====================================================================
def test_phase_follows_alert_isolate_restore():
    bridge = RedisBridge()
    phases = []
    for channel, raw in [
        (REDIS_CHANNEL_PORT_STATS, port_stats_json()),
        (REDIS_CHANNEL_ANOMALY_ALERT, alert_json()),
        (REDIS_CHANNEL_CONTROL_COMMAND, command_json("ISOLATE")),
        (REDIS_CHANNEL_ANOMALY_ALERT, alert_json()),  # attack continues while mitigated
        (REDIS_CHANNEL_CONTROL_COMMAND, command_json("RESTORE")),
    ]:
        for env in bridge.handle_message(channel, raw):
            if env["type"] == SYSTEM_STATUS_TYPE:
                phases.append(env["data"]["phase"])
    assert phases == ["NORMAL", "ATTACK_DETECTED", "MITIGATED", "NORMAL"]


# =====================================================================
# Test Suite 3: live subscription loop (fakeredis)
# =====================================================================
def test_run_relays_published_messages_to_clients():
    async def scenario() -> None:
        server = fakeredis.FakeServer()
        bridge = RedisBridge(redis_factory=lambda: fakeredis.aioredis.FakeRedis(server=server))
        hub = ConnectionManager()
        ws = FakeWebSocket()
        await hub.register(ws)
        task = asyncio.create_task(bridge.run(hub))
        for _ in range(50):
            if bridge.connected:
                break
            await asyncio.sleep(0.02)
        assert bridge.connected

        publisher = fakeredis.aioredis.FakeRedis(server=server)
        await publisher.publish(REDIS_CHANNEL_ANOMALY_ALERT, alert_json())
        await publisher.publish(REDIS_CHANNEL_PORT_STATS, b"garbage")
        for _ in range(50):
            if any(m["type"] == REDIS_CHANNEL_ANOMALY_ALERT for m in ws.sent) and bridge.received == 2:
                break
            await asyncio.sleep(0.02)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

        types = [m["type"] for m in ws.sent]
        assert REDIS_CHANNEL_ANOMALY_ALERT in types
        assert REDIS_CHANNEL_PORT_STATS not in types  # garbage dropped
        assert ws.sent[0]["data"]["upstream"] == "connected"
        assert bridge.dropped == 1

    asyncio.run(scenario())


def test_live_mode_health_reports_redis_status():
    server = fakeredis.FakeServer()
    app = create_app(enable_mock=False, start_source=False,
                     redis_factory=lambda: fakeredis.aioredis.FakeRedis(server=server))
    with TestClient(app) as client:
        body = client.get("/api/health").json()
        assert body["mode"] == "live"
        assert body["redis"] == {"connected": False, "received": 0, "dropped": 0}
        with client.websocket_connect("/ws") as ws:
            assert ws.receive_json()["type"] == REDIS_CHANNEL_TOPOLOGY_SYNC
            status = ws.receive_json()
            assert status["data"]["mode"] == "live" and status["data"]["upstream"] == "disconnected"
