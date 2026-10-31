#!/usr/bin/env bash
# ==============================================================================
# Self-Defending SDN Tower: Native OVS Large 8-Switch 5-Zone Topology Setup
# Phase 6-C-1 Milestone
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
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# [멱등성 보장] 기존 잔여 브릿지 및 네임스페이스 사전 정리
if [[ -f "${SCRIPT_DIR}/cleanup_large_ovs.sh" ]]; then
  echo ">>> [0/6] 기존 잔여 8-스위치 토폴로지 사전 클린업..."
  bash "${SCRIPT_DIR}/cleanup_large_ovs.sh" >/dev/null 2>&1 || true
fi

# ------------------------------------------------------------------------------
# 1. OVS 브릿지 8개 생성 및 OpenFlow 1.3 / DPID 설정
# ------------------------------------------------------------------------------
echo ">>> [1/6] OVS 브릿지 8개 생성 (S1~S8) 및 DPID 고정..."
for sw_num in {1..8}; do
  sw="s${sw_num}"
  ovs-vsctl --may-exist add-br "$sw"
  ovs-vsctl set bridge "$sw" protocols=OpenFlow13
  ovs-vsctl set-fail-mode "$sw" secure
  hex_dpid=$(printf "00000000000000%02x" "$sw_num")
  ovs-vsctl set bridge "$sw" other-config:datapath-id="$hex_dpid"
done

# ------------------------------------------------------------------------------
# 2. Ryu SDN 컨트롤러 연결
# ------------------------------------------------------------------------------
echo ">>> [2/6] Ryu SDN 컨트롤러 연결 (${CTRL_IP}:${CTRL_PORT})..."
for sw_num in {1..8}; do
  sw="s${sw_num}"
  ovs-vsctl set-controller "$sw" "tcp:${CTRL_IP}:${CTRL_PORT}"
  ovs-vsctl set controller "$sw" inactivity_probe=15000
done

# ------------------------------------------------------------------------------
# 3. 스위치 간 트렁크 veth 페어 생성 및 연결
# ------------------------------------------------------------------------------
echo ">>> [3/6] 스위치 간 트렁크 링크 veth 구축..."

create_trunk_link() {
  local u=$1; local v=$2; local u_port=$3; local v_port=$4
  local if_u="${u}-${v}"
  local if_v="${v}-${u}"

  ip link add "$if_u" type veth peer name "$if_v"
  ip link set "$if_u" up mtu 1500
  ip link set "$if_v" up mtu 1500

  ethtool -K "$if_u" tx off rx off gso off gro off tso off 2>/dev/null || true
  ethtool -K "$if_v" tx off rx off gso off gro off tso off 2>/dev/null || true

  ovs-vsctl add-port "$u" "$if_u" -- set Interface "$if_u" ofport_request="$u_port"
  ovs-vsctl add-port "$v" "$if_v" -- set Interface "$if_v" ofport_request="$v_port"
}

# Core S1 <-> S2
create_trunk_link "s1" "s2" 1 1

# S1 to Edges
create_trunk_link "s1" "s3" 2 99
create_trunk_link "s1" "s5" 3 99
create_trunk_link "s1" "s7" 4 98
create_trunk_link "s1" "s8" 5 98

# S2 to Edges
create_trunk_link "s2" "s4" 2 99
create_trunk_link "s2" "s6" 3 99
create_trunk_link "s2" "s7" 4 99
create_trunk_link "s2" "s8" 5 99

# ------------------------------------------------------------------------------
# 4. 호스트 네트워크 네임스페이스 생성 및 스위치 연결
# ------------------------------------------------------------------------------
echo ">>> [4/6] 호스트 네임스페이스 및 Access veth 링크 구축..."

