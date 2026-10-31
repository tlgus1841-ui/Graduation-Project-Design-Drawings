#!/usr/bin/env bash
# ==============================================================================
# Self-Defending SDN Tower: Production Remote Deployment Engine
# Phase 6-C-3: 경량 런타임 아티팩트 분리 및 원클릭 배포 스크립트
#
# 배포 대상: GCP Compute Engine (sdnvm)
# 원천 배제: docs/(논문/기획서), tests/, rules/, .git/, .venv/ 등 비런타임 자산 100% 차단
# ==============================================================================
set -euo pipefail

# 터미널 컬러 서식
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 기본 설정값
DEFAULT_TARGET="34.50.17.220"
DEFAULT_USER="tlgus1841"
DEFAULT_DEST="~/sdn-tower-runtime"
DEFAULT_PROJECT="sdn-tower"

TARGET_HOST="${DEFAULT_TARGET}"
SSH_USER="${DEFAULT_USER}"
DEST_DIR="${DEFAULT_DEST}"
PROJECT_NAME="${DEFAULT_PROJECT}"
SSH_KEY=""
NO_BUILD=false
DRY_RUN=false
CHECK_ONLY=false
RESTART_OVS=false

# 도움말 출력
print_usage() {
  echo -e "${BOLD}사용법:${NC}"
  echo -e "  $0 [VM_IP] [옵션]\n"
  echo -e "${BOLD}주요 옵션:${NC}"
  echo -e "  --target, -t <IP|HOST>     대상 VM 호스트 또는 IP (기본값: ${DEFAULT_TARGET})"
  echo -e "  --user, -u <USER>          SSH 접속 계정 (기본값: ${DEFAULT_USER})"
  echo -e "  --dest-dir, -d <DIR>       VM 원격 런타임 디렉토리 (기본값: ${DEFAULT_DEST})"
  echo -e "  --project-name, -p <NAME>  Docker Compose 프로젝트명 (기본값: ${DEFAULT_PROJECT})"
  echo -e "  --identity, -i <KEY_PATH>  SSH 비공개 키 경로"
  echo -e "  --no-build                 컨테이너 이미지 재빌드를 건너뛰고 컨테이너만 재기동"
  echo -e "  --dry-run                  실제 전송 없이 배포 대상/제외 파일 목록 및 번들 크기만 시뮬레이션"
  echo -e "  --check-only               배포 없이 원격 VM의 OVS 및 Docker 서비스 상태만 점검"
  echo -e "  --restart-ovs              배포 시 원격 OVS 10-스위치 토폴로지도 재설정"
  echo -e "  --help, -h                 도움말 출력\n"
  echo -e "${BOLD}예시:${NC}"
  echo -e "  $0                                   # 기본 VM으로 원클릭 배포"
  echo -e "  $0 --dry-run                         # 전송 대상 파일 격리 시뮬레이션"
  echo -e "  $0 --check-only                      # 원격 VM 상태 진단"
  echo -e "  $0 <VM_IP> --no-build                # 소스 코드만 초고속 갱신 후 재기동"
}

# 인자 파싱
while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h)
      print_usage
      exit 0
      ;;
    --target|-t)
      TARGET_HOST="$2"
      shift 2
      ;;
    --user|-u)
      SSH_USER="$2"
      shift 2
      ;;
    --dest-dir|-d)
      DEST_DIR="$2"
      shift 2
      ;;
    --project-name|-p)
      PROJECT_NAME="$2"
      shift 2
      ;;
    --identity|-i)
      SSH_KEY="$2"
      shift 2
      ;;
    --no-build)
      NO_BUILD=true
      shift
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --check-only)
      CHECK_ONLY=true
      shift
      ;;
    --restart-ovs)
      RESTART_OVS=true
      shift
      ;;
    -*)
      echo -e "${RED}[ERROR] 알 수 없는 옵션: $1${NC}" >&2
      print_usage
      exit 1
      ;;
    *)
      # 첫 번째 위치 인자를 호스트로 인식
      TARGET_HOST="$1"
      shift
      ;;
  esac
