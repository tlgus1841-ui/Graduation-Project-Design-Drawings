# 졸업작품 기획서: SDN 기반 분산 트래픽 이상 탐지 및 자동 라우팅 관제 시스템

## 1. 프로젝트 개요 (Overview)

### 1.1 프로젝트 명
- **국문:** SDN 기반 분산 트래픽 이상 탐지 및 자동 라우팅 웹 관제 시스템
- **영문:** SDN-based Distributed Traffic Anomaly Detection and Autonomous Rerouting Web Monitoring System

### 1.2 기획 배경 및 필요성
- **전통적 네트워크의 한계:** 기존 하드웨어 중심 네트워크는 트래픽 폭주, DDoS 공격, 비인가 트래픽 유입 등 비정상 상황 발생 시 실시간 대응과 유연한 경로 재설정에 구조적 한계가 존재함.
- **SDN(소프트웨어 정의 네트워킹) 도입:** 제어 평면(Control Plane)과 데이터 평면(Data Plane)을 분리하여 중앙 집중식 네트워크 프로그래밍을 가능하게 함으로써 즉각적인 플로우 제어(Flow Control)를 구현.
- **경량 AI 기반 계층형 이상 탐지:** 스위치 단위 부하를 최소화하기 위해 '포트 단위 통계(1차 이상 감지) → 세부 플로우/인그레스 포트 단위 통계(2차 정밀 분석)' 구조를 채택하여 실시간 탐지 효율성 극대화.
- **시각적 웹 관제탑(Control Tower):** 텍스트/터미널 기반의 디버깅을 탈피하여, 토폴로지 변화, 트래픽 유입량, 자동 우회 경로 활성화 상황을 웹 대시보드로 실시간 시각화하여 운영 편의성과 시연성을 극대화함.

### 1.3 핵심 목표
1. **가상 토폴로지 구축:** Mininet과 Open vSwitch(OVS)를 활용한 복합 네트워크 토폴로지 환경 구성.
2. **실시간 트래픽 분석 및 계층형 이상 탐지:** 포트/플로우 통계 2단계 감시 파이프라인 및 경량 머신러닝 기반 이상 트래픽 탐지.
3. **스푸핑 대응 자율 라우팅 제어:** IP 스푸핑 공격에 대비한 단독 인그레스 포트(In_port) 기반 차단 및 `OFPFC_MODIFY`를 통한 안전한 우회 경로 전환.
4. **웹 기반 실시간 통합 관제탑:** WebSocket을 통한 실시간 토폴로지 렌더링, 트래픽 차트 모니터링, 이벤트 알림 및 수동 제어 기능 제공.

---

## 2. 시스템 아키텍처 (System Architecture)

```
+-------------------------------------------------------------------------+
|                         웹 관제탑 (Frontend: React)                     |
|   - 인터랙티브 토폴로지 맵 (vis-network)                                  |
|   - 실시간 트래픽/메트릭 대시보드 (Chart.js / ApexCharts)                 |
|   - 경보 타임라인 & 수동 플로우/포트 제어 패널                            |
+-------------------------------------------------------------------------+
                                    ▲ WebSocket / REST API
                                    ▼
+-------------------------------------------------------------------------+
|                         웹 백엔드 (FastAPI)                             |
|   - 비동기 ASGI 서버 (Asyncio 기반 고속 스트리밍)                       |
|   - 웹 클라이언트 대상 WebSocket 브로드캐스터                           |
+-------------------------------------------------------------------------+
                                    ▲ IPC (Redis Pub/Sub)
                                    ▼
+-------------------------------------------------------------------------+
| SDN 제어 평면 (Docker: Python 3.8 / Ryu Controller, --net=host 모드)    |
|   - 동적 라우팅 엔진 (Dijkstra 알고리즘 기반 우회 경로 계산)              |
|   - 2-Tier 모니터링: 포트 통계(주기 2초) → 이상 시 In_port/Flow 분석     |
|   - 플로우 관리 엔진: OFPFC_MODIFY, In_port Drop, 타임아웃 라이프사이클   |
|   - LLDP 기반 네트워크 토폴로지 자동 탐색 및 루프 방지                  |
+-------------------------------------------------------------------------+
            ▲ Port/Flow Stats 수집           │ OpenFlow Rules (In_port Drop / Reroute)
            │                               ▼
+-----------------------+       +-----------------------------------------+
|   이상 탐지 엔진      |       |           데이터 평면 (Data Plane)       |
| - Isolation Forest    |<======| - Mininet 가상 네트워크 토폴로지 (Ubuntu) |
| - 실시간 피처 추출기  |       | - Open vSwitch (OVS) 스위치군           |
| - 백그라운드 추론 워커|       | - 가상 호스트 및 트래픽 발생기 (Scapy)  |
+-----------------------+       +-----------------------------------------+
```

---

## 3. 상세 기능 명세 (Key Features)

