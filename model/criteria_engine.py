"""Self-Defending SDN Tower - 공격 종류별 판단 기준 엔진 (8주차 기준표의 구현).

입력은 컨트롤러가 2초마다 발행하는 접속 포트별·종류별 패킷 수(`sdn:stats:flowcount`)이고, 출력은
포트마다의 위험도 단계와 공격 종류다. 기준표(docs/specs/attack_criteria.md)를 그대로 따른다:

* 평소 범위 기준선 = max(평균 + 3 × 표준편차, 최소값). 지표 하나라도 넘으면 주의(WATCH).
* 공격 종류별 규칙 (판정선을 넘은 상태가 2회 연속이면 확정):
    - SYN Flood : SYN − (FIN+RST) 차이가 기준선을 넘는 동안의 누적(CUSUM)이 H 이상
    - UDP Flood : UDP 초당 수 ≥ max(N × 평소 평균, 공격 최소 규모)
    - ICMP Flood: ICMP 초당 수 ≥ max(N × 평소 평균, 공격 최소 규모)
    - Slow HTTP : 서버 연결 수집기가 센 이 호스트의 '느린 요청' 연결(20초 넘게 요청이 안 끝남, 초당 500B 미만)이나
                  '안 끝난 요청' 연결(요청을 시작하고 5초 넘게 안 끝남, 초당 500B 미만) 중 큰 쪽이 10개 이상
    - 포트 스캔 : 이 호스트가 받은 실패 응답(RST + ICMP 도달 불가)으로 판단한다.
                  빠른 스캔 = 짧은 창(2주기, 약 4초)에 15개 이상(Zeek)이고 보낸 연결 시도(SYN + UDP)의
                  절반 이상이 실패(Jung 2004). 느린 스캔 = 긴 창(5분, Zeek)에 30개 이상이고 지금도 실패가
                  나오는 중(짧은 창에 1개 이상). 긴 창에는 정상 연결도 수백 개 섞이므로 비율은 보지 않는다.
                  UDP 스캔은 대상 서버가 ICMP 도달 불가를 처음 6개 뒤 초당 1개로 제한해서(리눅스 기본값)
                  응답이 적으므로, 짧은 창에 도달 불가 4개 이상이면 따로 스캔으로 본다.
                  망 정책이 입구에서 버리면 실패 응답이 없으므로, 서버 · DMZ의 허용 안 된 포트나 외부에서 막힌
                  패킷(zone_deny_port_scan · zone_deny_external)이 짧은 창에 15개 이상이어도 스캔으로 본다
                  (같은 PC가 UDP · ICMP Flood 크기로 보내는 중이면 Flood의 일부로 보고 스캔으로 세지 않는다)
    - 내부 확산 : 이 호스트가 ARP로 물어본 '없는 내부 주소'(컨트롤러가 셈)가 5분에 25개 이상이고 지금도 늘어나는 중
                  (Zeek: 5분 안에 서로 다른 호스트 25개 연결 실패), 또는 옆 사용자 · 관리망으로 가려다 망 정책에
                  막힌 패킷(zone_deny_internal)이 짧은 창에 10개 이상
* 확정된 공격의 세기(값 / 판정선)가 M 이상이면 위험(DANGER, 격리 + 우회), 아니면 경고(WARNING, 속도 제한).
  세기가 M 미만이어도 서비스가 나빠졌으면(컨트롤러의 서비스 상태 확인 ping 손실·지연이 2회 연속 기준 이상) 위험.
* 평소값: 미리 학습해 저장한 값(criteria_baseline.json)으로 시작하고, 정상일 때만 2초마다 EWMA로
  갱신한다(최근 약 10분 기억). 갱신된 평균·표준편차는 사전 학습값 ~ 2배 사이에서만 움직인다.
* 특수 상황 재학습: 관리자가 승인한 기간 동안은 양(SYN·UDP·ICMP 초당 수)만 상하한 없이 빠르게(최근 약 1분)
  다시 배우고, 기간이 끝나면 사전 학습값으로 돌아간다. 짝이 안 맞는 연결·실패 응답 같은 공격 신호는 다시 배우지 않는다.

참고문헌(전체 서지 정보는 docs/specs/attack_criteria.md §6): CUSUM(SYN Flood)은 Wang·Zhang·Shin 2002[4],
포트 스캔 실패 비율(TRW)은 Jung et al. 2004[5], Zeek 스캔 임계치는 Paxson 1999[6], 내부 확산 차단 설계는
Weaver et al. 2004[7], 평균+3σ EWMA 기준선은 Ye·Borror·Zhang 2002[8], Slow HTTP 분류는 Cambiaso et al. 2013[9],
Flood 유형 분류는 Mirkovic·Reiher 2004[10]을 따른다.
"""

