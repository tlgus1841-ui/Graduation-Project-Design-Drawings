# 16주차 실제 구성 E2E 검증: AI 탐지 + Ryu 컨트롤러 연동

| 항목 | 내용 |
|:---|:---|
| 작성 | 김관우 (PM & Tech Writer) |
| 측정일 | 2026.10.11 |
| 기준 코드 | `integration/week16-final` + `model/inference_worker.py` (신규) |
| 측정 도구 | `harness/verification/e2e_scenario.py` (14주차와 같은 시나리오) |
| 원본 데이터 | [`data/week16_real_e2e.json`](data/week16_real_e2e.json) |

## 1. 목적

14주차 E2E는 AI 탐지·FSM·방어 실행을 임시 구성으로 대신했다. 이번에는 세 명의 실제 코드를 하나로 이어 같은 시나리오를 다시 잰다. 빠져 있던 마지막 연결인 **AI 추론 워커**(포트 통계 → 모델 → 경보)를 새로 만들어 넣었다.

## 2. 구성: 14주차와 비교

| 단계 | 14주차 | 16주차 (이번) |
|:---|:---|:---|
| 스위칭·통계 수집 | Ryu (5~6주차 코드) | Ryu 컨트롤러 (박시현 `park16week`) |
| 피처 계산 | `pipeline/feature_extractor.py` | 같음 |
| AI 탐지 | 규칙 (BPP ≤ 80, ΔPPS ≥ 500) | **Isolation Forest** (유재민 `model/model.py`) + 오탐 방지 게이트 (`model/detection_guard.py`) |
| 경보 발행 | 임시 방어 루프 | **추론 워커** (`model/inference_worker.py`, 신규) |
| 방어 FSM | 명세 참조 구현 `SpecFSM` | **컨트롤러 FSM** (`harness/safety/flapping_fsm.py`) |
| 차단·우회 실행 | `ovs-ofctl` 직접 실행 | **컨트롤러 FlowMod** (차단 Priority 100, Dijkstra 우회 Priority 20) |
| 관제탑 | FastAPI live 모드 | 같음 |

**대체 구성 없음.** 단, 모델은 유재민의 합성 데이터(`model/synthetic_samples.py`)로 학습했다. 실제 Mininet 트래픽으로 학습한 모델은 아니다.

## 3. 추론 워커 동작

1. `sdn:stats:port`(2초 주기)를 받아 FeatureExtractor로 5대 피처를 만든다.
2. 감시 대상은 **보호 호스트가 없는 접속 포트**뿐이다 (접속 포트 S1:1·S1:2·S4:1 중 정상 사용자 S1:1과 서버 S4:1 제외 → S1:2). 트렁크 포트는 컨트롤러가 어차피 막지 않는다.
3. 모델 점수와 BPP를 게이트에 넣는다: BPP ≤ 80 **그리고** 점수 < 0 이 **2주기 연속**이면 공격 확정. 초당 100패킷 미만(명세 `ATTACK_CEASE_PPS`)은 공격 규모가 아니므로 연속 기록을 끊는다.
4. 확정된 동안 매 주기 `sdn:anomaly:alert`를 발행한다. 컨트롤러 FSM은 마지막 경보부터 쿨다운 10초를 재므로, 경보가 끊기면 10초 뒤 자동 복구된다.

차단 후에도 S1:2의 수신 카운터는 공격 패킷을 계속 센다 (버림은 수신 뒤에 일어난다). 그래서 공격이 이어지는 동안 경보도 이어지고, 공격이 멈추면 경보가 멈춘다.

## 4. 결과 (3회)

