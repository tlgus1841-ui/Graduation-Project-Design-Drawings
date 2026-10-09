"""reroute_metrics.py 단위 검증 (week10 계획서 §4)."""

import pytest

from pipeline.reroute_metrics import (
    compute_loss_rate,
    compute_path_load_share,
    compute_rtt_stats,
)


def test_loss_rate_all_received():
    assert compute_loss_rate(sent_seq=[1, 2, 3], received_seq=[1, 2, 3]) == 0.0


def test_loss_rate_some_lost():
    assert compute_loss_rate(sent_seq=[1, 2, 3, 4, 5], received_seq=[1, 2, 3, 5]) == 0.2


def test_loss_rate_no_packets_sent():
    assert compute_loss_rate(sent_seq=[], received_seq=[]) == 0.0


def test_loss_rate_meets_v2_threshold_for_healthy_reroute_sample():
    """defense_scenarios.md §7 V2 기준(손실률 ≤ 2.0%)에 부합하는 샘플 데이터."""
    sent = list(range(500))
    received = [s for s in sent if s not in (37,)]  # 500건 중 1건만 손실 = 0.2%
    assert compute_loss_rate(sent, received) <= 0.02


def test_rtt_stats_known_values():
    stats = compute_rtt_stats([10.0, 20.0, 30.0, 40.0, 50.0])
    assert stats.mean_ms == 30.0
    assert stats.max_ms == 50.0
    assert stats.samples == 5
    assert stats.p95_ms in (40.0, 50.0)  # 작은 샘플에서는 보수적으로 둘 중 하나면 통과


def test_rtt_stats_empty_raises():
    with pytest.raises(ValueError):
        compute_rtt_stats([])


def test_path_load_share_basic():
    share = compute_path_load_share({"S1-S2-S4": 8000, "S1-S3-S4": 2000})
    assert share["S1-S2-S4"] == 0.8
    assert share["S1-S3-S4"] == 0.2


def test_path_load_share_zero_total_does_not_crash():
    share = compute_path_load_share({"S1-S2-S4": 0, "S1-S3-S4": 0})
    assert share == {"S1-S2-S4": 0.0, "S1-S3-S4": 0.0}
