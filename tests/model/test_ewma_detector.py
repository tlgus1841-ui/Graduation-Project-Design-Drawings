"""ewma_detector.py 단위 검증."""

import pytest

from model.ewma_detector import EwmaDetector


def test_first_observation_is_baseline_not_anomaly():
    detector = EwmaDetector()
    assert detector.observe(100.0) is False
    assert detector.mean == 100.0


def test_stable_values_around_mean_are_not_flagged():
    detector = EwmaDetector(alpha=0.3, k=3.0)
    detector.observe(100.0)
    for value in (101.0, 99.0, 100.5, 99.5, 100.2):
        assert detector.observe(value) is False


def test_sudden_large_jump_is_flagged():
    detector = EwmaDetector(alpha=0.3, k=3.0)
    for value in (100.0, 100.0, 101.0, 99.0, 100.0):  # stable baseline, low variance
        detector.observe(value)
    assert detector.observe(500.0) is True  # huge, sudden jump


def test_slow_gradual_drift_eventually_flagged():
    """완전히 매끄러운 선형 증가라도, 분산이 작게 유지된 기준선 대비 벗어나면 언젠가 걸려야 한다."""
    detector = EwmaDetector(alpha=0.2, k=2.0)
    flagged_at = None
    value = 0.0
    for step in range(60):
        detector_result = detector.observe(value)
        if detector_result and flagged_at is None:
            flagged_at = step
        value += 2.0  # 서서히, 꾸준히 증가 (급격한 스파이크 아님)
    assert flagged_at is not None


def test_rejects_invalid_alpha():
    with pytest.raises(ValueError):
        EwmaDetector(alpha=0.0)
    with pytest.raises(ValueError):
        EwmaDetector(alpha=1.5)
