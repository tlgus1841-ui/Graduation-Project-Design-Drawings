"""10주차 실증: 정상 트래픽이 흐르는 도중 우회 경로(S1→S3→S4)로 바꿔도 패킷이 유실되지 않는지 측정한다.

H_legit → H_server로 10ms 간격 ping을 연속으로 보내는 동안 우회 규칙(Priority 100)을 주입하고,
ping 손실률과 우회 규칙의 패킷 카운터로 전환 성공과 무유실 여부를 확인한다.

우회 규칙은 "아래쪽부터" 설치한다(S3 → S4 → 마지막에 S1). S1이 길을 바꾸는 순간 S3·S4에는 이미
규칙이 있어야 첫 패킷부터 끊김 없이 이어진다 (계획서의 선제적 OFPFC_ADD 원칙).

현재는 컨트롤러의 REROUTE 구현 전이라 `ovs-ofctl`로 같은 규칙을 직접 주입해 경로 전환을 재현한다.
컨트롤러가 REROUTE를 지원하면 --via-controller 모드로 바꿔 같은 측정을 반복한다(검증서 §5).

사전 조건: Ryu 컨트롤러(127.0.0.1:6653) 실행, root 권한.
실행 예:
    sudo python3 -m harness.verification.reroute_loss_check --count 1000 --out reroute_check.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
PRIORITY_REROUTE = 100

# (스위치, 목적지 IP, 출력 포트) — 설치 순서가 곧 make-before-break 순서다.
BYPASS_FLOWS: List[Tuple[str, str, int]] = [
    ("s3", "10.0.0.4", 2),  # S3 → S4
    ("s3", "10.0.0.1", 1),  # S3 → S1 (복귀)
    ("s4", "10.0.0.1", 3),  # S4 → S3 (복귀 경로도 우회)
    ("s1", "10.0.0.4", 4),  # 마지막에 입구 S1을 S3 쪽으로 전환
]


def flow_add_cmd(switch: str, dst: str, port: int, priority: int = PRIORITY_REROUTE) -> str:
    return (f"ovs-ofctl -O OpenFlow13 add-flow {switch} "
            f"priority={priority},ip,nw_dst={dst},actions=output:{port}")


def parse_ping(output: str) -> Dict[str, float]:
    """`ping -q` 요약 줄에서 전송·수신·손실률을 꺼낸다."""
    m = re.search(r"(\d+) packets transmitted, (\d+) (?:packets )?received.*?([\d.]+)% packet loss", output)
    if not m:
        return {"transmitted": 0, "received": 0, "loss_percent": 100.0}
    return {"transmitted": int(m.group(1)), "received": int(m.group(2)), "loss_percent": float(m.group(3))}


def flow_packets(dump_flows_output: str, dst: str, priority: int) -> int:
    """특정 우선순위·목적지 규칙의 n_packets를 꺼낸다 (없으면 0)."""
    for line in dump_flows_output.splitlines():
        if f"priority={priority}," in line and f"nw_dst={dst}" in line:
            m = re.search(r"n_packets=(\d+)", line)
            return int(m.group(1)) if m else 0
    return 0


def run(count: int, interval: float, switch_after: float, userspace: bool, out: Path) -> Dict[str, object]:
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
        loss_all = net.pingAll()
        legit, s1 = net.get("h_legit"), net.get("s1")
        ping = f"ping -q -i {interval} -c {count} 10.0.0.4"

        # 1) 기준선: 경로 전환 없이 같은 ping
        baseline = parse_ping(legit.cmd(ping))

        # 2) 측정: ping 도중 우회 규칙 주입
        legit.sendCmd(ping)
        time.sleep(switch_after)
        installed_at = []
        for sw, dst, port in BYPASS_FLOWS:
            s1.cmd(flow_add_cmd(sw, dst, port))
            installed_at.append({"switch": sw, "dst": dst, "port": port, "t": round(time.time(), 3)})
        rerouted = parse_ping(legit.waitOutput())

        dumps = {sw: s1.cmd(f"ovs-ofctl -O OpenFlow13 dump-flows {sw}") for sw in ("s1", "s3", "s4")}
        bypass_hits = {
            "s1_to_s3": flow_packets(dumps["s1"], "10.0.0.4", PRIORITY_REROUTE),
            "s3_to_s4": flow_packets(dumps["s3"], "10.0.0.4", PRIORITY_REROUTE),
            "s4_return_via_s3": flow_packets(dumps["s4"], "10.0.0.1", PRIORITY_REROUTE),
        }
    finally:
        net.stop()

    result: Dict[str, object] = {
        "pingall_loss_percent": loss_all,
        "ping": {"count": count, "interval_s": interval, "switch_after_s": switch_after},
        "baseline": baseline,
        "rerouted": rerouted,
        "bypass_rule_hits": bypass_hits,
        "install_order": installed_at,
        "switched": all(v > 0 for v in bypass_hits.values()),
        "zero_loss": rerouted["transmitted"] > 0 and rerouted["received"] == rerouted["transmitted"],
    }
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="우회 경로 전환 중 정상 트래픽 유실률 측정")
    parser.add_argument("--count", type=int, default=1000, help="ping 개수")
    parser.add_argument("--interval", type=float, default=0.01, help="ping 간격(초)")
    parser.add_argument("--switch-after", type=float, default=3.0, help="ping 시작 후 우회 규칙 주입까지(초)")
    parser.add_argument("--userspace", action="store_true", help="OVS 유저스페이스 데이터패스 사용 (WSL 등)")
    parser.add_argument("--out", type=Path, default=Path("reroute_loss_check.json"), help="결과 JSON 경로")
    args = parser.parse_args()
    r = run(args.count, args.interval, args.switch_after, args.userspace, args.out)
    print(json.dumps({k: r[k] for k in ("baseline", "rerouted", "bypass_rule_hits", "switched", "zero_loss")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
