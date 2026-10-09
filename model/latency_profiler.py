"""Self-Defending SDN Tower - AI 파이프라인(피처 추출 + 추론) E2E 지연시간 프로파일러.

주간 계획: docs/writing/reports/weekly/week12_latency_profiler_plan.md

전체 E2E 지연(피처 추출 + 추론 + 플로우 주입)에서 "플로우 주입"은 박시현의
Ryu 컨트롤러가 실제 스위치에 OFPFC_ADD를 적용하는 구간이라 이 환경에선
측정할 수 없다. 이 모듈은 AI Worker가 통제 가능한 구간(피처 추출 + 추론)만
측정한다.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict

from harness.contracts import PortStatsMessage
from model.model import AnomalyModel
from pipeline.feature_extractor import FeatureExtractor


def measure_inference_ms(model: AnomalyModel, feature_dict: Dict[str, float]) -> float:
    start = time.perf_counter()
    model.predict_single(feature_dict)
    return (time.perf_counter() - start) * 1000


@dataclass
class LatencyReport:
    feature_extraction_ms: float
    inference_ms: float

    @property
    def ai_pipeline_total_ms(self) -> float:
        return self.feature_extraction_ms + self.inference_ms


def profile_pipeline(
    extractor: FeatureExtractor,
    model: AnomalyModel,
    prev_message: PortStatsMessage,
    current_message: PortStatsMessage,
) -> LatencyReport:
    """prev/current 포트 통계 한 쌍으로 피처 추출 -> 추론까지의 지연을 측정한다."""
    extractor.update(prev_message)  # 기준점 - 측정 제외

    start = time.perf_counter()
    features = extractor.update(current_message)
    feature_ms = (time.perf_counter() - start) * 1000

    if not features:
        raise ValueError("두 메시지 사이에서 델타를 낼 수 없습니다 (동일 타임스탬프 등).")

    inference_ms = measure_inference_ms(model, features[0])

    return LatencyReport(feature_extraction_ms=feature_ms, inference_ms=inference_ms)
