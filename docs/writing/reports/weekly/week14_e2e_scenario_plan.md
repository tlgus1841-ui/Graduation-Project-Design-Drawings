# 📗 [Domain Dev & QA] 14주차 구현 계획서 — 종합 E2E 시나리오 (AI 파이프라인 구간)
> **담당자:** 유재민 (22101498 / Domain Dev & QA)
> **해당 기간:** 14주차 (2026.11.30 ~ 2026.12.06)
> **상위 근거 문서:** [`schedule_and_milestones.md`](../../../planning/schedule_and_milestones.md), [`defense_scenarios.md`](../../../specs/defense_scenarios.md)

---

## 1. 목적 및 배경 — 지금까지의 블로커를 하나로 모아 재확인

14주차 본래 과제는 "4단계 E2E 시나리오(정상→공격탐지→차단/우회→자가복구) 풀코스 자동화, 손실률(≤2%)·반응시간(≤100ms) 검증"이다. 실제 네트워크 손실률/반응시간은 9·10·12주차에서 이미 블로커로 명시한 대로 **박시현의 Ryu 방어 로직(9~11주차) 병합 후 Mininet 실측이 필요**하다.

대신 이번 주차는 7~13주차에 만든 **AI Worker 측 구성요소(모델, 탐지 게이트, 복구 판정)를 하나로 엮어** defense_scenarios.md의 4단계 전이를 실제로 재현해본다. 이게 바로 "풀코스 자동화"에서 AI Worker가 담당하는 부분이다 — Ryu의 플로우 설치/삭제만 빠져 있을 뿐, 판단 로직 자체는 지금 전부 검증 가능하다.

## 2. 요구사항 정리 (DoD 기준)

| # | 요구사항 | 출처 | 처리 방식 |
|:---:|:---|:---|:---|
| R1 | 4단계 시나리오 AI 판단 체인 자동화 | schedule_and_milestones.md 14주차 | 통합 테스트로 구현 |
| R2 | 패킷 손실률 ≤ 2% (V2) | `defense_scenarios.md` §7 | **보류** — Mininet 실측 필요 (9·10주차와 동일 블로커) |
| R3 | E2E 반응시간 ≤ 100ms (V1, 탐지 주기 제외) | `defense_scenarios.md` §7 | AI 구간(피처추출+추론)은 12주차에 이미 <15ms로 확인. 플로우 주입 포함 전체 반응시간은 보류 |

## 3. 설계 개요
`tests/benchmarks/test_e2e_ai_pipeline_scenario.py` 하나로 4단계를 순서대로 재현한다:
1. **정상:** 정상 샘플 → 모델 추론 → `DetectionGuard` 미확정
2. **공격 탐지:** 공격 샘플을 `DETECT_CONSECUTIVE`(2)주기 연속 주입 → `DetectionGuard` 확정
3. **격리 유지:** `RecoveryMonitor`가 공격 지속 중엔 `MITIGATED` 유지
4. **자가 복구:** 정상 샘플로 전환 → `COOLDOWN_SEC`(10초) 경과 후 `RecoveryMonitor`가 `NORMAL`(= `should_restore`) 도달

7~13주차에 만든 모든 모듈(`model.py`, `detection_guard.py`, `recovery_monitor.py`)을 조립만 하는 테스트라 신규 소스 모듈은 추가하지 않는다.

## 4. 완료 기준 체크리스트 (DoD)
- [x] R1 — AI 파이프라인 4단계 통합 테스트
- [x] R3(AI 구간) — 12주차 결과 재확인
- [ ] R2, R3(전체) — 박시현 9~11주차 병합 후 Mininet 실측 필요
