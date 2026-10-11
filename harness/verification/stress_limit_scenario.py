"""Self-Defending SDN Tower - 3-Tier High-PPS Destructive Stress Test Scenario.

실행 환경 (Mininet + OVS + Docker Ryu/Redis 실행 중, root 권한 필요):
    sudo .venv/bin/python -m harness.verification.stress_limit_scenario \
        --out docs/writing/reports/verification/data/week16_stress_limit_test.json  # noqa: E501
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
from typing import Any, Dict, List

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_REPO_ROOT / "topo") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "topo"))

from harness.verification.e2e_scenario import (  # noqa: E402
    analyze,
    parse_ping_d,
    rule_packets,
)


def _dump(sw: str) -> str:
    return subprocess.run(
        ["ovs-ofctl", "-O", "OpenFlow13", "dump-flows", sw],
        capture_output=True,
        text=True,
    ).stdout


def _build_blaster_script(target_pps: int, workers: int, duration: int) -> str:
    """H_attacker 내부에서 AF_PACKET Raw Socket으로 초고속 SYN을 투하하는 스크립트 생성."""
    pps_per_worker = max(1, target_pps // max(1, workers))
    return f"""import multiprocessing
import random
import socket
import time
from scapy.layers.inet import IP, TCP
from scapy.layers.l2 import Ether

pool = [
    bytes(
        Ether(src="00:00:00:00:00:02", dst="00:00:00:00:00:04")
        / IP(
            src=f"{{random.randint(11, 220)}}.{{random.randint(0, 255)}}."
            f"{{random.randint(0, 255)}}.{{random.randint(1, 254)}}",
            dst="10.0.0.4",
        )
        / TCP(sport=random.randint(1024, 65535), dport=80, flags="S")
    )
    for _ in range(512)
]


def blast(pps_quota: int, dur: int) -> None:
    s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW)
    s.bind(("h_attacker-eth1", 0))
    end = time.monotonic() + dur
    batch = max(1, min(500, pps_quota // 100))
    interval = batch / pps_quota if pps_quota < 500000 else 0.0
    while time.monotonic() < end:
        t0 = time.monotonic()
        for i in range(batch):
            try:
                s.send(pool[i & 511])
            except Exception:
                pass
        if interval > 0.0:
            rem = interval - (time.monotonic() - t0)
            if rem > 0.0:
                time.sleep(rem)


if __name__ == "__main__":
    procs = [
        multiprocessing.Process(
            target=blast, args=({pps_per_worker}, {duration})
        )
        for _ in range({workers})
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
"""


def run_tier(
    target_pps: int,
    workers: int,
    duration: int = 12,
    model_path: str = "/tmp/iforest.joblib",
) -> Dict[str, Any]:
    from diamond_topo import DiamondTopo
    from mininet.log import setLogLevel
    from mininet.net import Mininet
    from mininet.node import OVSSwitch, RemoteController

    subprocess.run(
        ["mn", "-c"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    subprocess.run(
        ["docker", "compose", "restart", "ryu-controller"],
        cwd=str(_REPO_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(3)

    events_file = Path(f"/tmp/stress_events_{target_pps}.jsonl")
    events_file.unlink(missing_ok=True)
    worker_proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "model.inference_worker",
            "--model",
            model_path,
            "--log",
            str(events_file),
        ],
        cwd=str(_REPO_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(2)

    setLogLevel("warning")
    net = Mininet(
        topo=DiamondTopo(),
        controller=None,
        switch=OVSSwitch,
        autoSetMacs=False,
        autoStaticArp=False,
    )
    net.addController(
        "c0", controller=RemoteController, ip="127.0.0.1", port=6653
    )
    net.start()

    samples: List[Dict[str, Any]] = []
    stop = threading.Event()

    def sample_flows() -> None:
        while not stop.is_set():
            d = _dump("s1")
            samples.append(
                {
                    "t": time.time(),
                    "s1_drop_in2": rule_packets(d, "actions=drop"),
                    "s1_dst_server_p10": rule_packets(
                        d, "priority=10,ip,nw_dst=10.0.0.4"
                    ),
                    "s1_bypass_p100": rule_packets(
                        d, "priority=20,ip,nw_dst=10.0.0.4"
                    ),
                }
            )
            stop.wait(0.5)

    try:
        for sw in net.switches:
            sw.cmd(f"ovs-vsctl set bridge {sw.name} protocols=OpenFlow13")
        time.sleep(2)
        net.pingAll()
        legit = net.get("h_legit")
        attacker = net.get("h_attacker")
        s1 = net.get("s1")
        before, after = 4, 14
        total = before + duration + after
        threading.Thread(target=sample_flows, daemon=True).start()

        ping_log = f"/tmp/stress_ping_{target_pps}.txt"
        ping_start = time.time()
        legit.cmd(f"ping -D -i 0.05 -w {total} 10.0.0.4 > {ping_log} 2>&1 &")
        time.sleep(before)

        port_before = s1.cmd("ovs-ofctl -O OpenFlow13 dump-ports s1 2")
        attack_start = time.time()

        blaster_path = Path("/tmp/blaster.py")
        blaster_script = _build_blaster_script(target_pps, workers, duration)
        blaster_path.write_text(blaster_script)
        attacker.cmd(f"{sys.executable} {blaster_path}")
        attack_end = time.time()
        port_after = s1.cmd("ovs-ofctl -O OpenFlow13 dump-ports s1 2")
        legit.cmd("wait")
        ping_out = legit.cmd(f"cat {ping_log}")
        stop.set()
    finally:
        net.stop()
        worker_proc.terminate()
        worker_proc.wait()

    def rx(dump: str) -> int:
        m = re.search(r"rx pkts=(\d+)", dump)
        return int(m.group(1)) if m else 0

    attack_pkts = rx(port_after) - rx(port_before)
    run_rec: Dict[str, Any] = {
        "ping": {"start": ping_start, **parse_ping_d(ping_out)},
        "attack_start": attack_start,
        "attack_end": attack_end,
        "attack_packets_at_s1_port2": attack_pkts,
        "flow_samples": samples,
    }
    events = (
        [json.loads(line) for line in events_file.read_text().splitlines()]
        if events_file.exists()
        else []
    )
    res = analyze(run_rec, events)
    res["actual_pps"] = round(attack_pkts / (attack_end - attack_start), 1)
    ryu_logs = subprocess.run(
        ["docker", "logs", "sdn-ryu", "--tail", "60"],
        capture_output=True,
        text=True,
    ).stdout
    res["ryu_errors"] = [
        line
        for line in ryu_logs.splitlines()
        if any(k in line for k in ("Error", "Exception", "CircuitBreaker"))
    ]
    return res


def main() -> None:
    parser = argparse.ArgumentParser(
        description="3-Tier High-PPS Destructive Stress Test Runner"
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("/tmp/stress_results.json"),
        help="Output JSON file path",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=12,
        help="Attack duration per tier in seconds",
    )
    args = parser.parse_args()

    tiers = [
        ("Tier1_15k_PPS", 15000, 1),
        ("Tier2_60k_PPS", 60000, 2),
        ("Tier3_Max_Unthrottled", 999999, 4),
    ]
    results: Dict[str, Any] = {}
    for label, pps, w in tiers:
        print(f"Running {label}...", flush=True)
        results[label] = run_tier(pps, w, duration=args.duration)
        print(json.dumps({label: results[label]}, indent=2), flush=True)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("ALL_DONE")


if __name__ == "__main__":
    main()
