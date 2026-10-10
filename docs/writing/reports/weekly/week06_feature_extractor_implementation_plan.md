# 📗 [Domain Dev & QA] 6주차 구현 계획서 — 실시간 5대 파생 피처 계산기 (`pipeline/feature_extractor.py`)
> **담당자:** 유재민 (22101498 / Domain Dev & QA)
> **해당 기간:** 6주차 (2026.10.05 ~ 2026.10.11)
> **상위 근거 문서:** [`schedule_and_milestones.md`](../../../planning/schedule_and_milestones.md), [`phase2_traffic_features_model.md`](../../../guides/dev_b_domain_qa/phase2_traffic_features_model.md), [`week06_telemetry_pipeline_implementation_plan.md`](week06_telemetry_pipeline_implementation_plan.md)(박시현, 선행 의존성)

---

## 1. 목적 및 배경

박시현의 `ryu/app/controller.py`가 2초 주기로 Redis `sdn:stats:port` 채널에 `PortStatsMessage`(SSOT, `harness/contracts/sdn_events.py`)를 발행한다. 6주차 목표는 이 누적 포트 통계를 구독해 **시간당 변화량(델타)** 기반의 5대 파생 피처를 실시간 계산하고, 추후 Isolation Forest 학습(7주차)에 쓸 라벨링된 CSV 데이터셋을 쌓는 것이다.

- **대상 파일:** `pipeline/feature_extractor.py`, `pipeline/csv_logger.py`
- **입력:** Redis `sdn:stats:port` 채널의 `PortStatsMessage` (dpid·port_no별 rx_packets/rx_bytes/rx_errors 누적값)
- **출력:** `dataset/traffic_data.csv` (피처 5종 + label)
- **후속 연계:** 7주차 `model.py`가 이 CSV로 Isolation Forest를 학습

## 2. 요구사항 정리 (DoD 기준)

| # | 요구사항 | 출처 |
|:---:|:---|:---|
| R1 | Redis `sdn:stats:port` 비동기 구독 | schedule_and_milestones.md 6주차 |
| R2 | 5대 파생 피처 계산: ΔPPS, ΔBPS, BPP, ERR_Rate, Duration | phase2 가이드 §3.2 공식 |
| R3 | 정상/공격 트래픽 레이블(0/1)과 함께 CSV 누적 기록 | phase2 가이드 6주차 DoD |
| R4 | 포트별 "직전 관측치 없음"·"카운터 리셋"·"중복 타임스탬프" 방어 | 신규 식별 (설계 중 발견) |
| R5 | Redis 연결 시 `socket_connect_timeout` 명시 — 5주차 통합 점검에서 확인된 `ryu/app/controller.py`의 블로킹 지연(실측 ~350초) 재발 방지 | 직전 턴 회귀 검증에서 발견한 버그의 재발 방지 |

## 3. 설계 개요

### 3.1 피처 공식 (phase2 가이드 그대로)
1. ΔPPS = (rx_packets_t − rx_packets_{t-1}) / Δt
2. ΔBPS = (rx_bytes_t − rx_bytes_{t-1}) / Δt × 8
3. BPP = (rx_bytes_t − rx_bytes_{t-1}) / (rx_packets_t − rx_packets_{t-1} + ε)
4. ERR_Rate = (rx_errors_t − rx_errors_{t-1}) / (rx_packets_t − rx_packets_{t-1} + ε)
5. Duration = duration_sec (스냅샷 값 그대로)

### 3.2 모듈 구조
```
pipeline/
├── feature_extractor.py
│   ├── FeatureExtractor                # 포트별 직전 관측치(dpid,port_no) 보관, update()로 델타 피처 산출
│   ├── subscribe()                     # Redis pubsub 구독 핸들 생성
│   ├── run(pubsub, out_path, label, max_messages=None)
│   └── main()                          # CLI(--host --port --out --label)
└── csv_logger.py
    └── log_features(path, features, label)   # 피처 리스트를 label과 함께 CSV append (헤더 자동 생성)
```

### 3.3 방어 로직 (R4)
- **최초 관측치:** 직전 스냅샷이 없는 포트는 델타를 낼 기준이 없으므로 피처를 내지 않고 스냅샷만 저장
- **카운터 리셋/롤백:** `rx_packets`나 `rx_bytes`가 직전보다 줄어들면(스위치 재시작 등) 해당 구간은 버리고 새 값을 기준점으로만 갱신
- **Δt ≤ 0:** 중복/역전된 타임스탬프는 스킵 (0 또는 음수로 나누기 방지)
- **ε(1e-6):** 패킷 수 델타가 0일 때 BPP/ERR_Rate 0-division 방지

### 3.4 테스트 전략 — 실제 소켓 금지
직전 턴에서 `ryu/app/controller.py`가 유닛 테스트 중 실제 Redis 소켓에 연결을 시도해 테스트 1건당 수십 초씩 블로킹되는 문제를 확인했다(13개 테스트 합산 345초). 같은 실수를 반복하지 않기 위해, 본 모듈의 테스트는 **반드시 `fakeredis`**(이미 팀 dev 의존성에 추가됨)로 pubsub을 모킹하고, 실제 `redis.Redis` 소켓 연결은 CLI(`main()`) 경로에만 남긴다.

## 4. 리스크 및 대응
| 리스크 | 대응 |
|:---|:---|
| 포트 통계 수집 주기가 2.0초로 불안정하면 ΔPPS 오차 발생 | 박시현에게 수집 주기 안정성 인계 (4주차 계획서에서도 동일하게 명시됨) |
| Redis 미기동 시 `main()`이 블로킹 | `socket_connect_timeout` 명시 + 연결 실패 시 즉시 에러 메시지 후 종료 (장애 "격리"가 아니라 "조기 실패"가 목표 — AI 워커는 Redis 없이는 할 일이 없으므로 무한 재시도보다 즉시 실패가 안전) |
| CSV 파일이 커지며 레이블이 섞일 위험 | 세션(정상 캡처 1회, 공격 캡처 1회)마다 `--label`을 CLI로 명시, 로거는 기존 파일에 append만 수행 |

## 5. 완료 기준 체크리스트 (DoD)
- [ ] `FeatureExtractor.update()` 5대 피처 공식 정확히 구현, 최초 관측치/카운터 리셋/Δt≤0 방어
- [ ] `csv_logger.log_features()` 헤더 자동 생성 + append, label 컬럼 포함
- [ ] `run()`이 fakeredis 기반 테스트에서 발행된 메시지를 받아 CSV에 정확히 기록
- [ ] 전체 회귀(`pytest`, `flake8`, `mypy`) 통과, 실제 소켓 연결 없이 완료
