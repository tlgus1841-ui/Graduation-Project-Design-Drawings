"""14주차: 4단계 자율 방어 시나리오 AI 파이프라인 통합 검증 (week14 계획서).

docs/specs/defense_scenarios.md의 4단계(정상 -> 공격탐지 -> 격리 -> 복구)를
AI Worker가 통제하는 구간(추론 -> 탐지 게이트 -> 복구 판정)만으로 재현한다.
실제 Ryu 플로우 설치/삭제, Mininet 패킷 손실률(V2)·전체 반응시간(V1) 실측은
박시현의 9~11주차 구현 병합 후 실제 환경에서 검증해야 한다 (week09/week10/
week12 계획서에 명시한 것과 동일한 블로커).
"""

from model.detection_guard import DetectionGuard
from model.model import AnomalyModel
from model.recovery_monitor import COOLDOWN_SEC, RecoveryMonitor, RecoveryPhase

from tests.model.test_model_evaluator import _attack_sample, _build_dataset_csv, _normal_sample


def test_full_normal_attack_mitigate_recover_cycle(tmp_path):
    csv_path = str(tmp_path / "traffic_data.csv")
    _build_dataset_csv(csv_path)
    model = AnomalyModel()
    model.fit(csv_path)

    guard = DetectionGuard()
    recovery = RecoveryMonitor()

    # --- 1단계: 정상 ---
    normal = _normal_sample()
    _, normal_score = model.predict_single(normal)
    assert guard.observe(normal["bpp"], normal_score) is False

    # --- 2단계: 공격 탐지 (DETECT_CONSECUTIVE=2주기 연속 필요) ---
    attack = _attack_sample()
    _, attack_score = model.predict_single(attack)
    assert guard.observe(attack["bpp"], attack_score) is False  # 1주기째, 아직 미확정
    assert guard.observe(attack["bpp"], attack_score) is True  # 2주기째 -> 확정

    # --- 3단계: 격리 유지 (공격이 계속되는 한 MITIGATED) ---
    phase = recovery.observe(pps=attack["delta_pps"], score=attack_score, now=0.0)
    assert phase == RecoveryPhase.MITIGATED
    assert not recovery.should_restore

    # --- 4단계: 자가 복구 (공격 소멸 -> 쿨다운 -> NORMAL) ---
    cooldown_start = 2.0
    phase = recovery.observe(pps=normal["delta_pps"], score=normal_score, now=cooldown_start)
    assert phase == RecoveryPhase.COOLDOWN_VERIFY

    # 쿨다운 도중(아직 10초 미만)에는 계속 COOLDOWN_VERIFY
    phase = recovery.observe(
        pps=normal["delta_pps"], score=normal_score, now=cooldown_start + COOLDOWN_SEC - 0.1
    )
    assert phase == RecoveryPhase.COOLDOWN_VERIFY

    # 10초를 꽉 채우면 복구 확정
    phase = recovery.observe(
        pps=normal["delta_pps"], score=normal_score, now=cooldown_start + COOLDOWN_SEC
    )
    assert phase == RecoveryPhase.NORMAL
    assert recovery.should_restore


def test_flapping_during_recovery_keeps_full_cycle_safe(tmp_path):
    """4단계 도중 재공격이 끼어들면 플래핑 없이 다시 격리로 돌아가야 한다."""
    csv_path = str(tmp_path / "traffic_data.csv")
    _build_dataset_csv(csv_path)
    model = AnomalyModel()
    model.fit(csv_path)

    recovery = RecoveryMonitor()
    normal = _normal_sample()
    attack = _attack_sample()
    _, normal_score = model.predict_single(normal)
    _, attack_score = model.predict_single(attack)

    recovery.observe(pps=attack["delta_pps"], score=attack_score, now=0.0)  # MITIGATED
    recovery.observe(pps=normal["delta_pps"], score=normal_score, now=2.0)  # 쿨다운 시작

    # 쿨다운 거의 끝날 때쯔음 재공격
    phase = recovery.observe(pps=attack["delta_pps"], score=attack_score, now=11.0)
    assert phase == RecoveryPhase.MITIGATED
    assert not recovery.should_restore
