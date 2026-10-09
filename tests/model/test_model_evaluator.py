"""model.py 평가 하네스 (week07 계획서 §4).

Mininet/Ryu가 없는 환경이라 docs/specs/defense_scenarios.md §3.1/§3.2의
정상/공격 통계 특성을 따르는 합성 데이터셋으로 학습·평가한다. 합성 데이터
생성기 자체는 15주차에 model/synthetic_samples.py로 옮겨 재사용한다.
"""

import random
import time

import pytest
from sklearn.metrics import f1_score

from model.model import FEATURE_COLUMNS, AnomalyModel
from model.synthetic_samples import attack_sample as _attack_sample
from model.synthetic_samples import build_labeled_dataset_csv as _build_dataset_csv
from model.synthetic_samples import normal_sample as _normal_sample
from pipeline.csv_logger import FIELDNAMES

random.seed(42)


@pytest.fixture
def trained_model(tmp_path):
    csv_path = str(tmp_path / "traffic_data.csv")
    _build_dataset_csv(csv_path)
    model = AnomalyModel()  # R1 기본값(contamination=0.1) 그대로 사용
    model.fit(csv_path)
    return model


def test_model_detects_synthetic_attacks_f1_above_baseline(trained_model):
    y_true = []
    y_pred = []
    for _ in range(100):
        is_anomaly, _score = trained_model.predict_single(_normal_sample())
        y_true.append(0)
        y_pred.append(1 if is_anomaly else 0)
    for _ in range(100):
        is_anomaly, _score = trained_model.predict_single(_attack_sample())
        y_true.append(1)
        y_pred.append(1 if is_anomaly else 0)

    assert f1_score(y_true, y_pred) >= 0.90


def test_attack_score_lower_than_normal_score(trained_model):
    _, normal_score = trained_model.predict_single(_normal_sample())
    _, attack_score = trained_model.predict_single(_attack_sample())
    assert attack_score < normal_score


def test_predict_single_latency_under_10ms(trained_model):
    """IsolationForest(n_jobs=-1)는 호출마다 joblib 병렬 백엔드를 기동하는데,
    맨 첫 호출(또는 오랜만의 호출)은 그 기동 비용이 섞여 들쭉날쭉하다. 실제
    AI Worker는 상시 기동 상태로 패킷을 연속 처리하므로, 웜업 1회 후
    "정상 가동 중" 지연시간을 측정한다. 평균 대신 중앙값을 써서 OS
    스케줄링 튐 같은 일회성 아웃라이어에도 흔들리지 않게 한다.
    """
    sample = _attack_sample()
    trained_model.predict_single(sample)  # 웜업: 병렬 백엔드 기동 비용 제외

    iterations = 50
    latencies_ms = []
    for _ in range(iterations):
        start = time.perf_counter()
        trained_model.predict_single(sample)
        latencies_ms.append((time.perf_counter() - start) * 1000)

    latencies_ms.sort()
    median_ms = latencies_ms[iterations // 2]
    assert median_ms < 10.0


def test_save_and_load_roundtrip(trained_model, tmp_path):
    model_path = str(tmp_path / "isolation_forest.joblib")
    trained_model.save(model_path)

    loaded = AnomalyModel.load(model_path)
    sample = _attack_sample()
    assert trained_model.predict_single(sample) == loaded.predict_single(sample)


def test_predict_before_fit_raises():
    model = AnomalyModel()
    with pytest.raises(RuntimeError):
        model.predict_single(_normal_sample())


def test_fit_on_empty_csv_raises(tmp_path):
    empty_csv = tmp_path / "empty.csv"
    empty_csv.write_text("", encoding="utf-8")
    with pytest.raises(ValueError):
        AnomalyModel().fit(str(empty_csv))


def test_feature_columns_match_csv_logger_schema():
    for col in FEATURE_COLUMNS:
        assert col in FIELDNAMES