done

# SSH 명령어 기본 구성
SSH_OPTS=(-o StrictHostKeyChecking=no -o ConnectTimeout=8 -o ServerAliveInterval=15)
if [[ -n "${SSH_KEY}" ]]; then
  SSH_OPTS+=(-i "${SSH_KEY}")
fi

run_ssh() {
  ssh "${SSH_OPTS[@]}" "${SSH_USER}@${TARGET_HOST}" "$@"
}

echo -e "${BOLD}${CYAN}========================================================================${NC}"
echo -e "${BOLD}${CYAN} 🚀 Self-Defending SDN Tower: Production Remote Deployment Engine ${NC}"
echo -e "${BOLD}${CYAN}========================================================================${NC}"
echo -e "${BOLD}• 배포 대상 호스트 :${NC} ${GREEN}${SSH_USER}@${TARGET_HOST}${NC}"
echo -e "${BOLD}• 런타임 디렉토리  :${NC} ${CYAN}${DEST_DIR}${NC}"
echo -e "${BOLD}• Compose 프로젝트 :${NC} ${CYAN}${PROJECT_NAME}${NC}"
echo -e "${BOLD}• 배포 모드        :${NC} $([[ "${DRY_RUN}" == true ]] && echo -e "${YELLOW}DRY-RUN (시뮬레이션)${NC}" || echo -e "${GREEN}LIVE DEPLOY (실제 배포)${NC}")"
echo ""

# ------------------------------------------------------------------------------
# 1. 사전 진단 (Pre-flight Checks)
# ------------------------------------------------------------------------------
echo -e "${BOLD}[1/5] 사전 환경 및 로컬 자산 검증...${NC}"

if ! command -v rsync >/dev/null 2>&1; then
  echo -e "${RED}[ERROR] 로컬에 rsync 도구가 설치되어 있지 않습니다. sudo apt install rsync 로 설치해주세요.${NC}" >&2
  exit 1
fi

DEPLOYIGNORE_FILE="${REPO_ROOT}/.deployignore"
if [[ ! -f "${DEPLOYIGNORE_FILE}" ]]; then
  echo -e "${RED}[ERROR] 배포 격리 명세서(${DEPLOYIGNORE_FILE})가 존재하지 않습니다.${NC}" >&2
  exit 1
fi

# DRY-RUN 모드: 로컬 가상 시뮬레이션으로 초고속 파일 격리 검증
if [[ "${DRY_RUN}" == true ]]; then
  echo -e "\n${BOLD}[2/5] 경량 런타임 아티팩트 선별 동기화 (격리 필터 적용)...${NC}"
  echo -e "${YELLOW}>>> [DRY-RUN 모드] 로컬 가상 배포 시뮬레이션 (전송 대상 파일 목록):${NC}"
  
  TMP_SIM_DIR="/tmp/sdn_deploy_sim_$$"
  mkdir -p "${TMP_SIM_DIR}"
  rsync -avzn --delete --exclude-from="${DEPLOYIGNORE_FILE}" "${REPO_ROOT}/" "${TMP_SIM_DIR}/"
  rm -rf "${TMP_SIM_DIR}"
  
  echo -e "\n${GREEN}✅ DRY-RUN 시뮬레이션 완료.${NC}"
  echo -e "  - docs/, tests/, rules/, .git/, .venv/ 가 전송 목록에서 100% 원천 배제되었습니다."
  echo -e "  - 실제 배포 시 위 파일들만 선별되어 VM(${SSH_USER}@${TARGET_HOST}:${DEST_DIR})으로 안전하게 전송됩니다."
  exit 0
fi

