#!/usr/bin/env bash
# ==============================================================================
# Self-Defending SDN Tower: Native OVS 4-Switch Diamond Topology Setup
# Phase 6-A Milestone (Mininet Dependency Free)
# ==============================================================================
set -euo pipefail

# ------------------------------------------------------------------------------
# 0. Pre-flight Checks
# ------------------------------------------------------------------------------
if [[ $EUID -ne 0 ]]; then
  echo "❌ 오류: 본 스크립트는 네트워크 네임스페이스 및 OVS 조작을 위해 root 권한(sudo)이 필요합니다." >&2
  exit 1
fi

for cmd in ovs-vsctl ethtool ip; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "❌ 오류: 필수 명령어 '$cmd'를 찾을 수 없습니다." >&2
    echo "👉 설치 안내: sudo apt update && sudo apt install -y openvswitch-switch ethtool iproute2" >&2
    exit 1
  fi
done

if command -v systemctl &>/dev/null; then
  if ! systemctl is-active --quiet openvswitch-switch; then
    echo ">>> [Pre-flight] Open vSwitch 서비스 시작 중..."
    systemctl start openvswitch-switch || true
  fi
fi

CTRL_IP="${CTRL_IP:-127.0.0.1}"
CTRL_PORT="${CTRL_PORT:-6653}"  # OpenFlow 1.3 IANA 표준 포트
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# [멱등성 보장] 기존 잔여 브릿지 및 네임스페이스 사전 정리
if [[ -f "${SCRIPT_DIR}/teardown_native_ovs.sh" ]]; then
  echo ">>> [0/5] 기존 잔여 토폴로지 사전 클린업..."
  bash "${SCRIPT_DIR}/teardown_native_ovs.sh" >/dev/null 2>&1 || true
fi

# ------------------------------------------------------------------------------
# 1. OVS 브릿지 4개 생성 및 OpenFlow 1.3 설정
# ------------------------------------------------------------------------------
echo ">>> [1/5] OVS 브릿지 4개 생성 및 OpenFlow 1.3 설정..."
for sw in s1 s2 s3 s4; do
  ovs-vsctl --may-exist add-br "$sw"
  ovs-vsctl set bridge "$sw" protocols=OpenFlow13
  ovs-vsctl set-fail-mode "$sw" secure
done

# DPID 고정 (16자리 16진수)
ovs-vsctl set bridge s1 other-config:datapath-id=0000000000000001
ovs-vsctl set bridge s2 other-config:datapath-id=0000000000000002
ovs-vsctl set bridge s3 other-config:datapath-id=0000000000000003
ovs-vsctl set bridge s4 other-config:datapath-id=0000000000000004

# ------------------------------------------------------------------------------
# 2. Ryu SDN 컨트롤러 연결
# ------------------------------------------------------------------------------
echo ">>> [2/5] Ryu SDN 컨트롤러 연결 (${CTRL_IP}:${CTRL_PORT})..."
for sw in s1 s2 s3 s4; do
  ovs-vsctl set-controller "$sw" "tcp:${CTRL_IP}:${CTRL_PORT}"
  ovs-vsctl set controller "$sw" inactivity_probe=15000
done

# ------------------------------------------------------------------------------
# 3. 스위치 간 트렁크 veth 페어 생성 및 연결
# ------------------------------------------------------------------------------
echo ">>> [3/5] 스위치 간 트렁크 veth 페어 생성 및 연결..."

# S1 <-> S2 (S1 ofp:3, S2 ofp:1)
ip link add s1-s2 type veth peer name s2-s1
ovs-vsctl add-port s1 s1-s2 -- set Interface s1-s2 ofport_request=3
ovs-vsctl add-port s2 s2-s1 -- set Interface s2-s1 ofport_request=1
ip link set s1-s2 up && ip link set s2-s1 up
ethtool -K s1-s2 tx off rx off 2>/dev/null || true
ethtool -K s2-s1 tx off rx off 2>/dev/null || true

# S1 <-> S3 (S1 ofp:4, S3 ofp:1)
ip link add s1-s3 type veth peer name s3-s1
ovs-vsctl add-port s1 s1-s3 -- set Interface s1-s3 ofport_request=4
ovs-vsctl add-port s3 s3-s1 -- set Interface s3-s1 ofport_request=1
ip link set s1-s3 up && ip link set s3-s1 up
ethtool -K s1-s3 tx off rx off 2>/dev/null || true
ethtool -K s3-s1 tx off rx off 2>/dev/null || true

# S2 <-> S4 (S2 ofp:2, S4 ofp:2)
ip link add s2-s4 type veth peer name s4-s2
ovs-vsctl add-port s2 s2-s4 -- set Interface s2-s4 ofport_request=2
ovs-vsctl add-port s4 s4-s2 -- set Interface s4-s2 ofport_request=2
ip link set s2-s4 up && ip link set s4-s2 up
ethtool -K s2-s4 tx off rx off 2>/dev/null || true
ethtool -K s4-s2 tx off rx off 2>/dev/null || true

