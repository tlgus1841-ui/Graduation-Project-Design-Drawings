"""csv_logger.py 단위 검증 (week06 계획서 §5)."""

import csv

from pipeline.csv_logger import FIELDNAMES, log_features


def test_log_features_creates_header_once(tmp_path):
    out = tmp_path / "features.csv"
    rows = [{
        "timestamp": 1.0, "dpid": 1, "port_no": 1, "delta_pps": 10.0,
        "delta_bps": 800.0, "bpp": 100.0, "err_rate": 0.0, "duration_sec": 30,
    }]

    written_first = log_features(str(out), rows, label=0)
    written_second = log_features(str(out), rows, label=1)

    assert written_first == 1
    assert written_second == 1
    with open(out, newline="", encoding="utf-8") as f:
        reader = list(csv.reader(f))

    assert reader[0] == FIELDNAMES
    assert len(reader) == 3  # 헤더 1 + 데이터 2
    assert reader[1][-1] == "0"
    assert reader[2][-1] == "1"


def test_log_features_creates_parent_directory(tmp_path):
    out = tmp_path / "nested" / "dir" / "features.csv"
    row = {
        "timestamp": 1.0, "dpid": 1, "port_no": 1, "delta_pps": 0.0,
        "delta_bps": 0.0, "bpp": 0.0, "err_rate": 0.0, "duration_sec": 0,
    }
    log_features(str(out), [row], label=0)
    assert out.exists()


def test_log_features_empty_list_writes_nothing_but_no_error(tmp_path):
    out = tmp_path / "features.csv"
    written = log_features(str(out), [], label=0)
    assert written == 0
