#!/usr/bin/env bash
# ==============================================================================
# Self-Defending SDN Tower: Native OVS Traffic Injection Wrapper
# ==============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

TYPE="${1:-syn}"       # syn, scan, udp, icmp, slowhttp, spread, normal
DURATION="${2:-10}"
RATE="${3:-500}"

# 루트 권한 확인
if [[ $EUID -ne 0 ]]; then
  echo "❌ 오류: 패킷 전송을 위해 root 권한(sudo)이 필요합니다." >&2
  exit 1
fi

# 네임스페이스 확인
if ! ip netns list | grep -q "ns_attacker"; then
  echo "❌ 오류: 'ns_attacker' 네임스페이스가 존재하지 않습니다." >&2
  echo "👉 먼저 sudo ./scripts/setup_native_ovs.sh 를 실행하세요." >&2
  exit 1
fi

PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
if [[ ! -f "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

echo "🚀 [Native OVS] 주입 유형: ${TYPE^^} (시간: ${DURATION}s, 속도: ${RATE} PPS)..."

case "${TYPE,,}" in
  syn)
    ip netns exec ns_attacker env PYTHONPATH="${ROOT_DIR}" "${PYTHON_BIN}" -m traffic.traffic_attack --dst 10.0.0.4 --duration "${DURATION}" --rate "${RATE}"
    ;;
  scan)
    ip netns exec ns_attacker env PYTHONPATH="${ROOT_DIR}" "${PYTHON_BIN}" -m traffic.traffic_scan --kind tcp --dst 10.0.0.4 --ports 1-1000 --rate "${RATE}"
    ;;
  udp)
    ip netns exec ns_attacker env PYTHONPATH="${ROOT_DIR}" "${PYTHON_BIN}" -m traffic.traffic_flood --kind udp --dst 10.0.0.4 --duration "${DURATION}" --pps "${RATE}"
    ;;
  icmp)
    ip netns exec ns_attacker env PYTHONPATH="${ROOT_DIR}" "${PYTHON_BIN}" -m traffic.traffic_flood --kind icmp --dst 10.0.0.4 --duration "${DURATION}" --pps "${RATE}"
    ;;
  slowhttp)
    ip netns exec ns_attacker env PYTHONPATH="${ROOT_DIR}" "${PYTHON_BIN}" -m traffic.traffic_slowhttp --server 10.0.0.4 --sockets 150 --interval 2 --duration "${DURATION}"
    ;;
  spread)
    ip netns exec ns_attacker env PYTHONPATH="${ROOT_DIR}" "${PYTHON_BIN}" -m traffic.traffic_spread --subnet 10.0.0 --hosts 5-60 --port 445 --rate "${RATE}"
    ;;
  normal)
    ip netns exec ns_legit env PYTHONPATH="${ROOT_DIR}" "${PYTHON_BIN}" -m traffic.traffic_normal --dst 10.0.0.4 --duration "${DURATION}"
    ;;
  *)
    echo "Usage: sudo $0 {syn|scan|udp|icmp|slowhttp|spread|normal} [duration] [rate]"
    exit 1
    ;;
esac

echo "✅ 트래픽 주입 완료."
