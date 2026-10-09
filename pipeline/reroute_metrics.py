"""Self-Defending SDN Tower - 우회 라우팅 성능 측정 유틸 (손실률/RTT/경로 부하).

주간 계획: docs/writing/reports/weekly/week10_reroute_metrics_plan.md

Mininet `ping`/`iperf` 또는 Ryu 포트 통계에서 뽑은 실측값을 받아 집계하는
순수 함수로만 구성한다. 네트워크 동작 자체를 흉내 내지 않는다 — 측정 대상
(박시현의 우회 라우팅 구현)이 아직 없는 상태에서 가짜로 흉내 내면 실제
Mininet 실측과 다른 결과를 낼 위험이 있기 때문이다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Sequence


def compute_loss_rate(sent_seq: Sequence[int], received_seq: Sequence[int]) -> float:
    """송신 시퀀스 번호 대비 수신 시퀀스 번호로 패킷 손실률(0.0~1.0)을 계산한다."""
    if not sent_seq:
        return 0.0
    received = set(received_seq)
    lost = sum(1 for seq in sent_seq if seq not in received)
    return lost / len(sent_seq)


@dataclass
class RttStats:
    mean_ms: float
    p95_ms: float
    max_ms: float
    samples: int


def compute_rtt_stats(rtts_ms: Sequence[float]) -> RttStats:
    """RTT 샘플(ms) 목록에서 평균/95퍼센타일/최댓값을 계산한다."""
    if not rtts_ms:
        raise ValueError("RTT 샘플이 비어 있습니다.")

    sorted_rtts = sorted(rtts_ms)
    n = len(sorted_rtts)
    p95_index = min(n - 1, int(round(0.95 * (n - 1))))
    return RttStats(
        mean_ms=sum(sorted_rtts) / n,
        p95_ms=sorted_rtts[p95_index],
        max_ms=sorted_rtts[-1],
        samples=n,
    )


def compute_path_load_share(byte_counts_by_path: Dict[str, int]) -> Dict[str, float]:
    """경로별 전송 바이트 수를 받아 각 경로가 차지하는 비율(0.0~1.0)을 계산한다."""
    total = sum(byte_counts_by_path.values())
    if total == 0:
        return {path: 0.0 for path in byte_counts_by_path}
    return {path: count / total for path, count in byte_counts_by_path.items()}
