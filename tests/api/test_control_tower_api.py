"""
Control Tower Backend Test Harness (FastAPI + WebSocket Hub + Mock Generator)
Author: Gwanwoo Kim (22102237 / PM & Tech Writer)
Phase 2 (Week 4) Milestone

Runs without Redis, Ryu or a browser:
- WebSocket hub stale-session cleanup (browser F5 / tab close)
- Mock generator follows docs/specs/defense_scenarios.md and emits SSOT-valid payloads
- FastAPI endpoints and /ws initial snapshot
"""

import asyncio
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.mock_generator import (
    SYSTEM_STATUS_TYPE,
    MockTelemetryGenerator,
    Phase,
    is_trunk_port,
)
from api.websocket_hub import ConnectionManager
from harness.contracts import (
    REDIS_CHANNEL_ANOMALY_ALERT,
    REDIS_CHANNEL_CONTROL_COMMAND,
    REDIS_CHANNEL_PORT_STATS,
    REDIS_CHANNEL_TOPOLOGY_SYNC,
    AnomalyAlertMessage,
    ControlCommandMessage,
    PortStatsMessage,
    TopologySyncMessage,
)

CONTRACT_MODELS = {
    REDIS_CHANNEL_PORT_STATS: PortStatsMessage,
    REDIS_CHANNEL_ANOMALY_ALERT: AnomalyAlertMessage,
    REDIS_CHANNEL_CONTROL_COMMAND: ControlCommandMessage,
    REDIS_CHANNEL_TOPOLOGY_SYNC: TopologySyncMessage,
}


class FakeWebSocket:
    """Stand-in for a browser session; `alive=False` simulates a closed tab."""

    def __init__(self, alive: bool = True) -> None:
        self.alive = alive
        self.sent: List[Any] = []

    async def send_json(self, data: Any, mode: str = "text") -> None:
        if not self.alive:
            raise RuntimeError("Unexpected ASGI message 'websocket.send'")
        self.sent.append(data)


def run_cycle(generator: MockTelemetryGenerator, ticks: int) -> List[Dict[str, Any]]:
    envelopes: List[Dict[str, Any]] = []
    for _ in range(ticks):
        for envelope in generator.step():
            envelope["phase"] = generator.phase
            envelopes.append(envelope)
    return envelopes


# =====================================================================
# Test Suite 1: ConnectionManager
# =====================================================================
def test_broadcast_purges_stale_sessions():
    async def scenario() -> None:
        hub = ConnectionManager()
        live, dead = FakeWebSocket(), FakeWebSocket(alive=False)
        await hub.register(live)
        await hub.register(dead)

        delivered = await hub.broadcast({"type": "test", "data": {}})

        assert delivered == 1
        assert hub.count == 1
        assert live.sent == [{"type": "test", "data": {}}]

    asyncio.run(scenario())


def test_disconnect_is_idempotent():
    async def scenario() -> None:
        hub = ConnectionManager()
        ws = FakeWebSocket()
        await hub.register(ws)
        await hub.disconnect(ws)
        await hub.disconnect(ws)
        assert hub.count == 0

    asyncio.run(scenario())


def test_send_to_drops_failed_client():
    async def scenario() -> None:
        hub = ConnectionManager()
        dead = FakeWebSocket(alive=False)
        await hub.register(dead)
        assert await hub.send_to(dead, {"type": "x", "data": {}}) is False
        assert hub.count == 0

    asyncio.run(scenario())


# =====================================================================
# Test Suite 2: Mock scenario generator
# =====================================================================
def test_phase_timeline_matches_spec():
    gen = MockTelemetryGenerator()
    assert gen.phase_at(0) == Phase.CALIBRATING
    assert gen.phase_at(14.9) == Phase.CALIBRATING
    assert gen.phase_at(15) == Phase.NORMAL
    assert gen.phase_at(35) == Phase.ATTACK_DETECTED
    assert gen.phase_at(41) == Phase.MITIGATED
    assert gen.phase_at(61) == Phase.COOLDOWN_VERIFY
    assert gen.phase_at(71) == Phase.NORMAL  # cycle repeats, calibration only once


def test_all_payloads_satisfy_contracts():
    envelopes = run_cycle(MockTelemetryGenerator(), ticks=60)
    for envelope in envelopes:
        model = CONTRACT_MODELS.get(envelope["type"])
        if model is not None:
            model.model_validate(envelope["data"])
        else:
            assert envelope["type"] == SYSTEM_STATUS_TYPE
            assert envelope["data"]["phase"] in {p.value for p in Phase}


