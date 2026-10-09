# 📗 [Domain Dev & QA] 9주차 구현 계획서 — 플로우 테이블 고갈 방어 검증
> **담당자:** 유재민 (22101498 / Domain Dev & QA)
> **해당 기간:** 9주차 (2026.10.26 ~ 2026.11.01)
> **상위 근거 문서:** [`schedule_and_milestones.md`](../../../planning/schedule_and_milestones.md), [`defense_scenarios.md`](../../../specs/defense_scenarios.md) §3.3

---

## 1. 목적 및 배경 — 선행 의존성 문제

9주차 유재민의 본래 과제는 "박시현의 `whitelist_guard.py`(In_port 기반 Priority 100 Drop)가 실제로 플로우 테이블 고갈을 막는지 검증"이다. **그런데 이 브랜치 시점까지 `whitelist_guard.py`와 ISOLATE 명령 처리 로직이 아직 구현되어 있지 않다** (`ryu/app/controller.py`는 5~6주차의 L2/L3 스위칭 + 텔레메트리까지만 존재).

따라서 실제 컨트롤러를 대상으로 한 검증은 아직 불가능하다. 대신 **이 설계 결정이 왜 옳은지를 독립적으로 증명하는 벤치마크**를 먼저 만든다 — 박시현의 코드가 올라오면 같은 비교를 실제 컨트롤러의 `OVS-OFCTL dump-flows` 결과로 재현하면 된다.

## 2. 요구사항 정리 (DoD 기준)

| # | 요구사항 | 출처 | 이번 주차 처리 방식 |
|:---:|:---|:---|:---|
| R1 | 랜덤 IP 스푸핑 공격 시 플로우 테이블 고갈 방어 검증 | schedule_and_milestones.md 9주차 | 모의 플로우 테이블로 두 전략 비교 |
| R2 | In_port 1개 룰 차단 후 플로우 엔트리 증가율 0% | schedule_and_milestones.md 9주차 | 공격량과 무관하게 엔트리 1개 유지 검증 |
| R3 | 화이트리스트 포트 오차단 발생률 0% | schedule_and_milestones.md 9주차 | **보류** — `whitelist_guard.py` 없이는 검증 불가 |
| R4 | 공격 차단 중 컨트롤러 정상 가용성 확인 | schedule_and_milestones.md 9주차 | **보류** — 실제 컨트롤러/Mininet 필요 |

R3·R4는 박시현의 9주차 산출물이 이 브랜치에 merge된 후, 실제 `ryu/app/controller.py` + Mininet 환경에서 검증해야 한다. 이번 주차는 R1·R2만 독립적으로 완료한다.

## 3. 설계 개요

### 3.1 왜 in_port 차단인가 (벤치마크로 증명할 것)
`why_self_defending_sdn.md`가 이미 서술한 문제: 출발지 IP 기반 차단은 스푸핑된 IP마다 룰이 하나씩 늘어나 플로우 테이블이 고갈된다. 이를 숫자로 보여준다:
- **전략 A (순진한 방법):** 공격 패킷의 (스푸핑된) 출발지 IP마다 Drop 룰 추가 → 엔트리 수가 공격량에 거의 비례
- **전략 B (설계된 방법):** 공격 유입 포트(in_port) 하나에만 Drop 룰 추가 → 공격량과 무관하게 엔트리 1개

### 3.2 모듈 구조
```
tests/benchmarks/
└── test_flow_table_exhaustion.py
    ├── MockFlowTable            # 설치된 (match_key) 집합만 추적하는 단순 모델
    ├── block_by_source_ip()     # 전략 A
    ├── block_by_ingress_port()  # 전략 B
    └── 테스트 3종 (아래 §4)
```
`traffic/traffic_attack.py`의 `build_syn_packet()`/`flood_second()`를 그대로 재사용해 실제 스푸핑 패킷을 생성한다 — 5주차 산출물과의 일관성을 보장한다.

## 4. 테스트 전략
1. 전략 A로 공격 1,000건 처리 → 엔트리 수가 공격량에 거의 비례해서 늘어남을 확인 (고갈 위험 시연)
2. 전략 B로 공격 5,000건(최대 ATTACK_PPS) 처리 → 엔트리 수가 **1로 고정**됨을 확인
3. `flood_second(pps=5000)`로 실제 1초 분량 폭주를 만들어도 전략 B는 룰 1개로 충분함을 확인

## 5. 완료 기준 체크리스트 (DoD)
- [x] R1, R2 — 모의 플로우 테이블 벤치마크로 검증
- [ ] R3, R4 — 박시현의 `whitelist_guard.py` 병합 후 실제 환경에서 재검증 필요 (블로커 명시)
