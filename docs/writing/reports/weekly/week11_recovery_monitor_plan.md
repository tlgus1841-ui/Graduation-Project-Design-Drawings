# 📗 [Domain Dev & QA] 11주차 구현 계획서 — 공격 소멸 판정 & 쿨다운 플래핑 방지 (AI Worker 측)
> **담당자:** 유재민 (22101498 / Domain Dev & QA)
> **해당 기간:** 11주차 (2026.11.09 ~ 2026.11.15)
> **상위 근거 문서:** [`schedule_and_milestones.md`](../../../planning/schedule_and_milestones.md), [`defense_scenarios.md`](../../../specs/defense_scenarios.md) §2, §3.4, §8(Q2)

---

## 1. 목적 및 배경

9·10주차와 달리 11주차 과제("공격 중단 후 AI Worker의 트래픽 정상화 자동 판정 로직")는 **박시현의 산출물 없이도 독립적으로 완성 가능**하다 — 이건 애초에 AI Worker(유재민) 쪽 판단 로직이기 때문이다.

다만 `defense_scenarios.md` §8의 **Q2가 미결**이다: "쿨다운 중 공격 소멸 판정을 AI Worker가 할지, Ryu FSM(`flapping_fsm.py`)이 할지 주체 확정 필요(담당: 박시현)". `schedule_and_milestones.md`는 이 로직을 명시적으로 유재민의 11주차 과제로 지정하므로, 이번 주차는 **"AI Worker가 판단하고, Ryu는 그 판단(RESTORE 커맨드)을 실행만 한다"는 가정**으로 구현한다. Q2가 반대로 결정되면 이 모듈은 Ryu 쪽 FSM에 흡수되거나 참고용으로 남는다 — 어느 쪽이든 판단 로직 자체는 재사용 가능하다.

## 2. 요구사항 정리 (DoD 기준)

| # | 요구사항 | 출처 |
|:---:|:---|:---|
| R1 | 공격 중단 후 트래픽 정상화 자동 판정 | schedule_and_milestones.md 11주차 |
| R2 | 10초 쿨다운 하트비트 — 쿨다운 중 재공격 시 타이머 리셋(플래핑 방지) | schedule_and_milestones.md 11주차, `defense_scenarios.md` T4 |
| R3 | 정상 판정 기준: PPS < `ATTACK_CEASE_PPS`(100) **그리고** 스코어 ≥ `SCORE_THRESHOLD`(-0.5) | `defense_scenarios.md` §3.4 T3 |

## 3. 설계 개요

`defense_scenarios.md` §2의 FSM 중 `MITIGATED ⇄ COOLDOWN_VERIFY → NORMAL` 구간만 다룬다 (차단/우회 설치 자체는 박시현 담당).

```
model/
└── recovery_monitor.py
    ├── RecoveryPhase(Enum): MITIGATED | COOLDOWN_VERIFY | NORMAL
    └── RecoveryMonitor
        ├── observe(pps, score, now=None) -> RecoveryPhase   # 매 관측치마다 호출
        └── should_restore: bool 속성 (NORMAL 도달 시 True)
```

### 3.1 상태 전이 (defense_scenarios.md T3~T5 그대로)
- **T3 (MITIGATED → COOLDOWN_VERIFY):** `pps < 100 and score >= -0.5`
- **T4 (쿨다운 중 재공격 → MITIGATED):** 쿨다운 동안 위 조건이 깨지면 즉시 복귀 + 타이머 리셋
- **T5 (COOLDOWN_VERIFY → NORMAL):** 10초 연속 정상 판정 유지

## 4. 테스트 전략
- 공격 지속 중(PPS 높음)에는 MITIGATED 유지
- 공격 소멸 조건 충족 시 COOLDOWN_VERIFY 진입
- 10초 꽉 채워 정상 유지 시 NORMAL(= `should_restore=True`) 도달
- 쿨다운 중 재공격 발생 시 MITIGATED로 복귀 + 타이머가 리셋되어, 그 뒤 다시 10초를 꽉 채워야 복구됨을 확인 (플래핑 방지 핵심)
- PPS만 낮고 스코어가 안 좋으면(또는 반대) MITIGATED 유지 — 두 조건 모두 필요

## 5. 완료 기준 체크리스트 (DoD)
- [x] R1, R2, R3 — `RecoveryMonitor` 구현 및 단위 테스트
- [ ] 실제 `AnomalyAlertMessage` 스트림을 받아 동작시키는 통합은 Redis 연동이 필요한 범위라 추후(박시현 Q2 결론 이후) 연결
