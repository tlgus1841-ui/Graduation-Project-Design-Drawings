"""14주차 E2E 검증용 '임시 방어 루프' (stand-in).

실제 구성요소가 아직 없는 두 자리를 메워 4단계 시나리오 전체를 실제 Mininet에서 닫기 위한 도구다.

    [실제] Ryu 컨트롤러 → Redis sdn:stats:port
    [실제] 유재민 FeatureExtractor (5대 피처)
    [대체] AI 탐지 → 규칙: S1:2 BPP ≤ 80B 이고 ΔPPS ≥ 500 이면 스코어 -0.8, 아니면 -0.1
    [대체] 방어 FSM → harness.verification.fsm_acceptance.SpecFSM (명세 그대로의 참조 구현)
    [대체] 컨트롤러 방어 실행 → ovs-ofctl로 Priority 100 규칙 직접 설치/삭제
    [실제] Redis sdn:anomaly:alert / sdn:control:command 발행 → 관제탑 백엔드 → 브라우저

대체 구성요소는 최종 시스템의 성능 수치(AI F1, 컨트롤러 반응 시간)를 대신하지 않는다.
이 도구가 보여주는 것은 "구성요소들이 하나의 루프로 맞물려 돈다"는 통합 동작과 그때의 정상 트래픽 영향이다.

실행 (Ryu·Redis 실행 중, root):
    sudo .venv/bin/python -m harness.verification.e2e_defense_standin --log e2e_events.jsonl
"""

from __future__ import annotations

import argparse
import json
import signal
import subprocess
import time
from pathlib import Path
from typing import Callable, Dict, List

import redis

from harness.contracts import (
    REDIS_CHANNEL_ANOMALY_ALERT,
    REDIS_CHANNEL_CONTROL_COMMAND,
    REDIS_CHANNEL_PORT_STATS,
    AnomalyAlertMessage,
    ControlCommandMessage,
    PortStatsMessage,
    ThreatType,
)
from harness.verification.fsm_acceptance import Sample, SpecFSM, is_attack
from harness.verification.reroute_loss_check import BYPASS_FLOWS
from pipeline.feature_extractor import FeatureExtractor

WATCH = (1, 2)  # S1:2, H_attacker access port
RULE_BPP_MAX = 80.0
RULE_PPS_MIN = 500.0
PRIORITY = 100
MAX_PLAUSIBLE_PPS = 1e7  # far above any link in the testbed; larger means a counter reset


def standin_score(pps: float, bpp: float) -> float:
    """AI 스코어 자리를 메우는 규칙 (Isolation Forest 연동 전 임시)."""
    return -0.8 if 0 < bpp <= RULE_BPP_MAX and pps >= RULE_PPS_MIN else -0.1


def flow_commands(action: str) -> List[List[str]]:
    """ISOLATE / REROUTE / RESTORE 를 ovs-ofctl 호출 목록으로 바꾼다."""
    of = ["ovs-ofctl", "-O", "OpenFlow13"]
    if action == "ISOLATE":
        return [of + ["add-flow", "s1", f"priority={PRIORITY},in_port={WATCH[1]},actions=drop"]]
    if action == "REROUTE":  # 하류부터 설치, S1은 마지막 (10주차 검증)
        return [of + ["add-flow", sw, f"priority={PRIORITY},ip,nw_dst={dst},actions=output:{port}"]
                for sw, dst, port in BYPASS_FLOWS]
    if action == "RESTORE":  # 입구 S1부터 되돌리고 하류를 나중에 지운다
        cmds = [of + ["--strict", "del-flows", "s1", f"priority={PRIORITY},in_port={WATCH[1]}"]]
        cmds += [of + ["--strict", "del-flows", sw, f"priority={PRIORITY},ip,nw_dst={dst}"]
                 for sw, dst, _ in reversed(BYPASS_FLOWS)]
        return cmds
    raise ValueError(action)


