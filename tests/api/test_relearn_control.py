"""Special-situation relearn approval: POST /api/control/relearn → RELEARN command for the AI worker."""

import json

import fakeredis
import fakeredis.aioredis
import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.manual_control import ManualControlRejected, RelearnRequest, build_relearn_command
from harness.contracts import REDIS_CHANNEL_CONTROL_COMMAND

APPROVE_ALL = {"minutes": 30, "reason": "수강신청 기간 트래픽 증가 확인"}


def test_relearn_command_for_every_port_or_one_access_port():
    cmd = build_relearn_command(RelearnRequest(**APPROVE_ALL, operator="kim"))
    assert (cmd.action, cmd.target_dpid, cmd.target_port, cmd.duration_sec) == ("RELEARN", 0, 0, 1800.0)
    assert cmd.command_id.startswith("manual-relearn-") and cmd.reason.startswith("[MANUAL] kim:")
    one = build_relearn_command(RelearnRequest(**APPROVE_ALL, dpid=1, port=2))
    assert (one.target_dpid, one.target_port) == (1, 2)
    with pytest.raises(ManualControlRejected):
        build_relearn_command(RelearnRequest(**APPROVE_ALL, dpid=1, port=3))  # S1:3 is a trunk port


@pytest.mark.parametrize("payload", [
    {**APPROVE_ALL, "minutes": 0},
    {**APPROVE_ALL, "minutes": 241},  # at most 4 hours per approval
    {"minutes": 30, "reason": ""},
])
def test_bad_relearn_requests_are_refused(payload):
    with TestClient(create_app(enable_mock=True, start_source=False)) as client:
        assert client.post("/api/control/relearn", json=payload).status_code == 422


def test_relearn_is_published_and_token_enforced(monkeypatch):
    server = fakeredis.FakeServer()
    pubsub = fakeredis.FakeRedis(server=server).pubsub()
    pubsub.subscribe(REDIS_CHANNEL_CONTROL_COMMAND)
    pubsub.get_message(timeout=1)
    monkeypatch.setenv("SDN_ADMIN_TOKEN", "s3cret")
    app = create_app(enable_mock=False, start_source=False,
                     redis_factory=lambda: fakeredis.aioredis.FakeRedis(server=server))
    with TestClient(app) as client:
        assert client.post("/api/control/relearn", json=APPROVE_ALL).status_code == 401
        res = client.post("/api/control/relearn", json=APPROVE_ALL, headers={"X-Admin-Token": "s3cret"})
    assert res.status_code == 200 and res.json()["delivered_to"] == "redis"
    data = json.loads(pubsub.get_message(timeout=1)["data"])
    assert data["action"] == "RELEARN" and data["duration_sec"] == 1800.0