from __future__ import annotations

import json
import math
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Deque, Dict, Iterable, List, Optional, Tuple

from harness.contracts import (
    ACCESS_HOST_PORTS,
    FlowCountMessage,
    RiskStage,
    ServerConnMessage,
    ServiceHealthMessage,
    ThreatType,
)

PortKey = Tuple[int, int]
# 주의(WATCH) 판단에 쓰는 지표. gap = syn − (fin + rst), fail = rst_in + unreach_in (모두 초당)
WATCHED_INDICATORS = ("syn", "udp", "icmp", "gap", "fail")
DEFAULT_BASELINE_PATH = "model/criteria_baseline.json"


@dataclass(frozen=True)
class CriteriaConfig:
    """판단 기준 숫자. 정상 10분 측정의 최댓값에 2배 여유를 두고 정했다 (docs/specs/attack_criteria.md)."""

    k_sigma: float = 3.0
    # 평소 범위 최소값(초당) = 정상 최댓값의 2배를 10 단위로 올림.
    # 정상 최댓값(1초 보고, 10분): SYN 55 (몰림), SYN 차이 8, UDP 4, ICMP 19.2 (ping 0.05초 간격), 실패 응답 1
    floors: Dict[str, float] = field(default_factory=lambda: {
        "syn": 110.0, "udp": 10.0, "icmp": 40.0, "gap": 20.0, "fail": 10.0})
    # UDP·ICMP Flood: 평소 평균의 N배이면서 공격 최소 규모 이상.
    # N = 정상에서 본 최대 배율(2초 보고 UDP 최대 2.5 / 평균 0.49 ≈ 5배)의 2배. 1초 보고에서는 UDP가 8배까지 튀지만
    # 평균이 초당 0.5개라 판정선은 공격 최소 규모(50)가 정한다. N이 실제로 쓰이는 ICMP(평균 18)는 최대 1.06배
    flood_multiplier: float = 10.0
    # 공격 최소 규모(초당) = 측정한 약한 공격(초당 100개)의 절반 → 약한 공격도 2배 여유로 잡힌다
    attack_floors: Dict[str, float] = field(default_factory=lambda: {"udp": 50.0, "icmp": 50.0, "gap": 50.0})
    # SYN Flood: 기준선을 넘은 차이의 누적(패킷). 약한 공격(초당 100개)은 1초 보고 한 번(초과분 약 80개)에 넘는다
    cusum_h: float = 50.0
    # 포트 스캔: 빠른 스캔(짧은 창 4초)과 느린 스캔(긴 창 5분)의 실패 응답 수.
    # 정상 최대: 짧은 창 2개, 긴 창 13개, 도달 불가 짧은 창 2개
    scan_min: float = 15.0
    scan_ratio: float = 0.5
    scan_window_sec: float = 4.0
    scan_long_min: float = 30.0
    scan_long_window_sec: float = 300.0
    scan_unreach_min: float = 4.0
    # 확정된 공격의 세기(값 / 판정선)가 M 이상이면 경고를 건너뛰고 위험.
    # 측정한 약한 공격은 2배, 강한 공격(초당 1000개)은 20배 → 그 사이의 5배
    strong_multiplier: float = 5.0
    # 공격 종류 확정 = 판정선을 넘은 보고가 이만큼 연속 (보고 주기는 컨트롤러가 정한다: FLOW_COUNT_INTERVAL_SEC)
    confirm_intervals: int = 2
    # 주의는 4초 연속 정상이면 해제, 학습은 10초 연속 정상부터 재개
    watch_clear_sec: float = 4.0
    learn_resume_sec: float = 10.0
    # EWMA: 최근 약 10분을 기억 (보고 주기 dt마다 α = 2 / (600 / dt + 1), 2초 주기면 2 / 301)
    ewma_memory_sec: float = 600.0
    # 갱신된 평소값의 상한 = 사전 학습값 × cap_multiplier (하한 = 사전 학습값)
    cap_multiplier: float = 2.0
    # 서비스 악화: 서비스 상태 확인 ping의 손실(%) 또는 평균 왕복 시간(ms)이 이 값 이상인 보고가 health_confirm번 연속.
    # 정상 10분 최대: 손실 11.1%(ping 1개, 연속 없음), 평균 왕복 5.7ms(1초 개수 요청 포함) → 2배 여유로 25%, 12ms.
    # 보고가 health_stale_sec보다 오래됐으면(컨트롤러 확인 중단) 쓰지 않는다
    health_loss_percent: float = 25.0
    health_rtt_ms: float = 12.0
    health_confirm: int = 2
    health_stale_sec: float = 6.0
    # 특수 상황 재학습(관리자 승인): 다시 배우는 지표와 속도 (최근 약 1분 기억)
    relearn_indicators: Tuple[str, ...] = ("syn", "udp", "icmp")
    relearn_memory_sec: float = 60.0
    # 내부 확산: 긴 창(5분)에 물어본 없는 내부 주소 수 (Zeek 25개)
    spread_min: float = 25.0
    # 망 경계 위반: 짧은 창(4초)에 망 정책(Table 1)이 버린 패킷 수. 컨트롤러가 무엇을 막았는지에 따라 셋으로 나눠 보낸다:
    #   zone_deny_internal (옆 사용자 · 관리망으로 가려던 것)        → 내부 확산, zone_deny_min개 이상
    #   zone_deny_port_scan (서버 · DMZ의 허용 안 된 포트)          → 포트 스캔, scan_min개 이상 (Zeek 15개)
    #   zone_deny_external (외부에서 허용 안 된 곳으로 들어오려던 것) → 포트 스캔, scan_min개 이상
    # 막힌 서버 포트 패킷은 같은 PC가 UDP · ICMP Flood 크기로 보내는 중이면 Flood의 일부로 본다 (무작위 포트 UDP Flood)
    zone_deny_min: float = 10.0
    # Slow HTTP: 한 PC의 느린 요청(20초) · 안 끝난 요청(5초) 연결 수 중 큰 쪽. 정상 측정에서는 둘 다 0개
    slow_http_min: float = 10.0
    server_conn_stale_sec: float = 6.0