| 지표 | 1회 | 2회 | 3회 | 평균 | 14주차 (임시 구성) |
|:---|:---:|:---:|:---:|:---:|:---:|
| 공격 패킷 (S1:2 수신) | 30,363 | 35,114 | 34,011 | 33,163 | 35,159 |
| 공격 시작 → 첫 경보 = 차단 | 3.53초 | 3.24초 | 3.27초 | **3.35초** | 약 3.75초 |
| 경보 → 컨트롤러 차단·우회 명령 | 1.6ms | 1.3ms | 1.3ms | **1.4ms** | 78.4ms (`ovs-ofctl`) |
| 격리 중 S1에서 버려진 공격 패킷 | 24,435 | 27,448 | 25,955 | 25,946 | 28,118 |
| 격리 중 서버에 닿은 공격 패킷 | 0 | 0 | 0 | **0** | 0 |
| 복구 횟수 (플래핑) | 1 | 1 | 1 | **플래핑 0** | 0 |
| 공격 종료 → 자동 복구 | 10.81초 | 10.29초 | 11.51초 | **10.87초** | 12.73초 |
| 정상 ping 손실 (전체) | 0 / 1,441 | 0 / 1,452 | 0 / 1,444 | **0%** | 0% |
| 정상 ping 손실 (공격 구간) | 0 / 375 | 0 / 414 | 0 / 389 | **0%** | 0% |
| 경보가 난 포트 | S1:2만 | S1:2만 | S1:2만 | 오탐 0 | - |
| 경보 시 모델 점수 | -0.066 ~ -0.127 | | | 모두 < 0 | - |

- **경보 → 명령 1.4ms**는 컨트롤러가 경보를 받아 차단·우회 FlowMod를 보내고 조치 기록을 발행하기까지의 시간이다. 스위치가 규칙을 실제로 적용한 시점까지는 포함하지 않는다. 14주차의 78.4ms는 `ovs-ofctl` 프로세스 실행 시간이라 같은 기준이 아니다.
- **공격 시작 → 차단 3.35초**의 대부분은 2초 통계 주기 2번을 기다리는 시간이다 (오탐 방지를 위한 설계).
- **복구가 14주차보다 약 2초 빠른 이유:** 컨트롤러 FSM은 마지막 경보부터 10초를 재고, 14주차 `SpecFSM`은 공격 소멸 확인 샘플(2초) 뒤부터 10초를 쟀다.

**판정: 통과.** 실제 AI·컨트롤러 구성으로 4단계 루프가 3회 모두 사람 개입 없이 완결되었고, 정상 트래픽 손실 0%, 서버 도달 공격 0, 플래핑 0, 오탐 0.

## 5. 발견 사항과 후속

| 항목 | 내용 | 담당 |
|:---|:---|:---:|
| 반복 조치 기록 | 컨트롤러가 경보마다 ISOLATE·REROUTE를 다시 실행하고 기록을 발행해, 공격 20초 동안 관제탑 이벤트에 명령이 10쌍씩 쌓인다. MITIGATED 상태에서는 FSM 수명만 연장하고 기록은 생략하는 편이 깔끔하다. | 박시현 |
| 학습 데이터 | 모델이 합성 데이터로 학습됐다. 실제 Mininet 정상 트래픽을 `csv_logger`로 모아 `--train-csv`로 학습하면 실데이터 기준 F1을 낼 수 있다. | 유재민 |
| 우회 규칙 정리 | 복구 시 차단 규칙만 지우고 우회 규칙(Priority 20)은 `idle_timeout` 30초로 사라지기를 기다린다. 정상 트래픽이 계속 흐르면 우회로에 남는다. | 박시현 |
| 환경 | OVS 유저스페이스 데이터패스(클라우드 컨테이너)에서 측정. VM에서도 같은 명령으로 재현 가능하다. | 공통 |

## 6. 재현 방법

```bash
# 1) Redis, Ryu 컨트롤러 (docker compose 또는 직접 실행), 관제탑 백엔드
docker compose up -d redis-broker ryu-controller
SDN_MOCK=0 uv run uvicorn api.main:app --port 8000 &
# 2) AI 추론 워커 (모델 파일이 없으면 합성 데이터로 학습 후 저장)
uv run python -m model.inference_worker --model model/isolation_forest.joblib --log events.jsonl &
# 3) 시나리오 (root, Mininet이 설치된 python3)
sudo python3 -m harness.verification.e2e_scenario --before 25 --attack 20 --after 35 --userspace --out run.json
# 4) 분석
uv run python -m harness.verification.e2e_scenario --analyze run.json --events events.jsonl
```
