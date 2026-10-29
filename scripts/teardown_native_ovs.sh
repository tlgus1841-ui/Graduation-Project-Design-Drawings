#!/usr/bin/env bash
# ==============================================================================
# Self-Defending SDN Tower: Native OVS Topology Teardown & Clean
# ==============================================================================
set -euo pipefail

# Root 권한 확인
if [[ $EUID -ne 0 ]]; then
  echo "❌ 오류: 본 스크립트는 네트워크 네임스페이스 및 OVS 조작을 위해 root 권한(sudo)이 필요합니다." >&2
  exit 1
fi

echo ">>> [1/3] OVS 브릿지 삭제..."
for sw in s1 s2 s3 s4; do
  ovs-vsctl --if-exists del-br "$sw" 2>/dev/null || true
done

echo ">>> [2/3] 네트워크 네임스페이스 삭제..."
for ns in ns_legit ns_attacker ns_server; do
  ip netns del "$ns" 2>/dev/null || true
done

echo ">>> [3/3] 잔여 veth 링크 정리..."
for link in s1-s2 s1-s3 s2-s4 s3-s4 s1-legit s1-attacker s4-server; do
  ip link del "$link" 2>/dev/null || true
done

echo "=== ✅ Native OVS 토폴로지 정리 완료 ==="
