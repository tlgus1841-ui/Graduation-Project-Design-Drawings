"""
Self-Defending SDN Tower: Autonomous Self-Healing FSM (Anti-Flapping Engine).
Author: Sihyeon Park (22101489 / Tech Lead)
Phase 4 (Week 11) Milestone

State transitions:
NORMAL -> ATTACK_DETECTED -> MITIGATED -> COOLDOWN -> NORMAL
Prevents route flapping caused by simple timeout drops and guarantees
seamless rollback when attack traffic terminates.
"""

import time
from enum import Enum
from typing import Callable, Dict, Optional


class DefenseState(str, Enum):
    NORMAL = "NORMAL"
    ATTACK_DETECTED = "ATTACK_DETECTED"
    MITIGATED = "MITIGATED"
    COOLDOWN = "COOLDOWN_VERIFY"
    COOLDOWN_VERIFY = "COOLDOWN_VERIFY"


class FlappingFSM:
    """
    명시적 상태 전이 머신:
    - 공격 감지 시 MITIGATED 전환 및 차단/우회
    - 공격 트래픽 지속 시 Cooldown 타이머 리셋 (Heartbeat 유지)
    - 공격 소멸 후 지정된 cooldown_sec 경과 시 자동 무개입 복구 (NORMAL 롤백)
    """

    def __init__(
        self,
        cooldown_sec: float = 10.0,
        on_state_change: Optional[Callable[[DefenseState, DefenseState, Dict], None]] = None,
    ):
        self.state = DefenseState.NORMAL
        self.cooldown_sec = cooldown_sec
        self.on_state_change = on_state_change

        self.last_threat_time = 0.0
        self.last_state_change_time = time.time()
        self.mitigated_targets: Dict[str, Dict] = {}  # key: f"{dpid}:{in_port}"

    def get_state(self) -> DefenseState:
        return self.state

    def trigger_anomaly(self, dpid: int, in_port: int, threat_info: Optional[Dict] = None):
        """AI Worker로부터 이상 트래픽 경보가 수신되었을 때 호출"""
        now = time.time()
        self.last_threat_time = now
        key = f"{dpid}:{in_port}"
        self.mitigated_targets[key] = {
            "dpid": dpid,
            "in_port": in_port,
            "threat_info": threat_info or {},
            "timestamp": now,
        }

        prev = self.state
        if self.state in (DefenseState.NORMAL, DefenseState.COOLDOWN):
            self.state = DefenseState.MITIGATED
            self.last_state_change_time = now
            if self.on_state_change:
                self.on_state_change(prev, self.state, {"target": key, "action": "ISOLATE"})
        elif self.state == DefenseState.MITIGATED:
            # Heartbeat 유지 (수명 연장)
            pass

    def evaluate_heartbeat(self, current_time: Optional[float] = None) -> Optional[DefenseState]:
        """
        주기적으로 호출(예: 매 1~2초)되어 쿨다운 만료 여부를 판정하고 상태를 전이시킴.
        """
        now = current_time if current_time is not None else time.time()
        elapsed_since_threat = now - self.last_threat_time
        prev = self.state

        if self.state == DefenseState.MITIGATED:
            if elapsed_since_threat >= self.cooldown_sec:
                # 위협 소멸 후 풀 쿨다운 경과 시 바로 NORMAL 복귀
                self.state = DefenseState.NORMAL
                self.last_state_change_time = now
                cleared_targets = dict(self.mitigated_targets)
                self.mitigated_targets.clear()
                if self.on_state_change:
                    self.on_state_change(
                        prev, self.state, {"cleared_targets": cleared_targets, "action": "RESTORE"}
                    )
                return self.state
            elif elapsed_since_threat >= self.cooldown_sec / 2.0:
                # 위협 수신이 잠잠해지면 COOLDOWN 진입
                self.state = DefenseState.COOLDOWN
                self.last_state_change_time = now
                if self.on_state_change:
                    self.on_state_change(prev, self.state, {"elapsed": elapsed_since_threat})
                return self.state

        elif self.state == DefenseState.COOLDOWN:
            if elapsed_since_threat >= self.cooldown_sec:
                # 완전 쿨다운 완료 -> NORMAL 복귀 (차단 룰 제거 및 정상 경로 롤백)
                self.state = DefenseState.NORMAL
                self.last_state_change_time = now
                cleared_targets = dict(self.mitigated_targets)
                self.mitigated_targets.clear()
                if self.on_state_change:
                    self.on_state_change(
                        prev, self.state, {"cleared_targets": cleared_targets, "action": "RESTORE"}
                    )
                return self.state

        return self.state

    def force_restore(self):
        """관리자 수동 강제 복구 또는 서킷 브레이커 트리거 시 호출"""
        prev = self.state
        self.state = DefenseState.NORMAL
        self.last_threat_time = 0.0
        self.last_state_change_time = time.time()
        cleared_targets = dict(self.mitigated_targets)
        self.mitigated_targets.clear()
        if self.on_state_change:
            self.on_state_change(
                prev, self.state, {"action": "FORCE_RESTORE", "targets": cleared_targets}
            )
