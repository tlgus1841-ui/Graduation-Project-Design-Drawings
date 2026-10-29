#!/usr/bin/env bash
# ==============================================================================
# Self-Defending SDN Tower: Remote GCP VM Demo Controller
# Phase 6-A Milestone (Native OVS, Mininet-free) 원격 시연용 원클릭 제어기.
#
# 발표자 로컬 노트북에서 실행한다. 토폴로지·Ryu·Redis·관제탑 백엔드는 전부
# 원격 VM(예: docs/verification/week16_stress_limit_test_report.md의
# GCP e2-standard-4) 위에서 돌고, 이 스크립트는 SSH로 그 VM의 기존 스크립트
# (setup_native_ovs.sh / native_attack.sh / reset_env.sh)를 그대로 호출한다.
# VM 쪽 코드는 1줄도 건드리지 않는다 — 로컬에서 원격으로 같은 명령을 보낼 뿐이다.
#
# 사전 준비 (VM 쪽, 한 번만):
#   1) 이 저장소를 VM_REPO_DIR에 클론하고 `uv sync` 완료
#   2) openvswitch-switch, ethtool, docker, docker compose 설치 완료
#   3) sudo 비밀번호 없이 setup_native_ovs.sh / native_attack.sh / reset_env.sh를
#      돌릴 수 있도록 visudo로 NOPASSWD 설정 (SSH 비대화형 세션은 sudo 비밀번호
#      입력을 받을 수 없다)
#
# 사용 전 환경변수 설정 (로컬):
#   export VM_HOST=user@203.0.113.10       # 필수: SSH 접속 대상
#   export VM_SSH_KEY=~/.ssh/gcp_demo_key  # 선택: 기본은 ssh-agent/기본 키 사용
#   export VM_SSH_PORT=22                  # 선택: 기본 22
#   export VM_REPO_DIR=~/Graduation-Project-Design-Drawings  # 선택: 기본값 아래 참고
#
# 사용 예:
#   ./scripts/vm_demo_controller.sh status
#   ./scripts/vm_demo_controller.sh attack syn 10 500
#   ./scripts/vm_demo_controller.sh ping-status
#   ./scripts/vm_demo_controller.sh restart-all
# ==============================================================================
set -euo pipefail

VM_REPO_DIR="${VM_REPO_DIR:-~/Graduation-Project-Design-Drawings}"
VM_SSH_PORT="${VM_SSH_PORT:-22}"

if [[ -z "${VM_HOST:-}" ]]; then
  echo "❌ 오류: VM_HOST 환경변수가 설정되지 않았습니다." >&2
  echo "👉 예: export VM_HOST=user@203.0.113.10  (원격 GCP VM의 SSH 접속 대상)" >&2
  exit 1
fi

SSH_OPTS=(-p "${VM_SSH_PORT}" -o ConnectTimeout=8 -o BatchMode=yes)
if [[ -n "${VM_SSH_KEY:-}" ]]; then
  SSH_OPTS+=(-i "${VM_SSH_KEY}")
fi

# 원격 VM에서 한 명령을 실행한다. 저장소 디렉터리로 먼저 이동한다.
remote() {
  ssh "${SSH_OPTS[@]}" "${VM_HOST}" "cd ${VM_REPO_DIR} && $*"
}

check() {
  # check <표시 이름> <원격 쉘 조건식>
  local label="$1" cond="$2"
  if remote "${cond}" >/dev/null 2>&1; then
    echo "  ✅ ${label}"
  else
    echo "  ❌ ${label}"
  fi
}

