# 📗 [Domain Dev & QA] 15주차 구현 계획서 — 시연 자동화 & 데이터셋/리포트 패키징
> **담당자:** 유재민 (22101498 / Domain Dev & QA)
> **해당 기간:** 15주차 (2026.12.07 ~ 2026.12.13)
> **상위 근거 문서:** [`schedule_and_milestones.md`](../../../planning/schedule_and_milestones.md)

---

## 1. 목적 및 배경

15주차 과제 3가지 중 "고화질 시연 동영상 백업 녹화"는 실제 촬영 작업이라 코드 범위 밖이다. 나머지 둘을 패키징한다:
- **시연용 모의 공격 프로파일 프리셋** — 매번 `--min-pps`/`--max-pps`를 손으로 맞추지 않도록
- **정량 성능 평가 지표/데이터셋 최종 추출** — 7~14주차에 검증한 F1·FPR·지연시간을 하나의 리포트로 모음

겸사겸사 7주차부터 테스트 파일에 흩어져 있던 합성 데이터 생성기(`_normal_sample` 등)를 `model/synthetic_samples.py`로 모았다 — 리포트 생성기가 테스트 코드를 import하는 역방향 의존을 피하기 위함이다.

## 2. 요구사항 정리 (DoD 기준)

| # | 요구사항 | 출처 | 처리 방식 |
|:---:|:---|:---|:---|
| R1 | 시연용 모의 공격 프로파일 프리셋 패키징 | schedule_and_milestones.md 15주차 | `traffic/attack_profiles.py` + `traffic_attack.py --preset` |
| R2 | 정량 성능 평가 지표 리포트 추출 | schedule_and_milestones.md 15주차 | `model/benchmark_report.py` |
| R3 | (코드 범위 밖) 시연 동영상 백업 녹화 | schedule_and_milestones.md 15주차 | 실제 시연 당일 작업 |

## 3. 설계 개요

### 3.1 리팩터링: `model/synthetic_samples.py`
- `normal_sample()`, `attack_sample()`, `flash_crowd_sample()`, `build_labeled_dataset_csv()`
- 기존 `tests/model/test_model_evaluator.py`는 이 모듈을 import하도록 변경 (중복 제거, 하위 테스트 파일들의 기존 import 경로는 호환 유지)

### 3.2 공격 프리셋 (`traffic/attack_profiles.py`)
| 프리셋 | PPS 범위 | 용도 |
|:---|:---:|:---|
| `light` | 1,000~2,000 | 탐지 로직 단독 시연 |
| `standard` | 1,000~5,000 | `ATTACK_PPS` 기본 범위 |
| `heavy` | 4,000~5,000 | 플로우 테이블 고갈 방어(9주차) 시연 |

`traffic_attack.py`에 `--preset {light,standard,heavy}` 옵션 추가 (지정 시 `--min-pps`/`--max-pps` 무시).

### 3.3 최종 리포트 (`model/benchmark_report.py`)
`build_report(model, n_per_class)` → 정상/Flash Crowd/공격 각 N개로 F1·FPR·추론 지연(중앙값)을 한 번에 집계, `save_report()`로 JSON 저장.

## 4. 완료 기준 체크리스트 (DoD)
- [x] R1 — 프리셋 3종 + CLI 연동
- [x] R2 — 리포트 생성기 및 JSON 저장
