"""판단 기준 숫자 측정: 정상 시나리오의 평소값과 공격별 크기를 실제 패킷으로 잰다.

10-스위치 6-망 네이티브 토폴로지(scripts/setup_large_ovs.sh, ip netns)에서 사용자 PC 4대(h1~h4)와
외부 접속자(ext)가 정상 사용자로 normal_seconds 동안 traffic/normal_user.py를 돌리고(평소값 학습 구간),
이어서 내부 공격자(h2)와 외부 공격자(ext)가 공격을 하나씩 실행한다 (정상 트래픽은 계속 흐름).
숫자는 컨트롤러의 세는 규칙(sdn:stats:flowcount)과 포트 통계(sdn:stats:port)를 Redis에서 받아 기록한
것이다 — 판단 프로그램이 보는 것과 같은 값이다. (8주차~6-B의 다이아몬드 측정은 Mininet으로 했다)

실행 (토폴로지 · Ryu 컨트롤러 · Redis 실행 중, root):
    sudo bash scripts/setup_large_ovs.sh
    sudo .venv/bin/python -m harness.verification.criteria_measure --run --out runs/criteria
    .venv/bin/python -m harness.verification.criteria_measure --analyze runs/criteria  # 분석 + 평소값 파일

방어까지 켠 검증 (추론 워커를 --log events.jsonl로 함께 실행):
    sudo .venv/bin/python -m harness.verification.criteria_measure --run --defense --out runs/e2e
    .venv/bin/python -m harness.verification.criteria_measure --e2e runs/e2e --events events.jsonl
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import signal
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple, cast

REPO_ROOT = Path(__file__).resolve().parents[2]
VENV_PY = REPO_ROOT / ".venv" / "bin" / "python"
FLOW_COUNTS = "sdn:stats:flowcount"
PORT_STATS = "sdn:stats:port"
SERVICE_HEALTH = "sdn:health:service"
SERVER_CONNS = "sdn:stats:serverconn"
SERVICE = "service S3→web1"  # 서비스 상태 확인 ping (컨트롤러, 사용자 스위치 S3에서 웹서버로)
SERVER_IP = "10.0.0.11"  # 보호하는 DMZ 웹서버 (web1)
# 역할 → (ip netns 이름, IP). 이름은 scripts/setup_large_ovs.sh와 같다
HOSTS: Dict[str, Tuple[str, str]] = {
    "h1": ("ns_h1", "10.0.0.1"),    # 정상 사용자 (ping으로 손실을 잰다)
    "h2": ("ns_h2", "10.0.0.2"),    # 내부 공격자 · 감염 PC (공격 전에는 평범한 사용자)
    "h3": ("ns_h3", "10.0.0.3"),
    "h4": ("ns_h4", "10.0.0.4"),
    "ext": ("ns_ext", "192.168.100.100"),  # 외부 접속자 · 외부 공격자 (S9 외부 입구)
    "web1": ("ns_web1", SERVER_IP),
}
# (dpid, port) → 이름. 측정 대상은 호스트가 붙은 접속 포트 (harness.contracts.ACCESS_HOST_PORTS와 같다)
PORTS = {(3, 1): "S3:1 h1", (3, 2): "S3:2 h2", (4, 1): "S4:1 h3", (4, 2): "S4:2 h4",
         (9, 1): "S9:1 ext", (10, 1): "S10:1 web1"}
HOST_IPS = {(3, 1): "10.0.0.1", (3, 2): "10.0.0.2", (4, 1): "10.0.0.3", (4, 2): "10.0.0.4",
            (9, 1): "192.168.100.100", (10, 1): SERVER_IP}
KINDS = ("syn", "fin", "rst", "udp", "icmp", "rst_in", "unreach_in")
DERIVED = ("gap", "fail", "pps")  # gap = syn-(fin+rst), fail = rst_in+unreach_in, pps = 포트 전체 수신
# 쉬는 구간의 앞부분(초)은 직전 공격의 늦은 보고와 복구 시간이라 쉬는 구간 통계에서 뺀다
QUIET_SKIP = 6.0
# 공격하는 동안 서버에 거는 장애: 서버가 내보내는 패킷의 40%를 무작위로 버린다 (iptables statistic).
# 서버가 힘들어져 정상 사용자가 피해를 보는 상황을 만든다
SERVER_FAULTS = {"udp_weak_degraded": "OUTPUT -m statistic --mode random --probability 0.4 -j DROP"}
EXT = "--src 192.168.100.100"

# (이름, 공격하는 호스트, traffic 모듈과 인자, 길이(초))
ATTACKS: List[Tuple[str, str, str, int]] = [
    ("syn_strong", "h2", f"traffic.traffic_attack --dst {SERVER_IP} --min-pps 1000 --max-pps 1000 --duration 20", 20),
    ("udp_strong", "h2", f"traffic.traffic_flood --kind udp --dst {SERVER_IP} --pps 1000 --duration 20", 20),
    ("icmp_strong", "h2", f"traffic.traffic_flood --kind icmp --dst {SERVER_IP} --pps 1000 --duration 20", 20),
    ("syn_weak", "h2", f"traffic.traffic_attack --dst {SERVER_IP} --min-pps 100 --max-pps 100 --duration 20", 20),
    ("udp_weak", "h2", f"traffic.traffic_flood --kind udp --dst {SERVER_IP} --pps 100 --duration 20", 20),
    ("icmp_weak", "h2", f"traffic.traffic_flood --kind icmp --dst {SERVER_IP} --pps 100 --duration 20", 20),
    # 서비스 악화 조건 확인: 판정선의 4배(위험 기준 5배 미만) 공격, 서버를 일부러 나쁘게 만든 약한 공격
    ("icmp_mid", "h2", f"traffic.traffic_flood --kind icmp --dst {SERVER_IP} --pps 200 --duration 20", 20),
    ("udp_weak_degraded", "h2", f"traffic.traffic_flood --kind udp --dst {SERVER_IP} --pps 100 --duration 20", 20),
    # 외부 입구(S9)로 들어오는 Flood. 외부에서는 DMZ 웹 80 · 8080만 열려 있어 UDP · ICMP는 입구에서 막힌다
    ("ext_syn_strong", "ext", f"traffic.traffic_attack --dst {SERVER_IP} --min-pps 1000 --max-pps 1000 --duration 20",
     20),
    ("ext_udp_strong", "ext", f"traffic.traffic_flood --kind udp --dst {SERVER_IP} --pps 1000 --duration 20", 20),
    ("ext_icmp_strong", "ext", f"traffic.traffic_flood --kind icmp --dst {SERVER_IP} --pps 1000 --duration 20", 20),
    # 내부 확산: 없는 내부 주소 56개에 445 포트 연결 시도 (초당 10개)
    ("internal_spread", "h2", "traffic.traffic_spread --subnet 10.0.0 --hosts 30-85 --port 445 --rate 10", 9),
    # 옆으로 퍼지기(랜섬웨어): 실제로 있는 사용자 PC · 서버 · 관리망의 445에 연결 시도 → 망 정책이 막는다
    ("lateral_spread", "h2", "traffic.traffic_spread --subnet 10.0.0 --hosts 1,3,4,12,21,22,253,254 --port 445"
     " --rate 4", 5),
    # Slow HTTP (Slowloris 방식). 끝난 뒤 서버가 남은 연결을 시간 초과로 끊으며 RST를 한꺼번에 보내므로 뒤에 둔다
    ("slow_http_weak", "h2", f"traffic.traffic_slowhttp --server {SERVER_IP} --sockets 30 --interval 10 --duration 60",
     60),
    ("slow_http", "h2", f"traffic.traffic_slowhttp --server {SERVER_IP} --sockets 150 --interval 10 --duration 60", 60),
    # 스캔은 받은 실패 응답을 5분 동안 세므로, 실패가 적은 스캔부터 해서 앞 스캔의 실패가 섞이지 않게 한다
    ("udp_scan", "h2", f"traffic.traffic_scan --kind udp --dst {SERVER_IP} --ports 1-300 --rate 300", 1),
    ("tcp_scan_slow", "h2", f"traffic.traffic_scan --kind tcp --dst {SERVER_IP} --ports 1-40 --rate 2", 20),
    ("tcp_scan", "h2", f"traffic.traffic_scan --kind tcp --dst {SERVER_IP} --ports 1-1000 --rate 500", 2),
    ("ext_tcp_scan", "ext", f"traffic.traffic_scan --kind tcp --dst {SERVER_IP} {EXT} --ports 1-1000 --rate 500", 2),
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
    """보고 시각 t가 속한 구간 이름. 보고가 최대 한 주기 늦으므로 끝을 lag만큼 늘린다.

    구간 안에 든 보고가 먼저다. 늘린 끝은 어느 구간에도 들지 않은 보고에만 쓰고, 가장 최근에 끝난
    구간으로 보낸다 (앞 구간의 늘린 끝이 짧은 공격의 첫 보고를 가져가지 않게).
    """
    for ph in phases:
        if ph["start"] + ph.get("skip", 0.0) < t <= ph["end"]:
            return ph["name"]
    ended = [ph for ph in phases if ph["end"] < t <= ph["end"] + lag]
    return max(ended, key=lambda ph: ph["end"])["name"] if ended else None


def analyze(out_dir: Path) -> dict:
    records = [json.loads(line) for line in (out_dir / "tap.jsonl").read_text().splitlines() if line.strip()]
    phases = json.loads((out_dir / "phases.json").read_text())["phases"]
    groups: Dict[str, Dict[str, Dict[str, List[float]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for s in rate_samples(records):
        name = PORTS.get((s["dpid"], s["port"]))
        phase = phase_of(s["t"], phases)
        if name and phase:
            groups[phase][name][s["ind"]].append(s["v"])
    for rec in records:
        phase = phase_of(rec["data"]["timestamp"], phases) if rec["ch"] in (SERVICE_HEALTH, SERVER_CONNS) else None
        if phase and rec["ch"] == SERVICE_HEALTH:
            for ind in ("loss_percent", "rtt_avg_ms", "rtt_max_ms"):
                if rec["data"].get(ind) is not None:
                    groups[phase][SERVICE][ind].append(rec["data"][ind])
        elif phase:
            # 서버 연결 수집기: 접속한 PC마다 열린 연결, 느린 요청, 안 끝난 요청 수
            by_ip = {c["client_ip"]: c for c in rec["data"]["clients"]}
            for (dpid, port), name in PORTS.items():
                ip = HOST_IPS.get((dpid, port))
                c = by_ip.get(ip, {})
                groups[phase][name]["http_open"].append(c.get("open", 0))
                groups[phase][name]["http_slow"].append(c.get("slow", 0))
                groups[phase][name]["http_pending"].append(c.get("pending", 0))
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
    ps.subscribe(FLOW_COUNTS, PORT_STATS, SERVICE_HEALTH, SERVER_CONNS)
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
        # 공격 구간은 끝난 뒤의 조용한 구간 앞부분(복구 시간)까지 본다. 마지막 공격은 그만큼 늘려서 본다
        tail = phases[i + 1].get("skip", 0.0) if i + 1 < len(phases) else QUIET_SKIP
        end = ph["end"] + (tail if ph["name"] not in ("normal", "quiet") else 0.0)
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
        health = [e for e in events if e["kind"] == "health" and start <= e["t"] <= end]
        if health:
            # 컨트롤러의 서비스 상태 확인 ping: 가장 나빴던 보고와, 서비스 악화로 위험이 된 보고 수
            entry["service_loss_max"] = max(e["loss"] for e in health)
            entry["service_rtt_max_ms"] = max((e["rtt"] for e in health if e["rtt"] is not None), default=None)
            entry["danger_by_service"] = sum(
                1 for e in events if e["kind"] == "decision" and start <= e["t"] <= end
                and any(r.startswith("service degraded") for r in e.get("reasons", [])))
        name = ph["name"] if ph["name"] not in report else f"{ph['name']}_{i}"
        report[name] = entry
    return report


def _netns(host: str, cmd: str) -> List[str]:
    return ["ip", "netns", "exec", HOSTS[host][0], "sh", "-c", cmd]


def _background(host: str, cmd: str, log: Path) -> subprocess.Popen:
    """호스트의 네트워크 공간에서 cmd를 뒤에서 실행한다 (끝낼 때 프로세스 그룹째 멈춘다)."""
    with log.open("w") as f:
        return subprocess.Popen(_netns(host, cmd), cwd=REPO_ROOT, stdout=f, stderr=subprocess.STDOUT,
                                start_new_session=True)


def _stop(procs: List[subprocess.Popen]) -> None:
    for proc in procs:
        try:
            os.killpg(proc.pid, signal.SIGINT)  # ping은 SIGINT를 받아야 마지막 요약을 남긴다
        except ProcessLookupError:
            pass
    for proc in procs:
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)


def release_quarantined(reason: str) -> List[str]:
    """관리자 역할: 격리망에 있는 PC를 모두 원래 망으로 돌려보낸다 (다음 실험에 앞 실험의 격리가 섞이지 않게)."""
    import redis
    sys.path.insert(0, str(REPO_ROOT))
    from harness.contracts import ACCESS_HOST_PORTS, REDIS_CHANNEL_CONTROL_COMMAND, ControlCommandMessage

    r = redis.Redis()
    released = sorted(ip.decode() for ip in cast(Set[bytes], r.smembers("sdn:quarantined_hosts")))
    for ip in released:
        dpid, port = ACCESS_HOST_PORTS.get(ip, (0, 0))
        cmd = ControlCommandMessage(command_id=f"manual-measure-release-{ip}-{time.time():.0f}", action="RELEASE",
                                    target_dpid=dpid, target_port=port, reason=reason, target_ip=ip)
        r.publish(REDIS_CHANNEL_CONTROL_COMMAND, cmd.model_dump_json())
    return released


def run(out_dir: Path, normal_seconds: int, gap: int, surge_at: str, only: Optional[List[str]] = None,
        defense: bool = False) -> None:
    """토폴로지(scripts/setup_large_ovs.sh) · 컨트롤러 · Redis가 떠 있는 상태에서 정상 구간 + 공격을 실행한다."""
    attacks = [a for a in ATTACKS if not only or a[0] in only]
    out_dir.mkdir(parents=True, exist_ok=True)
    tapper = subprocess.Popen([str(VENV_PY), "-m", "harness.verification.criteria_measure", "--tap",
                               str(out_dir / "tap.jsonl")], cwd=REPO_ROOT)
    phases: List[dict] = []
    procs: List[subprocess.Popen] = []
    try:
        # 웹서버: 설치 스크립트가 띄운 것 대신 30초 동안 아무것도 안 오는 연결을 닫는 서버로 바꾼다
        # (Apache의 요청 대기 시간 20~40초와 같은 역할). 대용량 다운로드 파일도 둔다
        subprocess.run(["pkill", "-f", "http.server 80 --directory /tmp/sdn_web_root"], check=False)
        subprocess.run(_netns("web1", "mkdir -p /tmp/www && head -c 2048 /dev/urandom > /tmp/www/index.html"
                                      " && head -c 20000000 /dev/urandom > /tmp/www/big.bin"), check=True)
        procs.append(_background("web1", "cd /tmp/www && exec python3 -c \"from http.server import "
                                         "ThreadingHTTPServer, SimpleHTTPRequestHandler as H; H.timeout = 30; "
                                         "ThreadingHTTPServer(('', 80), H).serve_forever()\"", out_dir / "web.log"))
        # DNS 응답기: 보내기 실패(장애 주입 중 iptables가 버림)에도 죽지 않게 한다
        procs.append(_background("web1", "exec python3 -c \"import socket\ns=socket.socket(socket.AF_INET,"
                                         "socket.SOCK_DGRAM)\ns.bind(('0.0.0.0',53))\nwhile True:\n d,a=s.recvfrom(512)"
                                         "\n try:\n  s.sendto(d+b'0'*40,a)\n except OSError:\n  pass\"",
                                 out_dir / "dns.log"))
        # 서버 연결 수집기 (Slow HTTP): 웹서버의 네트워크 공간에서 ss를 읽는다
        procs.append(subprocess.Popen([str(VENV_PY), "-m", "pipeline.server_conn_agent", "--server-ip", SERVER_IP,
                                       "--netns", HOSTS["web1"][0]], cwd=REPO_ROOT, stdout=subprocess.DEVNULL,
                                      start_new_session=True))
        time.sleep(1)
        total = normal_seconds + sum(d + gap + 8 for *_, d in attacks) + gap + 30
        user = (f"exec {VENV_PY} {REPO_ROOT}/traffic/normal_user.py --server {SERVER_IP} --duration {total}"
                f" --surge-at {surge_at}")
        if defense:
            # 방어 검증: 정상 사용자의 ping을 시각과 함께 남겨 구간별 손실을 잰다 (e2e_scenario와 같은 방식)
            procs.append(_background("h1", f"exec ping -D -i 0.05 -w {total} {SERVER_IP}", out_dir / "ping_legit.txt"))
            procs.append(_background("h1", f"{user} --ping-interval 0 --seed 1", out_dir / "user_h1.log"))
        else:
            procs.append(_background("h1", f"{user} --ping-interval 0.05 --seed 1", out_dir / "user_h1.log"))
        for seed, host in enumerate(("h2", "h3", "h4"), start=2):
            procs.append(_background(host, f"{user} --ping-interval 1 --seed {seed}", out_dir / f"user_{host}.log"))
        # 외부 접속자는 공개된 웹만 쓴다 (ping · DNS · 닫힌 포트 실수는 외부에선 막혀 평소값을 흐린다)
        procs.append(_background("ext", f"{user} --ping-interval 0 --dns-mean 1e9 --mistake-every 1e9 --seed 6",
                                 out_dir / "user_ext.log"))
        t0 = time.time()
        time.sleep(normal_seconds)
        # The first 10 s are the users' start-up, not their steady state.
        phases.append({"name": "normal", "start": t0, "end": time.time(), "skip": 10.0})
        # 공격 시작 시각을 보고 주기와 엇갈리게 0~2초 무작위로 늦춘다. 쉬는 구간이 딱 30초면 공격이 매번
        # 보고 직후에 시작해 탐지 시간이 늘 가장 늦은 경우로만 재진다
        jitter = random.Random(7)
        for name, host, cmd, _ in attacks:
            q0 = time.time()
            time.sleep(gap + jitter.uniform(0.0, 2.0))
            phases.append({"name": "quiet", "start": q0, "end": time.time(), "skip": QUIET_SKIP})
            fault = SERVER_FAULTS.get(name)
            if fault:
                subprocess.run(_netns("web1", f"iptables -I {fault}"), check=True)
            a0 = time.time()
            done = subprocess.run(_netns(host, f"{VENV_PY} -m {cmd}"), cwd=REPO_ROOT, capture_output=True, text=True)
            log = (done.stdout + done.stderr).strip()
            phases.append({"name": name, "host": host, "start": a0, "end": time.time(), "log": log[-200:]})
            if fault:
                subprocess.run(_netns("web1", f"iptables -D {fault}"), check=False)
                phases[-1]["server_fault"] = fault
            print(f"[criteria_measure] {name} ({host}): {log[-120:]}", flush=True)
            # 실험이 끝나면 관리자가 확인하고 격리를 푼다 (쉬는 구간 앞부분 QUIET_SKIP초는 통계에서 빠진다)
            released = release_quarantined(f"measurement: {name} finished")
            if released:
                phases[-1]["released"] = released
        # 마지막 공격 뒤에도 쉬는 구간을 둬서 늦은 보고와 뒤처리(복구, 서버가 남은 연결을 끊는 것)까지 본다
        q0 = time.time()
        time.sleep(gap)
        phases.append({"name": "quiet", "start": q0, "end": time.time(), "skip": QUIET_SKIP})
    finally:
        (out_dir / "phases.json").write_text(json.dumps({"phases": phases}, ensure_ascii=False, indent=1))
        _stop(procs)
        tapper.terminate()


def main() -> None:
    p = argparse.ArgumentParser(description="판단 기준 숫자 측정 (정상 시나리오 + 공격)")
    p.add_argument("--run", action="store_true", help="네이티브 토폴로지에서 측정 실행 (root)")
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
