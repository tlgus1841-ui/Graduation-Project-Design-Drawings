"""
Manual Emergency Control Test Harness (week 13)
Author: Gwanwoo Kim (22102237 / PM & Tech Writer)

- valid ISOLATE/RESTORE on access ports is accepted and reaches WebSocket clients (mock mode)
- trunk / unknown ports are refused (409), malformed requests 422
- optional admin token (SDN_ADMIN_TOKEN) is enforced
- live mode publishes to Redis sdn:control:command (fakeredis)
"""

import json

import fakeredis
import fakeredis.aioredis
import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.manual_control import ManualControlRejected, ManualControlRequest, build_manual_command
from harness.contracts import REDIS_CHANNEL_CONTROL_COMMAND

ISOLATE_ATTACKER = {"action": "ISOLATE", "dpid": 1, "port": 2, "reason": "AI 오탐 의심, 수동 격리"}


@pytest.fixture
def mock_client():
    with TestClient(create_app(enable_mock=True, start_source=False)) as client:
        yield client


def test_build_manual_command_marks_it_manual():
    cmd = build_manual_command(ManualControlRequest(**ISOLATE_ATTACKER, operator="김관우"))
    assert cmd.action == "ISOLATE" and (cmd.target_dpid, cmd.target_port) == (1, 2)
    assert cmd.reason.startswith("[MANUAL] 김관우:")
    assert cmd.command_id.startswith("manual-isolate-")
    assert cmd.priority == 100


@pytest.mark.parametrize("dpid,port", [(1, 3), (2, 1), (4, 2)])
def test_trunk_ports_are_never_manually_controllable(dpid, port):
    with pytest.raises(ManualControlRejected):
        build_manual_command(ManualControlRequest(action="ISOLATE", dpid=dpid, port=port, reason="test"))


def test_manual_isolate_is_broadcast_to_dashboards(mock_client):
    with mock_client.websocket_connect("/ws") as ws:
        ws.receive_json()  # initial topology
        ws.receive_json()  # initial status
        res = mock_client.post("/api/control/manual", json=ISOLATE_ATTACKER)
        assert res.status_code == 200
        body = res.json()
        assert body["accepted"] is True and body["delivered_to"] == "mock"
        envelope = ws.receive_json()
    assert envelope["type"] == REDIS_CHANNEL_CONTROL_COMMAND
    assert envelope["data"]["command_id"] == body["command"]["command_id"]
    assert envelope["data"]["reason"].startswith("[MANUAL]")


@pytest.mark.parametrize(
    "payload,status",
    [
        ({**ISOLATE_ATTACKER, "port": 3}, 409),  # S1:3 trunk
        ({**ISOLATE_ATTACKER, "dpid": 9}, 409),  # no such switch
        ({**ISOLATE_ATTACKER, "action": "REROUTE"}, 422),  # rerouting stays automatic
        ({**ISOLATE_ATTACKER, "reason": "x"}, 422),  # reason required
    ],
)
def test_bad_requests_are_refused(mock_client, payload, status):
    assert mock_client.post("/api/control/manual", json=payload).status_code == status


def test_admin_token_is_enforced_when_configured(mock_client, monkeypatch):
    monkeypatch.setenv("SDN_ADMIN_TOKEN", "s3cret")
    assert mock_client.post("/api/control/manual", json=ISOLATE_ATTACKER).status_code == 401
    bad = mock_client.post("/api/control/manual", json=ISOLATE_ATTACKER, headers={"X-Admin-Token": "nope"})
    assert bad.status_code == 401
    ok = mock_client.post("/api/control/manual", json=ISOLATE_ATTACKER, headers={"X-Admin-Token": "s3cret"})
    assert ok.status_code == 200


def test_live_mode_publishes_to_redis_control_channel():
    server = fakeredis.FakeServer()
    sync = fakeredis.FakeRedis(server=server)
    pubsub = sync.pubsub()
    pubsub.subscribe(REDIS_CHANNEL_CONTROL_COMMAND)
    pubsub.get_message(timeout=1)  # subscribe confirmation

    app = create_app(enable_mock=False, start_source=False,
                     redis_factory=lambda: fakeredis.aioredis.FakeRedis(server=server))
    with TestClient(app) as client:
        res = client.post("/api/control/manual", json={**ISOLATE_ATTACKER, "action": "RESTORE"})
    assert res.status_code == 200
    assert res.json()["delivered_to"] == "redis"
    msg = pubsub.get_message(timeout=1)
    assert msg is not None and msg["type"] == "message"
    data = json.loads(msg["data"])
    assert data["action"] == "RESTORE" and data["target_port"] == 2


def test_live_mode_reports_redis_outage():
    def broken():
        raise ConnectionError("redis down")

    app = create_app(enable_mock=False, start_source=False, redis_factory=broken)
    with TestClient(app) as client:
        assert client.post("/api/control/manual", json=ISOLATE_ATTACKER).status_code == 503