@dataclass
class Baseline:
    mean: float = 0.0
    var: float = 0.0
    base_mean: float = 0.0
    base_std: float = 0.0

    @property
    def std(self) -> float:
        return math.sqrt(max(self.var, 0.0))

    def update(self, x: float, alpha: float, cap: float) -> None:
        delta = x - self.mean
        self.mean += alpha * delta
        self.var = (1 - alpha) * (self.var + alpha * delta * delta)
        # 사전 학습값 ~ cap배 사이에서만 움직인다 (천천히 키우는 공격에 끌려가지 않게, 한산할 때 너무 낮아지지 않게)
        self.mean = min(max(self.mean, self.base_mean), cap * self.base_mean)
        std = min(max(self.std, self.base_std), cap * self.base_std)
        self.var = std * std

    def follow(self, x: float, alpha: float) -> None:
        """승인된 재학습: 상하한 없이 따라간다."""
        delta = x - self.mean
        self.mean += alpha * delta
        self.var = (1 - alpha) * (self.var + alpha * delta * delta)

    def reset(self) -> None:
        """사전 학습값으로 되돌린다."""
        self.mean, self.var = self.base_mean, self.base_std * self.base_std


@dataclass
class Decision:
    dpid: int
    port: int
    stage: RiskStage
    threat_type: Optional[str]
    strength: float
    rates: Dict[str, float]
    lines: Dict[str, float]
    reasons: List[str]


@dataclass
class _PortState:
    prev_t: Optional[float] = None
    prev_counts: Dict[str, int] = field(default_factory=dict)
    baselines: Dict[str, Baseline] = field(default_factory=dict)
    cusum: float = 0.0
    streaks: Dict[str, int] = field(default_factory=dict)
    # (보고 시각, 실패 응답, 도달 불가, 연결 시도, 없는 내부 주소, 막힌 내부 확산, 막힌 서버 · 외부 접근) — 보고 주기마다 개수
    window: Deque[Tuple[float, float, float, float, float, float, float]] = field(default_factory=deque)
    stage: RiskStage = RiskStage.NORMAL
    normal_for: float = 0.0  # 연속으로 정상이었던 시간(초)
    relearn_until: float = 0.0  # 관리자가 승인한 재학습이 끝나는 시각 (0 = 재학습 아님)


