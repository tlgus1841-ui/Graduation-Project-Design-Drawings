#!/usr/bin/env bash
# ==============================================================================
# Self-Defending SDN Tower: Standard 8-Switch Traffic Injection Engine
# Phase 6-C-4: 8-스위치 엔터프라이즈 토폴로지 표준 트래픽 주입 도구
#
# 표준 발신지 : ns_h2 (User Zone A PC 2) 또는 ns_h4 (User Zone B PC 2)
# 표준 목적지 : 10.0.0.11 (Server Zone A Nginx Web Server / ns_h5)
# 정상 사용자 : ns_h1 (10.0.0.1 -> 10.0.0.11)
# ==============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

# 루트 권한 확인
if [[ $EUID -ne 0 ]]; then
  echo "❌ 오류: 네트워크 네임스페이스 패킷 전송을 위해 root 권한(sudo)이 필요합니다." >&2
  exit 1
fi

# ------------------------------------------------------------------------------
# 1. 토폴로지 자동 감지 및 네임스페이스 표준화
# ------------------------------------------------------------------------------
SRC_NS=""
DST_IP=""
LEGIT_NS=""

if ip netns list | grep -q "ns_h2"; then
  # 표준 8-스위치 5-Zone 토폴로지 (Standard Enterprise)
  SRC_NS="ns_h2"
  DST_IP="10.0.0.11"
  LEGIT_NS="ns_h1"
  TOPO_NAME="8-Switch Enterprise"
elif ip netns list | grep -q "ns_attacker"; then
  # 구형 4-스위치 다이아몬드 토폴로지 (Legacy Fallback)
  SRC_NS="ns_attacker"
  DST_IP="10.0.0.4"
  LEGIT_NS="ns_legit"
  TOPO_NAME="4-Switch Diamond (Legacy)"
else
  echo "❌ 오류: 활성화된 SDN 호스트 네임스페이스(ns_h2 또는 ns_attacker)를 찾을 수 없습니다." >&2
  echo "👉 먼저 OVS 토폴로지를 기동하세요 (예: sudo ./scripts/setup_large_ovs.sh)" >&2
  exit 1
fi

# ------------------------------------------------------------------------------
# 2. 파라미터 파싱 (위치 인자 및 플래그 동시 지원)
# ------------------------------------------------------------------------------
TYPE="${1:-syn}"
DURATION="${2:-10}"
RATE="${3:-500}"

# 사용자 지정 발신지/목적지 오버라이드 지원 (4번째, 5번째 인자)
if [[ $# -ge 4 && -n "${4}" ]]; then
  SRC_NS="${4}"
fi
if [[ $# -ge 5 && -n "${5}" ]]; then
  DST_IP="${5}"
fi

# 파이썬 실행 바이너리 탐색
PYTHON_BIN="python3"
if [[ -f "${ROOT_DIR}/.venv/bin/python" ]]; then
  PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
elif [[ -f "/home/tlgus1841/sdn-tower/.venv/bin/python" ]]; then
  PYTHON_BIN="/home/tlgus1841/sdn-tower/.venv/bin/python"
fi

echo "=========================================================================="
echo "🚀 [SDN Traffic Engine] ${TOPO_NAME} 트래픽 주입"
echo "   • 공격 유형   : ${TYPE^^}"
echo "   • 발신지 (Src): ${SRC_NS}"
echo "   • 대상 (Dst)  : ${DST_IP}"
echo "   • 지속/속도   : ${DURATION}초 / ${RATE} PPS"
echo "=========================================================================="

case "${TYPE,,}" in
  syn)
    ip netns exec "${SRC_NS}" env PYTHONPATH="${ROOT_DIR}" "${PYTHON_BIN}" -m traffic.traffic_attack --dst "${DST_IP}" --duration "${DURATION}" --rate "${RATE}"
    ;;
  scan)
    ip netns exec "${SRC_NS}" env PYTHONPATH="${ROOT_DIR}" "${PYTHON_BIN}" -m traffic.traffic_scan --kind tcp --dst "${DST_IP}" --ports 1-1000 --rate "${RATE}"
    ;;
  udp)
    ip netns exec "${SRC_NS}" env PYTHONPATH="${ROOT_DIR}" "${PYTHON_BIN}" -m traffic.traffic_flood --kind udp --dst "${DST_IP}" --duration "${DURATION}" --pps "${RATE}"
    ;;
  icmp)
    ip netns exec "${SRC_NS}" env PYTHONPATH="${ROOT_DIR}" "${PYTHON_BIN}" -m traffic.traffic_flood --kind icmp --dst "${DST_IP}" --duration "${DURATION}" --pps "${RATE}"
    ;;
  slowhttp)
    ip netns exec "${SRC_NS}" env PYTHONPATH="${ROOT_DIR}" "${PYTHON_BIN}" -m traffic.traffic_slowhttp --server "${DST_IP}" --sockets 150 --interval 2 --duration "${DURATION}"
    ;;
  spread)
    # 서버 대역(10.0.0.11~22) 대상 내부 무단 확산 스캔
    ip netns exec "${SRC_NS}" env PYTHONPATH="${ROOT_DIR}" "${PYTHON_BIN}" -m traffic.traffic_spread --subnet 10.0.0 --hosts 11-22 --port 445 --rate "${RATE}"
    ;;
  normal)
    ip netns exec "${LEGIT_NS}" env PYTHONPATH="${ROOT_DIR}" "${PYTHON_BIN}" -m traffic.traffic_normal --dst "${DST_IP}" --duration "${DURATION}"
    ;;
  *)
    echo "사용법: sudo $0 {syn|scan|udp|icmp|slowhttp|spread|normal} [지속초] [PPS] [발신_네임스페이스] [목적지_IP]"
    exit 1
    ;;
esac

echo "✅ 트래픽 주입 완료."