def test_alerts_only_while_attack_detected():
    envelopes = run_cycle(MockTelemetryGenerator(), ticks=60)
    alerts = [e for e in envelopes if e["type"] == REDIS_CHANNEL_ANOMALY_ALERT]
    assert alerts
    assert all(e["phase"] == Phase.ATTACK_DETECTED for e in alerts)
    assert all(e["data"]["score"] < -0.5 and e["data"]["bpp"] <= 80 for e in alerts)


def test_no_commands_during_calibration():
    envelopes = run_cycle(MockTelemetryGenerator(), ticks=7)  # 14s < 15s calibration
    assert all(e["type"] != REDIS_CHANNEL_CONTROL_COMMAND for e in envelopes)


def test_defense_command_sequence():
    envelopes = run_cycle(MockTelemetryGenerator(), ticks=60)
    actions = [e["data"]["action"] for e in envelopes if e["type"] == REDIS_CHANNEL_CONTROL_COMMAND]
    # Each cycle repeats REROUTE -> ISOLATE -> RESTORE (the last cycle may be partial)
    pattern = ["REROUTE", "ISOLATE", "RESTORE"]
    assert len(actions) >= 5  # 120s = one full cycle + REROUTE, ISOLATE of the next
    assert actions == (pattern * len(actions))[:len(actions)]


def test_isolate_never_targets_trunk_port():
    envelopes = run_cycle(MockTelemetryGenerator(), ticks=60)
    for e in envelopes:
        if e["type"] == REDIS_CHANNEL_CONTROL_COMMAND and e["data"]["action"] == "ISOLATE":
            assert not is_trunk_port(e["data"]["target_dpid"], e["data"]["target_port"])


def test_attacker_traffic_dropped_at_ingress_when_mitigated():
    gen = MockTelemetryGenerator()
    while gen.phase != Phase.MITIGATED:
        gen.step()

    def s1_counters() -> Dict[int, Any]:
        stats = next(e for e in gen.step() if e["type"] == REDIS_CHANNEL_PORT_STATS)
        return {s["port_no"]: s for s in stats["data"]["stats"]}

    before, after = s1_counters(), s1_counters()
    # Attack keeps arriving on S1:2 but nothing more leaves via the primary trunk S1:3
    assert after[2]["rx_packets"] - before[2]["rx_packets"] > 1000
    assert after[3]["tx_packets"] == before[3]["tx_packets"]
    # H_legit is carried over the bypass trunk S1:4
    assert after[4]["tx_packets"] > before[4]["tx_packets"]


def test_topology_snapshot_reflects_mitigation():
    topo = MockTelemetryGenerator().topology_snapshot(Phase.MITIGATED)
    links = {(link.source, link.target): link.status for link in topo.links}
    assert links[("s1", "h_attacker")] == "BLOCKED"
    assert links[("s1", "s3")] == links[("s3", "s4")] == "REROUTED"
    assert links[("s1", "s2")] == "ACTIVE"


# =====================================================================
# Test Suite 3: FastAPI endpoints
# =====================================================================
@pytest.fixture
def client():
    with TestClient(create_app(enable_mock=False)) as test_client:
        yield test_client


def test_health_endpoint(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["mode"] == "live"
    assert body["active_connections"] == 0


def test_topology_endpoint(client):
    topo = TopologySyncMessage.model_validate(client.get("/api/topology").json())
    assert {node.id for node in topo.nodes} >= {"s1", "s2", "s3", "s4", "h_legit", "h_attacker", "h_server"}


def test_websocket_sends_initial_snapshot(client):
    with client.websocket_connect("/ws") as ws:
        first, second = ws.receive_json(), ws.receive_json()
        assert first["type"] == REDIS_CHANNEL_TOPOLOGY_SYNC
        TopologySyncMessage.model_validate(first["data"])
        assert second["type"] == SYSTEM_STATUS_TYPE
        ws.send_text("ping")
        assert ws.receive_text() == "pong"


def test_repeated_reconnect_leaves_no_stale_sessions(client):
    """Spec V8: simulate browser F5 ten times in a row."""
    for _ in range(10):
        with client.websocket_connect("/ws") as ws:
            ws.receive_json()
            assert client.get("/api/health").json()["active_connections"] == 1
    assert client.get("/api/health").json()["active_connections"] == 0
