"""Operator emergency manual control (week 13): validate a manual ISOLATE/RESTORE request and
turn it into the same ControlCommandMessage the autonomous FSM publishes.

Guardrails:
- only ISOLATE and RESTORE (REROUTE stays automatic);
- only known access ports — trunk ports (switch-to-switch) are never isolatable, the same rule
  as the mock generator and the spec's whitelist guard;
- a reason is mandatory so every manual action is traceable in the event feed.
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field

from api.mock_generator import SWITCH_PORTS, is_trunk_port
from harness.contracts import ControlCommandMessage, DefenseAction

MANUAL_PRIORITY = 100
MANUAL_PREFIX = "[MANUAL]"


class ManualControlRequest(BaseModel):
    action: Literal["ISOLATE", "RESTORE"]
    dpid: int = Field(..., ge=1)
    port: int = Field(..., ge=1)
    reason: str = Field(..., min_length=3, max_length=200)
    operator: str = Field("admin", min_length=1, max_length=40)


class ManualControlRejected(ValueError):
    """Request is well-formed but not allowed (unknown or trunk port)."""


def build_manual_command(req: ManualControlRequest) -> ControlCommandMessage:
    if req.port not in SWITCH_PORTS.get(req.dpid, []):
        raise ManualControlRejected(f"S{req.dpid}:{req.port} 는 존재하지 않는 포트입니다.")
    if is_trunk_port(req.dpid, req.port):
        raise ManualControlRejected(f"S{req.dpid}:{req.port} 는 스위치 간 트렁크 포트라 수동 제어할 수 없습니다.")
    return ControlCommandMessage(
        command_id=f"manual-{req.action.lower()}-{uuid.uuid4().hex[:8]}",
        action=DefenseAction(req.action).value,
        target_dpid=req.dpid,
        target_port=req.port,
        reason=f"{MANUAL_PREFIX} {req.operator}: {req.reason.strip()}",
        priority=MANUAL_PRIORITY,
    )