cmd_status() {
  echo "🔎 [${VM_HOST}] Self-Defending SDN Tower 원격 스택 상태 점검..."
  if ! ssh "${SSH_OPTS[@]}" "${VM_HOST}" "true" 2>/dev/null; then
    echo "❌ 오류: ${VM_HOST}에 SSH로 접속할 수 없습니다. VM_HOST/VM_SSH_KEY/VM_SSH_PORT를 확인하세요." >&2
    exit 1
  fi
  check "Redis 브로커 컨테이너 (sdn-redis)"   "docker ps --format '{{.Names}}' | grep -qx sdn-redis"
  check "Ryu 컨트롤러 컨테이너 (sdn-ryu)"     "docker ps --format '{{.Names}}' | grep -qx sdn-ryu"
  check "Native OVS 브릿지 4개 (s1~s4)"       "[ \$(sudo ovs-vsctl list-br | grep -cE '^s[1-4]\$') -eq 4 ]"
  check "네트워크 네임스페이스 3개"            "[ \$(ip netns list | grep -cE 'ns_(legit|attacker|server)') -eq 3 ]"
  check "관제탑 백엔드 (uvicorn :8000)"        "curl -fsS --max-time 3 http://localhost:8000/api/health"
  check "AI 추론 워커 (model.inference_worker)" "pgrep -f model.inference_worker"
  check "정상 사용자 백그라운드 ping"          "pgrep -f 'ping .*10\\.0\\.0\\.4'"
  echo "ℹ️  개별 항목이 ❌이면 restart-all로 전체 재기동하거나, 해당 컴포넌트만 수동으로 올리세요."
}

cmd_attack() {
  local kind="${1:-}" duration="${2:-10}" rate="${3:-500}"
  case "${kind}" in
    syn|scan|udp|icmp|slowhttp|spread|normal) ;;
    *)
      echo "Usage: $0 attack {syn|scan|udp|icmp|slowhttp|spread|normal} [duration] [rate]" >&2
      exit 1
      ;;
  esac
  echo "🚀 [${VM_HOST}] 원격 공격 주입: ${kind} (${duration}s, ${rate} PPS)..."
  remote "sudo ./scripts/native_attack.sh '${kind}' '${duration}' '${rate}'"
}

cmd_ping_status() {
  echo "📶 [${VM_HOST}] 정상 사용자(ns_legit) → H_server(10.0.0.4) ping 손실률 확인 중 (20개, 약 4초)..."
  remote "sudo ip netns exec ns_legit ping -c 20 -i 0.2 -W 1 10.0.0.4" | tail -4
}

cmd_restart_all() {
  echo "♻️  [${VM_HOST}] 전체 스택 원클릭 재기동 (기존 환경 정리 → Redis/Ryu → Native OVS → 백엔드 → AI 워커)..."

  echo ">>> [1/5] 기존 환경 클린업 (reset_env.sh)..."
  remote "sudo ./scripts/reset_env.sh"

  echo ">>> [2/5] Redis 브로커 및 Ryu 컨트롤러 기동 (docker compose)..."
  remote "docker compose up -d redis-broker ryu-controller"
  sleep 3

  echo ">>> [3/5] Native OVS 4-스위치 토폴로지 기동..."
  remote "sudo ./scripts/setup_native_ovs.sh"

  echo ">>> [4/5] 관제탑 백엔드(Live 모드) 백그라운드 기동..."
  # SSH 세션이 백그라운드 프로세스의 fd를 기다리며 멈추지 않도록 stdin도 분리한다.
  remote "nohup env SDN_MOCK=0 REDIS_URL=redis://localhost:6379/0 uv run uvicorn api.main:app --host 0.0.0.0 --port 8000 > /tmp/sdn_backend.log 2>&1 < /dev/null &"
  sleep 2

  echo ">>> [5/5] AI 추론 워커 백그라운드 기동..."
  remote "nohup uv run python -m model.inference_worker --model model/isolation_forest.joblib --log /tmp/sdn_events.jsonl > /tmp/sdn_worker.log 2>&1 < /dev/null &"

  echo "✅ 재기동 완료. '$0 status'로 전체 상태를 확인하세요."
  echo "👉 정상 사용자 배경 ping은 직접 시작하세요 (관객에게 보여줄 터미널에서):"
  echo "   ssh ${VM_HOST} 'sudo ip netns exec ns_legit ping -i 0.5 10.0.0.4'"
}

main() {
  local action="${1:-}"
  shift || true
  case "${action}" in
    status)      cmd_status ;;
    attack)      cmd_attack "$@" ;;
    ping-status) cmd_ping_status ;;
    restart-all) cmd_restart_all ;;
    *)
      echo "Usage: $0 {status|attack <kind> [duration] [rate]|ping-status|restart-all}" >&2
      exit 1
      ;;
  esac
}

main "$@"
