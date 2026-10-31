#!/usr/bin/env bash
# ==============================================================================
# Self-Defending SDN Tower: Remote VM Demo Operator (Production Runtime)
# Phase 6-C-4: 8-스위치 엔터프라이즈 토폴로지 표준 원격 데모 제어 도구
# Target VM: sdnvm (GCP Compute Engine)
# ==============================================================================
set -euo pipefail

VM_HOST="${VM_HOST:-34.50.17.220}"
VM_USER="${VM_USER:-tlgus1841}"
REMOTE_RUNTIME_DIR="${REMOTE_RUNTIME_DIR:-/home/tlgus1841/sdn-tower-runtime}"
PROJECT_NAME="sdn-tower"
SSH_CMD="ssh -o StrictHostKeyChecking=no ${VM_USER}@${VM_HOST}"

ACTION="${1:-status}"

case "${ACTION}" in
  status)
    echo "=== [1/4] Production Containers Status (-p ${PROJECT_NAME}) ==="
    ${SSH_CMD} "docker ps --filter 'name=sdn-' --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"
    echo ""
    echo "=== [2/4] Native OVS Bridges (s1~s8) ==="
    ${SSH_CMD} "sudo ovs-vsctl show | grep -E 'Bridge|Controller|is_connected'" || echo "OVS not running"
    echo ""
    echo "=== [3/4] API Health (via Nginx Port 80) ==="
    curl -s -m 3 "http://${VM_HOST}/api/health" || echo "Nginx Proxy /api/health unreachable"
    echo ""
    echo "=== [4/4] Legit Ping Log (/tmp/h1_ping.log) ==="
    ${SSH_CMD} "tail -n 3 /tmp/h1_ping.log 2>/dev/null || tail -n 3 /tmp/h_legit_ping.log 2>/dev/null || echo 'No ping running'"
    ;;

  attack)
    ARG2="${2:-syn}"
    if [[ "${ARG2}" =~ ^[0-9]+$ ]]; then
      TYPE="syn"
      DURATION="${ARG2}"
      RATE="${3:-500}"
    else
      TYPE="${ARG2}"
      DURATION="${3:-10}"
      RATE="${4:-500}"
    fi
    echo "🚀 Triggering ${TYPE^^} Attack on VM (Duration: ${DURATION}s, Rate: ${RATE} PPS)..."
    ${SSH_CMD} "cd ${REMOTE_RUNTIME_DIR} && sudo ./scripts/native_attack.sh ${TYPE} ${DURATION} ${RATE}"
    echo "✅ Attack finished! Check Control Tower UI at http://${VM_HOST}"
    ;;

  stress)
    echo "🔥 Triggering Stress Limit Attack (ns_h2 -> Server Zone)..."
    ${SSH_CMD} "cd ${REMOTE_RUNTIME_DIR} && sudo ./scripts/native_attack.sh udp 10 5000"
    ;;

  ping-status)
    ${SSH_CMD} "tail -n 10 /tmp/h1_ping.log 2>/dev/null || tail -n 10 /tmp/h_legit_ping.log 2>/dev/null || echo 'No ping running'"
    ;;

  stop)
    echo "🛑 Stopping all demo services and background ping on VM..."
    ${SSH_CMD} "sudo pkill -f 'ping -i 0.5 10.0.0.11' 2>/dev/null || true
cd ${REMOTE_RUNTIME_DIR} && docker compose -p ${PROJECT_NAME} down
"
    echo "✅ Demo stopped and environment cleaned."
    ;;

  restart-all)
    echo "🔄 Restarting entire production stack on VM from ${REMOTE_RUNTIME_DIR}..."
    ${SSH_CMD} "cd ${REMOTE_RUNTIME_DIR} && docker compose -p ${PROJECT_NAME} restart"
    echo "✅ Stack restarted! Control Tower UI: http://${VM_HOST}"
    ;;

  logs)
    SERVICE="${2:-}"
    ${SSH_CMD} "cd ${REMOTE_RUNTIME_DIR} && docker compose -p ${PROJECT_NAME} logs -f ${SERVICE}"
    ;;

  *)
    echo "Usage: $0 {status|attack [type] [duration] [rate]|stress|ping-status|stop|restart-all|logs [service]}"
    ;;
esac
