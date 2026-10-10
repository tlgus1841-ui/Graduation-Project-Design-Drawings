#!/usr/bin/env bash
# ==============================================================================
# Self-Defending SDN Tower: Environment Cleanup and Reset Tool
# Author: Sihyeon Park (22101489 / Tech Lead)
# Phase 6 (Week 15 & 16) Milestone
# ==============================================================================

set -euo pipefail

echo "=============================================================================="
echo "🧹 Resetting Self-Defending SDN Tower Environment..."
echo "=============================================================================="

# 1. Kill stale traffic generators / python scripts
echo "[1/4] Stopping background traffic generators..."
pkill -f "python traffic/traffic_attack.py" 2>/dev/null || true
pkill -f "python traffic/traffic_normal.py" 2>/dev/null || true

# 2. Clean Mininet if installed
if command -v mn &> /dev/null; then
    echo "[2/4] Running Mininet cleanup (sudo mn -c)..."
    sudo mn -c 2>/dev/null || true
else
    echo "[2/4] Mininet binary not in PATH, skipping mn -c."
fi

# 3. Clean OVS bridges if present
if command -v ovs-vsctl &> /dev/null; then
    echo "[3/4] Deleting lingering OVS bridges (s1, s2, s3, s4)..."
    for sw in s1 s2 s3 s4; do
        sudo ovs-vsctl --if-exists del-br "$sw" 2>/dev/null || true
    done
else
    echo "[3/4] ovs-vsctl not installed or not in PATH, skipping."
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
