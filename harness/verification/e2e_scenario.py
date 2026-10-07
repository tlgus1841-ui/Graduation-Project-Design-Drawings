"""14주차 E2E 종합 시나리오: 정상 통신 → 스푸핑 공격·탐지 → 자율 격리·우회 → 자가 복구.

Mininet에서 정상 사용자의 연속 ping(50ms 간격)을 처음부터 끝까지 흘리면서, 중간에 공격기를 일정 시간
실행한다. 방어는 별도로 떠 있는 방어 루프(실제 FSM·컨트롤러가 들어오기 전에는 e2e_defense_standin)가
수행하고, 이 스크립트는 정상 트래픽 손실과 스위치 규칙 카운터를 기록한다. 방어 루프의 이벤트 로그와
합쳐 `analyze()`가 단계별 지표를 계산한다.

실행 (Ryu·Redis·방어 루프 실행 중, root, Mininet이 설치된 시스템 python3):
    sudo python3 -m harness.verification.e2e_scenario --userspace --out e2e_run.json
    uv run python -m harness.verification.e2e_scenario --analyze e2e_run.json --events e2e_events.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
PING_INTERVAL = 0.05


# ---------------------------------------------------------------------------
# Parsing (pure, unit-tested)
# ---------------------------------------------------------------------------
def parse_ping_d(output: str) -> Dict[str, Any]:
    """`ping -D` 출력에서 응답 받은 icmp_seq별 수신 시각과 전송 수를 꺼낸다."""
    replies = {int(m.group(2)): float(m.group(1))
               for m in re.finditer(r"\[(\d+\.\d+)\][^\n]*?icmp_seq=(\d+)", output)}
    m = re.search(r"(\d+) packets transmitted", output)
    return {"transmitted": int(m.group(1)) if m else 0,
            "received_seqs": sorted(replies), "reply_ts": [replies[k] for k in sorted(replies)]}


def seq_times(transmitted: int, received: List[int], reply_ts: List[float]) -> Dict[int, float]:
    """모든 seq의 시각. 받은 것은 응답 시각, 잃은 것은 앞뒤 응답 시각으로 선형 보간한다."""
    known = dict(zip(received, reply_ts))
    out: Dict[int, float] = {}
    for n in range(1, transmitted + 1):
        if n in known:
            out[n] = known[n]
            continue
        prev = max((k for k in known if k < n), default=None)
        nxt = min((k for k in known if k > n), default=None)
        if prev is not None and nxt is not None:
            out[n] = known[prev] + (known[nxt] - known[prev]) * (n - prev) / (nxt - prev)
        elif prev is not None:
            out[n] = known[prev]
        elif nxt is not None:
            out[n] = known[nxt]
    return out


def rule_packets(dump: str, match: str) -> int:
    """dump-flows 출력에서 `match` 문자열을 포함한 규칙의 n_packets 합."""
    total = 0
    for line in dump.splitlines():
        if match in line:
            m = re.search(r"n_packets=(\d+)", line)
            total += int(m.group(1)) if m else 0
    return total


def window_loss(times: Dict[int, float], received: List[int], t_from: float, t_to: float) -> Dict[str, float]:
    """[t_from, t_to) 시각에 해당하는 ping의 손실."""
    got = set(received)
    sent = [n for n, t in times.items() if t_from <= t < t_to]
    lost = [n for n in sent if n not in got]
    return {"sent": len(sent), "lost": len(lost),
            "loss_percent": round(100 * len(lost) / len(sent), 2) if sent else 0.0}


def first(events: List[Dict[str, Any]], kind: str, action: Optional[str] = None) -> Optional[Dict[str, Any]]:
    return next((e for e in events if e["kind"] == kind and (action is None or e.get("action") == action)), None)


def analyze(run: Dict[str, Any], events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """시나리오 기록과 방어 루프 이벤트를 합쳐 단계별 지표를 만든다."""
    p = run["ping"]
    a0, a1 = run["attack_start"], run["attack_end"]
    alert = first(events, "alert")
    iso = first(events, "command", "ISOLATE")
    rer = first(events, "command", "REROUTE")
    res = first(events, "command", "RESTORE")
    t_iso = iso["t"] if iso else a1

    times = seq_times(p["transmitted"], p["received_seqs"], p.get("reply_ts", []))
    t_end = max(times.values(), default=a1) + 1

    def loss(t_from: float, t_to: float) -> Dict[str, float]:
        return window_loss(times, p["received_seqs"], t_from, t_to)

    def sample_t(stats_ts: float) -> Optional[float]:
        e = next((e for e in events if e["kind"] == "sample" and e.get("stats_ts") == stats_ts), None)
        return e["t"] if e else None

    flows = run["flow_samples"]
    dst_rule = [s["s1_dst_server_p10"] for s in flows if t_iso <= s["t"] <= a1]
    drop_rule = [s["s1_drop_in2"] for s in flows if t_iso <= s["t"] <= a1]
    return {
        "attack_seconds": round(a1 - a0, 1),
        "attack_packets": run["attack_packets_at_s1_port2"],
        "detect_after_attack_s": round(alert["t"] - a0, 2) if alert else None,
        "first_alert_to_isolate_ms": round((iso["t"] - alert["t"]) * 1000, 1) if alert and iso else None,
        "decision_to_isolated_ms": (round((iso["t"] - st) * 1000, 1)
                                    if iso and (st := sample_t(iso["stats_ts"])) is not None else None),
        "flow_install_ms": {"REROUTE": rer["apply_ms"] if rer else None, "ISOLATE": iso["apply_ms"] if iso else None},
        "isolate_count": sum(1 for e in events if e["kind"] == "command" and e.get("action") == "ISOLATE"),
        "restore_count": sum(1 for e in events if e["kind"] == "command" and e.get("action") == "RESTORE"),
        "recovery_after_attack_s": round(res["t"] - a1, 2) if res else None,
        "dropped_at_s1_while_isolated": (drop_rule[-1] - drop_rule[0]) if len(drop_rule) > 1 else 0,
        "leaked_to_server_while_isolated": (dst_rule[-1] - dst_rule[0]) if len(dst_rule) > 1 else 0,
        "normal_loss": {
            "whole_run": loss(p["start"] - 1, t_end),
            "before_attack": loss(p["start"], a0),
            "attack_until_isolated": loss(a0, t_iso),
            "attack_while_isolated": loss(t_iso, a1),
            "after_attack": loss(a1, t_end),
        },
    }


# ---------------------------------------------------------------------------
# Mininet run (root)
# ---------------------------------------------------------------------------
def _dump(sw: str) -> str:
    return subprocess.run(["ovs-ofctl", "-O", "OpenFlow13", "dump-flows", sw],
                          capture_output=True, text=True).stdout


def run(before: int, attack: int, after: int, userspace: bool) -> Dict[str, Any]:
    from mininet.log import setLogLevel
    from mininet.net import Mininet
    from mininet.node import OVSSwitch, RemoteController

    sys.path.insert(0, str(REPO_ROOT / "topo"))
    from diamond_topo import DiamondTopo

    setLogLevel("warning")
    net = Mininet(topo=DiamondTopo(), controller=None, switch=OVSSwitch, autoSetMacs=False, autoStaticArp=False)
    net.addController("c0", controller=RemoteController, ip="127.0.0.1", port=6653)
    if userspace:
        for sw in net.switches:
            sw.datapath = "user"
    net.start()
    samples: List[Dict[str, Any]] = []
    stop = threading.Event()

    def sample_flows() -> None:
        while not stop.is_set():
            d = _dump("s1")
            samples.append({"t": time.time(),
                            "s1_drop_in2": rule_packets(d, "actions=drop"),
                            "s1_dst_server_p10": rule_packets(d, "priority=10,ip,nw_dst=10.0.0.4")})
            stop.wait(1.0)

    try:
        for sw in net.switches:
            sw.cmd(f"ovs-vsctl set bridge {sw.name} protocols=OpenFlow13")
        time.sleep(2)
        pingall_loss = net.pingAll()
        legit, attacker, s1 = net.get("h_legit"), net.get("h_attacker"), net.get("s1")
        total = before + attack + after
        threading.Thread(target=sample_flows, daemon=True).start()

        ping_start = time.time()
        legit.sendCmd(f"ping -D -i {PING_INTERVAL} -w {total} 10.0.0.4")
        time.sleep(before)
        port_before = s1.cmd("ovs-ofctl -O OpenFlow13 dump-ports s1 2")
        attack_start = time.time()
        attack_out = attacker.cmd(
            f"cd {REPO_ROOT} && .venv/bin/python -m traffic.traffic_attack --dst 10.0.0.4 --duration {attack}")
        attack_end = time.time()
        port_after = s1.cmd("ovs-ofctl -O OpenFlow13 dump-ports s1 2")
        ping_out = legit.waitOutput()
        stop.set()
    finally:
        net.stop()

    def rx(dump: str) -> int:
        m = re.search(r"rx pkts=(\d+)", dump)
        return int(m.group(1)) if m else 0

    return {
        "pingall_loss_percent": pingall_loss,
        "ping": {"start": ping_start, **parse_ping_d(ping_out)},
        "attack_start": attack_start,
        "attack_end": attack_end,
        "attack_packets_at_s1_port2": rx(port_after) - rx(port_before),
        "attacker_stdout": attack_out.strip().splitlines()[-1:] if attack_out.strip() else [],
        "flow_samples": samples,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="4단계 E2E 종합 시나리오")
    parser.add_argument("--before", type=int, default=20, help="공격 전 정상 구간(초)")
    parser.add_argument("--attack", type=int, default=20, help="공격 시간(초)")
    parser.add_argument("--after", type=int, default=30, help="공격 후 관찰 구간(초)")
    parser.add_argument("--userspace", action="store_true")
    parser.add_argument("--out", type=Path, default=Path("e2e_run.json"))
    parser.add_argument("--analyze", type=Path, help="기존 실행 기록을 분석만 한다")
    parser.add_argument("--events", type=Path, help="방어 루프 이벤트 로그 (jsonl)")
    args = parser.parse_args()
    if args.analyze:
        run_rec = json.loads(args.analyze.read_text())
        events = [json.loads(line) for line in args.events.read_text().splitlines()] if args.events else []
        print(json.dumps(analyze(run_rec, events), ensure_ascii=False, indent=2))
        return
    args.out.write_text(json.dumps(run(args.before, args.attack, args.after, args.userspace), ensure_ascii=False))
    print(f"saved {args.out}")


if __name__ == "__main__":
    main()
