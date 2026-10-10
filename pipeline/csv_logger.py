"""5대 파생 피처를 레이블과 함께 CSV로 누적 기록하는 로거 (week06 계획서 §3.2)."""

from __future__ import annotations

import csv
import os
from typing import Iterable, Mapping

FIELDNAMES = [
    "timestamp",
    "dpid",
    "port_no",
    "delta_pps",
    "delta_bps",
    "bpp",
    "err_rate",
    "duration_sec",
    "label",
]


def log_features(path: str, features: Iterable[Mapping[str, object]], label: int) -> int:
    """features를 label과 함께 CSV에 append한다. 파일이 없으면 헤더를 먼저 쓴다.

    기록한 행 수를 반환한다.
    """
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    file_exists = os.path.exists(path) and os.path.getsize(path) > 0

    rows_written = 0
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        for feature in features:
            row = dict(feature)
            row["label"] = label
            writer.writerow(row)
            rows_written += 1
    return rows_written
