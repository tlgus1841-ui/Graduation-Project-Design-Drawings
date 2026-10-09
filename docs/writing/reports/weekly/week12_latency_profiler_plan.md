# 📗 [Domain Dev & QA] 12주차 구현 계획서 — E2E 지연시간 프로파일러 & Contamination 튜닝
> **담당자:** 유재민 (22101498 / Domain Dev & QA)
> **해당 기간:** 12주차 (2026.11.16 ~ 2026.11.22)
> **상위 근거 문서:** [`schedule_and_milestones.md`](../../../planning/schedule_and_milestones.md), [`week06_feature_extractor_implementation_plan.md`](week06_feature_extractor_implementation_plan.md), [`week07_model_implementation_plan.md`](week07_model_implementation_plan.md)

---

## 1. 목적 및 배경

7~11주차로 "피처 추출(`feature_extractor.py`)"과 "추론(`model.py`)" 두 구성요소가 모두 준비됐다. 12주차는 이 둘을 이어 **AI Worker가 통제하는 구간의 E2E 지연시간**을 실측하고, Isolation Forest의 `contamination` 파라미터를 데이터로 재검증한다.

- 전체 E2E 지연(피처 추출 + 추론 + **플로우 주입**)에서 "플로우 주입"은 박시현의 Ryu 컨트롤러가 `OFPFC_ADD`를 실제 스위치에 적용하는 구간이라, 이 환경에선 측정할 수 없다. 이 모듈은 **AI Worker가 통제 가능한 구간(피처 추출 + 추론)만** 측정한다.

## 2. 요구사항 정리 (DoD 기준)

| # | 요구사항 | 출처 | 처리 방식 |
|:---:|:---|:---|:---|
| R1 | 피처 추출 지연 < 5ms | phase2 가이드 6주차 DoD | `measure_feature_extraction_ms()` |
| R2 | 추론 지연 < 10ms | phase2 가이드 7주차 DoD | `measure_inference_ms()` (11주차에 이미 버그 수정으로 확보) |
| R3 | 플로우 주입 포함 합산 지연 | schedule_and_milestones.md 12주차 | **보류** — Ryu 플로우 주입 코드 병합 후 실측 |
| R4 | Contamination 파라미터 정밀 튜닝 | schedule_and_milestones.md 12주차 | 합성 데이터셋으로 여러 값 스윕, R1(7주차, contamination=0.1)이 여전히 타당한지 재검증 |

## 3. 설계 개요

### 3.1 모듈 구조
```
model/
└── latency_profiler.py
    ├── measure_feature_extraction_ms(extractor, prev_message, current_message) -> float
    ├── measure_inference_ms(model, feature_dict) -> float
    ├── LatencyReport(feature_extraction_ms, inference_ms, ai_pipeline_total_ms)
    └── profile_pipeline(extractor, model, prev_message, current_message) -> LatencyReport
```

### 3.2 Contamination 튜닝
`tests/model/test_contamination_tuning.py`에서 `{0.05, 0.1, 0.15, 0.2}`를 스윕해, 7주차에 고정한 `contamination=0.1`이 F1 ≥ 0.90 기준을 가장 안정적으로 만족하는지 재확인한다. R1(phase2 가이드)이 0.1을 명시적으로 요구하므로, 더 나은 값이 나와도 **0.1을 기본값으로 유지**하고 결과만 리포트에 남긴다.

## 4. 완료 기준 체크리스트 (DoD)
- [x] R1, R2 — `latency_profiler.py`로 측정, 각 임계치 통과 확인
- [x] R4 — contamination 스윕 테스트로 0.1이 타당함을 재확인
- [ ] R3 — 박시현의 플로우 주입 코드 병합 후 Mininet에서 합산 실측 필요
