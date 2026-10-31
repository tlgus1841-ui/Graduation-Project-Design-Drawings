#!/usr/bin/env bash
# ==============================================================================
# Self-Defending SDN Tower: Native OVS 10-Switch Topology Teardown & Clean
# Enterprise Production Milestone (Phase 6-C Enterprise Standard)
# ==============================================================================
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "❌ 오류: 본 스크립트는 네트워크 네임스페이스 및 OVS 조작을 위해 root 권한(sudo)이 필요합니다." >&2
  exit 1
fi

echo ">>> [1/4] 패치/웹 서버 데몬 및 임시 디렉토리 정리..."
pkill -f "http.server 80 --directory /tmp/sdn_patch_root" 2>/dev/null || true
pkill -f "http.server 80 --directory /tmp/sdn_web_root" 2>/dev/null || true
rm -rf /tmp/sdn_patch_root /tmp/sdn_patch_server.log /tmp/sdn_web_root /tmp/sdn_web_server.log 2>/dev/null || true

# Docker container cleanup if present
if command -v docker &>/dev/null; then
  docker rm -f sdn-patch-server 2>/dev/null || true
fi

echo ">>> [2/4] OVS 브릿지 10개 (S1~S10) 삭제..."
for sw_num in {1..10}; do
  ovs-vsctl --if-exists del-br "s${sw_num}" 2>/dev/null || true
done

echo ">>> [3/4] 호스트 네트워크 네임스페이스 11개 삭제..."
for ns in ns_h1 ns_h2 ns_h3 ns_h4 ns_web1 ns_web2 ns_h5 ns_h6 ns_admin ns_patch ns_sink ns_ext; do
  ip netns del "$ns" 2>/dev/null || true
done

echo ">>> [4/4] 잔여 veth 인터페이스 링크 정리..."
# Trunk links
for pair in s1-s2 s2-s1 \
            s1-s3 s3-s1 s1-s4 s4-s1 s1-s5 s5-s1 s1-s6 s6-s1 s1-s7 s7-s1 s1-s8 s8-s1 s1-s9 s9-s1 s1-s10 s10-s1 \
            s2-s3 s3-s2 s2-s4 s4-s2 s2-s5 s5-s2 s2-s6 s6-s2 s2-s7 s7-s2 s2-s8 s8-s2 s2-s9 s9-s2 s2-s10 s10-s2; do
  ip link del "$pair" 2>/dev/null || true
done

# Host access links
for ns in ns_h1 ns_h2 ns_h3 ns_h4 ns_web1 ns_web2 ns_h5 ns_h6 ns_admin ns_patch ns_sink ns_ext; do
  ip link del "vs_${ns}" 2>/dev/null || true
  ip link del "vh_${ns}" 2>/dev/null || true
done

echo "=== ✅ Large 10-Switch 토폴로지 클린업 완료 ==="