def run(log_path: Path, redis_url: str, apply: Callable[[List[str]], None]) -> None:
    r = redis.Redis(connection_pool=redis.ConnectionPool.from_url(redis_url))
    pubsub = r.pubsub()
    pubsub.subscribe(REDIS_CHANNEL_PORT_STATS)
    extractor = FeatureExtractor()
    fsm = SpecFSM()
    log = log_path.open("w", encoding="utf-8")

    def record(kind: str, **fields: object) -> None:
        log.write(json.dumps({"t": time.time(), "kind": kind, **fields}, ensure_ascii=False) + "\n")
        log.flush()

    stop = {"flag": False}
    signal.signal(signal.SIGTERM, lambda *_: stop.__setitem__("flag", True))
    signal.signal(signal.SIGINT, lambda *_: stop.__setitem__("flag", True))
    record("start", watch=f"S{WATCH[0]}:{WATCH[1]}")

    while not stop["flag"]:
        item = pubsub.get_message(timeout=0.5)
        if not item or item.get("type") != "message":
            continue
        msg = PortStatsMessage.model_validate_json(item["data"])
        for f in extractor.update(msg):
            if (f["dpid"], f["port_no"]) != WATCH:
                continue
            if f["delta_pps"] > MAX_PLAUSIBLE_PPS:  # counter reset/wrap when switches are torn down
                record("discarded", stats_ts=f["timestamp"], pps=f["delta_pps"])
                continue
            sample = Sample(t=f["timestamp"], pps=f["delta_pps"], bpp=f["bpp"],
                            score=standin_score(f["delta_pps"], f["bpp"]))
            before = fsm.state
            cmds = fsm.step(sample)
            record("sample", stats_ts=f["timestamp"], pps=round(sample.pps, 1), bpp=round(sample.bpp, 1),
                   score=sample.score, state=fsm.state)
            # Alerts are raised while the attack is being confirmed (NORMAL → T1), not during mitigation.
            if is_attack(sample) and before == "NORMAL":
                alert = AnomalyAlertMessage(dpid=WATCH[0], in_port=WATCH[1],
                                            threat_type=ThreatType.SYN_FLOOD_SPOOFING.value,
                                            score=sample.score,
                                            pps=sample.pps, bps=f["delta_bps"], bpp=sample.bpp,
                                            metadata={"model": "stand-in-rule"})
                r.publish(REDIS_CHANNEL_ANOMALY_ALERT, alert.model_dump_json())
                record("alert", stats_ts=f["timestamp"])
            for action in cmds:
                t0 = time.time()
                for argv in flow_commands(action):
                    apply(argv)
                t1 = time.time()
                cmd = ControlCommandMessage(
                    command_id=f"standin-{action.lower()}-{int(t1 * 1000)}", action=action,
                    target_dpid=WATCH[0], target_port=WATCH[1] if action != "REROUTE" else 4,
                    reason=f"[E2E stand-in] {action} (rule+SpecFSM)", priority=PRIORITY)
                r.publish(REDIS_CHANNEL_CONTROL_COMMAND, cmd.model_dump_json())
                record("command", action=action, stats_ts=f["timestamp"], apply_ms=round((t1 - t0) * 1000, 1))
    record("stop")
    log.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="E2E 검증용 임시 방어 루프")
    parser.add_argument("--log", type=Path, default=Path("e2e_events.jsonl"))
    parser.add_argument("--redis-url", default="redis://localhost:6379/0")
    parser.add_argument("--dry-run", action="store_true", help="ovs-ofctl 대신 명령만 기록")
    args = parser.parse_args()
    applied: Dict[str, int] = {"n": 0}

    def apply(argv: List[str]) -> None:
        applied["n"] += 1
        if not args.dry_run:
            subprocess.run(argv, check=True, capture_output=True)

    run(args.log, args.redis_url, apply)


if __name__ == "__main__":
    main()