def _alpha(memory_sec: float, dt: float) -> float:
    """EWMA 계수: 보고 주기 dt로 최근 memory_sec초를 기억한다 (α = 2 / (N + 1), N = 기억할 보고 수)."""
    return 2.0 / (memory_sec / dt + 1.0)


def indicator_rates(counts: Dict[str, int], prev: Dict[str, int], dt: float) -> Optional[Dict[str, float]]:
    """누적 카운트 두 개 → 종류별 초당 수 + 파생 지표. 카운터가 줄었으면(리셋) None."""
    if dt <= 0 or any(counts.get(k, 0) < prev.get(k, 0) for k in counts):
        return None
    r = {k: (counts.get(k, 0) - prev.get(k, 0)) / dt for k in counts}
    r["gap"] = r.get("syn", 0.0) - r.get("fin", 0.0) - r.get("rst", 0.0)
    r["fail"] = r.get("rst_in", 0.0) + r.get("unreach_in", 0.0)
    return r


class CriteriaEngine:
    """FlowCountMessage를 받을 때마다 포트별 위험도 단계를 판단한다 (Redis와 분리, 테스트 가능)."""

    def __init__(self, config: Optional[CriteriaConfig] = None,
                 baselines: Optional[Dict[PortKey, Dict[str, Tuple[float, float]]]] = None,
                 ports: Optional[Iterable[PortKey]] = None,
                 host_ports: Optional[Dict[str, PortKey]] = None) -> None:
        self.config = config or CriteriaConfig()
        self.ports = set(ports) if ports is not None else None
        self._state: Dict[PortKey, _PortState] = {}
        self._health: Deque[ServiceHealthMessage] = deque(maxlen=self.config.health_confirm)
        self._port_ips = {key: ip for ip, key in (host_ports or ACCESS_HOST_PORTS).items()}
        self._slow: Dict[str, Tuple[int, int, float]] = {}  # 호스트 IP → (느린 요청 수, 안 끝난 요청 수, 보고 시각)
        for key, inds in (baselines or {}).items():
            st = self._state.setdefault(key, _PortState())
            for ind, (mean, std) in inds.items():
                st.baselines[ind] = Baseline(mean=mean, var=std * std, base_mean=mean, base_std=std)

    # ------------------------------------------------------------------
    def line(self, key: PortKey, ind: str) -> float:
        """평소 범위 기준선 = max(평균 + kσ, 최소값)."""
        b = self._state.get(key, _PortState()).baselines.get(ind, Baseline())
        return max(b.mean + self.config.k_sigma * b.std, self.config.floors.get(ind, 0.0))

    def attack_line(self, key: PortKey, ind: str) -> float:
        """UDP·ICMP·SYN 차이의 공격 판정선 = max(N × 평소 평균, 공격 최소 규모)."""
        b = self._state.get(key, _PortState()).baselines.get(ind, Baseline())
        return max(self.config.flood_multiplier * b.mean, self.config.attack_floors.get(ind, 0.0))

    def baseline(self, key: PortKey, ind: str) -> Baseline:
        return self._state.setdefault(key, _PortState()).baselines.setdefault(ind, Baseline())

    # ------------------------------------------------------------------
    def update_health(self, message: ServiceHealthMessage) -> None:
        """컨트롤러의 서비스 상태 확인 결과 (2초마다)."""
        self._health.append(message)

    def approve_relearn(self, until: float, key: Optional[PortKey] = None) -> List[PortKey]:
        """관리자가 승인한 특수 상황 재학습. key가 없으면 지켜보는 모든 포트. 대상 포트 목록을 돌려준다."""
        keys = [key] if key is not None else sorted(set(self._state) | (self.ports or set()))
        for k in keys:
            self._state.setdefault(k, _PortState()).relearn_until = until
        return keys

    def update_server_conns(self, message: ServerConnMessage) -> None:
        """서버 연결 수집기의 보고 (1초마다): 접속한 PC마다 느린 요청 · 안 끝난 요청 수."""
        self._slow = {c.client_ip: (c.slow, c.pending, message.timestamp) for c in message.clients}

    def _slow_requests(self, key: PortKey, now: float) -> Tuple[int, int]:
        slow, pending, ts = self._slow.get(self._port_ips.get(key, ""), (0, 0, 0.0))
        return (slow, pending) if now - ts <= self.config.server_conn_stale_sec else (0, 0)

    def _health_degraded(self, m: ServiceHealthMessage) -> bool:
        cfg = self.config
        return m.sent > 0 and (m.loss_percent >= cfg.health_loss_percent
                               or (m.rtt_avg_ms is not None and m.rtt_avg_ms >= cfg.health_rtt_ms))

    def service_degraded(self, now: float) -> Optional[str]:
        """최근 health_confirm번의 확인이 모두 나빴으면 그 이유, 아니면 None."""
        recent = list(self._health)
        if (len(recent) < self.config.health_confirm or now - recent[-1].timestamp > self.config.health_stale_sec
                or not all(self._health_degraded(m) for m in recent)):
            return None
        last = recent[-1]
        rtt = f"{last.rtt_avg_ms:.1f}ms" if last.rtt_avg_ms is not None else "no reply"
        return f"service degraded: loss {last.loss_percent:.0f}%, rtt {rtt}"

    # ------------------------------------------------------------------
    def update(self, message: FlowCountMessage) -> List[Decision]:
        by_port: Dict[int, Dict[str, int]] = {}
        for c in message.counts:
            by_port.setdefault(c.port_no, {})[c.kind] = c.packets
        decisions = []
        for port, counts in sorted(by_port.items()):
            key = (message.dpid, port)
            if self.ports is not None and key not in self.ports:
                continue
            st = self._state.setdefault(key, _PortState())
            prev_t, prev = st.prev_t, st.prev_counts
            st.prev_t, st.prev_counts = message.timestamp, counts
            if prev_t is None:
                continue
            dt = message.timestamp - prev_t
            rates = indicator_rates(counts, prev, dt)
            if rates is None:
                continue
            decisions.append(self._evaluate(key, st, rates, dt, message.timestamp))
        return decisions

    def _evaluate(self, key: PortKey, st: _PortState, r: Dict[str, float], dt: float, now: float) -> Decision:
        cfg = self.config
        relearning = now < st.relearn_until
        if st.relearn_until and not relearning:
            # 승인 기간이 끝남: 다시 배운 양을 사전 학습값으로 되돌린다
            st.relearn_until = 0.0
            for ind in cfg.relearn_indicators:
                self.baseline(key, ind).reset()
        lines = {ind: self.line(key, ind) for ind in WATCHED_INDICATORS}
        reasons = [f"{ind} {r.get(ind, 0.0):.0f}/s > {lines[ind]:.0f}" for ind in WATCHED_INDICATORS
                   if r.get(ind, 0.0) > lines[ind]]

        candidates: Dict[str, float] = {}
        # Slow HTTP: 서버가 응답도 못 하고 붙잡고 있는 이 PC의 연결. 안 끝난 요청(5초)으로 일찍 보고,
        # 요청 없이 열어만 둔 연결은 느린 요청(20초)으로 본다
        slow, pending = self._slow_requests(key, now)
        if slow or pending:
            reasons.append(f"slow requests {slow}, unfinished {pending}")
        if max(slow, pending) >= cfg.slow_http_min:
            candidates[ThreatType.SLOW_DDOS.value] = max(slow, pending) / cfg.slow_http_min
        # 포트 스캔: 받은 실패 응답 수. 빠른 스캔(Zeek 15개 + TRW 실패 비율), 느린 스캔(5분 30개),
        # UDP 스캔(도달 불가 4개). 세기는 그중 가장 큰 배율
        # 실패 응답은 이 PC가 보낸 연결 시도에 대한 답이어야 스캔이다: 한 주기에 보낸 시도의 2배까지만 센다.
        # (서버가 이 PC의 오래된 연결을 한꺼번에 끊으며 보낸 RST 묶음 같은 것은 스캔이 아니다)
        probes = (r.get("syn", 0.0) + r.get("udp", 0.0)) * dt
        # 망 정책이 버린 패킷 (zone_deny는 종류를 나누기 전의 이름, 옆 PC로 가려던 것과 같이 본다)
        denied_internal = (r.get("zone_deny", 0.0) + r.get("zone_deny_internal", 0.0)) * dt
        denied_probe = (r.get("zone_deny_port_scan", 0.0) + r.get("zone_deny_external", 0.0)) * dt
        st.window.append((now, min(r["fail"] * dt, 2 * probes), min(r.get("unreach_in", 0.0) * dt, 2 * probes),
                          probes, r.get("arp_fail", 0.0) * dt, denied_internal, denied_probe))
        # 창은 시간으로 자른다 (보고 시각이 조금씩 흔들려도 같은 개수가 들어가게 반 주기 여유)
        while st.window and st.window[0][0] <= now - cfg.scan_long_window_sec + dt / 2:
            st.window.popleft()
        recent = [w for w in st.window if w[0] > now - cfg.scan_window_sec + dt / 2]
        fails = sum(w[1] for w in recent)
        fails_long = sum(w[1] for w in st.window)
        unreach = sum(w[2] for w in recent)
        recent_denied_internal = sum(w[5] for w in recent)
        recent_denied_probe = sum(w[6] for w in recent)
        flood_sized = any(r.get(ind, 0.0) >= self.attack_line(key, ind) and r.get(ind, 0.0) > lines[ind]
                          for ind in ("udp", "icmp"))
        scan = []
        if fails >= cfg.scan_min and fails >= cfg.scan_ratio * sum(w[3] for w in recent):
            scan.append(fails / cfg.scan_min)
        if fails_long >= cfg.scan_long_min and fails > 0:
            scan.append(fails_long / cfg.scan_long_min)
        if unreach >= cfg.scan_unreach_min:
            scan.append(unreach / cfg.scan_unreach_min)
        if recent_denied_probe:
            reasons.append(f"blocked probes {recent_denied_probe:.0f}")
        if recent_denied_probe >= cfg.scan_min and not flood_sized:
            scan.append(recent_denied_probe / cfg.scan_min)
        if scan:
            candidates[ThreatType.PORT_SCAN.value] = max(scan)
        # 내부 확산:
        # 1) 없는 내부 주소를 5분에 25개 이상 찾아다녔고, 최근 4초에도 새 주소가 있음 (ARP 스캔)
        # 2) 망 정책 위반(ZONE_DENY, SMB 445 등 타 단말 침투 시도)이 최근 4초에 zone_deny_min 이상 발생
        spread_arp = sum(w[4] for w in st.window)
        spread_candidates = []
        if spread_arp >= cfg.spread_min and sum(w[4] for w in recent) > 0:
            spread_candidates.append(spread_arp / cfg.spread_min)
        if recent_denied_internal:
            reasons.append(f"zone_deny {recent_denied_internal:.0f}")
        if recent_denied_internal >= cfg.zone_deny_min:
            spread_candidates.append(recent_denied_internal / cfg.zone_deny_min)

        if spread_candidates:
            candidates[ThreatType.INTERNAL_SPREAD.value] = max(spread_candidates)
        # SYN Flood: 기준선을 넘는 동안의 초과분 누적. 한 번이라도 기준선 아래로 내려오면 0부터 다시
        if r["gap"] > lines["gap"]:
            st.cusum += (r["gap"] - lines["gap"]) * dt
        else:
            st.cusum = 0.0
        if st.cusum >= cfg.cusum_h and ThreatType.PORT_SCAN.value not in candidates:
            candidates[ThreatType.SYN_FLOOD_SPOOFING.value] = r["gap"] / self.attack_line(key, "gap")
        # UDP·ICMP Flood
        for ind, threat in (("udp", ThreatType.UDP_FLOOD.value), ("icmp", ThreatType.ICMP_FLOOD.value)):
            a_line = self.attack_line(key, ind)
            if r.get(ind, 0.0) >= a_line and r.get(ind, 0.0) > lines[ind]:
                candidates[threat] = r[ind] / a_line

        for threat in set(st.streaks) | set(candidates):
            st.streaks[threat] = st.streaks.get(threat, 0) + 1 if threat in candidates else 0
        confirmed = {t: s for t, s in candidates.items() if st.streaks[t] >= cfg.confirm_intervals}

        threat_type: Optional[str] = None
        strength = 0.0
        if confirmed:
            threat_type, strength = max(confirmed.items(), key=lambda kv: kv[1])
            st.stage = RiskStage.DANGER if strength >= cfg.strong_multiplier else RiskStage.WARNING
            st.normal_for = 0.0
            reasons.append(f"{threat_type} x{strength:.1f}")
            # 약한 공격이어도 정상 사용자가 실제로 피해를 보고 있으면 위험 (서비스 악화 조건)
            degraded = self.service_degraded(now) if st.stage == RiskStage.WARNING else None
            if degraded:
                st.stage = RiskStage.DANGER
                reasons.append(degraded)
        elif reasons or candidates:
            st.stage = RiskStage.WATCH
            st.normal_for = 0.0
        else:
            st.normal_for += dt
            if st.normal_for >= cfg.watch_clear_sec - dt / 2:
                st.stage = RiskStage.NORMAL
            if st.normal_for >= cfg.learn_resume_sec - dt / 2:
                alpha = _alpha(cfg.ewma_memory_sec, dt)
                for ind in WATCHED_INDICATORS:
                    if not (relearning and ind in cfg.relearn_indicators):
                        self.baseline(key, ind).update(r.get(ind, 0.0), alpha, cfg.cap_multiplier)
        if relearning:
            reasons.append("relearning (approved)")
            # 승인된 기간: 양은 경고 중이어도 따라 배운다. 위험 크기(판정선의 M배 이상)는 승인 중에도 배우지 않는다
            for ind in cfg.relearn_indicators:
                b = self.baseline(key, ind)
                line = max(cfg.flood_multiplier * b.mean, cfg.attack_floors.get(ind, cfg.floors.get(ind, 0.0)))
                if r.get(ind, 0.0) < cfg.strong_multiplier * line:
                    b.follow(r.get(ind, 0.0), _alpha(cfg.relearn_memory_sec, dt))
        return Decision(dpid=key[0], port=key[1], stage=st.stage, threat_type=threat_type, strength=strength,
                        rates={k: round(v, 2) for k, v in r.items()}, lines=lines, reasons=reasons)


