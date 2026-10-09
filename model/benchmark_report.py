"""Self-Defending SDN Tower - 최종 시연용 정량 성능 지표 리포트 생성기.

주간 계획: docs/writing/reports/weekly/week15_demo_packaging_plan.md

7~14주차에 검증한 AI Worker 측 DoD 수치(F1, FPR, 추론/피처 추출 지연)를
하나의 JSON 리포트로 모아, 최종 발표/시연 자료(김관우 담당)에 바로 쓸 수
있게 한다. 실제 Mininet 손실률/RTT(V2)는 포함하지 않는다 — 9/10/12/14주차
계획서에 명시한 대로 박시현의 방어 로직 병합 후 실측이 필요한 영역이다.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from typing import Dict

from sklearn.metrics import f1_score

from model.detection_guard import DetectionGuard
from model.model import AnomalyModel
from model.synthetic_samples import attack_sample, flash_crowd_sample, normal_sample


@dataclass
class BenchmarkReport:
    generated_at: float
    f1_score: float
    false_positive_rate: float
    median_inference_latency_ms: float
    sample_counts: Dict[str, int]


def _median(values: list) -> float:
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


def _confirmed_by_guard(model: AnomalyModel, sample: dict) -> bool:
    _is_anomaly, score = model.predict_single(sample)
    guard = DetectionGuard()
    guard.observe(sample["bpp"], score)
    return guard.observe(sample["bpp"], score)


def build_report(model: AnomalyModel, n_per_class: int = 100) -> BenchmarkReport:
    """정상/Flash Crowd/공격 샘플로 F1·FPR·추론 지연을 한 번에 집계한다."""
    normals = [normal_sample() for _ in range(n_per_class)]
    flash_crowds = [flash_crowd_sample() for _ in range(n_per_class)]
    attacks = [attack_sample() for _ in range(n_per_class)]

    y_true = [0] * (2 * n_per_class) + [1] * n_per_class
    y_pred = [
        1 if _confirmed_by_guard(model, s) else 0
        for s in (normals + flash_crowds + attacks)
    ]
    false_positives = sum(y_pred[: 2 * n_per_class])

    warmup_sample = attacks[0]
    model.predict_single(warmup_sample)  # 병렬 백엔드 기동 비용 제외
    latencies_ms = []
    for _ in range(50):
        start = time.perf_counter()
        model.predict_single(warmup_sample)
        latencies_ms.append((time.perf_counter() - start) * 1000)

    return BenchmarkReport(
        generated_at=time.time(),
        f1_score=f1_score(y_true, y_pred),
        false_positive_rate=false_positives / (2 * n_per_class),
        median_inference_latency_ms=_median(latencies_ms),
        sample_counts={"normal": n_per_class, "flash_crowd": n_per_class, "attack": n_per_class},
    )


def save_report(report: BenchmarkReport, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(report), f, ensure_ascii=False, indent=2)
