"""Flash Crowd 오탐 방지 통합 검증 (week13 계획서 §4) — F1 >= 0.95, FPR <= 1.0%.

Flash Crowd(정상 급증)는 PPS가 공격처럼 치솟지만 BPP는 정상 범위를 유지한다
(실제 사용자가 보낸 페이로드가 있는 패킷이기 때문). 반면 SYN Flood는
페이로드 없는 극소형 패킷(BPP<=80B)이다. 이 차이를 DetectionGuard의 BPP
게이트로 구분한다.
"""

import random
import time

from model.detection_guard import DetectionGuard
from model.model import AnomalyModel

from .test_model_evaluator import _attack_sample, _build_dataset_csv, _normal_sample

random.seed(7)


def _flash_crowd_sample() -> dict:
    return {
        "timestamp": time.time(),
        "dpid": 1,
        "port_no": 1,
        "delta_pps": random.uniform(200, 800),  # 공격처럼 PPS는 치솟지만
        "delta_bps": random.uniform(150_000, 700_000),
        "bpp": random.uniform(700, 1200),  # BPP는 정상 트래픽과 동일 (핵심 구분 신호)
        "err_rate": random.uniform(0, 0.001),
        "duration_sec": random.randint(10, 300),
    }


def _confirmed_by_guard(model: AnomalyModel, sample: dict) -> bool:
    """2주기 연속 동일한 트래픽 패턴이 지속된다고 가정하고 게이트를 평가한다."""
    _is_anomaly, score = model.predict_single(sample)
    guard = DetectionGuard()
    guard.observe(sample["bpp"], score)
    return guard.observe(sample["bpp"], score)


def test_flash_crowd_and_normal_rarely_confirmed_as_attack(tmp_path):
    csv_path = str(tmp_path / "traffic_data.csv")
    _build_dataset_csv(csv_path)
    model = AnomalyModel()
    model.fit(csv_path)

    negatives = [_normal_sample() for _ in range(100)] + [_flash_crowd_sample() for _ in range(100)]
    false_positives = sum(1 for sample in negatives if _confirmed_by_guard(model, sample))

    fpr = false_positives / len(negatives)
    assert fpr <= 0.01, f"FPR {fpr:.3%}가 1.0% 기준을 초과함 (오탐 {false_positives}/{len(negatives)})"


def test_real_attacks_still_detected_f1_above_baseline(tmp_path):
    csv_path = str(tmp_path / "traffic_data.csv")
    _build_dataset_csv(csv_path)
    model = AnomalyModel()
    model.fit(csv_path)

    y_true = []
    y_pred = []
    for _ in range(100):
        sample = _normal_sample()
        y_true.append(0)
        y_pred.append(1 if _confirmed_by_guard(model, sample) else 0)
    for _ in range(100):
        sample = _flash_crowd_sample()
        y_true.append(0)
        y_pred.append(1 if _confirmed_by_guard(model, sample) else 0)
    for _ in range(100):
        sample = _attack_sample()
        y_true.append(1)
        y_pred.append(1 if _confirmed_by_guard(model, sample) else 0)

    from sklearn.metrics import f1_score

    assert f1_score(y_true, y_pred) >= 0.95
