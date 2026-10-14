"""Self-Defending SDN Tower - DDoS 외 공격 유형 분류 (Port Scan, Slow 공격).

DDoS(SYN/UDP/ICMP Flood)는 model/detection_guard.py(DetectionGuard)가 이미
담당한다. 이 모듈은 그 외에 SDN 포트 통계(5대 피처)만으로 구분 가능한 공격
패턴을 추가한다.

중요한 한계 (정직하게 밝혀둠): Ryu가 주는 포트 통계는 L4 프로토콜(TCP/UDP/
ICMP)을 구분하지 못한다. SYN Flood와 UDP/ICMP Flood는 포트 레벨에서는
"BPP가 극히 작고 PPS가 치솟는다"는 동일한 신호로 보여서, 이 셋을 억지로
구분하지 않고 VOLUMETRIC_FLOOD 하나로 묶는다(= 기존 DetectionGuard가 잡는
범위 그대로, threat_type 이름만 SSOT 계약에 맞춰 매핑). 대신 패킷 볼륨 신호와
무관하게 구분 가능한 두 가지 새 패턴을 추가한다:

  - PORT_SCAN: 에러율(err_rate)이 평소보다 뚜렷하게 높아지는데 PPS/BPP는
    딱히 튀지 않는 패턴 (닫힌 포트로의 연결 시도 → RST/ICMP unreachable 누적).
  - SLOW_DRIFT: Isolation Forest의 점별(point-wise) 판단으로는 못 잡는 "서서히
    기준선을 벗어나는" 패턴 (Slowloris류 Slow DDoS의 프록시 신호, EWMA로 탐지).
    포트 통계만으로는 "연결을 오래 열어두고 있다"는 진짜 신호(연결 지속시간,
    반쯤 열린 연결 수)를 볼 수 없어서 완벽한 탐지는 아니다 — 자세한 한계와
    향후 확장 방향은 PR 설명/리포트에 정리했다.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, Tuple

from harness.contracts import ThreatType
from model.ewma_detector import EwmaDetector

ERR_RATE_SCAN_MIN = 0.3  # 정상 트래픽의 err_rate는 0에 가까움 (실측값, defense_scenarios.md §3.1)
DETECT_CONSECUTIVE = 2  # model/detection_guard.py와 동일한 오탐 방지 기준

PortKey = Tuple[int, int]


class AttackCategory(str, Enum):
    NORMAL = "NORMAL"
    VOLUMETRIC_FLOOD = "VOLUMETRIC_FLOOD"  # SYN/UDP/ICMP Flood - 포트 통계로는 서로 구분 불가
    PORT_SCAN = "PORT_SCAN"
    SLOW_DRIFT = "SLOW_DRIFT"


# AnomalyAlertMessage.threat_type은 harness.contracts.ThreatType의 값 그대로 쓴다 (SSOT 일치).
CATEGORY_TO_THREAT_TYPE: Dict[AttackCategory, str] = {
    AttackCategory.VOLUMETRIC_FLOOD: ThreatType.SYN_FLOOD_SPOOFING.value,
    AttackCategory.PORT_SCAN: ThreatType.PORT_SCAN.value,
    AttackCategory.SLOW_DRIFT: ThreatType.SLOW_DDOS.value,
}


class StreakGuard:
    """N번 연속 의심스러워야 확정하는 범용 플래핑 방지 게이트.

    model/detection_guard.py의 DetectionGuard와 같은 패턴이지만 BPP/score에
    고정되지 않은 범용 버전 — PORT_SCAN/SLOW_DRIFT처럼 서로 다른 조건을 쓰는
    공격 유형에도 재사용한다.
    """

    def __init__(self, consecutive_required: int = DETECT_CONSECUTIVE):
        self.consecutive_required = consecutive_required
        self._streak = 0

    def observe(self, suspicious: bool) -> bool:
        self._streak = self._streak + 1 if suspicious else 0
        return self._streak >= self.consecutive_required


class SecondaryAttackClassifier:
    """VOLUMETRIC_FLOOD 이외의 공격 유형(PORT_SCAN, SLOW_DRIFT)을 포트별로 추적한다.

    VOLUMETRIC_FLOOD는 이 분류기의 책임이 아니다 — 기존에 실측 검증된
    DetectionGuard 경로를 그대로 두고, 이 분류기는 그와 독립적으로 매 관측치마다
    병행 실행된다 (한 포트가 동시에 플러드와 포트 스캔을 당할 수도 있으므로).
    """

    def __init__(
        self,
        ewma_feature: str = "err_rate",
        ewma_alpha: float = 0.3,
        ewma_k: float = 3.0,
        consecutive_required: int = DETECT_CONSECUTIVE,
    ):
        self.ewma_feature = ewma_feature
        self._ewma_alpha = ewma_alpha
        self._ewma_k = ewma_k
        self._consecutive_required = consecutive_required
        self._ewma: Dict[PortKey, EwmaDetector] = {}
        self._streaks: Dict[PortKey, Dict[AttackCategory, StreakGuard]] = {}

    def observe(self, feature: dict) -> Tuple[AttackCategory, bool]:
        """피처 1건을 반영해 (분류, 확정 여부)를 반환한다.

        분류는 NORMAL일 수 있다 (아직 의심 조건을 못 만족한 상태). 확정은
        같은 포트에서 같은 분류가 consecutive_required 주기 연속 나와야 True.
        """
        key: PortKey = (feature["dpid"], feature["port_no"])
        ewma = self._ewma.setdefault(key, EwmaDetector(alpha=self._ewma_alpha, k=self._ewma_k))
        trend_anomaly = ewma.observe(feature[self.ewma_feature])

        if feature["err_rate"] >= ERR_RATE_SCAN_MIN:
            category = AttackCategory.PORT_SCAN
        elif trend_anomaly:
            category = AttackCategory.SLOW_DRIFT
        else:
            category = AttackCategory.NORMAL

        streaks = self._streaks.setdefault(key, {})
        if category == AttackCategory.NORMAL:
            for guard in streaks.values():
                guard.observe(False)
            return category, False

        for other_category, guard in streaks.items():
            if other_category != category:
                guard.observe(False)
        confirmed = streaks.setdefault(category, StreakGuard(self._consecutive_required)).observe(True)
        return category, confirmed
