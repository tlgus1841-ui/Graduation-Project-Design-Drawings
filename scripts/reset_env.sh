#!/usr/bin/env bash
# ==============================================================================
# Self-Defending SDN Tower: Environment Cleanup and Reset Tool
# Author: Sihyeon Park (22101489 / Tech Lead)
# Phase 6 (Week 15 & 16) Milestone
# ==============================================================================

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=============================================================================="
echo "🧹 Resetting Self-Defending SDN Tower Environment..."
echo "=============================================================================="

# 1. Kill stale traffic generators / python scripts
echo "[1/4] Stopping background traffic generators, AI workers, and ping probes..."
pkill -f "traffic/traffic_attack.py" 2>/dev/null || true
pkill -f "traffic/traffic_normal.py" 2>/dev/null || true
pkill -f "traffic.traffic_attack" 2>/dev/null || true
pkill -f "traffic.traffic_normal" 2>/dev/null || true
pkill -f "model.inference_worker" 2>/dev/null || true
pkill -f "ping -i" 2>/dev/null || true

# 2. Clean Native OVS & Network Namespaces
echo "[2/4] Cleaning Native OVS bridges, network namespaces, and veth links..."
if [[ -f "${ROOT_DIR}/scripts/teardown_native_ovs.sh" ]]; then
    sudo "${ROOT_DIR}/scripts/teardown_native_ovs.sh" 2>/dev/null || true
else
    if command -v ovs-vsctl &> /dev/null; then
        for sw in s1 s2 s3 s4; do
            sudo ovs-vsctl --if-exists del-br "$sw" 2>/dev/null || true
        done
    fi
    for ns in ns_legit ns_attacker ns_server; do
        sudo ip netns del "$ns" 2>/dev/null || true
    done
    for link in s1-s2 s1-s3 s2-s4 s3-s4 s1-legit s1-attacker s4-server; do
        sudo ip link del "$link" 2>/dev/null || true
    done
fi

# 3. Clean Legacy Mininet if installed
if command -v mn &> /dev/null; then
    echo "[3/4] Running legacy Mininet cleanup (sudo mn -c)..."
    sudo mn -c 2>/dev/null || true
fi

# 4. Flush Redis test keys if Redis is available
if command -v redis-cli &> /dev/null && redis-cli ping &> /dev/null; then
    echo "[4/4] Flushing Redis database..."
    redis-cli flushdb > /dev/null || true
else
    echo "[4/4] Redis not active on localhost:6379, skipping flush."
fi

echo "=============================================================================="
echo "✅ Environment cleanup complete! Ready for fresh demo run."
echo "=============================================================================="
