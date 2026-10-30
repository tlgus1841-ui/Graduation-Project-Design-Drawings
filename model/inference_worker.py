"""Self-Defending SDN Tower - AI 추론 워커 (통계 → 판단 → 경보).

기본(판단 기준 모드): Ryu가 2초마다 발행하는 `sdn:stats:flowcount`(포트별·종류별 패킷 수)를
CriteriaEngine(model/criteria_engine.py, 8주차 기준표)으로 판단해, 경고(WARNING, 속도 제한)나
위험(DANGER, 격리 + 우회) 단계인 포트에 대해 `sdn:anomaly:alert`를 발행한다. 포트 통계
(`sdn:stats:port`)는 Isolation Forest 점수와 경보의 pps·bps·bpp 값을 채우는 데만 쓴다.

--legacy: 이전 방식. `sdn:stats:port`를 받아 FeatureExtractor의 5대 피처와 AnomalyModel(Isolation
Forest) 점수, DetectionGuard(BPP ≤ 80 그리고 점수 < 0, 2주기 연속)로 판단한다.

경보는 공격이 확정된 동안 매 주기 발행한다. 컨트롤러 FSM은 마지막 경보 시각부터 쿨다운을 재므로,
경보가 끊긴 뒤 10초가 지나야 자동 복구된다 (harness/safety/flapping_fsm.py).

감시 대상은 호스트가 붙은 접속(access) 포트뿐이다. 트렁크 포트는 컨트롤러가 어차피 막지 않고,
보호 호스트(정상 사용자·서버)가 붙은 포트도 경보 대상에서 뺀다 (화이트리스트).

실행 (Ryu·Redis 실행 중):
    uv run python -m model.inference_worker --model model/isolation_forest.joblib --log events.jsonl
    uv run python -m model.inference_worker --learn 600   # 정상 트래픽 10분으로 평소값 사전 학습 후 저장

실데이터 재학습/실데이터 F1 측정(--legacy Isolation Forest): pipeline/feature_extractor.py가 이미
Redis sdn:stats:port를 구독해 --label 0/1로 레이블링된 CSV를 기록하는 캡처 CLI를 제공한다
(uv run python pipeline/feature_extractor.py --label 0 --out dataset/real_normal.csv 등).
이 워커는 그 CSV를 --train-csv로 받아 학습하는 소비자 쪽이므로 별도 캡처 기능을 두지 않는다.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import signal
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from harness.contracts import (  # noqa: E402
    REDIS_CHANNEL_ANOMALY_ALERT,
    REDIS_CHANNEL_CONTROL_COMMAND,
    REDIS_CHANNEL_FLOW_COUNTS,
    REDIS_CHANNEL_PORT_STATS,
    REDIS_CHANNEL_SERVER_CONNS,
    REDIS_CHANNEL_SERVICE_HEALTH,
    AnomalyAlertMessage,
    ControlCommandMessage,
    DefenseAction,
    FlowCountMessage,
    PortStatsMessage,
    RiskStage,
    ServerConnMessage,
    ServiceHealthMessage,
)
from harness.safety.whitelist_guard import DEFAULT_ACCESS_PORTS  # noqa: E402
from model.attack_classifier import (  # noqa: E402
    CATEGORY_TO_THREAT_TYPE,
    AttackCategory,
    SecondaryAttackClassifier,
)
from model.criteria_engine import (  # noqa: E402
    DEFAULT_BASELINE_PATH,
    BaselineLearner,
    CriteriaEngine,
    Decision,
    load_baselines,
    save_baselines,
)
from model.detection_guard import DetectionGuard  # noqa: E402
from model.model import DEFAULT_MODEL_PATH, AnomalyModel  # noqa: E402
from pipeline.feature_extractor import FeatureExtractor  # noqa: E402

PortKey = Tuple[int, int]

# 보호 호스트가 붙은 접속 포트: S1:1 = H_legit(10.0.0.1), S4:1 = H_server(10.0.0.4)
PROTECTED_HOST_PORTS = {(1, 1), (4, 1)}
# 초당 100패킷 미만은 공격 규모가 아니다 (명세 §6 ATTACK_CEASE_PPS = 정상 PPS 상한).
MIN_ATTACK_PPS = 100.0
# 테스트베드 어느 링크보다도 큰 값. 이보다 크면 카운터 리셋으로 생긴 가짜 델타다.
MAX_PLAUSIBLE_PPS = 1e7


def watched_ports() -> List[PortKey]:
    """경보 대상 포트 = 접속 포트 - 보호 호스트 포트."""
    return sorted((dpid, port) for dpid, ports in DEFAULT_ACCESS_PORTS.items() for port in ports
                  if (dpid, port) not in PROTECTED_HOST_PORTS)


class InferenceWorker:
    """PortStatsMessage 한 건을 받아, 공격이 확정된 포트의 경보 목록을 돌려준다 (Redis와 분리, 테스트 가능)."""

    def __init__(self, model: AnomalyModel, ports: Optional[List[PortKey]] = None,
                 min_pps: float = MIN_ATTACK_PPS, criteria: Optional[CriteriaEngine] = None) -> None:
        self.model = model
        self.ports = set(ports if ports is not None else watched_ports())
        # 판단 기준 모드: 경보는 process_counts()만 낸다. 포트 통계는 점수·pps 기록용
        self.criteria = criteria
        self.last_features: Dict[PortKey, dict] = {}
        self.last_decisions: List[Decision] = []
        self.min_pps = min_pps
        self.extractor = FeatureExtractor()
        self.guards: Dict[PortKey, DetectionGuard] = {}
        # DDoS(volumetric flood)는 위 DetectionGuard가 전담한다 (실측 검증된 경로, 그대로 둔다).
        # 그 외 공격 유형(포트 스캔, Slow 공격)은 이 분류기가 독립적으로 병행 탐지한다 —
        # 한 포트가 동시에 플러드와 포트 스캔을 당할 수도 있으므로 서로 배타적이지 않다.
        self.secondary = SecondaryAttackClassifier()
        self.last_samples: List[dict] = []

    def process(self, message: PortStatsMessage) -> List[AnomalyAlertMessage]:
        alerts: List[AnomalyAlertMessage] = []
        self.last_samples = []
        for f in self.extractor.update(message):
            key = (f["dpid"], f["port_no"])
            if key not in self.ports or f["delta_pps"] > MAX_PLAUSIBLE_PPS:
                continue
            _, score = self.model.predict_single(f)
            self.last_features[key] = {**f, "score": score}
            if self.criteria is not None:
                self.last_samples.append({**f, "score": round(score, 4), "confirmed": False, "category": "criteria"})
                continue
            # Too little traffic to be a flood: feed an impossible BPP so the guard's streak resets.
            gate_bpp = f["bpp"] if f["delta_pps"] >= self.min_pps else math.inf
            flood_confirmed = self.guards.setdefault(key, DetectionGuard()).observe(gate_bpp, score)
            secondary_category, secondary_confirmed = self.secondary.observe(f)

            confirmed_category = (
                AttackCategory.VOLUMETRIC_FLOOD if flood_confirmed
                else secondary_category if secondary_confirmed
                else None
            )
            self.last_samples.append({
                **f, "score": round(score, 4),
                "confirmed": confirmed_category is not None,
                "category": (confirmed_category or secondary_category).value,
            })
            if confirmed_category is not None:
                alerts.append(AnomalyAlertMessage(
                    dpid=f["dpid"], in_port=f["port_no"],
                    threat_type=CATEGORY_TO_THREAT_TYPE[confirmed_category],
                    score=score, pps=f["delta_pps"], bps=f["delta_bps"], bpp=f["bpp"], err_rate=f["err_rate"],
                    metadata={"model": "isolation_forest", "stats_ts": str(f["timestamp"])}))
        return alerts

    def process_health(self, message: ServiceHealthMessage) -> None:
        """판단 기준 모드: 컨트롤러의 서비스 상태 확인 결과 (위험 단계의 서비스 악화 조건)."""
        if self.criteria is not None:
            self.criteria.update_health(message)

    def process_server_conns(self, message: ServerConnMessage) -> None:
        """판단 기준 모드: 서버 연결 수집기의 느린 요청 수 (Slow HTTP)."""
        if self.criteria is not None:
            self.criteria.update_server_conns(message)

    def process_command(self, cmd: ControlCommandMessage, now: Optional[float] = None) -> List[PortKey]:
        """관리자의 특수 상황 재학습 승인(RELEARN). 포트 0이면 지켜보는 모든 포트. 재학습할 포트 목록을 돌려준다."""
        if self.criteria is None or cmd.action != DefenseAction.RELEARN.value or not cmd.duration_sec:
            return []
        until = (time.time() if now is None else now) + cmd.duration_sec
        key = None if cmd.target_port == 0 else (cmd.target_dpid, cmd.target_port)
        return self.criteria.approve_relearn(until, key)

    def process_counts(self, message: FlowCountMessage) -> List[AnomalyAlertMessage]:
        """판단 기준 모드: 종류별 패킷 수 → 단계 판단 → 경고·위험 포트의 경보."""
        if self.criteria is None:
            return []
        self.last_decisions = [d for d in self.criteria.update(message) if (d.dpid, d.port) in self.ports]
        alerts: List[AnomalyAlertMessage] = []
        for d in self.last_decisions:
            if d.stage not in (RiskStage.WARNING, RiskStage.DANGER) or d.threat_type is None:
                continue
            f = self.last_features.get((d.dpid, d.port), {})
            alerts.append(AnomalyAlertMessage(
                dpid=d.dpid, in_port=d.port, threat_type=d.threat_type, stage=d.stage.value,
                # 점수: 판정선 대비 세기(배수)를 음수로 (낮을수록 이상, 기존 점수와 같은 방향)
                score=-round(d.strength, 3), pps=f.get("delta_pps", 0.0), bps=f.get("delta_bps", 0.0),
                bpp=f.get("bpp", 0.0), err_rate=f.get("err_rate", 0.0),
                metadata={"model": "criteria", "reasons": "; ".join(d.reasons), "stats_ts": str(message.timestamp),
                          "ai_score": f"{f.get('score', 0.0):.4f}"}))
        return alerts


def load_model(model_path: Path, train_csv: Optional[Path]) -> Tuple[AnomalyModel, str]:
    """저장된 모델 → 학습 CSV → 합성 데이터 순서로 모델을 준비한다."""
    if model_path.exists():
        return AnomalyModel.load(str(model_path)), f"loaded {model_path}"
    if train_csv is not None:
        model, source = AnomalyModel().fit(str(train_csv)), f"trained on {train_csv}"
    else:
        from model.synthetic_samples import build_labeled_dataset_csv
        csv_path = Path(tempfile.mkdtemp()) / "synthetic.csv"
        build_labeled_dataset_csv(str(csv_path))
        model, source = AnomalyModel().fit(str(csv_path)), "trained on synthetic samples (no real-traffic CSV given)"
    model.save(str(model_path))
    return model, source


def run(worker: InferenceWorker, redis_url: str, log_path: Optional[Path]) -> None:
    import redis

    r = redis.Redis(connection_pool=redis.ConnectionPool.from_url(redis_url))
    pubsub = r.pubsub()
    pubsub.subscribe(REDIS_CHANNEL_PORT_STATS, REDIS_CHANNEL_CONTROL_COMMAND, REDIS_CHANNEL_FLOW_COUNTS,
                     REDIS_CHANNEL_SERVICE_HEALTH, REDIS_CHANNEL_SERVER_CONNS)
    log = log_path.open("w", encoding="utf-8") if log_path else None

    def record(kind: str, **fields: object) -> None:
        if log:
            log.write(json.dumps({"t": time.time(), "kind": kind, **fields}, ensure_ascii=False) + "\n")
            log.flush()

    stop = {"flag": False}
    signal.signal(signal.SIGTERM, lambda *_: stop.__setitem__("flag", True))
    signal.signal(signal.SIGINT, lambda *_: stop.__setitem__("flag", True))
    record("start", watch=[f"S{d}:{p}" for d, p in sorted(worker.ports)])
    print(f"[inference_worker] watching {sorted(worker.ports)}", flush=True)

    while not stop["flag"]:
        item = pubsub.get_message(timeout=0.5)
        if not item or item.get("type") != "message":
            continue
        channel = item["channel"].decode() if isinstance(item["channel"], bytes) else item["channel"]
        if channel == REDIS_CHANNEL_CONTROL_COMMAND:
            # Logged so one file holds the alert → command timeline for the E2E analysis.
            cmd = ControlCommandMessage.model_validate_json(item["data"])
            record("command", action=cmd.action, target=f"S{cmd.target_dpid}:{cmd.target_port}",
                   command_id=cmd.command_id)
            relearn = worker.process_command(cmd)
            if relearn:
                record("relearn", ports=[f"S{d}:{p}" for d, p in relearn], seconds=cmd.duration_sec)
            continue
        if channel == REDIS_CHANNEL_SERVICE_HEALTH:
            health = ServiceHealthMessage.model_validate_json(item["data"])
            worker.process_health(health)
            record("health", sent=health.sent, loss=health.loss_percent, rtt=health.rtt_avg_ms)
            continue
        if channel == REDIS_CHANNEL_SERVER_CONNS:
            conns = ServerConnMessage.model_validate_json(item["data"])
            worker.process_server_conns(conns)
            busy = {c.client_ip: [c.open, c.slow, c.pending] for c in conns.clients if c.slow or c.pending}
            if busy:
                record("serverconn", slow=busy)
            continue
        if channel == REDIS_CHANNEL_FLOW_COUNTS:
            alerts = worker.process_counts(FlowCountMessage.model_validate_json(item["data"]))
            for d in worker.last_decisions:
                record("decision", port=f"S{d.dpid}:{d.port}", stage=d.stage.value, threat=d.threat_type,
                       strength=round(d.strength, 2), reasons=d.reasons,
                       rates={k: d.rates.get(k, 0.0) for k in ("syn", "fin", "rst", "udp", "icmp", "gap", "fail")})
            for alert in alerts:
                r.publish(REDIS_CHANNEL_ANOMALY_ALERT, alert.model_dump_json())
                record("alert", stats_ts=float(alert.metadata["stats_ts"]), port=f"S{alert.dpid}:{alert.in_port}",
                       score=round(alert.score, 4), stage=alert.stage, threat=alert.threat_type)
            continue
        message = PortStatsMessage.model_validate_json(item["data"])
        alerts = worker.process(message)
        for s in worker.last_samples:
            record("sample", stats_ts=s["timestamp"], port=f"S{s['dpid']}:{s['port_no']}",
                   pps=round(s["delta_pps"], 1), bpp=round(s["bpp"], 1), score=s["score"], confirmed=s["confirmed"])
        for alert in alerts:
            r.publish(REDIS_CHANNEL_ANOMALY_ALERT, alert.model_dump_json())
            record("alert", stats_ts=float(alert.metadata["stats_ts"]), port=f"S{alert.dpid}:{alert.in_port}",
                   score=round(alert.score, 4))
    record("stop")
    if log:
        log.close()


def learn(seconds: float, out: Path, redis_url: str) -> None:
    """정상 트래픽만 흐르는 동안 평소값을 학습해 저장한다 (사전 학습)."""
    import redis

    r = redis.Redis(connection_pool=redis.ConnectionPool.from_url(redis_url))
    pubsub = r.pubsub()
    pubsub.subscribe(REDIS_CHANNEL_FLOW_COUNTS)
    learner = BaselineLearner()
    deadline = time.time() + seconds
    while time.time() < deadline:
        item = pubsub.get_message(timeout=0.5)
        if item and item.get("type") == "message":
            learner.update(FlowCountMessage.model_validate_json(item["data"]))
    save_baselines(str(out), learner.baselines(), seconds)
    print(f"[inference_worker] baseline learned for {sorted(learner.samples)} -> {out}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="AI 추론 워커: 종류별 패킷 수 → 판단 기준 → 경보 발행")
    parser.add_argument("--model", type=Path, default=Path(DEFAULT_MODEL_PATH))
    parser.add_argument("--train-csv", type=Path, help="모델 파일이 없을 때 학습할 CSV (csv_logger 형식)")
    parser.add_argument("--redis-url", default=os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    parser.add_argument("--log", type=Path, help="경보·명령 이벤트 기록 (jsonl)")
    parser.add_argument("--baseline", type=Path, default=Path(DEFAULT_BASELINE_PATH),
                        help="사전 학습한 평소값 (없으면 최소값만으로 판단)")
    parser.add_argument("--learn", type=float, help="이 시간(초) 동안 평소값을 학습해 --baseline에 저장하고 끝냄")
    parser.add_argument("--legacy", action="store_true", help="이전 판단 방식 (BPP + Isolation Forest 점수)")
    args = parser.parse_args()
    if args.learn:
        learn(args.learn, args.baseline, args.redis_url)
        return
    model, source = load_model(args.model, args.train_csv)
    print(f"[inference_worker] model: {source}", flush=True)
    criteria = None
    if not args.legacy:
        baselines = load_baselines(str(args.baseline))
        criteria = CriteriaEngine(baselines=baselines, ports=watched_ports())
        print(f"[inference_worker] criteria mode, baseline: {args.baseline if baselines else 'none (floors only)'}",
              flush=True)
    run(InferenceWorker(model, criteria=criteria), args.redis_url, args.log)


if __name__ == "__main__":
    main()
