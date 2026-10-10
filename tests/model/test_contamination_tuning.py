"""Isolation Forest contamination 파라미터 튜닝 재검증 (week12 계획서 §3.2).

7주차에 phase2 가이드 R1이 요구한 contamination=0.1을 그대로 썼는데, 12주차
목표는 "정밀 튜닝" — 즉 0.1이 실제로 괜찮은 선택인지 다른 값과 비교해
데이터로 재확인하는 것이다. 더 나은 값이 나와도 R1 요구사항이 명시적으로
0.1을 지정하므로 기본값은 그대로 0.1을 유지한다.
"""

from sklearn.metrics import f1_score

from model.model import AnomalyModel

from .test_model_evaluator import _attack_sample, _build_dataset_csv, _normal_sample

CANDIDATE_CONTAMINATIONS = [0.05, 0.1, 0.15, 0.2]


def _f1_for_contamination(csv_path: str, contamination: float) -> float:
    model = AnomalyModel(contamination=contamination)
    model.fit(csv_path)

    y_true, y_pred = [], []
    for _ in range(100):
        is_anomaly, _ = model.predict_single(_normal_sample())
        y_true.append(0)
        y_pred.append(1 if is_anomaly else 0)
    for _ in range(100):
        is_anomaly, _ = model.predict_single(_attack_sample())
        y_true.append(1)
        y_pred.append(1 if is_anomaly else 0)

    return f1_score(y_true, y_pred)


def test_default_contamination_meets_f1_baseline(tmp_path):
    """R1이 지정한 contamination=0.1(AnomalyModel 기본값)이 F1 >= 0.90을 만족해야 한다."""
    csv_path = str(tmp_path / "traffic_data.csv")
    _build_dataset_csv(csv_path)

    f1 = _f1_for_contamination(csv_path, contamination=0.1)
    assert f1 >= 0.90


def test_contamination_sweep_reports_scores(tmp_path):
    """후보 contamination 값들의 F1을 전부 계산해, 0.1 근방이 합리적인 선택인지 확인한다."""
    csv_path = str(tmp_path / "traffic_data.csv")
    _build_dataset_csv(csv_path)

    scores = {c: _f1_for_contamination(csv_path, c) for c in CANDIDATE_CONTAMINATIONS}

    # 모든 후보가 "쓸 만한" 수준(F1 > 0.5, 무작위 추측보다 훨씬 나음)이어야 하고,
    # 그 중에서도 R1이 지정한 0.1이 90% 기준선을 만족해야 한다 — 즉 0.1 선택이
    # "운이 좋아서 통과한" 값이 아니라 데이터로 재확인된 합리적인 선택임을 보여준다.
    assert all(score > 0.5 for score in scores.values()), scores
    assert scores[0.1] >= 0.90
