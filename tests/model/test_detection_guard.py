"""detection_guard.py 단위 검증 (week13 계획서 §4)."""

from model.detection_guard import DetectionGuard, is_suspicious

ATTACK_BPP = 64.0
# 실측 AnomalyModel 점수는 공격 -0.15~-0.05, 정상 +0.02~+0.15 범위
# (model/detection_guard.py 모듈 docstring의 보정 노트 참고).
ATTACK_SCORE = -0.1
NORMAL_BPP = 900.0
NORMAL_SCORE = 0.08


def test_is_suspicious_true_for_attack_like_values():
    assert is_suspicious(bpp=ATTACK_BPP, score=ATTACK_SCORE)


def test_is_suspicious_false_when_bpp_normal_even_if_score_bad():
    """Flash Crowd 핵심 조건: BPP가 정상 범위면 점수가 나빠도 의심 대상이 아니다."""
    assert not is_suspicious(bpp=NORMAL_BPP, score=ATTACK_SCORE)


def test_is_suspicious_false_when_score_good_even_if_bpp_small():
    assert not is_suspicious(bpp=ATTACK_BPP, score=NORMAL_SCORE)


def test_attack_confirmed_after_consecutive_periods():
    guard = DetectionGuard()
    assert guard.observe(ATTACK_BPP, ATTACK_SCORE) is False  # 1주기째, 아직 미확정
    assert guard.observe(ATTACK_BPP, ATTACK_SCORE) is True   # 2주기 연속 -> 확정


def test_single_spike_does_not_confirm_attack():
    guard = DetectionGuard()
    assert guard.observe(ATTACK_BPP, ATTACK_SCORE) is False
    assert guard.observe(NORMAL_BPP, NORMAL_SCORE) is False  # 정상으로 복귀, 스트릭 리셋
    assert guard.observe(ATTACK_BPP, ATTACK_SCORE) is False  # 다시 1주기째


def test_flash_crowd_never_confirmed_even_with_many_observations():
    guard = DetectionGuard()
    for _ in range(10):
        confirmed = guard.observe(bpp=NORMAL_BPP, score=ATTACK_SCORE)
        assert confirmed is False
