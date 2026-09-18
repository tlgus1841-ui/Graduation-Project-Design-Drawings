# 📗 [Domain Dev & QA] Phase 2: 트래픽 생성기 & 피처 파이프라인 & AI 모델 가이드
> **담당자:** 유재민 (22101498 / Domain Dev & QA)  
> **해당 기간:** 4주차 ~ 7주차 (2026.09.21 ~ 2026.10.18)  
> **핵심 산출물:** `traffic/traffic_normal.py`, `traffic/traffic_attack.py`, `pipeline/feature_extractor.py`, `model/model.py`, `tests/harness/model_evaluator.py`  
> **선행 조건:** Phase 1 마일스톤(Python 3.10 `uv` 셋업, 계약 스키마 확정) 완료

---

## 1. Phase 2 개발 목표 및 완료 기준 (Definition of Done)

- [ ] **4주차 DoD:** Scapy 정상 트래픽 생성기(`traffic_normal.py`) 구현, Poisson 간격 HTTP GET/대용량 전송 모사, Wireshark 기준 TCP Checksum 무결성 100% 검증
- [ ] **5주차 DoD:** Scapy 랜덤 IP 변조 SYN Flooding 공격기(`traffic_attack.py`) 구현, 초당 1,000~5,000 PPS 주입 및 `del pkt[IP].chksum` 커널 재계산 적용
- [ ] **6주차 DoD:** Redis `sdn:stats:port`를 비동기 구독하여 5대 파생 피처($\Delta \text{PPS}$, $\Delta \text{BPS}$, $\text{BPP}$ 등)를 실시간 계산하는 `feature_extractor.py` 및 CSV 로거 완성
- [ ] **7주차 DoD:** Scikit-learn Isolation Forest 이상 탐지 모델(`model.py`) 학습 파이프라인 구축 및 단위 평가 하네스(`model_evaluator.py`) 통과

---

## 2. 주차별 작업 위치 및 파일 매트릭스

| 주차 | 대상 파일 경로 | 역할 및 설명 |
|:---:|:---|:---|
| **4주차** | `traffic/traffic_normal.py` | H_legit(10.0.0.1)에서 H_server(10.0.0.4)로 현실적 웹 트래픽/핑을 전송하는 Scapy 생성기 |
| **5주차** | `traffic/traffic_attack.py` | H_attacker(10.0.0.2)에서 임의 위조 IP로 SYN 패킷을 폭주시키는 고속 공격기 |
| **6주차** | `pipeline/feature_extractor.py` | Ryu 포트 누적 통계에서 델타값 및 패킷당 평균 바이트(BPP)를 계산하는 실시간 엔진 |
| **6주차** | `pipeline/logger.py` | 피처를 레이블(Normal=0, Attack=1)과 함께 `dataset/traffic_data.csv`로 저장하는 모듈 |
| **7주차** | `model/model.py` | Isolation Forest 학습 및 직렬화(`model.joblib`), 단일 샘플 이상치 스코어링 클래스 |
| **7주차** | `tests/harness/model_evaluator.py` | 모델의 추론 시간(<10ms)과 F1-Score를 측정하는 테스트 하네스 러너 |

---

## 3. 주차별 실전 바이브 코딩 5-Step 워크플로우

### [4주차] Scapy 정상 트래픽 생성기 (`traffic/traffic_normal.py`)

#### Step 1: 현실적 정상 패턴 모사 프롬프트
```markdown
당신은 Self-Defending SDN Tower의 AI/보안 엔지니어 유재민입니다.
Python 3.10, Scapy 2.5 환경에서 H_legit(10.0.0.1) 단말에서 구동될 `traffic/traffic_normal.py`를 작성해 주세요.

[요구사항]
1. 목적지: H_server (10.0.0.4, 포트 80 및 443)
2. 트래픽 패턴 혼합:
   - 패턴 A (70%): 일반 웹 서핑 모사 (HTTP GET 요청, 페이로드 500~1,000 바이트)
   - 패턴 B (20%): 대용량 파일 다운로드 (1,400 바이트 풀 사이즈 패킷 연속 전송)
   - 패턴 C (10%): 주기적 ICMP Ping (Echo Request, 64 바이트)
3. 발송 간격: 지수 분포(Poisson distribution) 또는 0.05~0.5초 사이의 무작위 딜레이
4. 무결성 보장:
   - 패킷 생성 후 전송 직전 `del pkt[IP].chksum`, `del pkt[TCP].chksum`을 호출하여 Linux 커널의 Checksum Offload가 올바르게 재계산되도록 강제할 것.
```

#### Step 2: 실행 명령어
```bash
# uv를 통해 루트 권한으로 실행 (Scapy Raw Socket 요구)
sudo uv run python traffic/traffic_normal.py
```

---

### [5주차] 무작위 IP 스푸핑 SYN Flooding 공격기 (`traffic/traffic_attack.py`)

