"""Self-Defending SDN Tower - EWMA 기반 경량 시계열 이상 탐지기.

Isolation Forest(AnomalyModel)는 매 관측치를 독립적으로 판단하는 점별(point-wise)
탐지기라, SYN Flood처럼 수치가 확 튀는 공격은 잘 잡지만, Slowloris 같은 Slow
DDoS처럼 서서히 기준선에서 벗어나는 패턴은 놓치기 쉽다. EWMA(지수 가중 이동평균)
기반 통계적 공정관리(SPC) 기법으로 이 틈을 보완한다.

model/attack_classifier.py의 SLOW_DRIFT 분류에 쓰인다.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class _EwmaState:
    mean: float
    variance: float
    initialized: bool = False


class EwmaDetector:
    """하나의 피처 값 스트림에 대해 EWMA 평균/분산을 추적하고,
    현재 값이 그 평균에서 k*표준편차 이상 벗어나면 이상으로 판정한다."""

    def __init__(self, alpha: float = 0.3, k: float = 3.0, min_std: float = 1e-6, warmup: int = 5):
        if not 0.0 < alpha <= 1.0:
            raise ValueError("alpha는 0과 1 사이여야 합니다.")
        self.alpha = alpha
        self.k = k
        self.min_std = min_std
        self.warmup = warmup
        self._count = 0
        self._state = _EwmaState(mean=0.0, variance=0.0, initialized=False)

    def observe(self, value: float) -> bool:
        """값을 반영하고, 이상치 여부를 반환한다.

        초기화 직후에는 분산이 0에 가까워, 아주 작은 편차에도 k*std를 넘어서버려
        거의 항상 오탐이 난다 (분산이 아직 쌓이지 않았기 때문). warmup 관측치
        동안은 분산만 쌓고 판정은 내리지 않는다 (표준적인 SPC 번인 구간).
        """
        self._count += 1
        if not self._state.initialized:
            self._state = _EwmaState(mean=value, variance=0.0, initialized=True)
            return False

        deviation = value - self._state.mean
        std = max(self._state.variance ** 0.5, self.min_std)
        is_anomaly = self._count > self.warmup and abs(deviation) > self.k * std

        # 평균은 계속 적응시킨다 (공격이 끝나고 정상으로 복귀했을 때 다시 기준선으로
        # 따라붙어야 하므로). 분산은 warmup 구간에서만 학습하고 이후엔 고정한다 —
        # 계속 갱신하면 "서서히 커지는 드리프트" 자체가 매 스텝 분산에 반영되어
        # "정상 변동 폭"으로 재학습되어 버린다. 그러면 드리프트가 아무리 계속돼도
        # 편차와 임계값이 같이 커져서 결국 다시 "정상"으로 판정되는 문제가
        # 실측으로 확인됐다 (deviation·std가 같은 값으로 수렴해버림). SPC 관리도에서
        # 관리한계를 최초 기준 구간에서만 추정하고 이후 고정하는 것과 같은 이유다.
        self._state.mean += self.alpha * deviation
        if self._count <= self.warmup:
            self._state.variance = (1 - self.alpha) * (self._state.variance + self.alpha * deviation ** 2)

        return is_anomaly

    @property
    def mean(self) -> float:
        return self._state.mean

    @property
    def std(self) -> float:
        return max(self._state.variance ** 0.5, self.min_std)
