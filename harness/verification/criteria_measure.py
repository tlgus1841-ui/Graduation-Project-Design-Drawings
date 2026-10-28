"""판단 기준 숫자 측정: 정상 시나리오 5종의 평소값과 공격별 크기를 실제 패킷으로 잰다.

다이아몬드 토폴로지에서 두 접속 호스트(H_legit, H_attacker)가 정상 사용자로 normal_seconds 동안
traffic/normal_user.py를 돌리고(평소값 학습 구간), 이어서 H_attacker가 공격을 하나씩 실행한다
(정상 트래픽은 계속 흐름). 숫자는 컨트롤러의 세는 규칙(sdn:stats:flowcount)과 포트 통계
(sdn:stats:port)를 Redis에서 받아 기록한 것이다 — 판단 프로그램이 보는 것과 같은 값이다.

실행 (Ryu 컨트롤러·Redis 실행 중):
    sudo python3 -m harness.verification.criteria_measure --run --out runs/criteria   # 시스템 python3 (Mininet)
    .venv/bin/python -m harness.verification.criteria_measure --analyze runs/criteria  # 분석 + 평소값 파일

방어까지 켠 검증 (추론 워커를 --log events.jsonl로 함께 실행):
    sudo python3 -m harness.verification.criteria_measure --run --defense --out runs/e2e
    .venv/bin/python -m harness.verification.criteria_measure --e2e runs/e2e --events events.jsonl
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
VENV_PY = REPO_ROOT / ".venv" / "bin" / "python"
FLOW_COUNTS = "sdn:stats:flowcount"
PORT_STATS = "sdn:stats:port"
# (dpid, port) → 이름. 측정 대상은 호스트가 붙은 접속 포트
PORTS = {(1, 1): "S1:1 H_legit", (1, 2): "S1:2 H_attacker", (4, 1): "S4:1 H_server"}
KINDS = ("syn", "fin", "rst", "udp", "icmp", "rst_in", "unreach_in")
DERIVED = ("gap", "fail", "pps")  # gap = syn-(fin+rst), fail = rst_in+unreach_in, pps = 포트 전체 수신

ATTACKS: List[Tuple[str, str, int]] = [
    ("syn_strong", "traffic.traffic_attack --dst 10.0.0.4 --min-pps 1000 --max-pps 1000 --duration 20", 20),
    ("udp_strong", "traffic.traffic_flood --kind udp --pps 1000 --duration 20", 20),
    ("icmp_strong", "traffic.traffic_flood --kind icmp --pps 1000 --duration 20", 20),
    ("syn_weak", "traffic.traffic_attack --dst 10.0.0.4 --min-pps 100 --max-pps 100 --duration 20", 20),
    ("udp_weak", "traffic.traffic_flood --kind udp --pps 100 --duration 20", 20),
    ("icmp_weak", "traffic.traffic_flood --kind icmp --pps 100 --duration 20", 20),
    ("tcp_scan", "traffic.traffic_scan --kind tcp --ports 1-1000 --rate 500", 2),
    ("tcp_scan_slow", "traffic.traffic_scan --kind tcp --ports 1-40 --rate 2", 20),
    ("udp_scan", "traffic.traffic_scan --kind udp --ports 1-300 --rate 300", 1),
]


# ---------------------------------------------------------------------------
# Rates (pure, unit-tested)
# ---------------------------------------------------------------------------
def rate_samples(records: Iterable[dict]) -> List[dict]:
    """tap 기록 → 보고 주기마다 (t, dpid, port, indicator, 초당 값) 목록.

    누적 카운트의 직전 보고 대비 증가량을 시간으로 나눈다. 음수(카운터 리셋)는 버린다.
    """
    prev_counts: Dict[Tuple[int, int, str], Tuple[float, int]] = {}
    prev_rx: Dict[Tuple[int, int], Tuple[float, int]] = {}
    per_tick: Dict[Tuple[float, int, int], Dict[str, float]] = defaultdict(dict)
    out: List[dict] = []
    for rec in records:
        data, t = rec["data"], rec["data"]["timestamp"]
        if rec["ch"] == FLOW_COUNTS:
            for c in data["counts"]:
                key = (data["dpid"], c["port_no"], c["kind"])
                if key in prev_counts:
                    t0, n0 = prev_counts[key]
                    if t > t0 and c["packets"] >= n0:
                        per_tick[(t, data["dpid"], c["port_no"])][c["kind"]] = (c["packets"] - n0) / (t - t0)
                prev_counts[key] = (t, c["packets"])
        elif rec["ch"] == PORT_STATS:
            for s in data["stats"]:
                key2 = (s["dpid"], s["port_no"])
                if key2 in prev_rx:
                    t0, n0 = prev_rx[key2]
                    if t > t0 and s["rx_packets"] >= n0:
                        out.append({"t": t, "dpid": s["dpid"], "port": s["port_no"], "ind": "pps",
                                    "v": (s["rx_packets"] - n0) / (t - t0)})
                prev_rx[key2] = (t, s["rx_packets"])
    for (t, dpid, port), kinds in sorted(per_tick.items()):
        for kind, v in kinds.items():
            out.append({"t": t, "dpid": dpid, "port": port, "ind": kind, "v": v})
        if all(k in kinds for k in ("syn", "fin", "rst")):
            out.append({"t": t, "dpid": dpid, "port": port, "ind": "gap",
                        "v": kinds["syn"] - kinds["fin"] - kinds["rst"]})
        if all(k in kinds for k in ("rst_in", "unreach_in")):
            out.append({"t": t, "dpid": dpid, "port": port, "ind": "fail", "v": kinds["rst_in"] + kinds["unreach_in"]})
    return out


def summarize(values: List[float]) -> Dict[str, float]:
    if not values:
        return {"n": 0}
    v = sorted(values)
    n = len(v)
    mean = sum(v) / n
    std = math.sqrt(sum((x - mean) ** 2 for x in v) / n)

    def pct(p: float) -> float:
        return v[min(n - 1, int(round(p * (n - 1))))]
    return {"n": n, "mean": round(mean, 2), "std": round(std, 2), "p95": round(pct(0.95), 2),
            "p99": round(pct(0.99), 2), "max": round(v[-1], 2)}


def phase_of(t: float, phases: List[dict], lag: float = 4.5) -> Optional[str]:
    """보고 시각 t가 속한 구간 이름. 보고가 최대 한 주기 늦으므로 끝을 lag만큼 늘린다."""
    for ph in phases:
        if ph["start"] + ph.get("skip", 0.0) < t <= ph["end"] + lag:
            return ph["name"]
    return None


def analyze(out_dir: Path) -> dict:
    records = [json.loads(line) for line in (out_dir / "tap.jsonl").read_text().splitlines() if line.strip()]
    phases = json.loads((out_dir / "phases.json").read_text())["phases"]
    groups: Dict[str, Dict[str, Dict[str, List[float]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for s in rate_samples(records):
        name = PORTS.get((s["dpid"], s["port"]))
        phase = phase_of(s["t"], phases)
        if name and phase:
            groups[phase][name][s["ind"]].append(s["v"])
    return {phase: {port: {ind: summarize(vals) for ind, vals in sorted(inds.items())}
                    for port, inds in sorted(ports.items())}
            for phase, ports in groups.items()}


# ---------------------------------------------------------------------------
# Mininet run (root, system python3)
# ---------------------------------------------------------------------------
def tap(path: Path) -> None:
    """Redis 채널 기록기 (.venv python으로 실행)."""
    import redis
    ps = redis.Redis().pubsub()
    ps.subscribe(FLOW_COUNTS, PORT_STATS)
    with path.open("w") as f:
        while True:
            m = ps.get_message(timeout=1.0)
            if m and m["type"] == "message":
                f.write(json.dumps({"ch": m["channel"].decode(), "data": json.loads(m["data"])}) + "\n")
                f.flush()


def baseline_from_run(out_dir: Path, ports: Optional[List[Tuple[int, int]]] = None):
    """측정의 정상 구간(normal)에 들어온 종류별 카운트로 평소값(평균·표준편차)을 계산한다."""
    sys.path.insert(0, str(REPO_ROOT))
    from harness.contracts import FlowCountMessage
    from model.criteria_engine import BaselineLearner

    phases = json.loads((out_dir / "phases.json").read_text())["phases"]
    normal = next(ph for ph in phases if ph["name"] == "normal")
    learner = BaselineLearner(ports=ports)
    for line in (out_dir / "tap.jsonl").read_text().splitlines():
        rec = json.loads(line)
        if rec["ch"] != FLOW_COUNTS:
            continue
        t = rec["data"]["timestamp"]
        if normal["start"] + normal.get("skip", 0.0) < t <= normal["end"]:
            learner.update(FlowCountMessage.model_validate(rec["data"]))
    return learner.baselines(), normal["end"] - normal["start"] - normal.get("skip", 0.0)


def analyze_e2e(out_dir: Path, events_path: Path) -> dict:
    """방어를 켠 실행: 구간별 경보·조치와 정상 사용자 ping 손실."""
    sys.path.insert(0, str(REPO_ROOT))
    from harness.verification.e2e_scenario import parse_ping_d, seq_times, window_loss

    phases = json.loads((out_dir / "phases.json").read_text())["phases"]
    events = [json.loads(line) for line in events_path.read_text().splitlines() if line.strip()]
    ping = parse_ping_d((out_dir / "ping_legit.txt").read_text())
    times = seq_times(ping["transmitted"], ping["received_seqs"], ping["reply_ts"])
    report: Dict[str, dict] = {"whole_run_legit_loss": window_loss(times, ping["received_seqs"], 0, 1e12)}
    for i, ph in enumerate(phases):
        start = ph["start"] + ph.get("skip", 0.0)
        # 공격 구간은 끝난 뒤의 조용한 구간 앞부분(복구 시간)까지 본다
        end = ph["end"] + (phases[i + 1]["skip"] if i + 1 < len(phases) and ph["name"] not in ("normal", "quiet")
                           else 0.0)
        alerts = [e for e in events if e["kind"] == "alert" and start <= e["t"] <= end]
        commands = [e for e in events if e["kind"] == "command" and start <= e["t"] <= end]
        watch = [e for e in events if e["kind"] == "decision" and e["stage"] == "WATCH" and start <= e["t"] <= end]
        entry = {"seconds": round(end - start, 1), "alerts": len(alerts), "watch_reports": len(watch),
                 "commands": [c["action"] for c in commands],
                 "legit_loss": window_loss(times, ping["received_seqs"], start, end)}
        if alerts:
            entry["first_alert_after_s"] = round(alerts[0]["t"] - ph["start"], 2)
            entry["first_stage"] = alerts[0].get("stage")
            entry["threats"] = sorted({a.get("threat") for a in alerts})
            entry["stages"] = sorted({a.get("stage") for a in alerts})
        name = ph["name"] if ph["name"] not in report else f"{ph['name']}_{i}"
        report[name] = entry
    return report


def run(out_dir: Path, normal_seconds: int, gap: int, surge_at: str, only: Optional[List[str]] = None,
        defense: bool = False) -> None:
    from mininet.log import setLogLevel
    from mininet.net import Mininet
    from mininet.node import OVSSwitch, RemoteController

    sys.path.insert(0, str(REPO_ROOT / "topo"))
    from diamond_topo import DiamondTopo

    attacks = [a for a in ATTACKS if not only or a[0] in only]
    out_dir.mkdir(parents=True, exist_ok=True)
    setLogLevel("warning")
    net = Mininet(topo=DiamondTopo(), controller=None, switch=OVSSwitch, autoSetMacs=False, autoStaticArp=False)
    net.addController("c0", controller=RemoteController, ip="127.0.0.1", port=6653)
    for sw in net.switches:
        sw.datapath = "user"
    net.start()
    tapper = subprocess.Popen([str(VENV_PY), "-m", "harness.verification.criteria_measure", "--tap",
                               str(out_dir / "tap.jsonl")], cwd=REPO_ROOT)
    phases: List[dict] = []
    try:
        for sw in net.switches:
            sw.cmd(f"ovs-vsctl set bridge {sw.name} protocols=OpenFlow13")
        for h in net.hosts:
            # The userspace datapath does not fill in offloaded checksums; real TCP/UDP needs them off.
            h.cmd(f"ethtool -K {h.defaultIntf()} tx off rx off")
        time.sleep(3)
        net.pingAll()
        legit, attacker, server = net.get("h_legit", "h_attacker", "h_server")
        server.cmd("mkdir -p /tmp/www && head -c 2048 /dev/urandom > /tmp/www/index.html"
                   " && head -c 20000000 /dev/urandom > /tmp/www/big.bin")
        server.cmd("cd /tmp/www && python3 -m http.server 80 > /dev/null 2>&1 &")
        server.cmd("python3 -c \"import socket\ns=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)\n"
                   "s.bind(('0.0.0.0',53))\nwhile True:\n d,a=s.recvfrom(512); s.sendto(d+b'0'*40,a)\""
                   " > /dev/null 2>&1 &")
        time.sleep(1)
        total = normal_seconds + sum(d + gap + 8 for _, _, d in attacks) + 30
        user = f"python3 {REPO_ROOT}/traffic/normal_user.py --server 10.0.0.4 --duration {total} --surge-at {surge_at}"
        if defense:
            # 방어 검증: 정상 사용자의 ping을 시각과 함께 남겨 구간별 손실을 잰다 (e2e_scenario와 같은 방식)
            legit.cmd(f"ping -D -i 0.05 -w {total} 10.0.0.4 > {out_dir}/ping_legit.txt 2>&1 &")
            legit.cmd(f"{user} --ping-interval 0 --seed 1 > {out_dir}/user_legit.log 2>&1 &")
        else:
            legit.cmd(f"{user} --ping-interval 0.05 --seed 1 > {out_dir}/user_legit.log 2>&1 &")
        attacker.cmd(f"{user} --ping-interval 1 --seed 2 > {out_dir}/user_attacker.log 2>&1 &")
        t0 = time.time()
        time.sleep(normal_seconds)
        # The first 10 s are the users' start-up, not their steady state.
        phases.append({"name": "normal", "start": t0, "end": time.time(), "skip": 10.0})
        for name, cmd, _ in attacks:
            q0 = time.time()
            time.sleep(gap)
            phases.append({"name": "quiet", "start": q0, "end": time.time(), "skip": 6.0})
            a0 = time.time()
            log = attacker.cmd(f"cd {REPO_ROOT} && {VENV_PY} -m {cmd}")
            phases.append({"name": name, "start": a0, "end": time.time(), "log": log.strip()[-200:]})
            print(f"[criteria_measure] {name}: {log.strip()[-120:]}", flush=True)
        time.sleep(4)
    finally:
        (out_dir / "phases.json").write_text(json.dumps({"phases": phases}, ensure_ascii=False, indent=1))
        for h in net.hosts:
            h.cmd("pkill -f normal_user.py; pkill -f http.server; pkill -f 'socket.SOCK_DGRAM'; pkill -INT ping")
        tapper.terminate()
        net.stop()


def main() -> None:
    p = argparse.ArgumentParser(description="판단 기준 숫자 측정 (정상 시나리오 + 공격)")
    p.add_argument("--run", action="store_true", help="Mininet에서 측정 실행 (root, 시스템 python3)")
    p.add_argument("--analyze", type=Path, help="측정 폴더를 분석해 summary.json 작성")
    p.add_argument("--tap", type=Path, help=argparse.SUPPRESS)
    p.add_argument("--out", type=Path, default=Path("runs/criteria"))
    p.add_argument("--normal-seconds", type=int, default=600)
    p.add_argument("--gap", type=int, default=30, help="공격 사이 조용한 구간(초)")
    p.add_argument("--surge-at", default="360,480", help="정상 사용자 급증 시각(초)")
    p.add_argument("--only", default="", help="이 공격만 (쉼표 목록)")
    p.add_argument("--defense", action="store_true", help="방어 검증 실행: 정상 사용자 ping을 시각과 함께 기록")
    p.add_argument("--baseline-out", type=Path, help="--analyze 때 정상 구간의 평소값을 이 파일로 저장")
    p.add_argument("--e2e", type=Path, help="방어 검증 폴더 분석 (--events 필요)")
    p.add_argument("--events", type=Path, help="추론 워커 --log 파일")
    a = p.parse_args()
    if a.tap:
        tap(a.tap)
    elif a.run:
        run(a.out, a.normal_seconds, a.gap, a.surge_at, [x for x in a.only.split(",") if x], a.defense)
    elif a.analyze:
        summary = analyze(a.analyze)
        (a.analyze / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
        print(json.dumps(summary, ensure_ascii=False, indent=1))
        if a.baseline_out:
            from model.criteria_engine import save_baselines
            baselines, seconds = baseline_from_run(a.analyze)
            save_baselines(str(a.baseline_out), baselines, seconds)
            print(f"[criteria_measure] baseline ({seconds:.0f}s of normal traffic) -> {a.baseline_out}")
    elif a.e2e:
        report = analyze_e2e(a.e2e, a.events)
        (a.e2e / "e2e_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))
        print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
