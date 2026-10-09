"""recovery_monitor.py 단위 검증 (week11 계획서 §4)."""

from model.recovery_monitor import ATTACK_CEASE_PPS, RecoveryMonitor, RecoveryPhase

ATTACK_PPS = 3000.0
# model/detection_guard.py 보정 노트 참고: 실측 AnomalyModel 점수는
# 공격 -0.15~-0.05, 정상 +0.02~+0.15 범위라 그 범위 안의 값을 쓴다.
ATTACK_SCORE = -0.1
NORMAL_PPS = 50.0
NORMAL_SCORE = 0.08


def test_stays_mitigated_while_attack_continues():
    monitor = RecoveryMonitor()
    phase = monitor.observe(pps=ATTACK_PPS, score=ATTACK_SCORE, now=0.0)
    assert phase == RecoveryPhase.MITIGATED
    assert not monitor.should_restore


def test_enters_cooldown_when_attack_ceases():
    monitor = RecoveryMonitor()
    phase = monitor.observe(pps=NORMAL_PPS, score=NORMAL_SCORE, now=0.0)
    assert phase == RecoveryPhase.COOLDOWN_VERIFY
    assert not monitor.should_restore


def test_restores_after_full_cooldown_of_normal_observations():
    monitor = RecoveryMonitor(cooldown_sec=10.0)
    monitor.observe(pps=NORMAL_PPS, score=NORMAL_SCORE, now=0.0)  # 쿨다운 시작

    # 2초 간격으로 계속 정상 (아직 10초 미만)
    for t in (2.0, 4.0, 6.0, 8.0, 9.9):
        phase = monitor.observe(pps=NORMAL_PPS, score=NORMAL_SCORE, now=t)
        assert phase == RecoveryPhase.COOLDOWN_VERIFY

    phase = monitor.observe(pps=NORMAL_PPS, score=NORMAL_SCORE, now=10.0)
    assert phase == RecoveryPhase.NORMAL
    assert monitor.should_restore


def test_flapping_reattack_resets_cooldown_timer():
    """쿨다운 중 재공격(T4) 시 MITIGATED로 복귀하고, 그 뒤엔 다시 10초를 꽉 채워야 한다."""
    monitor = RecoveryMonitor(cooldown_sec=10.0)
    monitor.observe(pps=NORMAL_PPS, score=NORMAL_SCORE, now=0.0)  # 쿨다운 시작
    monitor.observe(pps=NORMAL_PPS, score=NORMAL_SCORE, now=8.0)  # 거의 다 됐는데

    phase = monitor.observe(pps=ATTACK_PPS, score=ATTACK_SCORE, now=8.5)  # 재공격!
    assert phase == RecoveryPhase.MITIGATED
    assert not monitor.should_restore

    # 재공격 직후 바로 정상으로 돌아와도, 과거에 쌓인 시간은 리셋되어 있어야 한다.
    monitor.observe(pps=NORMAL_PPS, score=NORMAL_SCORE, now=9.0)  # 새 쿨다운 시작
    phase = monitor.observe(pps=NORMAL_PPS, score=NORMAL_SCORE, now=18.9)  # 9.9초 경과
    assert phase == RecoveryPhase.COOLDOWN_VERIFY  # 아직 10초 안 됨

    phase = monitor.observe(pps=NORMAL_PPS, score=NORMAL_SCORE, now=19.0)  # 10초 경과
    assert phase == RecoveryPhase.NORMAL


def test_low_pps_but_bad_score_keeps_mitigated():
    """PPS는 낮아졌지만 이상치 스코어가 아직 안 좋으면 복구 시작 안 함 (두 조건 모두 필요)."""
    monitor = RecoveryMonitor()
    phase = monitor.observe(pps=10.0, score=ATTACK_SCORE, now=0.0)
    assert phase == RecoveryPhase.MITIGATED


def test_good_score_but_high_pps_keeps_mitigated():
    """스코어는 정상이지만 PPS가 여전히 높으면(예: Flash Crowd 겹침) 복구 시작 안 함."""
    monitor = RecoveryMonitor()
    phase = monitor.observe(pps=500.0, score=NORMAL_SCORE, now=0.0)
    assert phase == RecoveryPhase.MITIGATED


def test_boundary_pps_exactly_at_threshold_is_not_normal():
    """ATTACK_CEASE_PPS 경계값 자체는 '여전히 공격'으로 판정한다 (< 비교, <= 아님)."""
    monitor = RecoveryMonitor()
    phase = monitor.observe(pps=float(ATTACK_CEASE_PPS), score=NORMAL_SCORE, now=0.0)
    assert phase == RecoveryPhase.MITIGATED
