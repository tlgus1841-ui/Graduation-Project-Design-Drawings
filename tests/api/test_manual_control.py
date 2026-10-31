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
from harness.contracts import MANUAL_RESTORE_HOLD_SEC, REDIS_CHANNEL_CONTROL_COMMAND

ISOLATE_ATTACKER = {"action": "ISOLATE", "dpid": 3, "port": 2, "reason": "AI 오탐 의심, 수동 격리"}


@pytest.fixture
def mock_client():
    with TestClient(create_app(enable_mock=True, start_source=False)) as client:
        yield client


def test_build_manual_command_marks_it_manual():
    cmd = build_manual_command(ManualControlRequest(**ISOLATE_ATTACKER, operator="김관우"))
    assert cmd.action == "ISOLATE" and (cmd.target_dpid, cmd.target_port) == (3, 2)
    assert cmd.reason.startswith("[MANUAL] 김관우:")
    assert cmd.command_id.startswith("manual-isolate-")
    assert cmd.priority == 100


@pytest.mark.parametrize("dpid,port", [(1, 1), (1, 2), (3, 99)])
def test_trunk_ports_are_never_manually_controllable(dpid, port):
    with pytest.raises(ManualControlRejected):
        build_manual_command(ManualControlRequest(action="ISOLATE", dpid=dpid, port=port, reason="test"))


@pytest.mark.parametrize("dpid,port", [(5, 1), (7, 1)])  # h5 Web, h_admin
def test_protected_host_ports_cannot_be_manually_isolated(dpid, port):
    """관리자가 포트 번호를 잘못 입력해도 h5 Web/h_admin은 수동으로 격리할 수 없다."""
    with pytest.raises(ManualControlRejected):
        build_manual_command(ManualControlRequest(action="ISOLATE", dpid=dpid, port=port, reason="test"))


@pytest.mark.parametrize("dpid,port", [(5, 1), (7, 1)])
def test_protected_host_ports_can_still_be_manually_restored(dpid, port):
    """RESTORE는 격리가 아니므로 보호 포트 체크 대상이 아니다."""
    cmd = build_manual_command(ManualControlRequest(action="RESTORE", dpid=dpid, port=port, reason="test"))
    assert cmd.action == "RESTORE"


def test_manual_isolate_is_broadcast_to_dashboards(mock_client):
    with mock_client.websocket_connect("/ws") as ws:
        ws.receive_json()  # initial topology
        ws.receive_json()  # initial status
        res = mock_client.post("/api/control/manual", json=ISOLATE_ATTACKER)
        assert res.status_code == 200
        body = res.json()
        assert body["accepted"] is True and body["delivered_to"] == "mock"
        assert body["auto_isolation_hold_sec"] == 0  # no controller in mock mode, so no hold
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
        isolate = client.post("/api/control/manual", json=ISOLATE_ATTACKER)
    assert res.status_code == 200
    assert res.json()["delivered_to"] == "redis"
    # The controller holds auto re-isolation after a manual restore; the UI shows how long.
    assert res.json()["auto_isolation_hold_sec"] == MANUAL_RESTORE_HOLD_SEC
    assert isolate.json()["auto_isolation_hold_sec"] == 0
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


def test_quarantine_release_endpoint(mock_client):
    # Unknown host rejected
    res_bad = mock_client.post("/api/control/quarantine/release", json={
        "target_ip": "10.0.0.99",
        "reason": "Host scan completed",
    })
    assert res_bad.status_code == 409

    # Valid release for 10.0.0.2
    res_ok = mock_client.post("/api/control/quarantine/release", json={
        "target_ip": "10.0.0.2",
        "reason": "Host scan and patch completed",
        "operator": "security_admin",
    })
    assert res_ok.status_code == 200
    body = res_ok.json()
    assert body["accepted"] is True
    assert body["command"]["action"] == "RELEASE"
    assert body["command"]["target_ip"] == "10.0.0.2"
    assert "[MANUAL] security_admin:" in body["command"]["reason"]


def test_quarantine_list_endpoint(mock_client):
    res = mock_client.get("/api/control/quarantine/list")
    assert res.status_code == 200
    assert "count" in res.json()
    assert "hosts" in res.json()
