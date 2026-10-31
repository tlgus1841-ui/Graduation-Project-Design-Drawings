"""Operator emergency manual control (week 13): validate a manual ISOLATE/RESTORE request and
turn it into the same ControlCommandMessage the autonomous FSM publishes.

Guardrails:
- only ISOLATE and RESTORE (REROUTE stays automatic);
- only known access ports — trunk ports (switch-to-switch) are never isolatable, the same rule
  as the mock generator and the spec's whitelist guard;
- a reason is mandatory so every manual action is traceable in the event feed.

Special-situation relearn (RELEARN): the operator approves, for a set period, that a real rise in traffic
(course registration, an event) becomes the new normal. The AI worker relearns traffic volume for that
period and returns to the pre-learned baseline afterwards; the controller ignores the command.
"""

from __future__ import annotations

import uuid
from typing import Literal, Optional

from pydantic import BaseModel, Field

from api.mock_generator import SWITCH_PORTS, is_trunk_port
from harness.contracts import ACCESS_HOST_PORTS, ControlCommandMessage, DefenseAction
from harness.safety.whitelist_guard import DEFAULT_PROTECTED_ACCESS_PORTS

MANUAL_PRIORITY = 100
MANUAL_PREFIX = "[MANUAL]"
RELEARN_MAX_MINUTES = 240
PROTECTED_ACCESS_PORTS = DEFAULT_PROTECTED_ACCESS_PORTS


class ManualControlRequest(BaseModel):
    action: Literal["ISOLATE", "RESTORE"]
    dpid: int = Field(..., ge=1)
    port: int = Field(..., ge=1)
    reason: str = Field(..., min_length=3, max_length=200)
    operator: str = Field("admin", min_length=1, max_length=40)


class RelearnRequest(BaseModel):
    minutes: int = Field(..., ge=1, le=RELEARN_MAX_MINUTES, description="Approved relearning period")
    dpid: int = Field(0, ge=0, description="0 with port 0 = every watched access port")
    port: int = Field(0, ge=0)
    reason: str = Field(..., min_length=3, max_length=200)
    operator: str = Field("admin", min_length=1, max_length=40)


class QuarantineReleaseRequest(BaseModel):
    target_ip: str = Field(..., description="Release target host IP (e.g. 10.0.0.2)")
    reason: str = Field(..., min_length=3, max_length=200, description="Mandatory audit justification")
    operator: str = Field("admin", min_length=1, max_length=40)


class ManualControlRejected(ValueError):
    """Request is well-formed but not allowed (unknown, trunk, or protected host port)."""


def build_manual_command(req: ManualControlRequest) -> ControlCommandMessage:
    if req.port not in SWITCH_PORTS.get(req.dpid, []):
        raise ManualControlRejected(f"S{req.dpid}:{req.port} 는 존재하지 않는 포트입니다.")
    if is_trunk_port(req.dpid, req.port):
        raise ManualControlRejected(f"S{req.dpid}:{req.port} 는 스위치 간 트렁크 포트라 수동 제어할 수 없습니다.")
    if req.action == "ISOLATE" and req.port in PROTECTED_ACCESS_PORTS.get(req.dpid, []):
        raise ManualControlRejected(f"S{req.dpid}:{req.port} 는 보호 호스트 포트라 격리할 수 없습니다.")
    return ControlCommandMessage(
        command_id=f"manual-{req.action.lower()}-{uuid.uuid4().hex[:8]}",
        action=DefenseAction(req.action).value,
        target_dpid=req.dpid,
        target_port=req.port,
        reason=f"{MANUAL_PREFIX} {req.operator}: {req.reason.strip()}",
        priority=MANUAL_PRIORITY,
    )


def build_relearn_command(req: RelearnRequest) -> ControlCommandMessage:
    if req.port and (req.port not in SWITCH_PORTS.get(req.dpid, []) or is_trunk_port(req.dpid, req.port)):
        raise ManualControlRejected(f"S{req.dpid}:{req.port} 는 접속 포트가 아니라 재학습할 수 없습니다.")
    return ControlCommandMessage(
        command_id=f"manual-relearn-{uuid.uuid4().hex[:8]}",
        action=DefenseAction.RELEARN.value,
        target_dpid=req.dpid if req.port else 0,
        target_port=req.port,
        reason=f"{MANUAL_PREFIX} {req.operator}: {req.reason.strip()} ({req.minutes}분 재학습 승인)",
        priority=0,
        duration_sec=req.minutes * 60.0,
    )


def build_quarantine_release_command(
    req: QuarantineReleaseRequest, host_ports: Optional[dict] = None
) -> ControlCommandMessage:
    hp = host_ports or ACCESS_HOST_PORTS
    if req.target_ip not in hp:
        raise ManualControlRejected(f"{req.target_ip} 는 등록된 호스트가 아닙니다.")
    dpid, port = hp[req.target_ip]
    return ControlCommandMessage(
        command_id=f"manual-release-{uuid.uuid4().hex[:8]}",
        action=DefenseAction.RELEASE.value,
        target_dpid=dpid,
        target_port=port,
        reason=f"{MANUAL_PREFIX} {req.operator}: {req.reason.strip()}",
        priority=MANUAL_PRIORITY,
        target_ip=req.target_ip,
    )
