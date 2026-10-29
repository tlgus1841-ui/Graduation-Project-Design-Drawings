# 🛡️ Self-Defending SDN Tower
> **SDN 기반 분산 트래픽 이상 탐지 및 자율 라우팅 관제 시스템**  
> *Self-Defending SDN Tower: AI-driven SDN Traffic Anomaly Detection & Autonomous Rerouting Web Monitoring System*

![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.8(Ryu)-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109.2-009688?logo=fastapi)
![React](https://img.shields.io/badge/React-18.3.1-61DAFB?logo=react)
![OpenFlow](https://img.shields.io/badge/OpenFlow-1.3-orange)
![Redis](https://img.shields.io/badge/Redis-7.2-red?logo=redis)
![Tests](https://img.shields.io/badge/Tests-267%20Passed%20(100%25)-brightgreen)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

---

## 📌 1. 프로젝트 소개 (Overview)

**Self-Defending SDN Tower**는 소프트웨어 정의 네트워킹(**SDN**)과 **경량 머신러닝/통계적 이상 탐지 기술**을 융합한 차세대 자율 방어 네트워크 관제 플랫폼입니다.

기존 네트워크 보안 솔루션은 IP 스푸핑 공격 시 수많은 차단 룰을 스위치에 주입하여 **스위치 플로우 테이블 폭발(Exhaustion)**을 야기하거나, 공격 탐지 후에도 관리자의 수동 개입 전까지 서비스가 마비되는 한계를 가집니다.

본 시스템은 공격 유입 시 출발지 IP에 구애받지 않고 **공격 유입 물리 포트(`in_port`) 단일 격리**와 **선제적 다중 홉 우회 라우팅(Autonomous Rerouting)**을 밀리초(ms) 단위로 자율 집행하여, **"공격 중에도 정상 서비스 무중단(Zero Packet Loss)"**을 실현합니다.

---

## ⚡ 2. 핵심 성능 스펙 (Verified System Specs)

실제 분산 테스트베드(GCP VM / OVS 4-스위치 다이아몬드 토폴로지)에서 실측 검증된 정량적 스펙입니다:

| 성능 지표 | 실측 검증 수치 | 비고 |
| :--- | :--- :--- | :--- |
| **초고속 방어 반응 속도** | **1.4 ~ 2.5 ms** | 이상 경보 수신 후 In_port 격리 및 우회 플로우 설치 완료까지 |
| **정상 트래픽 가용성** | **손실률 0.0% (Zero Loss)** | 대규모 공격 중에도 정상 호스트 통신 무유실 유지 |
| **왕복 네트워크 지연시간 (RTT)** | **평균 0.07 ms** | 커널 레벨 Native OVS + netns 환경 실측 지연시간 |
| **극한 내구성 스트레스 실증** | **952k PPS (초당 95만 패킷)** | 952k PPS 폭격 시 서버 유출 0개, 총 **858만 개 패킷 완벽 차단** |
| **데이터 플레인 독립성** | **Mininet 100% 탈피** | 순수 커널 OVS 2.17 + Linux Network Namespace 기반 상용급 구축 |
| **이상 탐지 확정 시간** | **1.7 ~ 2.5 초** | 1초 주기 실시간 카운트 집계 엔진 기준 |
| **지원 공격 유형 분류** | **6종 정밀 분류** | SYN/UDP/ICMP Flood, Port Scan, Slow HTTP, 내부 확산 |
| **테스트 슈트 통과율** | **267 / 267 (100% Pass)** | API, 하네스, 모델, 컨트롤러, 벤치마크 전수 검증 |
| **관제탑 웹 대시보드 성능** | **60 FPS 무지연 렌더링** | vis-network 토폴로지 및 실시간 ApexCharts 시계열 렌더링 |

---

## 🏛️ 3. 시스템 아키텍처 (Architecture)

### 3.1 논리 계층 아키텍처
```
+-----------------------------------------------------------------------------------+
|                        [Layer 4: 웹 관제탑 (Frontend)]                            |
|  - React 18.3 (Vite) + Tailwind CSS + Lucide Icons                                |
|  - vis-network: 실시간 네트워크 토폴로지 시각화 (노드 상태, 링크 트래픽, 우회 활성화)  |
|  - ApexCharts: 실시간 BPP / PPS 시계열 차트 & 이상치 스코어 스트리밍               |
|  - Event Timeline: 실시간 보안 알림 피드 & 비상 수동 격리/복원 제어 패널           |
+-----------------------------------------------------------------------------------+
                                        ▲ WebSocket (실시간 브로드캐스팅)
                                        ▼ REST API (비상 수동 제어 / Relearn 승인)
+-----------------------------------------------------------------------------------+
|                        [Layer 3: 웹 관제 백엔드 (FastAPI)]                         |
|  - Python 3.10, FastAPI 0.109.2, Uvicorn 0.27.1                                   |
|  - Asyncio 기반 고속 WebSocket Hub (다중 클라이언트 세션 멀티캐스팅)               |
|  - Redis Bridge: 4채널 구독 (stats, alert, command, flowcount) → Pydantic 스키마 검증 |
|  - Manual Control: 비상 격리/복원 및 60초 자동 격리 지연(Hold) 안전 장치           |
+-----------------------------------------------------------------------------------+
                                        ▲▼ Redis 7.2 Pub/Sub (고속 IPC 버스)
+-----------------------------------------------------------------------------------+
|                        [Layer 2: AI 이상 탐지 및 분류 엔진]                       |
|  - Isolation Forest: 실시간 BPP, ΔPPS 기반 이상치 탐지                             |
|  - Criteria Engine: 1초 주기 실측 카운트 기반 6종 공격 정밀 분류 (학술 논문 출처 반영)|
|    (SYN/UDP/ICMP Flood, Port Scan, Slow HTTP, 내부 확산)                          |
|  - EwmaDetector & Contamination Tuning: Flash Crowd(정상 급증) 오탐 방지          |
+-----------------------------------------------------------------------------------+
                                        ▲ 텔레메트리 발행 / ▼ 플로우 제어 명령
+-----------------------------------------------------------------------------------+
|                        [Layer 1: SDN 컨트롤러 (Ryu 4.34)]                         |
|  - Docker (Python 3.8 격리), OpenFlow 1.3 표준                                    |
|  - NetworkX Dijkstra: S1-S2-S4(주 경로) ↔ S1-S3-S4(우회 경로) 선제적 프로비저닝   |
|  - FSM 상태머신: Normal → Under Attack → Mitigated → Restoring (플래핑 방지)      |
|  - Circuit Breaker: AI 장애 시 컨트롤러 보호 및 안전 모드 전환                    |
+-----------------------------------------------------------------------------------+
                                        ▲ OpenFlow 1.3
+-----------------------------------------------------------------------------------+
|                        [Layer 0: Data Plane (OVS 4-Switch Topo)]                  |
|  - 4-Switch Diamond Topology (S1: Ingress, S2: Primary, S3: Bypass, S4: Egress)   |
|  - Host: H_legit (10.0.0.1), H_attacker (10.0.0.2), H_server (10.0.0.4)           |
+-----------------------------------------------------------------------------------+
```

### 3.2 4-스위치 다이아몬드 토폴로지
```text
                  +---------------+
                  |  S2 (Primary) |
             +--->|  DPID: 2      |---+
             |    +---------------+   |
             |                        |
             | (port 3)               | (port 2)
     +---------------+          +---------------+
     |  S1 (Ingress) |          |  S4 (Egress)  |
     |  DPID: 1      |          |  DPID: 4      |
     +---------------+          +---------------+
       | (p1)   | (p2)            | (p1)
       |        |                 |
     H_legit  H_attacker        H_server
     (10.0.0.1)(10.0.0.2)       (10.0.0.4)
       | (port 4)               | (port 3)
       |                        |
       |    +---------------+   |
       +--->|  S3 (Bypass)  |---+
            |  DPID: 3      |
            +---------------+
```

---

## 🛠️ 4. 기술 스택 및 확정 버전 (Golden Version Matrix)

| 계층 | 컴포넌트 | 확정 버전 | 실행 환경 | 주요 역할 |
|:---|:---|:---|:---|:---|
| **OS** | **Ubuntu Linux** | **22.04 LTS** | Native / GCP VM | 시스템 기본 운영체제 |
| **Data Plane** | **Open vSwitch (OVS)** | **2.17.x** | Host Native | OpenFlow 1.3 가상 스위칭 데이터 플레인 |
| **Control Plane** | **Ryu Controller** | **4.34** | Docker (`python:3.8-slim`) | OpenFlow 1.3 제어 및 선제적 Dijkstra 우회 라우팅 |
| **IPC Bus** | **Redis** | **7.2-alpine** | Docker 컨테이너 | Ryu-AI-FastAPI 간 4채널 고속 메시지 브로커 |
| **AI / Model** | **Scikit-learn** | **1.3.2** | Python 3.10 (Host venv) | Isolation Forest 이상 탐지 및 Criteria 분류 엔진 |
| | **Scapy** | **2.5.0** | Python 3.10 | 공격/정상 트래픽 모의 주입 및 패킷 분석 |
| **Web Backend**| **FastAPI** | **0.109.2** | Python 3.10 | 비동기 WebSocket Hub 및 REST 관제 API |
| | **Uvicorn** | **0.27.1** | Python 3.10 | 고성능 비동기 ASGI 서버 |
| | **Pydantic** | **2.6.1** | Python 3.10 | IPC 메시지 계약(Contracts) 검증 및 직렬화 |
| **Web Frontend**| **React** | **18.3.1** | Node.js 20 LTS (Vite) | 관제탑 SPA 프론트엔드 |
| | **vis-network** | **9.1.13** | npm | 동적 네트워크 토폴로지 실시간 렌더링 |
| | **ApexCharts** | **3.54.1** | npm | BPP / PPS 시계열 트래픽 모니터링 차트 |
| | **Tailwind CSS**| **3.4.19** | npm | 반응형 관제탑 다크 테마 스타일링 |

---

## 📂 5. 프로젝트 디렉토리 구조

```text
Self_Defending_SDN_Tower/
├── docker-compose.yml                     # Redis 7.2 및 Ryu 4.34 컨테이너 오케스트레이션
├── pyproject.toml                         # Python 3.10 (uv) 의존성 및 린트/테스트 설정
├── .cursorrules                           # AI 에이전트 개발 수칙 인덱스 및 핵심 수칙
│
├── rules/                                 # 🤖 AI 에이전트 개발 규칙 (환경, 아키텍처, 계약, 품질)
│
├── docs/                                  # 6대 핵심 기술 및 프로젝트 문서
│   ├── thesis/                            # 🎓 학사 졸업논문 원고 (thesis_draft.md)
│   ├── manual/                            # 🖥️ 관제탑 시스템 운영자 매뉴얼 (operator_manual.md)
│   ├── specs/                             # 🔍 6종 공격 판단 기준, 방어 시나리오, IPC 통신 규격
│   ├── verification/                      # ✅ 952k 극한 테스트 실측 검증 보고서 및 데이터셋 (data/)
│   ├── presentation/                      # 📊 최종 발표 슬라이드, 데모 런북, PPT 프롬프트
│   └── planning/                          # 📐 종합 로드맵 (ROADMAP.md), 개발 계획서, 프로젝트 기획서
│
├── api/                                   # FastAPI 관제탑 백엔드 (REST / WebSocket / Redis Bridge)
├── ui/                                    # React 18 + Vite 관제탑 웹 대시보드
├── harness/                               # IPC 계약 스키마(contracts/), 안전 가드레일(safety/)
├── ryu/                                   # Ryu 4.34 컨트롤러 앱 및 Dijkstra 우회 엔진
├── topo/                                  # 4-스위치 다이아몬드 토폴로지 (diamond_topo.py)
├── pipeline/                              # 실시간 피처 추출기 및 CSV 로거
├── model/                                 # Isolation Forest 탐지 모델 및 Criteria 분류 엔진
├── traffic/                               # Scapy 정상/공격 트래픽 생성기 (flood, scan, slowhttp, spread)
├── scripts/                               # E2E 시나리오 데모 러너 및 제어 스크립트
└── tests/                                 # 267개 단위/통합/벤치마크 테스트 스위트
```

---

## 📚 6. 주요 문서 바로가기

* 🎓 **최종 학술 논문 초안:** [`docs/thesis/thesis_draft.md`](docs/thesis/thesis_draft.md)
* 🖥️ **관제탑 사용자 매뉴얼:** [`docs/manual/operator_manual.md`](docs/manual/operator_manual.md)
* 🔍 **6종 공격 판단 기준 명세서:** [`docs/specs/attack_criteria.md`](docs/specs/attack_criteria.md)
* 🛡️ **4단계 자율 방어 시나리오 명세서:** [`docs/specs/defense_scenarios.md`](docs/specs/defense_scenarios.md)
* 📡 **컴포넌트 간 IPC 통신 계약 규격:** [`docs/specs/contract_first_ipc_guide.md`](docs/specs/contract_first_ipc_guide.md)
* ✅ **952k PPS 극한 스트레스 실증 보고서:** [`docs/verification/week16_stress_limit_test_report.md`](docs/verification/week16_stress_limit_test_report.md)
* 📊 **발표 슬라이드 아웃라인 & 시연 런북:** [`docs/presentation/ppt_slide_deck_outline.md`](docs/presentation/ppt_slide_deck_outline.md)
* 📋 **종합 로드맵 (ROADMAP):** [`docs/planning/ROADMAP.md`](docs/planning/ROADMAP.md)
* 🚀 **순수 OVS 단독 구동 전환 계획서:** [`docs/planning/native_ovs_transition_plan.md`](docs/planning/native_ovs_transition_plan.md)

---

## 🚀 7. 빠른 시작 (Getting Started)

### 7.1 환경 준비
* **Python**: 3.10+ 및 패키지 관리자 `uv` 권장
* **Node.js**: 20 LTS 이상 (UI 구동용)
* **Docker & Docker Compose**: Ryu 컨트롤러 및 Redis 브로커 구동용

### 7.2 설치 및 테스트
```bash
# 1. 저장소 클론
git clone https://github.com/tlgus1841-ui/Graduation-Project-Design-Drawings.git
cd Graduation-Project-Design-Drawings

# 2. Python 가상환경 및 의존성 동기화
uv sync

# 3. 전체 테스트 스위트 실행 (267개 전수 통과 확인)
uv run pytest -v
```

### 7.3 관제탑 백엔드 & UI 실행
```bash
# 터미널 1: 관제탑 백엔드 실행 (Mock 모드: 4단계 시나리오 텔레메트리 자동 송출)
uv run uvicorn api.main:app --reload --port 8000
# → REST API: http://localhost:8000/api/health
# → WebSocket: ws://localhost:8000/ws

# 터미널 2: 관제탑 UI 대시보드 실행
cd ui
npm install
npm run dev
# → 브라우저 접속: http://localhost:5173
```

### 7.4 실제 SDN 컨트롤러 & Redis 연동 (Live 모드)
```bash
# 1. Redis 브로커 및 Ryu 컨트롤러 기동
docker compose up -d redis-broker ryu-controller

# 2. 백엔드를 Live 모드로 실행
SDN_MOCK=0 REDIS_URL=redis://localhost:6379/0 uv run uvicorn api.main:app --port 8000

# 3. AI 이상 탐지 워커 실행
uv run python -m model.inference_worker --model model/isolation_forest.joblib
```

### 7.5 [Phase 6-A] 순수 커널 OVS 단독 구동 (Mininet 완전 탈피)
```bash
# 1. 4-스위치 다이아몬드 토폴로지 기동 (root 권한 필요)
sudo ./scripts/setup_native_ovs.sh

# 2. 정상 사용자 배경 Ping 실행 (손실률 관측)
sudo ip netns exec ns_legit ping -i 0.5 10.0.0.4

# 3. 원클릭 트래픽 주입 (SYN, Port Scan, UDP, ICMP, Slow HTTP, Lateral Spread 등)
sudo ./scripts/native_attack.sh syn 10 500       # 10초간 500 PPS SYN Flood
sudo ./scripts/native_attack.sh scan 5 200       # 5초간 200 PPS Port Scan
sudo ./scripts/native_attack.sh udp 10 400       # 10초간 400 PPS UDP Flood

# 4. 원격 클라우드 VM 제어 (GCP VM 원클릭 연동)
./scripts/vm_demo_controller.sh status           # 전체 컴포넌트 상태 일괄 점검
./scripts/vm_demo_controller.sh attack syn 10 500 # 원격 VM에 공격 주입
./scripts/vm_demo_controller.sh ping-status      # 정상 Ping 손실률 확인

# 5. 토폴로지 클린업
sudo ./scripts/teardown_native_ovs.sh
```

---

## 👥 8. 팀 역할 분담

| 역할 | 담당자 | 주요 기여 내용 |
|:---:|:---:|:---|
| **Tech Lead** | **박시현** | • SDN 데이터 플레인 및 테스트 하네스 아키텍처 총괄 설계<br>• Ryu OpenFlow 1.3 코어 컨트롤러 및 Dijkstra 우회 라우팅 구현<br>• 시스템 간 IPC 스키마 동결 및 전체 회귀 테스트 체계 구축 |
| **Domain Dev & QA** | **유재민** | • Isolation Forest 이상 탐지 및 6종 공격 Criteria 분류 엔진 구현<br>• Scapy 기반 현실적 모의 패킷 발생기(Flood, Scan, Slow HTTP, Spread) 제작<br>• 952k PPS 극한 벤치마크 수행 및 정량 검증 데이터셋 추출 |
| **PM & Tech Writer** | **김관우** | • React 관제탑 대시보드(vis-network, ApexCharts) 및 FastAPI 백엔드 구현<br>• 4단계 자율 방어 정책 시나리오 기획 및 프로젝트 마일스톤 관리<br>• 최종 학술 논문(`thesis_draft.md`) 및 발표 자료 제작 총괄 |
