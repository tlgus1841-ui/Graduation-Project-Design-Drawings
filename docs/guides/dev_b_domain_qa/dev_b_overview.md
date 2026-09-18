# 📗 [Domain Dev & QA] 유재민 엔지니어링 개요 및 데이터 품질 책임
> **성명:** 유재민 (22101498)  
> **직책:** Domain Dev & QA (AI/보안 엔지니어 & 품질 보증)  
> **책임 영역:** 트래픽 생성기(Scapy), 5대 SDN 실시간 파생 피처, Isolation Forest 탐지 모델, 벤치마크 및 정량 데이터셋 추출  
> **기준 문서:** `docs/planning/ai_harness_engineering_plan.md`, `docs/planning/schedule_and_milestones.md`

---

## 1. 역할 정의 및 데이터/보안 관리 권한

Domain Dev & QA는 현실적인 네트워크 공격을 모의하고, SDN 제어 평면 텔레메트리로부터 위협을 밀리초 단위로 식별하는 AI 모델 및 품질 보증(QA) 평가 하네스를 총괄합니다.

### 1.1 담당 소스코드 및 산출물 영역
- `traffic/`: Scapy 가변 정상 트래픽(`traffic_normal.py`), 무작위 IP 변조 SYN Flooding 공격기(`traffic_attack.py`)
- `pipeline/`: 실시간 5대 파생 피처 계산 모듈(`feature_extractor.py`), CSV 데이터셋 로거
- `model/`: Scikit-learn 경량 비지도 이상 탐지 엔진(`model.py`, `inference_worker.py`)
- `tests/harness/`: 모델 벤치마크 평가 하네스(`model_evaluator.py`), 지연시간 프로파일러(`latency_profiler.py`)
- `dataset/`: 훈련 및 평가용 정규화 CSV 데이터셋 및 혼동행렬/ROC 평가 리포트

### 1.2 핵심 개발 및 검증 책임
1. **패킷 무결성 보장:** Linux 커널 Checksum Offload 누락 방지 (`del pkt[IP].chksum`, `del pkt[TCP].chksum`).
2. **실시간 피처 엔지니어링:** 무거운 CIC-DDoS2019 대신 Ryu 포트 통계로부터 즉시 산출 가능한 5대 지표($\Delta \text{PPS}$, $\Delta \text{BPS}$, $\text{BPP}$ 등) 계산.
3. **경량 AI 추론성:** Isolation Forest 추론 지연시간 10ms 미만 유지, F1-Score 95% 이상 달성.
4. **정량적 벤치마크 데이터 추출:** 패킷 손실률(Loss Rate), E2E 지연시간, 오탐률(FPR) 데이터를 주차별로 김관우(PM)에게 전달.

---

## 2. 주차별 가이드 바로가기

* [Phase 1 (1~3주차): uv 환경 구축 및 피처 스펙 확립 (회고)](phase1_environment_setup.md)
* [Phase 2 (4~7주차): 트래픽 생성기, 5대 피처, Isolation Forest (당면 과제)](phase2_traffic_features_model.md)
* [Phase 3 (8주차): 모델 추론 레이턴시(<10ms) 및 1차 평가](phase3_midterm_evaluation.md)
* [Phase 4 (9~11주차): IP 스푸핑 방어 검증 및 무유실 벤치마크](phase4_spoofing_defense_benchmark.md)
* [Phase 5 & 6 (12~16주차): E2E 지연시간 프로파일링 및 최종 평가 데이터셋](phase5_6_latency_final_dataset.md)
