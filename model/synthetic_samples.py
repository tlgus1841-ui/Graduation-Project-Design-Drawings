"""Self-Defending SDN Tower - 합성 트래픽 피처 샘플 생성기 (정상/공격/Flash Crowd).

주간 계획: docs/writing/reports/weekly/week15_demo_packaging_plan.md

Mininet/Ryu가 없는 환경에서 docs/specs/defense_scenarios.md §3.1/§3.2의
정상/공격 통계 특성을 따르는 합성 데이터를 생성한다. 7주차부터 테스트
파일(test_model_evaluator.py)에 흩어져 있던 생성기를 여기로 모았다 —
15주차의 최종 데이터셋/리포트 패키징(model/benchmark_report.py)이
테스트 코드를 import하는 역방향 의존을 피하기 위함이다.
"""

from __future__ import annotations

import random
import time

from pipeline.csv_logger import log_features


def normal_sample() -> dict:
    return {
        "timestamp": time.time(),
        "dpid": 1,
        "port_no": 1,
        "delta_pps": random.uniform(10, 100),
        "delta_bps": random.uniform(5_000, 15_000),
        "bpp": random.uniform(700, 1200),
        "err_rate": random.uniform(0, 0.001),
        "duration_sec": random.randint(10, 300),
    }


def attack_sample() -> dict:
    return {
        "timestamp": time.time(),
        "dpid": 1,
        "port_no": 2,
        "delta_pps": random.uniform(1000, 5000),
        "delta_bps": random.uniform(500_000, 2_500_000),
        "bpp": random.uniform(54, 74),
        "err_rate": random.uniform(0, 0.001),
        "duration_sec": random.randint(10, 300),
    }


def flash_crowd_sample() -> dict:
    """PPS는 공격처럼 치솟지만 BPP는 정상 범위 (실제 사용자가 보낸 페이로드가 있는 패킷)."""
    return {
        "timestamp": time.time(),
        "dpid": 1,
        "port_no": 1,
        "delta_pps": random.uniform(200, 800),
        "delta_bps": random.uniform(150_000, 700_000),
        "bpp": random.uniform(700, 1200),
        "err_rate": random.uniform(0, 0.001),
        "duration_sec": random.randint(10, 300),
    }


def build_labeled_dataset_csv(path: str, n_normal: int = 360, n_attack: int = 40) -> None:
    """IsolationForest는 '희귀한 이상치'를 가정하는 모델이라, 실제 운영 환경처럼
    정상이 다수(90%)·공격이 소수(10%)인 비율로 학습 데이터를 구성한다
    (contamination=0.1 기본값과 일치, 7주차에 1:1로 구성했다가 F1 미달로 수정한 이력 있음).
    """
    log_features(path, [normal_sample() for _ in range(n_normal)], label=0)
    log_features(path, [attack_sample() for _ in range(n_attack)], label=1)
