"""Self-Defending SDN Tower - 시연용 공격 프로파일 프리셋.

주간 계획: docs/writing/reports/weekly/week15_demo_packaging_plan.md

실제 시연 중에는 매번 --min-pps/--max-pps를 손으로 맞추는 대신, 시나리오에
맞는 프리셋 이름 하나만 고르면 되도록 패키징한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class AttackPreset:
    name: str
    min_pps: int
    max_pps: int
    description: str


PRESETS: Dict[str, AttackPreset] = {
    "light": AttackPreset(
        name="light", min_pps=1000, max_pps=2000,
        description="약한 SYN Flood - 탐지 로직 단독 시연용",
    ),
    "standard": AttackPreset(
        name="standard", min_pps=1000, max_pps=5000,
        description="schedule_and_milestones.md의 ATTACK_PPS 기본 범위",
    ),
    "heavy": AttackPreset(
        name="heavy", min_pps=4000, max_pps=5000,
        description="ATTACK_PPS 상한 근접 - 플로우 테이블 고갈 방어(9주차) 시연용",
    ),
}


def get_preset(name: str) -> AttackPreset:
    try:
        return PRESETS[name]
    except KeyError:
        available = ", ".join(sorted(PRESETS))
        raise ValueError(f"알 수 없는 프리셋: '{name}'. 사용 가능한 프리셋: {available}") from None
