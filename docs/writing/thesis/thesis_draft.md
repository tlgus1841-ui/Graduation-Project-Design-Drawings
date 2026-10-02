# [학술 논문 초안] SDN 기반 분산 트래픽 이상 탐지 및 자율 라우팅 관제 시스템
## Self-Defending SDN Tower: Distributed Traffic Anomaly Detection and Autonomous Rerouting Web Monitoring System

**저자:** 박시현 (22101489), 유재민 (22101498), 김관우 (22102237)  
**지도교수:** [지도교수명]  
**소속:** 컴퓨터공학부 / 소프트웨어전공  
**제출일자:** 2026년 [ ]월 [ ]일  

---

### 초록 (Abstract)
현대 네트워크 인프라에서 발신지 IP 변조(IP Spoofing)를 동반한 분산 서비스 거부(DDoS) 공격은 기존 인라인 방화벽과 침입 방지 시스템(IPS)의 플로우 테이블 메모리 고갈을 유발하고, 관리자의 수동 개입에 의존하는 복구 체계로 인해 심각한 서비스 중단 시간을 초래한다. 본 논문에서는 소프트웨어 정의 네트워킹(SDN)의 중앙 집중식 제어력과 경량 머신러닝 이상 탐지 알고리즘을 결합한 자율 치유형 관제 시스템 'Self-Defending SDN Tower'를 제안하고 실증한다.  
제안하는 시스템은 (1) 스위치 포트 대역폭의 2-Tier 비동기 모니터링을 통해 컨트롤러 오버헤드를 최소화하고, (2) 실시간 5대 파생 피처 기반의 Isolation Forest 비지도 학습으로 밀리초 단위의 이상 트래픽을 탐지한다. (3) 탐지 즉시 가변적인 IP 대신 물리/가상 인그레스 포트(`in_port`) 기반의 정밀 격리 규칙을 주입하여 플로우 테이블 폭발을 방지하며, (4) 다중 경로 토폴로지 상에서 피해 링크의 정상 플로우를 Dijkstra 기반 대체 경로로 무유실(`Packet Loss 0%`) 우회 전환한다. 마지막으로 (5) 위협 소멸 시 FSM(상태 전이 머신) 타임아웃을 통해 최단 경로로 자가 복구하는 5단계 폐루프(Closed-Loop)를 달성한다. Mininet 가상 에뮬레이션 환경에서의 실험 결과, IP 스푸핑 공격 발생 후 [ ]초 이내에 자율 격리 및 우회가 완료되었으며 정상 트래픽의 연속성이 유지됨을 검증하였다.

**주제어(Keywords):** 소프트웨어 정의 네트워킹 (SDN), OpenFlow 1.3, 이상 트래픽 탐지, Isolation Forest, IP 스푸핑 방어, 자율 라우팅, 실시간 관제탑

---

## 1. 서론 (Introduction)
### 1.1 연구 배경 및 문제 제기
- 기존 하드웨어 네트워크의 한계 (정적 라우팅, 가시성 부재)
- IP 변조 공격에 대한 플로우 테이블 고갈 취약점
- Human-in-the-loop 수동 대응 지연

### 1.2 연구 목적 및 시스템 범위
- SDN 제어/데이터 평면 분리를 활용한 자율 폐루프(Closed-Loop) 제어
- 경량 AI 기반 실시간 초저지연 이상치 스코어링

---

## 2. 관련 연구 (Related Works)
> 💡 *참조 자료: `docs/study/01_` ~ `08_` 스터디 문서 및 RFC/학술 논문*
### 2.1 소프트웨어 정의 네트워킹 및 OpenFlow 프로토콜
### 2.2 SDN 환경에서의 DDoS 탐지 및 머신러닝 기법
### 2.3 기존 자가 치유(Self-Healing) 및 동적 우회 연구와의 차별성

---

## 3. 시스템 아키텍처 및 설계 (System Architecture)
> 💡 *참조 자료: `docs/planning/roadmap_v2.md`, `harness/contracts/sdn_events.py`*
### 3.1 전체 계층 구조 (Data Plane, Control Plane, AI Worker, Web Layer)
### 3.2 Contract-First 비동기 IPC 버스 설계 (Redis Pub/Sub & WebSocket Hub)
### 3.3 실시간 5대 파생 피처 엔지니어링 ($\Delta\text{PPS}, \Delta\text{BPS}, \text{BPP}, \dots$)

---

## 4. 자가 방어 및 자율 라우팅 메커니즘 (Defense & Self-Healing)
> 💡 *참조 자료: `docs/specs/defense_scenarios.md`*
### 4.1 경량 2-Tier 텔레메트리 파이프라인
### 4.2 In_port 기반 스푸핑 방어 및 Access/Trunk 포트 격리 가드레일
### 4.3 Dijkstra 최단 경로 동적 우회 라우팅
### 4.4 FSM 기반 플래핑(Flapping) 방지 및 안전 롤백 메커니즘

---

## 5. 구현 및 실험 환경 (Implementation & Experiments)
### 5.1 실험 환경 구성 (Mininet 다이아몬드 토폴로지, Docker Ryu, OVS 2.17)
### 5.2 모의 트래픽 주입 시나리오 (Scapy 정상 트래픽 vs Random IP SYN Flood)
### 5.3 성능 평가 지표 및 실험 결과
- 탐지 성능: F1-Score, 오탐률(FPR), 추론 지연시간(Latency)
- 인프라 연속성: 우회 시 패킷 손실률(Loss rate), RTT 지연 변화
- 자가 복구 반응 속도

---

## 6. 결론 및 향후 과제 (Conclusion & Future Work)
- 연구 성과 요약
- 한계점 및 향후 대규모 토폴로지 확장 방안

---

## 참고문헌 (References)
[1] McKeown, N., et al. "OpenFlow: enabling innovation in campus networks." ACM SIGCOMM CCR, 2008.  
[2] Liu, F. T., Ting, K. M., & Zhou, Z. H. "Isolation forest." IEEE ICDM, 2008.  
[3] Ryu SDN Controller Documentation (Release 4.34).  
