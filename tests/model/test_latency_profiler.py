"""latency_profiler.py 단위 검증 (week12 계획서 §4)."""

import time

import pytest

from harness.contracts import PortStatsMessage
from model.latency_profiler import measure_inference_ms, profile_pipeline
from model.model import AnomalyModel
from pipeline.feature_extractor import FeatureExtractor

from .test_model_evaluator import _attack_sample, _build_dataset_csv


def _port_stats(ts: float, rx_packets: int, rx_bytes: int) -> PortStatsMessage:
    return PortStatsMessage.model_validate({
        "timestamp": ts,
        "dpid": 1,
        "stats": [{
            "dpid": 1, "port_no": 2,
            "rx_packets": rx_packets, "tx_packets": 0,
            "rx_bytes": rx_bytes, "tx_bytes": 0,
            "duration_sec": 10,
        }],
    })


@pytest.fixture
def trained_model(tmp_path):
    csv_path = str(tmp_path / "traffic_data.csv")
    _build_dataset_csv(csv_path)
    model = AnomalyModel()
    model.fit(csv_path)
    return model


def test_feature_extraction_under_5ms(trained_model):
    extractor = FeatureExtractor()
    prev_msg = _port_stats(ts=0.0, rx_packets=100, rx_bytes=8000)
    cur_msg = _port_stats(ts=2.0, rx_packets=5100, rx_bytes=326400)

    report = profile_pipeline(extractor, trained_model, prev_msg, cur_msg)

    assert report.feature_extraction_ms < 5.0


def test_inference_under_10ms(trained_model):
    sample = _attack_sample()
    measure_inference_ms(trained_model, sample)  # 웜업

    latency_ms = measure_inference_ms(trained_model, sample)
    assert latency_ms < 10.0


def test_combined_ai_pipeline_total(trained_model):
    extractor = FeatureExtractor()
    prev_msg = _port_stats(ts=0.0, rx_packets=100, rx_bytes=8000)
    cur_msg = _port_stats(ts=2.0, rx_packets=5100, rx_bytes=326400)

    profile_pipeline(extractor, trained_model, prev_msg, cur_msg)  # 웜업
    report = profile_pipeline(FeatureExtractor(), trained_model, prev_msg, cur_msg)

    # R3(플로우 주입 포함 합산)은 보류지만, AI 파이프라인 구간만으로도
    # 5ms + 10ms 예산을 넘지 않는지 확인한다.
    assert report.ai_pipeline_total_ms < 15.0


def test_profile_pipeline_raises_when_no_delta_available(trained_model):
    extractor = FeatureExtractor()
    same_msg = _port_stats(ts=time.time(), rx_packets=100, rx_bytes=8000)

    with pytest.raises(ValueError):
        profile_pipeline(extractor, trained_model, same_msg, same_msg)
