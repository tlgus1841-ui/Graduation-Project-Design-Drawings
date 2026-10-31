#!/usr/bin/env bash
# ==============================================================================
# Self-Defending SDN Tower: All-in-One Production Stack Operator
# Phase 6-B All-in-One Docker Compose & Native OVS Orchestration
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

ACTION="${1:-status}"

cd "${REPO_ROOT}"

case "${ACTION}" in
  up|start)
    echo "=========================================================="
    echo "🚀 [1/3] Native OVS 8-Switch 5-Zone Topology Setup..."
    echo "=========================================================="
    if [[ $EUID -eq 0 ]]; then
      bash "${SCRIPT_DIR}/setup_large_ovs.sh"
    else
      sudo bash "${SCRIPT_DIR}/setup_large_ovs.sh"
    fi

    echo ""
    echo "=========================================================="
    echo "🐳 [2/3] All-in-One Docker Compose Services Starting..."
    echo "=========================================================="
    docker compose up -d --build

    echo ""
    echo "=========================================================="
    echo "⏳ [3/3] Waiting for services to become healthy..."
    echo "=========================================================="
    for i in {1..30}; do
      UNHEALTHY=$(docker compose ps --format '{{.Service}}: {{.Health}}' | grep -v 'healthy' | grep -v '^\s*$' || true)
      if [[ -z "${UNHEALTHY}" ]]; then
        echo "✅ All services are healthy!"
        break
      fi
      sleep 1
    done

    # Start background ping for legitimate traffic monitoring (h1 -> h5 Web)
    if ip netns list | grep -q "ns_h1"; then
      echo "📡 Starting background legitimate traffic ping (h1 -> h5 Web: 10.0.0.11)..."
      sudo pkill -f 'ping -i 0.5 10.0.0.11' 2>/dev/null || true
      sudo ip netns exec ns_h1 ping -i 0.5 10.0.0.11 > /tmp/h1_ping.log 2>&1 &
    fi

    echo ""
    echo "=========================================================="
    echo "🎉 Production Stack Ready!"
    echo "   • Web Control Tower UI : http://localhost"
    echo "   • Legacy UI Port       : http://localhost:5173"
    echo "   • Backend REST API     : http://localhost:8000/api/health"
    echo "   • OpenFlow 1.3 Port    : 6653"
    echo "=========================================================="
    ;;

  down|stop)
    echo "=========================================================="
    echo "🛑 Stopping Legitimate Ping & Background Traffic..."
    echo "=========================================================="
    sudo pkill -f 'ping -i 0.5' 2>/dev/null || true

    echo ""
    echo "=========================================================="
    echo "🐳 Stopping Docker Compose Services..."
    echo "=========================================================="
    docker compose down

    echo ""
    echo "=========================================================="
    echo "🧹 Teardown Native OVS Topology..."
    echo "=========================================================="
    if [[ $EUID -eq 0 ]]; then
      bash "${SCRIPT_DIR}/cleanup_large_ovs.sh" 2>/dev/null || true
    else
      sudo bash "${SCRIPT_DIR}/cleanup_large_ovs.sh" 2>/dev/null || true
    fi
    echo "✅ Stack and network topology fully stopped."
    ;;

  restart)
    "${BASH_SOURCE[0]}" down
    sleep 2
    "${BASH_SOURCE[0]}" up
    ;;

  status)
    echo "=== [1/4] Docker Compose Services Status ==="
    docker compose ps
    echo ""
    echo "=== [2/4] Native OVS Bridges Status ==="
    if command -v ovs-vsctl &>/dev/null; then
      sudo ovs-vsctl show | grep -E 'Bridge|Controller|is_connected' || echo "OVS bridges not found"
    else
      echo "ovs-vsctl not installed"
    fi
    echo ""
    echo "=== [3/4] Backend API Health ==="
    curl -s -m 3 http://localhost:8000/api/health || curl -s -m 3 http://localhost/api/health || echo "API unreachable"
    echo ""
    echo ""
    echo "=== [4/4] Legit Traffic Ping Log ==="
    tail -n 3 /tmp/h_legit_ping.log 2>/dev/null || echo "No ping log running"
    ;;

  logs)
    SERVICE="${2:-}"
    if [[ -n "${SERVICE}" ]]; then
      docker compose logs -f "${SERVICE}"
    else
      docker compose logs -f
    fi
    ;;

  *)
    echo "Usage: $0 {up|down|restart|status|logs [service]}"
    exit 1
    ;;
esac