# S3 <-> S4 (S3 ofp:2, S4 ofp:3)
ip link add s3-s4 type veth peer name s4-s3
ovs-vsctl add-port s3 s3-s4 -- set Interface s3-s4 ofport_request=2
ovs-vsctl add-port s4 s4-s3 -- set Interface s4-s3 ofport_request=3
ip link set s3-s4 up && ip link set s4-s3 up
ethtool -K s3-s4 tx off rx off 2>/dev/null || true
ethtool -K s4-s3 tx off rx off 2>/dev/null || true

# ------------------------------------------------------------------------------
# 4. 호스트 네임스페이스 및 veth 연결
# ------------------------------------------------------------------------------
echo ">>> [4/5] 호스트 네임스페이스 및 veth 연결 (체크섬 오프로드 해제, rp_filter 해제, 기본 라우트 추가)..."

# [H_legit] (10.0.0.1, 00:00:00:00:00:01) -> S1 ofport: 1
ip netns add ns_legit
ip netns exec ns_legit sysctl -w net.ipv6.conf.all.disable_ipv6=1 >/dev/null
ip link add veth_legit type veth peer name s1-legit
ip link set veth_legit netns ns_legit
ovs-vsctl add-port s1 s1-legit -- set Interface s1-legit ofport_request=1
ip link set s1-legit up
ethtool -K s1-legit tx off rx off 2>/dev/null || true

ip netns exec ns_legit ip link set lo up
ip netns exec ns_legit ip link set veth_legit address 00:00:00:00:00:01
ip netns exec ns_legit ip addr add 10.0.0.1/24 dev veth_legit
ip netns exec ns_legit ip link set veth_legit up
ip netns exec ns_legit ip route add default via 10.0.0.254 dev veth_legit 2>/dev/null || true
ip netns exec ns_legit ethtool -K veth_legit tx off rx off 2>/dev/null || true

# [H_attacker] (10.0.0.2, 00:00:00:00:00:02) -> S1 ofport: 2
ip netns add ns_attacker
ip netns exec ns_attacker sysctl -w net.ipv6.conf.all.disable_ipv6=1 >/dev/null
# Scapy 무작위 IP 스푸핑 패킷이 커널에서 드랍되지 않도록 rp_filter 해제
ip netns exec ns_attacker sysctl -w net.ipv4.conf.all.rp_filter=0 >/dev/null
ip link add veth_att type veth peer name s1-attacker
ip link set veth_att netns ns_attacker
ovs-vsctl add-port s1 s1-attacker -- set Interface s1-attacker ofport_request=2
ip link set s1-attacker up
ethtool -K s1-attacker tx off rx off 2>/dev/null || true

ip netns exec ns_attacker ip link set lo up
ip netns exec ns_attacker ip link set veth_att address 00:00:00:00:00:02
ip netns exec ns_attacker ip addr add 10.0.0.2/24 dev veth_att
ip netns exec ns_attacker ip link set veth_att up
ip netns exec ns_attacker sysctl -w net.ipv4.conf.veth_att.rp_filter=0 >/dev/null
ip netns exec ns_attacker ip route add default via 10.0.0.254 dev veth_att 2>/dev/null || true
ip netns exec ns_attacker ethtool -K veth_att tx off rx off 2>/dev/null || true

# [H_server] (10.0.0.4, 00:00:00:00:00:04) -> S4 ofport: 1
ip netns add ns_server
ip netns exec ns_server sysctl -w net.ipv6.conf.all.disable_ipv6=1 >/dev/null
ip link add veth_srv type veth peer name s4-server
ip link set veth_srv netns ns_server
ovs-vsctl add-port s4 s4-server -- set Interface s4-server ofport_request=1
ip link set s4-server up
ethtool -K s4-server tx off rx off 2>/dev/null || true

ip netns exec ns_server ip link set lo up
ip netns exec ns_server ip link set veth_srv address 00:00:00:00:00:04
ip netns exec ns_server ip addr add 10.0.0.4/24 dev veth_srv
ip netns exec ns_server ip link set veth_srv up
ip netns exec ns_server ip route add default via 10.0.0.254 dev veth_srv 2>/dev/null || true
ip netns exec ns_server ethtool -K veth_srv tx off rx off 2>/dev/null || true

# ------------------------------------------------------------------------------
# 5. 정적 ARP (Neighbor) 테이블 구성 (iproute2 표준)
# ------------------------------------------------------------------------------
echo ">>> [5/5] 정적 ARP(Neighbor) 테이블 구성 (초기 브로드캐스트 스톰 방지)..."
ip netns exec ns_legit ip neigh replace 10.0.0.4 lladdr 00:00:00:00:00:04 dev veth_legit nud permanent
ip netns exec ns_attacker ip neigh replace 10.0.0.4 lladdr 00:00:00:00:00:04 dev veth_att nud permanent
ip netns exec ns_server ip neigh replace 10.0.0.1 lladdr 00:00:00:00:00:01 dev veth_srv nud permanent
ip netns exec ns_server ip neigh replace 10.0.0.2 lladdr 00:00:00:00:00:02 dev veth_srv nud permanent

echo "=== ✅ Native OVS 4-스위치 토폴로지 구축 완료 ==="
