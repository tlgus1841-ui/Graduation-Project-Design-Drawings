"""Self-Defending SDN Tower - 공격 소멸 판정 및 쿨다운 플래핑 방지 (AI Worker 측).

주간 계획: docs/writing/reports/weekly/week11_recovery_monitor_plan.md

docs/specs/defense_scenarios.md §2, §3.4의 FSM 중 MITIGATED <-> COOLDOWN_VERIFY
-> NORMAL 구간을 AI Worker 쪽에서 판단한다. 차단/우회 플로우 설치·삭제 자체는
박시현 담당(ryu/app/controller.py, flapping_fsm.py)이며, 이 모듈은 "지금
RESTORE를 요청해도 되는가"만 판단한다.

SCORE_RECOVERY_THRESHOLD 보정 (13주차에 실측으로 수정, model/detection_guard.py
참고): 원래 -0.5였으나, 실제 AnomalyModel의 decision_function() 점수는
공격도 -0.15~-0.05 범위라 "score >= -0.5"가 항상 참이 되어 사실상 아무런
게이트 역할을 못 했다(= PPS 조건 하나만으로 복구를 판단하던 것과 동일).
공격/정상 점수가 0을 기준으로 깨끗이 갈리는 걸 실측으로 확인해 0.0으로
재보정했다.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

ATTACK_CEASE_PPS = 100  # docs/specs/defense_scenarios.md §6
SCORE_RECOVERY_THRESHOLD = 0.0
COOLDOWN_SEC = 10.0


class RecoveryPhase(str, Enum):
    MITIGATED = "MITIGATED"
    COOLDOWN_VERIFY = "COOLDOWN_VERIFY"
    NORMAL = "NORMAL"


def _is_normal(pps: float, score: float) -> bool:
    return pps < ATTACK_CEASE_PPS and score >= SCORE_RECOVERY_THRESHOLD


class RecoveryMonitor:
    """MITIGATED 상태에서 공격 소멸을 감지하고, 쿨다운 동안 재공격 여부를
    지켜봐 플래핑 없이 RESTORE 시점을 판단한다."""

    def __init__(self, cooldown_sec: float = COOLDOWN_SEC) -> None:
        self.cooldown_sec = cooldown_sec
        self.phase = RecoveryPhase.MITIGATED
        self._cooldown_started_at: Optional[float] = None

    def observe(self, pps: float, score: float, now: float) -> RecoveryPhase:
        """최신 PPS/이상치 스코어 관측치를 반영해 현재 phase를 갱신하고 반환한다."""
        normal_now = _is_normal(pps, score)

        if self.phase == RecoveryPhase.MITIGATED:
            if normal_now:
                # T3: 공격 소멸 조건 충족 -> 쿨다운 검증 구간 진입
                self.phase = RecoveryPhase.COOLDOWN_VERIFY
                self._cooldown_started_at = now
            return self.phase

        if self.phase == RecoveryPhase.COOLDOWN_VERIFY:
            if not normal_now:
                # T4: 쿨다운 중 재공격 -> MITIGATED 복귀, 타이머 리셋 (플래핑 방지)
                self.phase = RecoveryPhase.MITIGATED
                self._cooldown_started_at = None
                return self.phase

            assert self._cooldown_started_at is not None
            if now - self._cooldown_started_at >= self.cooldown_sec:
                # T5: 쿨다운 내내 정상 유지 -> 복구 확정
                self.phase = RecoveryPhase.NORMAL
            return self.phase

        return self.phase  # NORMAL 도달 후에는 상위(Ryu FSM)가 RESTORE를 처리

    @property
    def should_restore(self) -> bool:
        return self.phase == RecoveryPhase.NORMAL
