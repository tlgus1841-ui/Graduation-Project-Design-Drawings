#!/usr/bin/env bash
# ==============================================================================
# Self-Defending SDN Tower: 8-Switch Enterprise Autonomous Defense Demo
# Author: Sihyeon Park (22101489 / Tech Lead)
# Phase 6-C-4: 8-스위치 엔터프라이즈 토폴로지 표준 시나리오 가이드
# ==============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

echo "=============================================================================="
echo "🛡️  Self-Defending SDN Tower: 8-Switch 5-Zone Enterprise Defense Demo"
echo "=============================================================================="

# 1. 의존성 및 서비스 점검
echo "[Step 1/5] 환경 및 서비스 상태 점검..."
if command -v docker &> /dev/null; then
  RUNNING=$(docker ps --filter "name=sdn-" --format "{{.Names}}" | tr '\n' ' ')
  echo "  -> 실행 중인 SDN 컨테이너: ${RUNNING:-없음}"
fi

# 2. Redis 브로커 점검
echo "[Step 2/5] Redis 메시지 버스 점검..."
if command -v redis-cli &> /dev/null && redis-cli ping &> /dev/null; then
  echo "  -> Redis 상태: 정상 연결 (PONG)"
else
  echo "  -> 알림: 로컬 Redis 미감지 (Docker compose sdn-redis 컨테이너 참조)"
fi

# 3. 8-스위치 5-Zone 엔터프라이즈 토폴로지 개요
echo ""
echo "[Step 3/5] 8-스위치 5-Zone 엔터프라이즈 아키텍처:"
cat << 'EOF'
           [User Zone A: h1, h2]          [User Zone B: h3, h4]
                     │                              │
                ┌────┴────┐                    ┌────┴────┐
                │Switch S3│                    │Switch S4│
                └────┬────┘                    └────┬────┘
                     │ (Trunk P99)                  │ (Trunk P99)
        ┌────────────┴──────────────────────────────┴────────────┐
        │  [Dual-Core Backbone Zone: S1 (0x01) <-> S2 (0x02)]   │
        └────────────┬──────────────────────────────┬────────────┘
                     │ (Trunk P99)                  │ (Trunk P99)
                ┌────┴────┐                    ┌────┴────┐
                │Switch S5│                    │Switch S6│
                └────┬────┘                    └────┬────┘
                     │                              │
          [Server A: h5 Web, h6 API]    [Server B: h7 DB, h8 Backup]

        [Admin Zone S7: h_admin, h_patch (10.0.0.253)]
        [Quarantine Zone S8: h_sink (10.0.0.250)]
EOF

# 4. 4단계 자율 자기방어 생명주기
echo ""
echo "[Step 4/5] 4단계 자율 방어 생명주기 시나리오:"
echo "  [Stage 1] NORMAL    : h1(10.0.0.1) -> h5 Web(10.0.0.11) 정상 통신 (손실률 0.0%)"
echo "  [Stage 2] ATTACK    : h2(10.0.0.2)에서 6종 공격 주입 -> AI 워커 즉각 탐지 (< 1.5s)"
echo "  [Stage 3] MITIGATE  : Ryu OpenFlow Table 2 동적 차단 및 S1-S2 자율 우회 포워딩"
echo "  [Stage 4] QUARANTINE: 침해 호스트 격리망 이동 -> 오직 패치서버(10.0.0.253)만 접속 허용"
echo "  [Stage 5] RECOVERY  : 치료 완료 후 FSM 쿨다운(10s) -> Zero-loss 원상 복구"

# 5. 실행 명령어 가이드
echo ""
echo "[Step 5/5] 실행 및 검증 옵션:"
echo "  A) 원격 VM 원클릭 배포:"
echo "     ./scripts/deploy_remote.sh 34.50.17.220"
echo ""
echo "  B) 실환경 공격 주입 테스트 (Native OVS):"
echo "     sudo ./scripts/native_attack.sh syn 10 500"
echo "     sudo ./scripts/native_attack.sh spread 10 300"
echo ""
echo "  C) 웹 관제탑 접속 (실시간 대시보드):"
echo "     http://34.50.17.220/"
echo "=============================================================================="