### 3.1 2-Tier 계층형 모니터링 및 이상 탐지
- **1차 모니터링 (포트 레벨):** 스위치 포트 통계(`OFPPortStatsRequest`)를 주기적(2초)으로 폴링하여 링크 대역폭 급증 감지 (컨트롤러 부하 최소화).
- **2차 모니터링 (진입 포트 및 플로우 레벨):** 특정 포트에서 이상 징후 감지 시 해당 스위치에 세부 플로우/인그레스 통계를 질의하여 이상 유입 경로 식별.
- **실시간 특징 추출 & 경량 추론:** PPS, BPS, Byte/Packet 등 파생 메트릭을 바탕으로 Isolation Forest 모델이 백그라운드 워커에서 이상치 스코어링.

### 3.2 IP 스푸핑 대응 및 동적 라우팅 정책
- **IP 스푸핑 무력화 방지 (In_port 격리):** Scapy 등의 무작위 Src IP 변조(DDoS) 공격 시, 개별 IP 매칭 대신 공격 트래픽이 유입되는 **진입 인그레스 포트(`in_port`)를 매칭 조건으로 지정하여 높은 우선순위(`Priority 100`) Drop 규칙 설치** (플로우 테이블 폭발 및 차단 우회 원천 차단).
- **정상 트래픽 동반 차단 방지 (Port Classification):** 스위치 간 트렁크(Trunk) 포트가 아닌 **단말 연결 단독 액세스(Access) 포트만 In_port Drop 대상**으로 지정하여 정상 통신 보호.
- **플로우 테이블 충돌 방지:** 단순 추가(`OFPFC_ADD`) 대신 기존 정상 경로 엔트리를 명시적으로 수정(`OFPFC_MODIFY`)하여 패킷 루프 및 유실 방지.
- **플로우 타임아웃 라이프사이클 관리:**
  - 우회 경로 플로우: `Idle Timeout = 10초`, `Hard Timeout = 30초`를 설정하여 공격 종료 시 기본 최단 경로로 자동 롤백.
  - 진입 포트 차단 플로우: `Idle Timeout = 15초`를 적용하여 공격 트래픽 소멸 시 포트 통신 자동 정상화.

### 3.3 웹 관제탑 (Monitoring Dashboard)
- **노드 및 링크 시각화:** 링크 및 포트 상태 색상 매핑 (정상: 녹색, 포트 혼잡: 황색, In_port 차단/우회: 적색/청색).
- **실시간 데이터 스트리밍:** WebSocket 기반 포트 트래픽 메트릭 및 이상치 스코어 타임라인 스트리밍.
- **이벤트 로그 타임라인:** 공격 감지, In_port 차단 규칙 주입, Flow Rule 수정 내역, 자가 복구(타임아웃 롤백) 트랜잭션 기록.
- **수동 비상 제어(Emergency Override):** 관리자 직접 특정 포트/호스트 강제 격리 버튼 제공.

---

## 4. 기술 스택 (Tech Stack)

| 구분 | 분류 | 기술/도구 | 선정 사유 |
|---|---|---|---|
| **가상화 & 인프라** | Host OS | **Ubuntu 22.04 LTS** | 안정적인 개발 환경 및 Mininet 패키지 네이티브 구동 |
| | Controller Env | **Docker (Python 3.8)** | Ryu 라이브러리의 Python 3.10+ 구형 의존성 빌드 오류 원천 차단 |
| | Network Driver | **Docker `--net=host`** | Mininet OVS와 컨테이너 간 포트 바인딩 및 네임스페이스 통신 실패 원천 방지 |
| | Network Emulator| **Mininet 2.3+** | 표준 가상 SDN 토폴로지 에뮬레이션 |
| | Virtual Switch | **Open vSwitch (OVS)** | OpenFlow 1.3 표준 준수 및 고속 가상 스위칭 |
| | Traffic Generator| **Scapy, Hping3, iPerf3** | Random IP Spoofing DDoS 및 정상 트래픽 모의 주입 |
| **제어 평면 (SDN)** | SDN Controller | **Ryu Controller (OF 1.3)** | 오픈플로우 프로그래밍 표준 컨트롤러 |
| | Topology Discovery| **LLDP / NetworkX** | 멀티패스 환경 내 루프 방지 및 Dijkstra 최단 경로 탐색 |
| **이상 탐지 (AI/ML)** | ML Framework | **Scikit-learn** | 경량 Isolation Forest 모델 추론 및 낮은 지연시간 보장 |
| | Feature Engineering| **Flow-Stats 파생 피처** | PPS, BPS, Byte/Packet 등 Ryu 측정 가능 5종 피처 정규화 |
| | Benchmark Dataset | **CIC-DDoS2019 (선별 피처)** | Ryu 측정 가능 컬럼만 추출/가공하여 사전 모델 학습 |
| **프로세스 연동 (IPC)**| Message Broker | **Redis Pub/Sub** | Ryu(Eventlet)와 FastAPI(Asyncio)의 비동기 충돌 방지 및 고속 큐잉 |
| **웹 백엔드** | Web Framework | **FastAPI (Python 3.10+)** | 비동기 WebSocket 서버 및 관제 REST API 구현 |
| **웹 프론트엔드** | UI Framework | **React (Vite) + Tailwind CSS**| 반응형 대시보드 컴포넌트 신속 구성 |
| | Topology Graph | **vis-network** | 네트워크 노드/엣지 상태 실시간 동적 렌더링 |
| | Live Chart | **ApexCharts (or Chart.js)** | 실시간 트래픽 유입량 스트리밍 차트 |