create_host() {
  local ns=$1; local sw=$2; local port=$3; local ip_addr=$4; local mac_addr=$5
  local veth_host="vh_${ns}"
  local veth_sw="vs_${ns}"

  ip netns add "$ns"

  ip link add "$veth_host" type veth peer name "$veth_sw"
  ip link set "$veth_host" netns "$ns"
  ip link set "$veth_sw" up mtu 1500

  ip -n "$ns" link set dev "$veth_host" address "$mac_addr"
  ip -n "$ns" addr add "$ip_addr/24" dev "$veth_host"
  ip -n "$ns" link set dev "$veth_host" up
  ip -n "$ns" link set dev lo up

  ethtool -K "$veth_sw" tx off rx off gso off gro off tso off 2>/dev/null || true
  ip netns exec "$ns" ethtool -K "$veth_host" tx off rx off gso off gro off tso off 2>/dev/null || true

  ovs-vsctl add-port "$sw" "$veth_sw" -- set Interface "$veth_sw" ofport_request="$port"
}

# User Zone (S3: h1, h2 / S4: h3, h4)
create_host "ns_h1" "s3" 1 "10.0.0.1" "00:00:00:00:00:01"
create_host "ns_h2" "s3" 2 "10.0.0.2" "00:00:00:00:00:02"
create_host "ns_h3" "s4" 1 "10.0.0.3" "00:00:00:00:00:03"
create_host "ns_h4" "s4" 2 "10.0.0.4" "00:00:00:00:00:04"

# Server Zone (S5: h5, h6 / S6: h7, h8)
create_host "ns_h5" "s5" 1 "10.0.0.11" "00:00:00:00:00:11"
create_host "ns_h6" "s5" 2 "10.0.0.12" "00:00:00:00:00:12"
create_host "ns_h7" "s6" 1 "10.0.0.21" "00:00:00:00:00:21"
create_host "ns_h8" "s6" 2 "10.0.0.22" "00:00:00:00:00:22"

# Admin Zone (S7: h_admin, h_patch)
create_host "ns_admin" "s7" 1 "10.0.0.254" "00:00:00:00:00:fe"
create_host "ns_patch" "s7" 2 "10.0.0.253" "00:00:00:00:00:fd"

# Quarantine Zone (S8: h_sink)
create_host "ns_sink" "s8" 1 "10.0.0.250" "00:00:00:00:00:fa"

# ------------------------------------------------------------------------------
# 5. 보안 업데이트 패치 서버 서비스 기동 (10.0.0.253:80)
# ------------------------------------------------------------------------------
echo ">>> [5/6] 보안 업데이트 패치 서버 서비스 기동 (10.0.0.253:80)..."
mkdir -p /tmp/sdn_patch_root/patches
cp "${ROOT_DIR}/docker/patch_server/clean_agent.sh" /tmp/sdn_patch_root/patches/
chmod +x /tmp/sdn_patch_root/patches/clean_agent.sh
echo '<html><body><h1>SDN Patch Server (10.0.0.253)</h1><a href="/patches/clean_agent.sh">clean_agent.sh</a></body></html>' > /tmp/sdn_patch_root/index.html

# Fallback-safe HTTP server daemon inside ns_patch
ip netns exec ns_patch nohup python3 -m http.server 80 --directory /tmp/sdn_patch_root > /tmp/sdn_patch_server.log 2>&1 &
echo ">>> 패치 서버 PID: $! (ns_patch / 10.0.0.253:80)"

# ------------------------------------------------------------------------------
# 6. 토폴로지 링크 및 인터페이스 활성화 확인
# ------------------------------------------------------------------------------
echo ">>> [6/6] 인터페이스 활성화 및 검증..."
for sw_num in {1..8}; do
  ip link set "s${sw_num}" up || true
done

echo "=========================================================================="
echo "✅ Native OVS 8-Switch 5-Zone 엔터프라이즈 토폴로지 구성이 완료되었습니다!"
echo "   - Backbone: S1 (DPID: 0x01), S2 (DPID: 0x02)"
echo "   - User:     S3 (h1, h2), S4 (h3, h4)"
echo "   - Server:   S5 (h5 Web, h6 API), S6 (h7 DB, h8 Backup)"
echo "   - Admin:    S7 (h_admin: 10.0.0.254, h_patch: 10.0.0.253)"
echo "   - Quarantine: S8 (h_sink: 10.0.0.250)"
echo "=========================================================================="
