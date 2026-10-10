"""benchmark_report.py 단위 검증 (week15 계획서)."""

import json

from model.benchmark_report import build_report, save_report
from model.model import AnomalyModel
from model.synthetic_samples import build_labeled_dataset_csv


def _trained_model(tmp_path) -> AnomalyModel:
    csv_path = str(tmp_path / "traffic_data.csv")
    build_labeled_dataset_csv(csv_path)
    model = AnomalyModel()
    model.fit(csv_path)
    return model


def test_build_report_meets_dod_thresholds(tmp_path):
    model = _trained_model(tmp_path)
    report = build_report(model, n_per_class=50)

    assert report.f1_score >= 0.90
    assert report.false_positive_rate <= 0.05
    assert report.median_inference_latency_ms < 10.0
    assert report.sample_counts == {"normal": 50, "flash_crowd": 50, "attack": 50}


def test_save_report_writes_valid_json(tmp_path):
    model = _trained_model(tmp_path)
    report = build_report(model, n_per_class=20)

    out_path = str(tmp_path / "benchmark_report.json")
    save_report(report, out_path)

    with open(out_path, encoding="utf-8") as f:
        data = json.load(f)
    assert data["f1_score"] == report.f1_score
    assert "generated_at" in data
