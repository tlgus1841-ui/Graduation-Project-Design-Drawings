# 📘 [Tech Lead] Phase 5 & 6: 관제탑 연동 & 긴급 서킷브레이커 & 종합 시연 가이드
> **담당자:** 박시현 (22101489 / Tech Lead)  
> **해당 기간:** 12주차 ~ 16주차 (2026.11.16 ~ 2026.12.20)  
> **핵심 산출물:** `harness/safety/circuit_breaker.py`, `scripts/demo_scenario.sh`, `scripts/reset_env.sh`  
> **선행 조건:** Phase 4 자가 치유 FSM 및 우회 라우팅 완성

---

## 1. Phase 5 & 6 개발 목표 및 완료 기준 (Definition of Done)

- [ ] **12~13주차 DoD:** 관리자 수동 포트 격리/복원 REST API 연동 및 AI 이상 시 컨트롤러를 보호하는 긴급 서킷브레이커(`circuit_breaker.py`) 구현
- [ ] **14주차 DoD:** 4단계 E2E 시나리오(정상 ➔ 공격/탐지 ➔ 격리/우회 ➔ 자가복구) 풀코스 자동화 반복 테스트 및 패킷 유실률 2% 미만 달성
- [ ] **15주차 DoD:** 원클릭 시연 스크립트(`demo_scenario.sh`) 및 시스템 초기화 툴(`reset_env.sh`) 패키징
- [ ] **16주차 DoD:** 기말 최종 심사위원 라이브 시연 및 기술 질의응답 완벽 대응

---

## 2. 긴급 서킷 브레이커 및 원클릭 데모 자동화

### 2.1 긴급 서킷 브레이커 (`harness/safety/circuit_breaker.py`)
AI Worker가 오작동하여 초당 수십 건 이상의 격리 명령을 남발하거나 정상 호스트 포트를 반복 차단하려 할 경우, 제어권을 즉시 차단하고 수동 관리자 모드로 강제 전환하는 안전 장치입니다.

### 2.2 원클릭 시연 자동화 스크립트 (`scripts/demo_scenario.sh`)
```bash
#!/bin/bash
# 4단계 시나리오 원클릭 실행 스크립트
echo "[Step 1] 가상 인프라 및 Docker Ryu, Redis, FastAPI 백엔드 일괄 실행..."
# Mininet 토폴로지 구동 및 정상 트래픽 송출
# 30초 후 H_attacker SYN Flood 공격 주입
# AI Worker의 자동 차단 및 우회 모니터링
# 공격 중단 후 10초 내 자가 복구 완료 검증
```