---

## 5. 단계별 개발 로드맵 (Development Roadmap)

1. **1단계: 인프라 및 컨테이너 환경 구축 (환경 격리 및 네트워크 공유)**
   - Ubuntu 22.04 호스트에 Mininet 설치
   - Python 3.8 기반 **Ryu Controller Docker 이미지 빌드**
   - 컨테이너 실행 시 **`--net=host` 모드**를 적용하여 호스트 Mininet OVS 스위치와 컨트롤러 간 로컬 루프백(`127.0.0.1:6653`) 통신 보장
   - 다중 우회 경로 가상 토폴로지 구성 및 LLDP + NetworkX 기반 루프 없는 기본 L2/L3 포워딩 로직 작성
   - **[주의사항 - 토폴로지 분리]:** 공격자 단말(H_att)과 정상 단말(H_legit)이 동일 포트를 공유하지 않도록 스위치의 물리 포트를 1:1로 분리 구성

2. **2단계: 트래픽 생성 및 2-Tier 메트릭 수집 파이프라인 구축**
   - Scapy를 활용해 정상 트래픽 및 Random IP Spoofing SYN Flooding 공격 생성 스크립트 작성
   - Ryu에서 주기적(2초) **`OFPPortStatsRequest`** 수집 파이프라인 구축 (링크 대역폭 모니터링)
   - 포트 임계치 초과 시 이상 유입 진입 포트(In_port) 및 세부 통계(PPS, BPS)를 추출하는 2단계 모니터링 로직 구현
   - Ryu 이벤트 데이터를 FastAPI로 전달하기 위한 Redis Pub/Sub 파이프라인 연결
   - **[실무 구현 팁 - OVS 포트 번호 바인딩]:** Mininet 리눅스 인터페이스 번호와 OpenFlow 프로토콜상의 `ofport(port_no)`가 일치하지 않을 수 있으므로, Ryu의 `EventOFPStateChange` 및 `OFPPortDescStatsReply` 핸드셰이크 시점에 보고되는 `port_no` 매핑 딕셔너리를 관리 및 참조할 것.

3. **3단계: AI 이상 탐지 엔진 및 In_port 격리 기반 안전한 재라우팅 구현**
   - 선별된 피처 기반으로 학습된 Isolation Forest 경량 모델을 Ryu 백그라운드 스레드에 탑재
   - 이상 감지 시 대응:
     - **[주의사항 - 정상 트래픽 보호]:** 스위치 간 상호 연결 포트(Trunk Port)를 차단하지 않고, 공격 단말이 직접 물려 있는 **액세스 포트(`in_port`)만 타겟팅**하여 `Priority 100` Drop 플로우 설치 (`Idle Timeout = 15초`)
     - 영향받는 링크를 경유하던 정상 플로우는 `OFPFC_MODIFY`를 사용해 즉각 대체 링크로 우회(`Idle Timeout = 10초`)
   - **[실무 구현 팁 - 타임아웃 차등 설계]:** 안전한 장애 복구를 위해 `In_port Drop Timeout(15초)`을 `우회 플로우 Timeout(10초)`보다 길게 유지하여 공격 트래픽이 완전히 소멸한 후 기본 경로로 안전하게 복귀되도록 라이프사이클을 보장할 것.

4. **4단계: 독립 프로세스 기반 웹 관제탑 구축**
   - Redis Pub/Sub 메시지를 수신하여 브라우저로 중계하는 FastAPI 비동기 WebSocket 서버 구현
   - React + vis-network 기반 실시간 토폴로지 대시보드 제작 (정상: 녹색, 혼잡: 황색, In_port 차단/우회: 적색/청색)
   - 실시간 트래픽 속도(PPS/BPS) 시계열 차트 및 In_port 차단/우회/복구 이벤트 로그 타임라인 완성

5. **5단계: 종합 시연 시나리오 및 복구 검증**
   - **이상 탐지 & In_port 격리/우회:** 정상 통신 중 Scapy 랜덤 IP 스푸핑 공격 주입 → 1차 포트 혼잡 감지 → 2차 이상 탐지 엔진 동작 → 웹 경보 발생 및 링크 상태 갱신 → 진입 포트(`in_port`) Drop 규칙 설치 및 피해 링크 정상 트래픽 우회(`OFPFC_MODIFY`) 확인
   - **동반 차단 방지 검증:** 공격자 포트 차단 상태에서도 정상 단말 간 통신이 우회 경로를 통해 끊김 없이 유지되는지 확인
   - **무중단 자가 복구:** 모의 공격 종료 → Drop 규칙 및 우회 플로우의 Idle Timeout 만료 → 기본 최단 경로로 자동 원상 복귀 확인
