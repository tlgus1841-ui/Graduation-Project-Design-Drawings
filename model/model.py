"""Self-Defending SDN Tower - Isolation Forest 기반 실시간 이상 탐지 모델.

주간 계획: docs/writing/reports/weekly/week07_model_implementation_plan.md
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Dict, List, Tuple

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import joblib  # noqa: E402
import numpy as np  # noqa: E402
from sklearn.ensemble import IsolationForest  # noqa: E402
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

FEATURE_COLUMNS = ["delta_pps", "delta_bps", "bpp", "err_rate", "duration_sec"]
DEFAULT_MODEL_PATH = "model/isolation_forest.joblib"


def _load_dataset(csv_path: str) -> Tuple["np.ndarray", "np.ndarray"]:
    """csv_logger.log_features()가 쓴 CSV에서 피처 행렬과 라벨 벡터를 읽는다."""
    rows: List[List[float]] = []
    labels: List[int] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append([float(row[col]) for col in FEATURE_COLUMNS])
            labels.append(int(row["label"]))

    if not rows:
        raise ValueError(f"{csv_path}에 학습 데이터가 없습니다.")
    return np.array(rows), np.array(labels)


class AnomalyModel:
    """5대 SDN 파생 피처를 입력받아 Isolation Forest로 이상 유무를 판별한다."""

    def __init__(self, n_estimators: int = 100, contamination: float = 0.1, random_state: int = 42) -> None:
        self.pipeline = Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "iforest",
                    IsolationForest(
                        n_estimators=n_estimators,
                        contamination=contamination,
                        random_state=random_state,
                        n_jobs=-1,
                    ),
                ),
            ]
        )
        self._fitted = False

    def fit(self, csv_path: str) -> "AnomalyModel":
        """CSV 데이터셋으로 학습한다. 라벨 컬럼은 학습에 쓰지 않는다 (비지도 학습)."""
        features, _labels = _load_dataset(csv_path)
        self.pipeline.fit(features)
        self._fitted = True
        return self

    def predict_single(self, feature_dict: Dict[str, float]) -> Tuple[bool, float]:
        """단일 포트 통계 피처에 대해 (이상 여부, 이상치 점수)를 반환한다.

        점수가 낮을수록(음수로 갈수록) 이상치에 가깝다. `decision_function()`만
        호출한다 — IsolationForest.predict()는 내부적으로 decision_function을
        다시 계산하므로 둘 다 부르면 100개 트리를 두 번 순회하게 되어, 실측상
        단일 추론 지연이 요구사항(<10ms)의 2배 가까이 걸리는 문제가 있었다.
        """
        if not self._fitted:
            raise RuntimeError("모델이 아직 학습되지 않았습니다. fit()을 먼저 호출하세요.")

        row = np.array([[feature_dict[col] for col in FEATURE_COLUMNS]])
        score = float(self.pipeline.decision_function(row)[0])
        return score < 0, score

    def save(self, path: str = DEFAULT_MODEL_PATH) -> None:
        directory = Path(path).parent
        if str(directory):
            directory.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.pipeline, path)

    @classmethod
    def load(cls, path: str = DEFAULT_MODEL_PATH) -> "AnomalyModel":
        instance = cls()
        instance.pipeline = joblib.load(path)
        instance._fitted = True
        return instance