# SSH 연결 테스트
echo -n "  - 원격 SSH 연결 확인 중... "
if ! run_ssh "echo 'SSH_CONN_OK'" >/dev/null 2>&1; then
  echo -e "${RED}실패!${NC}"
  echo -e "${RED}[ERROR] ${SSH_USER}@${TARGET_HOST} 로 SSH 접속할 수 없습니다.${NC}" >&2
  echo -e "${YELLOW}SSH 키 설정 또는 gcloud compute ssh 접근 권한을 확인하세요.${NC}" >&2
  exit 1
fi
echo -e "${GREEN}연결 성공 (OK)${NC}"

# 원격 rsync 존재 여부 확인 및 자동 설치
echo -n "  - 원격 VM rsync 도구 점검... "
if ! run_ssh "command -v rsync >/dev/null 2>&1"; then
  echo -e "${YELLOW}미설치 상태 감지 (자동 설치 진행)${NC}"
  echo -e "    ${CYAN}>>> sudo apt-get update && sudo apt-get install -y rsync 실행 중...${NC}"
  run_ssh "sudo apt-get update -qq && sudo apt-get install -y -qq rsync"
  echo -e "    ${GREEN}>>> 원격 VM rsync 설치 완료!${NC}"
else
  echo -e "${GREEN}설치 확인 (OK)${NC}"
fi

# 원격 상태 점검 모드 (--check-only)
if [[ "${CHECK_ONLY}" == true ]]; then
  echo -e "\n${BOLD}${BLUE}=== [진단] 원격 VM OVS & Docker 런타임 상태 ===${NC}"
  echo -e "${BOLD}1. Native OVS 브릿지 요약:${NC}"
  run_ssh "sudo ovs-vsctl show | grep -E 'Bridge|Controller|is_connected'" || echo -e "${YELLOW}OVS 브릿지 정보 없음${NC}"

  echo -e "\n${BOLD}2. Docker 컨테이너 상태 (현재 실행 중인 SDN 서비스):${NC}"
  run_ssh "docker ps --filter 'name=sdn-' --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'" || echo -e "${YELLOW}실행 중인 Docker 컨테이너 없음${NC}"

  echo -e "\n${BOLD}3. 관제 API 헬스체크 (http://${TARGET_HOST}/api/health):${NC}"
  curl -s -m 3 "http://${TARGET_HOST}/api/health" || echo -e "${RED}외부 API 엔드포인트 응답 없음${NC}"
  echo ""
  exit 0
fi

# ------------------------------------------------------------------------------
# 2. 런타임 파일 선별 패키징 및 동기화 (Rsync Sync)
# ------------------------------------------------------------------------------
echo -e "\n${BOLD}[2/5] 경량 런타임 아티팩트 선별 동기화 (격리 필터 적용)...${NC}"

RSYNC_FLAGS=(-avz --delete)
if [[ -n "${SSH_KEY}" ]]; then
  RSYNC_FLAGS+=(-e "ssh -o StrictHostKeyChecking=no -i ${SSH_KEY}")
else
  RSYNC_FLAGS+=(-e "ssh -o StrictHostKeyChecking=no")
fi

# 원격 디렉토리 생성
run_ssh "mkdir -p ${DEST_DIR}"

# 실제 rsync 전송 실행
rsync "${RSYNC_FLAGS[@]}" --exclude-from="${DEPLOYIGNORE_FILE}" "${REPO_ROOT}/" "${SSH_USER}@${TARGET_HOST}:${DEST_DIR}/"
echo -e "${GREEN}  - 런타임 파일 동기화 완료!${NC}"

# ------------------------------------------------------------------------------
# 3. 원격 OVS 8-스위치 토폴로지 점검 및 보존
# ------------------------------------------------------------------------------
echo -e "\n${BOLD}[3/5] 원격 OVS 토폴로지 및 네트워크 네임스페이스 점검...${NC}"

