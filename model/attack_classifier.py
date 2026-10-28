"""Self-Defending SDN Tower - DDoS 외 공격 유형(Port Scan, Slow DDoS) 보조 분류기.

v1(이번에 교체)에서는 PORT_SCAN을 rx_errors(err_rate) 임계치로, SLOW_DRIFT를
duration_sec(포트 가동 시간) EWMA 추세로 판정했다. 둘 다 실측·재검토 결과 실제
Mininet/OVS 트래픽에서는 작동할 수 없는 신호였다:

- rx_errors는 OpenFlow 포트의 "물리/링크 계층 수신 오류" 카운터다(CRC·프레임 오류
  등). 닫힌 포트로 보낸 TCP SYN에 대한 RST 응답은 스위치 입장에서 완전히 정상적인
  프레임이라 rx_errors를 전혀 올리지 않는다. 게다가 이 프로젝트의 공격 트래픽은
  `traffic/checksum_utils.py`로 체크섬을 일부러 정상화해서 보내므로, 코드베이스
  안 어떤 트래픽 생성기도 rx_errors를 움직이지 못한다 — 즉 유닛 테스트에서만
  통과하고 실제 환경에서는 영원히 발동하지 않는 신호였다.
- duration_sec은 "그 포트가 켜져 있던 시간"(업타임)이다. 공격 여부와 무관하게
  항상 똑같은 속도로 흘러가므로, 이걸 EWMA로 추적해도 "공격 추세"가 아니라
  "시간이 흐른다"는 사실만 감지하게 된다.

v2: 두 유형 모두 실제로 관측 가능한 신호 하나 — **DetectionGuard(플러드)가 걸러낸
MIN_ATTACK_PPS 미달 구간에서, BPP는 작은데(BPP_ATTACK_MAX 이하) delta_pps가
EWMA 기준선에서 벗어나는 것** — 에서 출발한다. 포트 통계만으로는 "포트 스캔"과
"Slow DDoS 전조"를 구조적으로 구분할 근거가 없으므로(둘 다 "플러드에는 못 미치는
소형 패킷 트래픽의 비정상적 증가"로 똑같이 보인다), 지속 시간으로 나눈다: 짧게
튀면 탐색성 버스트(포트 스캔), SUSTAINED_TICKS_FOR_SLOW_DDOS 이상 계속되면
저속·장기 자원 고갈(Slow DDoS)로 승격한다.

traffic/traffic_scan.py로 이 신호를 실제 패킷(sub-flood PPS, 포트 순환 SYN)으로
재현해 검증한다.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, Tuple

from harness.contracts import ThreatType
from model.detection_guard import BPP_ATTACK_MAX
from model.ewma_detector import EwmaDetector

DETECT_CONSECUTIVE = 2
# 2초 주기 기준 약 20초. 이보다 오래 계속되면 탐색성 버스트(포트 스캔)가 아니라
# 저속·장기 지속 공격(Slow DDoS)으로 본다.
SUSTAINED_TICKS_FOR_SLOW_DDOS = 10
# model/inference_worker.py의 MIN_ATTACK_PPS와 같은 값: 이 미달 구간만 다룬다
# (그 이상은 DetectionGuard의 플러드 경로가 이미 전담).
DEFAULT_SUB_FLOOD_PPS = 100.0

PortKey = Tuple[int, int]


class AttackCategory(str, Enum):
    NORMAL = "NORMAL"
    VOLUMETRIC_FLOOD = "VOLUMETRIC_FLOOD"
    PORT_SCAN = "PORT_SCAN"
    SLOW_DRIFT = "SLOW_DRIFT"


CATEGORY_TO_THREAT_TYPE: Dict[AttackCategory, str] = {
    AttackCategory.VOLUMETRIC_FLOOD: ThreatType.SYN_FLOOD_SPOOFING.value,
    AttackCategory.PORT_SCAN: ThreatType.PORT_SCAN.value,
    AttackCategory.SLOW_DRIFT: ThreatType.SLOW_DDOS.value,
}


class StreakGuard:
    """연속 관측치 스트릭을 추적한다. consecutive_required 이상이면 확정."""

    def __init__(self, consecutive_required: int = DETECT_CONSECUTIVE):
        self.consecutive_required = consecutive_required
        self._streak = 0

    def observe(self, suspicious: bool) -> bool:
        self._streak = self._streak + 1 if suspicious else 0
        return self._streak >= self.consecutive_required

    @property
    def streak(self) -> int:
        return self._streak


class SecondaryAttackClassifier:
    """DetectionGuard(플러드)와 병행 실행되는, 플러드 임계치 미달 소형 패킷 탐지기.

    판정 대상: delta_pps < sub_flood_pps(플러드 기준 미달)이면서 bpp가 작은
    (<= BPP_ATTACK_MAX) 트래픽이 EWMA 기준선에서 벗어날 때. 짧게
    (SUSTAINED_TICKS_FOR_SLOW_DDOS 미달) 튀면 PORT_SCAN, 그보다 오래 계속되면
    SLOW_DRIFT로 승격한다. 한 포트가 동시에 플러드와 이 경로를 모두 탈 일은
    없다 — 플러드 임계치 미달 구간만 다루기 때문이다.
    """

    def __init__(
        self,
        sub_flood_pps: float = DEFAULT_SUB_FLOOD_PPS,
        ewma_alpha: float = 0.3,
        ewma_k: float = 2.5,
        consecutive_required: int = DETECT_CONSECUTIVE,
        sustained_ticks_for_slow: int = SUSTAINED_TICKS_FOR_SLOW_DDOS,
    ):
        self.sub_flood_pps = sub_flood_pps
        self._ewma_alpha = ewma_alpha
        self._ewma_k = ewma_k
        self._consecutive_required = consecutive_required
        self._sustained_ticks_for_slow = sustained_ticks_for_slow
        self._ewma: Dict[PortKey, EwmaDetector] = {}
        self._streaks: Dict[PortKey, StreakGuard] = {}

    def observe(self, feature: dict) -> Tuple[AttackCategory, bool]:
        key = (feature["dpid"], feature["port_no"])
        ewma = self._ewma.setdefault(key, EwmaDetector(alpha=self._ewma_alpha, k=self._ewma_k))
        baseline_before = ewma.mean
        trend_anomaly = ewma.observe(feature["delta_pps"])

        suspicious = (
            trend_anomaly
            # EWMA는 기준선 대비 증가·감소 양방향 이탈을 모두 "이상"으로 본다 (범용 SPC 설계,
            # 그대로 둔다). 여기서는 증가(버스트)만 의심한다 — 급등 직후의 "기준선 복귀"도
            # 큰 음의 편차로 잡혀버려 바로 다음 재급등을 연속 스트릭으로 오인하는 걸 막는다.
            and feature["delta_pps"] > baseline_before
            and feature["delta_pps"] < self.sub_flood_pps
            and feature["bpp"] <= BPP_ATTACK_MAX
        )
        guard = self._streaks.setdefault(key, StreakGuard(self._consecutive_required))
        confirmed = guard.observe(suspicious)

        if not suspicious and not confirmed:
            return AttackCategory.NORMAL, False

        category = (
            AttackCategory.SLOW_DRIFT
            if guard.streak >= self._sustained_ticks_for_slow
            else AttackCategory.PORT_SCAN
        )
        return category, confirmed
