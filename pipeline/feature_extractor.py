"""Self-Defending SDN Tower - Redis `sdn:stats:port` 구독 및 5대 파생 피처 실시간 계산기.

주간 계획: docs/writing/reports/weekly/week06_feature_extractor_implementation_plan.md
실행 예: uv run python pipeline/feature_extractor.py --label 0 --out dataset/traffic_data.csv
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# `python pipeline/feature_extractor.py`로 직접 실행될 때도 harness/pipeline을
# 절대 임포트할 수 있도록 저장소 루트를 sys.path에 추가한다.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import redis  # noqa: E402

from harness.contracts import REDIS_CHANNEL_PORT_STATS, PortStatsMessage  # noqa: E402
from pipeline.csv_logger import log_features  # noqa: E402

EPSILON = 1e-6
PortKey = Tuple[int, int]


@dataclass
class _PortSnapshot:
    timestamp: float
    rx_packets: int
    rx_bytes: int
    rx_errors: int


class FeatureExtractor:
    """포트별 직전 관측치를 보관하고, 신규 관측치가 들어올 때마다 5대 파생 피처를 계산한다."""

    def __init__(self) -> None:
        self._prev: Dict[PortKey, _PortSnapshot] = {}

    def update(self, message: PortStatsMessage) -> List[dict]:
        """PortStatsMessage 한 건을 처리해, 델타를 낼 수 있는 포트의 피처만 반환한다."""
        features: List[dict] = []
        for stat in message.stats:
            key: PortKey = (stat.dpid, stat.port_no)
            prev = self._prev.get(key)
            current = _PortSnapshot(
                timestamp=message.timestamp,
                rx_packets=stat.rx_packets,
                rx_bytes=stat.rx_bytes,
                rx_errors=stat.rx_errors,
            )

            if prev is None:
                # 최초 관측치는 델타를 낼 기준이 없어 기준점으로만 저장한다.
                self._prev[key] = current
                continue

            dt = current.timestamp - prev.timestamp
            d_packets = current.rx_packets - prev.rx_packets
            d_bytes = current.rx_bytes - prev.rx_bytes
            d_errors = current.rx_errors - prev.rx_errors

            self._prev[key] = current

            if dt <= 0 or d_packets < 0 or d_bytes < 0:
                # 중복/역전 타임스탬프이거나 스위치 재시작으로 카운터가 리셋된 구간은 버린다.
                continue

            features.append(
                {
                    "timestamp": current.timestamp,
                    "dpid": stat.dpid,
                    "port_no": stat.port_no,
                    "delta_pps": d_packets / dt,
                    "delta_bps": (d_bytes / dt) * 8,
                    "bpp": d_bytes / (d_packets + EPSILON),
                    "err_rate": d_errors / (d_packets + EPSILON),
                    "duration_sec": stat.duration_sec,
                }
            )
        return features


def subscribe(client: "redis.Redis", channel: str = REDIS_CHANNEL_PORT_STATS):
    """Redis pubsub을 구독하고 핸들을 반환한다."""
    pubsub = client.pubsub()
    pubsub.subscribe(channel)
    return pubsub


def run(
    pubsub,
    out_path: str,
    label: int,
    max_messages: Optional[int] = None,
    poll_timeout: float = 1.0,
) -> int:
    """구독 중인 pubsub에서 메시지를 받아 피처를 계산하고 CSV에 누적 기록한다.

    기록한 행 수를 반환한다. max_messages를 주면 그 개수만큼 "message" 타입
    이벤트를 처리한 뒤 종료한다 (테스트 및 유한 캡처 세션용).

    `pubsub.listen()`(무한 블로킹 제너레이터) 대신 `get_message(timeout=...)`를
    직접 polling한다. ryu/app/controller.py가 타임아웃 없는 소켓 호출로 테스트를
    수백 초씩 블로킹시킨 사례를 겪은 뒤, 이 모듈은 항상 유한 타임아웃을 갖는
    호출만 사용하도록 설계했다.
    """
    extractor = FeatureExtractor()
    written = 0
    received = 0

    while max_messages is None or received < max_messages:
        item = pubsub.get_message(timeout=poll_timeout)
        if item is None:
            continue
        if item.get("type") != "message":
            continue
        received += 1

        try:
            payload = json.loads(item["data"])
            message = PortStatsMessage.model_validate(payload)
        except Exception:
            # 손상된 메시지는 건너뛰고 수신을 계속한다 (장애 격리).
            continue

        features = extractor.update(message)
        if features:
            written += log_features(out_path, features, label=label)

    return written


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Redis sdn:stats:port 구독 5대 파생 피처 추출기")
    parser.add_argument("--host", default=os.getenv("REDIS_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("REDIS_PORT", "6379")))
    parser.add_argument("--out", default="dataset/traffic_data.csv", help="CSV 출력 경로")
    parser.add_argument(
        "--label", type=int, choices=(0, 1), required=True,
        help="이번 캡처 세션의 라벨 (0=정상 트래픽, 1=공격 트래픽)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    # 직전 턴에서 ryu/app/controller.py가 connect timeout 미설정으로 수십 초씩
    # 블로킹되는 문제를 확인했으므로, 여기서는 반드시 연결 타임아웃을 명시한다.
    client = redis.Redis(
        host=args.host,
        port=args.port,
        db=0,
        decode_responses=True,
        socket_timeout=1.0,
        socket_connect_timeout=1.0,
    )
    pubsub = subscribe(client)
    written = run(pubsub, args.out, args.label)
    print(f"[feature_extractor] {written}건 기록 완료 -> {args.out}")


if __name__ == "__main__":
    main()
