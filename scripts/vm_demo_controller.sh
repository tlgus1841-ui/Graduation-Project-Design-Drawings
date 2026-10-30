#!/usr/bin/env bash
# ==============================================================================
# Self-Defending SDN Tower: Remote VM Demo Operator (Production Docker Compose)
# Target VM: sdnvm (GCP Compute Engine)
# ==============================================================================
set -euo pipefail

VM_HOST="${VM_HOST:-34.64.79.240}"
VM_USER="${VM_USER:-tlgus1841}"
SSH_CMD="ssh -o StrictHostKeyChecking=no ${VM_USER}@${VM_HOST}"

ACTION="${1:-status}"

case "${ACTION}" in
  status)
    echo "=== [1/4] Production Containers Status ==="
    ${SSH_CMD} "cd /home/tlgus1841/sdn-tower && docker compose ps"
    echo ""
    echo "=== [2/4] Native OVS Bridges ==="
    ${SSH_CMD} "sudo ovs-vsctl show | grep -E 'Bridge|Controller|is_connected'" || echo "OVS not running"
    echo ""
    echo "=== [3/4] API Health (via Nginx Port 80 & Direct Port 8000) ==="
    curl -s -m 3 "http://${VM_HOST}/api/health" || echo "Nginx Proxy /api/health unreachable"
    echo ""
    echo "=== [4/4] Legit Ping Log ==="
    ${SSH_CMD} "tail -n 3 /tmp/h_legit_ping.log 2>/dev/null" || echo "No ping running"
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
    ${SSH_CMD} "cd /home/tlgus1841/sdn-tower && sudo ./scripts/native_attack.sh ${TYPE} ${DURATION} ${RATE}"
    echo "✅ Attack finished! Check Control Tower UI at http://${VM_HOST}"
    ;;

  stress)
    echo "🔥 Triggering 952k PPS Stress Limit Attack..."
    ${SSH_CMD} "cd /home/tlgus1841/sdn-tower && sudo ip netns exec ns_attacker env PYTHONPATH=/home/tlgus1841/sdn-tower /home/tlgus1841/sdn-tower/.venv/bin/python -m harness.verification.stress_limit_scenario --before 5 --attack 12 --after 10 --tier 3"
    ;;

  ping-status)
    ${SSH_CMD} "tail -n 10 /tmp/h_legit_ping.log 2>/dev/null" || echo "No ping running"
    ;;

  stop)
    echo "🛑 Stopping all demo services and topology on VM..."
    ${SSH_CMD} "cd /home/tlgus1841/sdn-tower && ./scripts/prod_stack.sh down"
    echo "✅ Demo stopped and environment cleaned."
    ;;

  restart-all)
    echo "🔄 Restarting entire production stack on VM (All-in-One Docker Compose Mode)..."
    ${SSH_CMD} "cd /home/tlgus1841/sdn-tower
tmux kill-server 2>/dev/null || true
./scripts/prod_stack.sh restart
"
    echo "✅ Stack restarted! Control Tower UI: http://${VM_HOST} (or http://${VM_HOST}:5173)"
    ;;

  logs)
    SERVICE="${2:-}"
    ${SSH_CMD} "cd /home/tlgus1841/sdn-tower && docker compose logs -f ${SERVICE}"
    ;;

  *)
    echo "Usage: $0 {status|attack [type] [duration] [rate]|stress|ping-status|stop|restart-all|logs [service]}"
    ;;
esac
