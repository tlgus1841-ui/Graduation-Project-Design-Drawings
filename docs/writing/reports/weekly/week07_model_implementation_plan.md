# 📗 [Domain Dev & QA] 7주차 구현 계획서 — Isolation Forest 이상 탐지 모델 (`model/model.py`)
> **담당자:** 유재민 (22101498 / Domain Dev & QA)
> **해당 기간:** 7주차 (2026.10.12 ~ 2026.10.18)
> **상위 근거 문서:** [`schedule_and_milestones.md`](../../../planning/schedule_and_milestones.md), [`phase2_traffic_features_model.md`](../../../guides/dev_b_domain_qa/phase2_traffic_features_model.md), [`week06_feature_extractor_implementation_plan.md`](week06_feature_extractor_implementation_plan.md)

---

## 1. 목적 및 배경

6주차 `feature_extractor.py` + `csv_logger.py`가 쌓아둔 5대 피처 CSV(`dataset/traffic_data.csv`, label 0/1)를 입력으로, **Scikit-learn Isolation Forest** 비지도 이상 탐지 모델을 학습하고, 단일 샘플 실시간 추론(<10ms)이 가능한지 평가 하네스로 검증한다.

- **대상 파일:** `model/model.py`
- **입력:** 6주차 CSV 데이터셋 (`delta_pps, delta_bps, bpp, err_rate, duration_sec, label`)
- **출력:** `model/isolation_forest.joblib` (직렬화된 학습 파이프라인)
- **후속 연계:** 9주차 박시현의 `In_port Priority 100 Drop` 트리거가 이 모델의 이상치 스코어를 기준으로 동작

## 2. 요구사항 정리 (DoD 기준)

| # | 요구사항 | 출처 |
|:---:|:---|:---|
| R1 | `IsolationForest(n_estimators=100, contamination=0.1, random_state=42, n_jobs=-1)` + `StandardScaler` Pipeline | phase2 가이드 7주차 |
| R2 | `fit(csv_path)` — CSV로 학습 후 `model/isolation_forest.joblib` 저장 | phase2 가이드 7주차 |
| R3 | `predict_single(feature_dict) -> (is_anomaly: bool, score: float)` | phase2 가이드 7주차 |
| R4 | 단일 추론 지연 <10ms | phase2 가이드 DoD 표 |
| R5 | F1-Score ≥ 0.90 (1차 기준선) | phase2 가이드 DoD 표 |
| R6 | 평가 하네스(`model_evaluator.py`)로 R4/R5 자동 검증 | phase2 가이드 7주차 |

## 3. 설계 개요

### 3.1 디렉토리 배치에 대한 결정 (선행 문서 간 불일치 해소)
`phase2_traffic_features_model.md`는 평가 하네스 경로를 `tests/harness/model_evaluator.py`로 적지만, `docs/guides/00_common/git_collaboration_guide.md`의 담당 디렉토리표는 `tests/harness/`를 **박시현 전담 디렉토리**로 지정한다(유재민의 "절대 수정 금지 영역"에 `harness/`가 포함). 두 문서가 충돌하므로, 이미 이 저장소에서 쓰고 있는 실제 관례(`traffic/`→`tests/traffic/`, `pipeline/`→`tests/pipeline/`, `api/`→`tests/api/`, `ryu/`→`tests/ryu/` — 소스 디렉토리명을 그대로 미러링)를 따라 **`model/` → `tests/model/`**에 배치한다. 테스트 파일명(`test_model_evaluator.py`)은 두 문서가 일치하는 대로 유지한다.

### 3.2 모듈 구조
```
model/
└── model.py
    ├── FEATURE_COLUMNS = [delta_pps, delta_bps, bpp, err_rate, duration_sec]
    ├── AnomalyModel
    │   ├── __init__(n_estimators=100, contamination=0.1, random_state=42)
    │   ├── fit(csv_path) -> self
    │   ├── predict_single(feature_dict) -> (is_anomaly: bool, score: float)
    │   ├── save(path) / classmethod load(path)
    └── _load_dataset(csv_path) -> (X, y)   # 6주차 csv_logger가 쓴 CSV를 그대로 읽음
```

### 3.3 학습/평가 데이터 전략
Mininet·Ryu가 없는 이 환경에서는 실제 공격을 재현해 CSV를 쌓을 수 없다. 평가 하네스는 4~6주차에 이미 확정된 정상/공격 통계 특성(`docs/specs/defense_scenarios.md` §3.1, §3.2)을 따르는 **합성 데이터셋**을 생성해 학습·평가한다:
- 정상: `delta_pps` 10~100, `bpp` 700~1,200B, `err_rate` ≈ 0
- 공격: `delta_pps` 1,000~5,000, `bpp` ≈ 64B(54~74B 패킷에서 유도), `err_rate` ≈ 0

실제 Mininet 환경에서 수집한 CSV로 재학습해도 `AnomalyModel.fit()` 인터페이스는 동일하게 동작한다.

## 4. 테스트 전략
- `fit()` → `predict_single()`이 정상/공격 합성 샘플을 각각 올바르게 분류하는지 (F1 ≥ 0.90)
- 단일 추론 100회 반복 평균 지연 < 10ms
- `save()`/`load()` 라운드트립 후 예측 결과 동일
- 학습 전 `predict_single()` 호출 시 명시적 에러

## 5. 완료 기준 체크리스트 (DoD)
- [ ] `model/model.py` — Pipeline(StandardScaler + IsolationForest) 구현
- [ ] `fit`/`predict_single`/`save`/`load` 전부 구현 및 테스트
- [ ] `tests/model/test_model_evaluator.py` — F1 ≥ 0.90, 추론 지연 < 10ms 검증
- [ ] 전체 회귀(`pytest`, `flake8`, `mypy`) 통과
