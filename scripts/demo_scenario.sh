#!/usr/bin/env bash
# ==============================================================================
# Self-Defending SDN Tower: 4-Stage Autonomous Defense Demo Runner
# Author: Sihyeon Park (22101489 / Tech Lead)
# Phase 6 (Week 15 & 16) Milestone
# ==============================================================================

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

echo "=============================================================================="
echo "🛡️  Self-Defending SDN Tower: E2E Autonomous Defense Demo (v1.0.0)"
echo "=============================================================================="

# 1. Check prerequisites
echo "[Step 1/5] Checking environment and services..."
if ! command -v uv &> /dev/null; then
    echo "❌ Error: 'uv' package manager not found. Please install uv."
    exit 1
fi

echo "  -> Running regression test suite..."
uv run pytest -q

# 2. Redis check / start
echo "[Step 2/5] Checking Redis message bus..."
if ! command -v redis-cli &> /dev/null || ! redis-cli ping &> /dev/null; then
    echo "  -> Notice: Redis not detected on localhost:6379."
    echo "  -> Tip: Start Docker container with: docker compose up -d redis-broker"
fi

# 3. Print demo topology & architecture overview
echo "[Step 3/5] Topology architecture:"
echo "       [H_legit: 10.0.0.1 (P1)]       "
echo "       [H_attacker: 10.0.0.2 (P2)]   "
echo "                     │               "
echo "                ┌────┴────┐          "
echo "                │ Switch 1│ (Ingress)"
echo "                └────┬────┘          "
echo "             (P3)   │   (P4)        "
echo "        ┌───────────┴───────────┐    "
echo "        ▼                       ▼    "
echo "   ┌─────────┐             ┌─────────┐"
echo "   │Switch 2 │ (Primary)   │Switch 3 │ (Bypass)"
echo "   └────┬────┘             └────┬────┘"
echo "        │ (P2)                  │ (P2)"
echo "        └───────────┬───────────┘    "
echo "             (P2)   │   (P3)        "
echo "                ┌────┴────┐          "
echo "                │ Switch 4│ (Egress) "
echo "                └────┬────┘          "
echo "                     │ (P1)          "
echo "             [H_server: 10.0.0.4]    "

# 4. Scenario Lifecycle Outline
echo ""
echo "[Step 4/5] 4-Stage Autonomous Defense Scenario Sequence:"
echo "  [Stage 1] NORMAL: H_legit -> H_server via S1-S2-S4 (Baseline, Loss: 0%)"
echo "  [Stage 2] ATTACK: H_attacker injects SYN Flood -> AI Worker detects (Score < -0.8)"
echo "  [Stage 3] MITIGATE: Ryu installs In_port 2 Drop (Priority 100) & S1-S3-S4 Bypass"
echo "  [Stage 4] RECOVER: Attack ceases -> FSM Cooldown (10s) -> Zero-loss Rollback"

# 5. Execution options
echo ""
echo "[Step 5/5] Launch options:"
echo "  A) Run Headless Automated 4-Stage Simulation:"
echo "     uv run pytest tests/harness/test_full_scenario.py -v"
echo ""
echo "  B) Start Web Control Tower API Server:"
echo "     uv run uvicorn api.main:app --host 0.0.0.0 --port 8000"
echo ""
echo "  C) Run Scapy Normal / Attack Traffic:"
echo "     sudo uv run python traffic/traffic_normal.py"
echo "     sudo uv run python traffic/traffic_attack.py"
echo "=============================================================================="
