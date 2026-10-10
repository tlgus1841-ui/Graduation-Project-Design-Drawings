# 📗 [Domain Dev & QA] 13주차 구현 계획서 — Flash Crowd 오탐 방지 게이트
> **담당자:** 유재민 (22101498 / Domain Dev & QA)
> **해당 기간:** 13주차 (2026.11.23 ~ 2026.11.29)
> **상위 근거 문서:** [`schedule_and_milestones.md`](../../../planning/schedule_and_milestones.md), [`defense_scenarios.md`](../../../specs/defense_scenarios.md) §3.2(T1), §6, §8(Q1)

---

## 1. 목적 및 배경

정상 트래픽 급증(Flash Crowd — 예: 이벤트로 접속자가 몰림)은 PPS가 공격처럼 치솟지만, 패킷당 바이트 수(BPP)는 정상 범위(700~1,200B)를 유지한다. 반면 SYN Flood는 페이로드 없는 극소형 패킷(BPP ≤ 80B)이다. Isolation Forest 점수 하나만으로 판단하면 PPS 급증에 휘둘려 Flash Crowd를 공격으로 오판할 위험이 있다 — 그래서 `defense_scenarios.md` T1은 **BPP와 점수 두 조건을 함께**, 그것도 **2주기 연속** 충족해야 공격을 확정하도록 설계돼 있다.

이번 주차는 이 "오탐 방지 게이트"를 실제로 구현하고, Flash Crowd 샘플에 대해 FPR ≤ 1.0%, 실제 공격에 대해 F1 ≥ 0.95를 달성하는지 검증한다.

## 2. 요구사항 정리 (DoD 기준)

| # | 요구사항 | 출처 |
|:---:|:---|:---|
| R1 | Flash Crowd vs 실제 공격 오탐 방지 임계치 튜닝 | schedule_and_milestones.md 13주차 |
| R2 | F1-Score ≥ 0.95 | schedule_and_milestones.md 13주차 |
| R3 | 오탐률(FPR) ≤ 1.0% | schedule_and_milestones.md 13주차 |
| R4 | 공격 확정 조건: BPP ≤ 80B **그리고** score < -0.5, `DETECT_CONSECUTIVE`(2)주기 연속 | `defense_scenarios.md` §3.2 T1 |

## 3. 설계 개요

### 3.1 왜 Isolation Forest 점수만으로는 부족한가
7주차 모델은 5대 피처(ΔPPS 포함)를 전부 입력으로 쓰므로 어느 정도는 BPP로 구분하지만, "점수 < 0"이라는 기본 컷오프 하나만 보면 PPS 급증의 영향을 완전히 배제하지 못한다. `defense_scenarios.md`가 이미 BPP 임계치(`BPP_ATTACK_MAX`=80)를 모델 점수와 **별도의 명시적 게이트**로 둔 이유가 여기에 있다 — 두 신호를 AND로 묶으면 PPS만 튄 Flash Crowd는 BPP 게이트에서 바로 걸러진다.

### 3.2 모듈 구조
```
model/
└── detection_guard.py
    ├── is_suspicious(bpp, score) -> bool      # BPP<=80 AND score<-0.5 (단일 관측치)
    └── DetectionGuard                          # DETECT_CONSECUTIVE(2)주기 연속 확인
        └── observe(bpp, score) -> bool (공격 확정 여부)
```

## 4. 테스트 전략
1. `DetectionGuard` 단위: 연속 충족 시 확정, 단발 스파이크는 확정 안 됨, 좋은 주기가 끼면 스트릭 리셋
2. **Flash Crowd 핵심 검증:** BPP가 정상 범위면 점수가 나빠도 절대 확정되지 않음
3. 통합: 정상 100 + Flash Crowd 100 + 공격 100 샘플을 모델 점수 → `DetectionGuard`에 통과시켜 R2(F1≥0.95)·R3(FPR≤1.0%) 동시 달성 확인

## 5. 완료 기준 체크리스트 (DoD)
- [x] R1~R4 — `detection_guard.py` 구현 및 통합 테스트로 F1/FPR 수치 검증