# ----------------------------------------------------------------------
# 사전 학습: 정상 구간의 초당 값들 → 포트·지표별 평균/표준편차 → JSON 파일
# ----------------------------------------------------------------------
class BaselineLearner:
    """정상 트래픽만 흐르는 동안 FlowCountMessage를 모아 평소값을 계산한다."""

    def __init__(self, ports: Optional[Iterable[PortKey]] = None) -> None:
        self.ports = set(ports) if ports is not None else None
        self._prev: Dict[PortKey, Tuple[float, Dict[str, int]]] = {}
        self.samples: Dict[PortKey, Dict[str, List[float]]] = {}

    def update(self, message: FlowCountMessage) -> None:
        by_port: Dict[int, Dict[str, int]] = {}
        for c in message.counts:
            by_port.setdefault(c.port_no, {})[c.kind] = c.packets
        for port, counts in by_port.items():
            key = (message.dpid, port)
            if self.ports is not None and key not in self.ports:
                continue
            prev = self._prev.get(key)
            self._prev[key] = (message.timestamp, counts)
            if prev is None:
                continue
            rates = indicator_rates(counts, prev[1], message.timestamp - prev[0])
            if rates is None:
                continue
            for ind in WATCHED_INDICATORS:
                self.samples.setdefault(key, {}).setdefault(ind, []).append(rates.get(ind, 0.0))

    def baselines(self) -> Dict[PortKey, Dict[str, Tuple[float, float]]]:
        out: Dict[PortKey, Dict[str, Tuple[float, float]]] = {}
        for key, inds in self.samples.items():
            for ind, vals in inds.items():
                mean = sum(vals) / len(vals)
                std = math.sqrt(sum((v - mean) ** 2 for v in vals) / len(vals))
                out.setdefault(key, {})[ind] = (round(mean, 3), round(std, 3))
        return out


def save_baselines(path: str, baselines: Dict[PortKey, Dict[str, Tuple[float, float]]], seconds: float) -> None:
    doc = {"version": 1, "learned_seconds": round(seconds),
           "ports": {f"{d}:{p}": {ind: {"mean": m, "std": s} for ind, (m, s) in inds.items()}
                     for (d, p), inds in sorted(baselines.items())}}
    Path(path).write_text(json.dumps(doc, ensure_ascii=False, indent=1))


def load_baselines(path: str) -> Optional[Dict[PortKey, Dict[str, Tuple[float, float]]]]:
    """저장된 평소값. 없으면 None (그때는 최소값만으로 판단한다 — 고정 기준)."""
    p = Path(path)
    if not p.exists():
        return None
    doc = json.loads(p.read_text())
    out: Dict[PortKey, Dict[str, Tuple[float, float]]] = {}
    for key, inds in doc.get("ports", {}).items():
        dpid, port = (int(x) for x in key.split(":"))
        out[(dpid, port)] = {ind: (v["mean"], v["std"]) for ind, v in inds.items()}
    return out
