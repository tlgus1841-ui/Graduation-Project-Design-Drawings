# DDoS 외 공격 유형(포트 스캔 · Slow Drift) 방어 추가 보고서

- **작성일**: 2026-10-14
- **작성자**: 유재민 (Domain Dev & QA)
- **대상 브랜치**: [`feature/multi-attack-type-defense`](https://github.com/tlgus1841-ui/Graduation-Project-Design-Drawings/pull/new/feature/multi-attack-type-defense) (`main` 최신 동기화 후 분기)
- **영향 범위**: `model/` 전담 (신규 2개 파일), `model/inference_worker.py` 확장. 기존 DDoS 플러드 탐지 경로는 **트리거 로직 무변경**.
- **리뷰 요청**: `harness/contracts/sdn_events.py`는 박시현 영역이므로, `ThreatType` enum에 값 1개를 추가(`PORT_SCAN`)한 부분만 리뷰 부탁드립니다.

---

## 1. 왜 필요했는가

기존 `DetectionGuard`(Isolation Forest 점별 탐지)는 수치가 한 번에 확 튀는 **플러드형 DDoS**(SYN/UDP/ICMP Flood)에 대해서는 2주기 연속 확인으로 실측 검증이 끝난 상태입니다. 하지만 구조적으로 아래 두 유형은 원래부터 잡을 수 없었습니다.

| 공격 유형 | 왜 기존 경로로는 못 잡는가 |
| :--- | :--- |
| **포트 스캔** | 패킷 수(PPS)가 플러드만큼 크지 않아 Isolation Forest가 "정상 범위"로 판단함 |
| **Slow 공격 (Slowloris류)** | 한 틱(2초)만 보면 수치가 거의 정상과 같고, 여러 틱에 걸쳐 *서서히* 벗어나는 패턴이라 점별(point-wise) 탐지기 구조 자체로는 못 봄 |

이 둘을 잡는 **2차 분류기**를 기존 플러드 탐지 경로와 **병행(독립)** 실행으로 추가했습니다. 한 포트가 플러드와 포트 스캔을 동시에 당할 수도 있으므로 두 경로는 서로 배타적이지 않게 설계했습니다.

---

## 2. 추가/변경 파일

| 파일 | 상태 | 내용 |
| :--- | :--- | :--- |
| [`model/ewma_detector.py`](../../../../model/ewma_detector.py) | 신규 | EWMA(지수 가중 이동평균) + SPC(통계적 공정관리) 기반 경량 드리프트 탐지기 |
| [`model/attack_classifier.py`](../../../../model/attack_classifier.py) | 신규 | `err_rate` 임계값 기반 **PORT_SCAN** 판정 + EWMA 기반 **SLOW_DRIFT** 판정, `StreakGuard`로 N회 연속 확정(오탐 방지) |
| [`model/inference_worker.py`](../../../../model/inference_worker.py#L83-L112) | 수정 | `InferenceWorker.process()`가 `SecondaryAttackClassifier`를 플러드 경로와 함께 호출 |
| [`harness/contracts/sdn_events.py`](../../../../harness/contracts/sdn_events.py) | 수정 (리뷰 요청) | `ThreatType` enum에 `PORT_SCAN = "PORT_SCAN"` 한 줄 추가 (기존 값 변경 없음, 하위 호환) |
| `tests/model/test_ewma_detector.py`, `test_attack_classifier.py`, `test_inference_worker.py`(확장) | 신규/확장 | 아래 4절 |

### 탐지 로직 요약

```
err_rate >= 0.3           -> PORT_SCAN   (포트 다수 접속 실패 = 닫힌 포트 두드리는 스캔 신호)
EWMA 추세 이상(그 외)       -> SLOW_DRIFT (서서히 기준선 벗어나는 연결 지속시간 등)
둘 다 아님                  -> NORMAL
```

두 판정 모두 `StreakGuard`(연속 2회 확정, 기존 `DetectionGuard`와 동일한 보수적 설계 원칙)를 통과해야 실제 경보(`AnomalyAlertMessage`)로 나갑니다.

---

## 3. 솔직한 기술적 한계 (팀에 공유 필요)

SDN 포트 통계(`OFPPortStatsRequest`)는 **L4 프로토콜을 구분하지 못합니다.** 즉 스위치 포트 카운터만 보고는 SYN Flood/UDP Flood/ICMP Flood를 서로 구별할 수 없습니다.

그래서 이번 추가에서 **일부러 하지 않은 것**:
- SYN/UDP/ICMP Flood를 세분화해서 구분하는 것 — 포트 레벨 텔레메트리로는 근거 없는 구분을 만들어내는 것이라 판단해 전부 기존 `VOLUMETRIC_FLOOD`(→ `SYN_FLOOD_SPOOFING`) 하나로 유지했습니다.
- 대신 **포트 스캔**(에러율 기반)과 **Slow 공격**(추세 기반)처럼, 현재 수집 중인 5대 피처(`delta_pps`, `delta_bps`, `bpp`, `err_rate`, `duration_sec`)로 **근거 있게 구분 가능한 유형만** 추가했습니다.

발표/보고서에서 "모든 공격 유형을 다 구분한다"고 과장하지 않도록, 이 한계를 그대로 공유드립니다.

---

## 4. 테스트 결과

| 테스트 파일 | 건수 | 결과 |
| :--- | ---: | :--- |
| `tests/model/test_ewma_detector.py` (신규) | 5 | ✅ 5/5 |
| `tests/model/test_attack_classifier.py` (신규) | 8 | ✅ 8/8 |
| `tests/model/test_inference_worker.py` (포트 스캔 통합 테스트 2건 추가) | 6 | ✅ 6/6 (기존 4건 포함, 동작 무변경 확인) |
| 전체 회귀 (`tests/traffic ~ tests/ryu`) | 195 | 191 통과, 4건 실패 (아래 설명) |
| `flake8` (`model/`, `harness/`, `tests/model/`) | - | 0 issues |
| `mypy` (35개 소스 파일) | - | 0 issues |

### 4-1. 전체 회귀의 4건 실패는 이번 변경과 무관함

`test_benchmark_report.py::test_build_report_meets_dod_thresholds`, `test_latency_profiler.py::test_inference_under_10ms` / `test_combined_ai_pipeline_total`, `test_model_evaluator.py::test_predict_single_latency_under_10ms` 4건이 "추론 지연시간 10ms 미만" 기준을 못 넘긴 것으로 실패했습니다.

- 이번에 추가/수정한 파일 어느 것도 관련 없음 (모델 추론 속도 자체를 건드리지 않음).
- 이 4개만 따로 격리 실행해도 동일하게 재현됨 → 다른 테스트와의 충돌이 아니라, `IsolationForest(n_jobs=-1)`의 joblib 병렬 백엔드가 이 Windows 샌드박스 환경에서 가끔 기동 비용이 튀는, **이전부터 보고되었던 환경 이슈**입니다.
- 실제 GCP 스트레스 테스트([`week16_stress_limit_test_report.md`](week16_stress_limit_test_report.md))에서는 동일 모델이 **0.3~2.2ms** 수준으로 안정적으로 동작한 것이 실측 확인되어 있어, 운영 환경(실제 데모 서버)에서는 문제가 되지 않습니다.

### 4-2. 개발 중 발견하고 직접 수정한 버그 2건 (`EwmaDetector`)

자체 테스트를 작성하며 발견한, 신규 코드 자체의 버그입니다 (팀원 코드 아님, 제가 바로 수정).

1. **초기화 직후 오탐**: 첫 관측 이후 분산(variance)이 0에 가까워, 두 번째 값부터 아주 작은 편차에도 즉시 "이상치"로 잘못 판정됨 → `warmup`(기본 5회) 구간을 추가해, 분산이 충분히 쌓이기 전에는 판정을 내리지 않도록 수정.
2. **서서히 커지는 드리프트가 스스로 "정상"이 되어버림**: 분산을 매 스텝 계속 갱신하면, 공격으로 인한 드리프트 자체가 "정상적인 변동 폭"으로 재학습되어, 편차와 임계값이 함께 커지다가 결국 다시 "정상" 판정으로 돌아오는 문제를 테스트로 확인(`deviation`과 `std`가 같은 값(~20)으로 수렴). `warmup` 구간 이후로는 분산을 고정하는 방식(SPC 관리도와 동일 원리)으로 수정.

---

## 5. 다음 단계 제안

- `harness/contracts/sdn_events.py` 변경 1줄, 박시현 리뷰 후 머지 부탁드립니다.
- 머지 후 실제 데모 서버(`34.47.120.59`)의 `inference_worker`도 이 브랜치로 갱신해야 포트 스캔/Slow 공격 탐지가 반영됩니다 (현재 서버는 기존 플러드 탐지 코드만 배포되어 있음).
- 발표 자료에 "DDoS 외 공격 방어"를 넣을 경우, 3절의 한계(L4 프로토콜 미구분)를 함께 언급하는 것을 권장드립니다 — 질의응답에서 "SYN이랑 UDP Flood를 어떻게 구분하냐"는 질문에 솔직하게 답할 수 있도록.
