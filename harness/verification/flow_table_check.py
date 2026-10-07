"""9주차 실증: IP 스푸핑 SYN Flood 동안 스위치 플로우 테이블이 폭증하지 않는지 측정한다.

출발지 IP를 패킷마다 바꾸는 공격에 컨트롤러가 출발지 기준 규칙을 만들면 규칙 수가 패킷 수만큼
늘어난다(플로우 테이블 폭발). 이 스크립트는 다이아몬드 토폴로지에서 공격기를 돌리는 동안
1초마다 각 스위치의 플로우 개수를 기록해 증가 여부를 확인한다.

사전 조건: Ryu 컨트롤러(127.0.0.1:6653)와 Redis가 실행 중이어야 한다. Mininet은 root 권한 필요.
실행 예:
    sudo python3 -m harness.verification.flow_table_check --duration 10 --out flow_check.json
(Mininet이 설치된 시스템 python3로 실행하고, 공격기는 저장소의 .venv 파이썬으로 띄운다.)
WSL 등 OVS 커널 모듈이 없는 환경에서는 --userspace 를 붙인다.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
from pathlib import Path
from typing import Dict, List

SWITCHES = ("s1", "s2", "s3", "s4")
REPO_ROOT = Path(__file__).resolve().parents[2]


def count_flows(dump_flows_output: str) -> int:
    """`ovs-ofctl dump-flows` 출력에서 플로우 항목 수를 센다 (헤더 줄 제외)."""
    return sum(1 for line in dump_flows_output.splitlines() if "priority=" in line)


def rx_packets(dump_ports_output: str) -> int:
    """`ovs-ofctl dump-ports <sw> <port>` 출력에서 수신 패킷 수를 꺼낸다."""
    m = re.search(r"rx pkts=(\d+)", dump_ports_output)
    return int(m.group(1)) if m else 0


def summarize(samples: List[Dict[str, int]]) -> Dict[str, Dict[str, int]]:
    """스위치별 공격 전(첫 샘플) 대비 최대 증가량을 계산한다."""
    if not samples:
        return {}
    first = samples[0]
    return {
        sw: {"before": first[sw], "max": max(s[sw] for s in samples), "growth": max(s[sw] for s in samples) - first[sw]}
        for sw in SWITCHES
    }


def run(duration: int, userspace: bool, out: Path) -> Dict[str, object]:
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
    try:
        for sw in net.switches:
            sw.cmd(f"ovs-vsctl set bridge {sw.name} protocols=OpenFlow13")
        time.sleep(2)
        loss = net.pingAll()

        s1 = net.get("s1")

        def flows() -> Dict[str, int]:
            return {sw: count_flows(s1.cmd(f"ovs-ofctl -O OpenFlow13 dump-flows {sw}")) for sw in SWITCHES}

        samples: List[Dict[str, int]] = [flows()]
        rx0 = rx_packets(s1.cmd("ovs-ofctl -O OpenFlow13 dump-ports s1 2"))
        attacker = net.get("h_attacker")
        cmd = f"cd {REPO_ROOT} && .venv/bin/python -m traffic.traffic_attack --dst 10.0.0.4 --duration {duration}"
        done = threading.Event()
        attack_out: List[str] = []

        def attack() -> None:
            attack_out.append(attacker.cmd(cmd))
            done.set()

        t0 = time.time()
        threading.Thread(target=attack, daemon=True).start()
        while not done.is_set():
            time.sleep(1)
            samples.append(flows())
        elapsed = time.time() - t0
        samples.append(flows())
        rx1 = rx_packets(s1.cmd("ovs-ofctl -O OpenFlow13 dump-ports s1 2"))
        flow_dump_s1 = s1.cmd("ovs-ofctl -O OpenFlow13 dump-flows s1")
    finally:
        net.stop()

    result: Dict[str, object] = {
        "pingall_loss_percent": loss,
        "attack_packets_at_s1_port2": rx1 - rx0,
        "attack_seconds": round(elapsed, 1),
        "attack_pps": round((rx1 - rx0) / elapsed) if elapsed else 0,
        "flow_samples": samples,
        "flow_summary": summarize(samples),
        "s1_flows_after_attack": flow_dump_s1.strip().splitlines(),
        "attacker_stdout": attack_out[0].strip().splitlines()[-1:] if attack_out else [],
    }
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="IP 스푸핑 공격 중 플로우 테이블 증가량 측정")
    parser.add_argument("--duration", type=int, default=10, help="공격 시간(초)")
    parser.add_argument("--userspace", action="store_true", help="OVS 유저스페이스 데이터패스 사용 (WSL 등)")
    parser.add_argument("--out", type=Path, default=Path("flow_table_check.json"), help="결과 JSON 경로")
    args = parser.parse_args()
    result = run(args.duration, args.userspace, args.out)
    print(json.dumps(result["flow_summary"], ensure_ascii=False))
    print(f"pingall loss {result['pingall_loss_percent']}%, attack {result['attack_packets_at_s1_port2']} pkts "
          f"in {result['attack_seconds']}s ({result['attack_pps']} PPS)")


if __name__ == "__main__":
    main()
