"""11주차 실증: 자가 복구 FSM이 명세(docs/specs/defense_scenarios.md §2~3)대로 플래핑 없이 복구하는지 검증한다.

2초 주기 포트 통계 샘플(S1:2의 PPS·BPP와 AI 스코어)을 시나리오별로 만들어 FSM에 차례로 넣고,
FSM이 내보낸 명령(REROUTE·ISOLATE·RESTORE)을 세어 다음을 판정한다.

- 지속 공격이 끝나면 쿨다운 10초 뒤 RESTORE가 정확히 1번 나오는가 (T3 → T5)
- 쿨다운 중 재공격하면 차단을 풀지 않고 MITIGATED로 돌아가는가 (T4, 수용 기준 V5: 해제 0회)
- 켜졌다 꺼졌다 하는 공격에도 차단·해제를 반복하지 않는가 (플래핑 0회)
- 단발 스파이크나 정상 트래픽 급증(Flash Crowd)에는 반응하지 않는가

`SpecFSM`은 명세를 그대로 옮긴 참조 구현이다. Tech Lead의 실제 FSM(`flapping_fsm.py`)이 들어오면
`step(sample) -> 명령 목록` 형태로 감싸 `evaluate()`에 넘기면 같은 시나리오로 검증된다.
`NaiveFSM`은 쿨다운 없이 공격이 멈추자마자 해제하는 비교용 구현으로, 플래핑을 잡아내는지 확인하는 데 쓴다.

실행 예:
    uv run python -m harness.verification.fsm_acceptance
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Protocol

SAMPLE_SEC = 2.0
CALIBRATION_SEC = 15.0
COOLDOWN_SEC = 10.0
SCORE_THRESHOLD = -0.5
BPP_ATTACK_MAX = 80.0
DETECT_CONSECUTIVE = 2
ATTACK_CEASE_PPS = 100.0


@dataclass(frozen=True)
class Sample:
    t: float
    pps: float
    bpp: float
    score: float


ATTACK = dict(pps=3000.0, bpp=64.0, score=-0.8)
QUIET = dict(pps=0.0, bpp=0.0, score=-0.1)
FLASH_CROWD = dict(pps=2500.0, bpp=820.0, score=-0.3)  # 급증했지만 패킷 크기가 정상


class FSM(Protocol):
    state: str

    def step(self, s: Sample) -> List[str]: ...


def is_attack(s: Sample) -> bool:
    return 0 < s.bpp <= BPP_ATTACK_MAX and s.score < SCORE_THRESHOLD


def is_clean(s: Sample) -> bool:
    return s.pps < ATTACK_CEASE_PPS and s.score >= SCORE_THRESHOLD


@dataclass
class SpecFSM:
    """명세 §2~3의 5상태 FSM 참조 구현 (T1~T5)."""

    state: str = "CALIBRATING"
    _t0: Optional[float] = None
    _streak: int = 0
    _cooldown_from: float = 0.0

    def step(self, s: Sample) -> List[str]:
        if self._t0 is None:
            self._t0 = s.t
        self._streak = self._streak + 1 if is_attack(s) else 0
        if self.state == "CALIBRATING":
            if s.t - self._t0 >= CALIBRATION_SEC:
                self.state = "NORMAL"
            return []
        if self.state == "NORMAL" and self._streak >= DETECT_CONSECUTIVE:  # T1 → T2
            self.state = "MITIGATED"
            return ["REROUTE", "ISOLATE"]
        if self.state == "MITIGATED" and is_clean(s):  # T3
            self.state = "COOLDOWN_VERIFY"
            self._cooldown_from = s.t
            return []
        if self.state == "COOLDOWN_VERIFY":
            if self._streak >= DETECT_CONSECUTIVE:  # T4: 재공격, 차단 유지
                self.state = "MITIGATED"
            elif not is_clean(s):  # 정상 판정이 끊기면 10초를 처음부터 다시 센다
                self._cooldown_from = s.t
            elif s.t - self._cooldown_from >= COOLDOWN_SEC:  # T5
                self.state = "NORMAL"
                return ["RESTORE"]
        return []


@dataclass
class NaiveFSM:
    """비교용: 쿨다운 없이 공격이 멈추면 바로 해제한다 (타임아웃식 복구)."""

    state: str = "NORMAL"
    _streak: int = 0

    def step(self, s: Sample) -> List[str]:
        self._streak = self._streak + 1 if is_attack(s) else 0
        if self.state == "NORMAL" and self._streak >= DETECT_CONSECUTIVE:
            self.state = "MITIGATED"
            return ["REROUTE", "ISOLATE"]
        if self.state == "MITIGATED" and is_clean(s):
            self.state = "NORMAL"
            return ["RESTORE"]
        return []


def timeline(spans: List[tuple], until: float) -> List[Sample]:
    """[(시작, 끝, 프로필)] 구간으로 2초 간격 샘플을 만든다. 구간 밖은 QUIET."""
    out = []
    t = 0.0
    while t <= until:
        prof = next((p for a, b, p in spans if a <= t < b), QUIET)
        out.append(Sample(t=t, **prof))
        t += SAMPLE_SEC
    return out


SCENARIOS: Dict[str, List[Sample]] = {
    "steady": timeline([(20, 40, ATTACK)], 80),
    "reattack_in_cooldown": timeline([(20, 40, ATTACK), (46, 56, ATTACK)], 100),
    "pulsing_4s": timeline([(a, a + 4, ATTACK) for a in range(20, 80, 8)], 120),
    "single_spike": timeline([(30, 32, ATTACK)], 60),
    "flash_crowd": timeline([(20, 40, FLASH_CROWD)], 60),
}

# 시나리오별 기대값: (ISOLATE 횟수, RESTORE 횟수)
EXPECTED = {
    "steady": (1, 1),
    "reattack_in_cooldown": (1, 1),
    "pulsing_4s": (1, 1),
    "single_spike": (0, 0),
    "flash_crowd": (0, 0),
}


@dataclass
class Result:
    isolates: int = 0
    restores: int = 0
    flaps: int = 0
    recovery_sec: Optional[float] = None
    log: List[str] = field(default_factory=list)


def evaluate(make_fsm: Callable[[], FSM], samples: List[Sample]) -> Result:
    fsm = make_fsm()
    r = Result()
    last_attack = max((s.t for s in samples if is_attack(s)), default=None)
    restored_once = False
    for s in samples:
        for cmd in fsm.step(s):
            r.log.append(f"{s.t:5.1f}s {cmd}")
            if cmd == "ISOLATE":
                r.isolates += 1
                if restored_once:
                    r.flaps += 1  # 해제했다가 다시 차단 = 플래핑 1회
            elif cmd == "RESTORE":
                r.restores += 1
                restored_once = True
                if last_attack is not None:
                    r.recovery_sec = s.t - last_attack
    return r


def run_all(make_fsm: Callable[[], FSM]) -> Dict[str, Dict[str, object]]:
    report: Dict[str, Dict[str, object]] = {}
    for name, samples in SCENARIOS.items():
        r = evaluate(make_fsm, samples)
        report[name] = {
            "isolates": r.isolates,
            "restores": r.restores,
            "flaps": r.flaps,
            "recovery_sec": r.recovery_sec,
            "pass": (r.isolates, r.restores) == EXPECTED[name] and r.flaps == 0,
            "log": r.log,
        }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="자가 복구 FSM 플래핑 수용 시험")
    parser.add_argument("--out", type=Path, help="결과 JSON 경로 (생략 시 화면 출력만)")
    args = parser.parse_args()
    out = {"SpecFSM": run_all(SpecFSM), "NaiveFSM": run_all(NaiveFSM)}
    for impl, rep in out.items():
        print(f"== {impl}")
        for name, r in rep.items():
            print(f"  {name:22s} isolate={r['isolates']} restore={r['restores']} flaps={r['flaps']} "
                  f"recovery={r['recovery_sec']} pass={r['pass']}")
    if args.out:
        args.out.write_text(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