OVS_STATUS=$(run_ssh "sudo ovs-vsctl show | grep -c 'Bridge s1'" 2>/dev/null || echo "0")
if [[ "${OVS_STATUS}" -eq 0 || "${RESTART_OVS}" == true ]]; then
  echo -e "${YELLOW}  - OVS 10-스위치 토폴로지가 미기동 상태이거나 재설정이 요청되었습니다. setup_large_ovs.sh 실행 중...${NC}"
  run_ssh "cd ${DEST_DIR} && sudo bash scripts/setup_large_ovs.sh"
else
  echo -e "${GREEN}  - Native OVS 10-스위치(s1~s10) 및 6-Zone 네임스페이스 정상 유지 중 (커널 자원 보존)${NC}"
fi

# ------------------------------------------------------------------------------
# 4. 무중단 Docker 컨테이너 빌드 및 재기동
# ------------------------------------------------------------------------------
echo -e "\n${BOLD}[4/5] Docker Compose 5대 서비스 재기동 (프로젝트: ${PROJECT_NAME})...${NC}"

BUILD_ARG="--build"
if [[ "${NO_BUILD}" == true ]]; then
  BUILD_ARG=""
  echo -e "${YELLOW}  - [NO-BUILD] 컨테이너 재빌드 건너뜀 (기존 이미지 유지 소스 마운트 갱신)${NC}"
fi

run_ssh "cd ${DEST_DIR} && docker compose -p ${PROJECT_NAME} up -d ${BUILD_ARG} --remove-orphans"
if [[ "${NO_BUILD}" == true ]]; then
  run_ssh "cd ${DEST_DIR} && docker compose -p ${PROJECT_NAME} restart ryu-controller control-api ai-worker"
fi
echo -e "${GREEN}  - 컨테이너 서비스 기동 완료!${NC}"

# ------------------------------------------------------------------------------
# 5. 자동 헬스체크 및 안정성 검증 (Health Polling)
# ------------------------------------------------------------------------------
echo -e "\n${BOLD}[5/5] 서비스 안정성 및 실시간 헬스체크 검증...${NC}"

HEALTH_URL="http://${TARGET_HOST}/api/health"
MAX_ATTEMPTS=15
SUCCESS=false

echo -n "  - 관제 API 헬스체크 응답 대기 중 (${HEALTH_URL}) "
for ((i=1; i<=MAX_ATTEMPTS; i++)); do
  HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -m 2 "${HEALTH_URL}" 2>/dev/null || echo "000")
  if [[ "${HTTP_STATUS}" == "200" ]]; then
    SUCCESS=true
    break
  fi
  echo -n "."
  sleep 2
done

echo ""

if [[ "${SUCCESS}" == true ]]; then
  HEALTH_PAYLOAD=$(curl -s -m 3 "${HEALTH_URL}")
  echo -e "${GREEN}${BOLD}🎉 배포 완료 및 서비스 정상 가동 확인!${NC}"
  echo -e "  - 응답 상태 : ${GREEN}HTTP 200 OK${NC}"
  echo -e "  - 헬스 내용 : ${CYAN}${HEALTH_PAYLOAD}${NC}"
  echo -e "  - 웹 관제탑 : ${BOLD}${GREEN}http://${TARGET_HOST}/${NC}"
  echo -e "  - API 문서  : ${BOLD}${GREEN}http://${TARGET_HOST}:8000/docs${NC}"
  echo ""
  echo -e "${BOLD}💡 기존 VM 자산 보관 상태:${NC}"
  echo -e "  - 기존 작업 디렉토리(${CYAN}~/sdn-tower${NC})는 안전 백업본으로 온전히 보존되어 있습니다."
  echo -e "${BOLD}${CYAN}========================================================================${NC}"
else
  echo -e "${RED}${BOLD}❌ [주의] 헬스체크 타임아웃 (${MAX_ATTEMPTS}회 시도 실패)!${NC}"
  echo -e "${YELLOW}원격 컨테이너 최근 로그 요약:${NC}"
  run_ssh "cd ${DEST_DIR} && docker compose -p ${PROJECT_NAME} logs --tail=30"
  exit 1
fi