#### Step 1: 초고속 SYN Flooding 생성기 프롬프트
```markdown
당신은 Self-Defending SDN Tower의 Domain Dev 유재민입니다.
H_attacker(10.0.0.2)에서 출발지 IP를 무작위 변조하여 H_server(10.0.0.4:80)로 초당 1,000~5,000개의 SYN 패킷을 폭주시키는 `traffic/traffic_attack.py`를 작성해 주세요.

[핵심 요구사항]
1. 출발지 IP 랜덤화: 1.0.0.0 ~ 223.255.255.255 범위에서 사설 IP 대역을 제외한 임의 IP 생성.
2. 출발지 포트 랜덤화: 1024 ~ 65535 임의 포트.
3. TCP Flags: "S" (SYN 플래그 고정).
4. 패킷 크기 특성: 페이로드가 없는 54~74 바이트의 극소형 패킷 (공격 탐지 BPP 피처의 핵심 단서).
5. 커널 체크섬 오프로드 에러 방지:
   - del p[IP].chksum 및 del p[TCP].chksum 필수 적용.
6. Scapy `send(..., verbose=False)` 또는 `sendpfast`로 고속 송출 지원.
```

---

### [6주차] 실시간 5대 SDN 파생 피처 계산기 (`pipeline/feature_extractor.py`)

#### 5대 표준 피처 산출 공식
1. **$\Delta \text{PPS}$ (초당 패킷 수):** $\frac{\text{rx\_packets}_t - \text{rx\_packets}_{t-1}}{\Delta t}$
2. **$\Delta \text{BPS}$ (초당 바이트 수):** $\frac{\text{rx\_bytes}_t - \text{rx\_bytes}_{t-1}}{\Delta t} \times 8$
3. **$\text{BPP}$ (패킷당 바이트 수 - 핵심 탐지 지표):** $\frac{\text{rx\_bytes}_t - \text{rx\_bytes}_{t-1}}{\text{rx\_packets}_t - \text{rx\_packets}_{t-1} + \epsilon}$
4. **$\text{ERR\_Rate}$ (에러 패킷 비율):** $\frac{\text{rx\_errors}_t - \text{rx\_errors}_{t-1}}{\text{rx\_packets}_t - \text{rx\_packets}_{t-1} + \epsilon}$
5. **$\text{Duration}$ (포트 활성 지속 시간):** $\text{duration\_sec}$

```bash
# 피처 추출 파이프라인 구동
uv run python pipeline/feature_extractor.py
```

---

### [7주차] Isolation Forest 비지도 이상 탐지 파이프라인 (`model/model.py`)

```markdown
당신은 Self-Defending SDN Tower의 AI 엔지니어 유재민입니다.
Scikit-learn 1.3.2 기반으로 실시간 SDN 피처를 입력받아 이상 유무를 판별하는 `model/model.py`를 작성해 주세요.

[요구사항]
1. 알고리즘: `IsolationForest(n_estimators=100, contamination=0.1, random_state=42, n_jobs=-1)`
2. 전처리: `StandardScaler`를 결합한 Pipeline 구성.
3. 입력 피처 5종: `['delta_pps', 'delta_bps', 'bpp', 'err_rate', 'duration_sec']`
4. 메서드:
   - `fit(csv_path)`: CSV 데이터셋으로 학습 후 `model/isolation_forest.joblib` 저장
   - `predict_single(feature_dict) -> (is_anomaly: bool, score: float)`: 단일 포트 통계에 대한 실시간 추론 (<5ms 완료 필수)
5. 이상치 판정: predict() 결과 -1이면 이상(True), 점수가 낮을수록 위험도 높음.
```

```bash
# 모델 벤치마크 및 추론 지연시간 검증 하네스 실행
uv run pytest tests/harness/test_model_evaluator.py -v
```

---

## 4. 치명적 함정 & 가드레일 (Gotchas)

1. **커널 Checksum 무효화로 인한 OVS 패킷 폐기:** Scapy로 IP를 조작할 때 체크섬 필드를 지우지 않으면, Linux 커널이 이전 체크섬을 그대로 사용하여 수신 스위치(OVS)나 커널 스택에서 패킷이 조용히 폐기됩니다. 반드시 `del pkt[IP].chksum`을 실행하십시오.
2. **CIC-DDoS2019 공개 데이터셋의 피처 불일치:** 공개 벤치마크 데이터셋의 Flow Duration, Fwd Packet Length Mean 등 80개 피처는 SDN 포트 통계에서 실시간으로 구할 수 없습니다. 반드시 본 가이드의 **5대 파생 피처**만을 사용해야 합니다.

---

## 5. 팀원 인계 사항 및 A4 주간 보고서 예시 문구

### 5.1 인계 사항
- **박시현 (Tech Lead):** 포트별 통계 수집 주기가 2.0초로 일정해야 $\Delta \text{PPS}$ 오차가 최소화됩니다.
- **김관우 (PM & Tech Writer):** 정상 트래픽 시 평균 BPP(700~1,200 Bytes) vs DDoS 공격 시 BPP(64 Bytes) 극명한 대비 그래프 데이터를 제공합니다.

### 5.2 A4 주간 보고서 기재 문구
> "Domain Dev & QA (유재민): Checksum 재계산 무결성을 갖춘 Scapy 정상 및 SYN Flood 공격기 구현 완료. 실시간 5대 파생 피처 계산 파이프라인 구축 및 Isolation Forest 모델 학습을 통한 단일 추론 4.2ms 달성 확인."
