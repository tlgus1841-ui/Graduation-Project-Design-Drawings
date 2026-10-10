# 📗 [Domain Dev & QA] 10주차 구현 계획서 — 우회 라우팅 성능 측정 유틸
> **담당자:** 유재민 (22101498 / Domain Dev & QA)
> **해당 기간:** 10주차 (2026.11.02 ~ 2026.11.08)
> **상위 근거 문서:** [`schedule_and_milestones.md`](../../../planning/schedule_and_milestones.md), [`defense_scenarios.md`](../../../specs/defense_scenarios.md) §7(V2)

---

## 1. 목적 및 배경 — 선행 의존성 문제 (9주차와 동일한 패턴)

10주차 본래 과제는 "박시현의 Dijkstra 우회 라우팅(NetworkX, `OFPFC_ADD`)이 실제로 H_legit 통신을 무유실로 유지하는지 측정"이다. 이 기능(`ryu/app/controller.py`의 우회 경로 설치 로직)이 **아직 이 브랜치에 없어**, 실제 S1→S2→S4 ↔ S1→S3→S4 전환을 측정할 수 없다.

9주차와 동일하게, **측정 도구 자체**를 먼저 만들어 둔다. 박시현의 구현이 병합되면 Mininet에서 `ping`/`iperf` 결과를 이 도구에 그대로 넣어 V2 기준을 검증한다.

## 2. 요구사항 정리 (DoD 기준)

| # | 요구사항 | 출처 | 이번 주차 처리 방식 |
|:---:|:---|:---|:---|
| R1 | 패킷 손실률(Loss Rate) 계산 | schedule_and_milestones.md 10주차 | `compute_loss_rate()` 구현 |
| R2 | RTT(지연시간) 통계 계산 | schedule_and_milestones.md 10주차 | `compute_rtt_stats()` 구현 |
| R3 | 대체 경로 트래픽 부하 분산 측정 | schedule_and_milestones.md 10주차 | `compute_path_load_share()` 구현 |
| R4 | 우회 전환 시 H_legit 무유실 통신 실측 (V2: 손실률 ≤ 2.0%) | `defense_scenarios.md` §7 V2 | **보류** — 박시현의 우회 라우팅 구현 병합 후 Mininet에서 실측 필요 |

## 3. 설계 개요

### 3.1 모듈 구조
```
pipeline/
└── reroute_metrics.py
    ├── compute_loss_rate(sent_seq, received_seq) -> float
    ├── RttStats(mean_ms, p95_ms, max_ms, samples)
    ├── compute_rtt_stats(rtts_ms) -> RttStats
    └── compute_path_load_share(byte_counts_by_path) -> Dict[str, float]
```
- 입력은 Mininet `ping`(시퀀스 번호, RTT) 또는 Ryu 포트 통계(바이트 수)에서 뽑아낸 원시 값이라고 가정한다 — 네트워크 동작 자체를 흉내 내지 않고, **실측값을 받아 집계하는 순수 함수**로만 구성한다 (측정 대상이 없는 상태에서 가짜 네트워크 동작을 시뮬레이션하면 실측과 다른 결과를 낼 위험이 있기 때문).

## 4. 테스트 전략
- 손실률: 전부 수신/일부 손실/송신 0건 경계 조건
- RTT 통계: 알려진 값으로 평균/95퍼센타일/최댓값 검증, 빈 입력 시 에러
- 경로 부하 분산: 두 경로 비율 계산, 전체 0바이트 경계 조건
- V2 기준선(≤2.0%) 검증용 샘플 데이터로 `compute_loss_rate`가 임계치 판정에 바로 쓰일 수 있음을 확인

## 5. 완료 기준 체크리스트 (DoD)
- [x] R1, R2, R3 — 측정 유틸 구현 및 단위 테스트
- [ ] R4 — 박시현의 Dijkstra 우회 라우팅 병합 후 Mininet 실측 필요 (블로커 명시)
