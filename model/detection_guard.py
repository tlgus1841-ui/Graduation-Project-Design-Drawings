"""Self-Defending SDN Tower - 오탐 방지 공격 확정 게이트 (Flash Crowd vs 실제 공격).

주간 계획: docs/writing/reports/weekly/week13_detection_guard_plan.md

docs/specs/defense_scenarios.md §3.2 T1: BPP <= BPP_ATTACK_MAX(80) 그리고
score < SCORE_THRESHOLD가 DETECT_CONSECUTIVE(2)주기 연속 충족되어야 공격으로
확정한다. PPS가 치솟아도(Flash Crowd) BPP가 정상 범위면 BPP 게이트에서
바로 걸러져 공격으로 오판하지 않는다 — Isolation Forest 점수 하나만으로
판단하지 않는 이유다.

SCORE_THRESHOLD 보정 (13주차에 실측으로 수정): defense_scenarios.md §6은
원래 -0.5로 적혀 있었으나, 실제 학습된 AnomalyModel의
decision_function() 점수는 공격 샘플도 -0.15~-0.05 범위라 -0.5에
전혀 도달하지 못해 이 임계치로는 공격이 영원히 탐지되지 않는 치명적
버그였다. 공격(약 -0.15~-0.05)과 정상(약 +0.02~+0.15) 점수가 0을
기준으로 깨끗이 갈리는 걸 실측으로 확인해 0.0으로 재보정했다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

BPP_ATTACK_MAX = 80.0
SCORE_THRESHOLD = 0.0
DETECT_CONSECUTIVE = 2


def is_suspicious(bpp: float, score: float) -> bool:
    """단일 관측치가 공격 의심 조건(BPP 작음 + 이상치 점수 나쁨)을 모두 만족하는가."""
    return bpp <= BPP_ATTACK_MAX and score < SCORE_THRESHOLD


@dataclass
class DetectionGuard:
    """DETECT_CONSECUTIVE 주기 연속으로 의심 조건이 충족돼야 공격을 확정한다
    (단발성 스파이크 오탐 방지)."""

    consecutive_required: int = DETECT_CONSECUTIVE
    _streak: int = field(default=0, init=False)

    def observe(self, bpp: float, score: float) -> bool:
        """관측치를 반영하고, 공격이 확정되었는지(bool) 반환한다."""
        if is_suspicious(bpp, score):
            self._streak += 1
        else:
            self._streak = 0
        return self._streak >= self.consecutive_required
