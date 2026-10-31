# 🛡️ Self-Defending SDN Tower
> **SDN 기반 분산 트래픽 이상 탐지 및 자율 라우팅 관제 시스템**  
> *Self-Defending SDN Tower: AI-driven SDN Traffic Anomaly Detection & Autonomous Rerouting Web Monitoring System*

![CI](https://github.com/tlgus1841-ui/Graduation-Project-Design-Drawings/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.8(Ryu)-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109.2-009688?logo=fastapi)
![React](https://img.shields.io/badge/React-18.3.1-61DAFB?logo=react)
![OpenFlow](https://img.shields.io/badge/OpenFlow-1.3-orange)
![Redis](https://img.shields.io/badge/Redis-7.2-red?logo=redis)
![Tests](https://img.shields.io/badge/Tests-298%20Passed%20(100%25)-brightgreen)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

---

## 📌 1. 프로젝트 소개 (Overview)

**Self-Defending SDN Tower**는 소프트웨어 정의 네트워킹(**SDN**)과 **경량 머신러닝/통계적 이상 탐지 기술**을 융합한 차세대 자율 방어 네트워크 관제 플랫폼입니다.

기존 네트워크 보안 솔루션은 IP 스푸핑 공격 시 수많은 차단 룰을 스위치에 주입하여 **스위치 플로우 테이블 폭발(Exhaustion)**을 야기하거나, 공격 탐지 후에도 관리자의 수동 개입 전까지 서비스가 마비되는 한계를 가집니다.

본 시스템은 공격 유입 시 출발지 IP에 구애받지 않고 **공격 유입 물리 포트(`in_port`) 단일 격리**와 **선제적 다중 홉 우회 라우팅(Autonomous Rerouting)**을 밀리초(ms) 단위로 자율 집행하여, **"공격 중에도 정상 서비스 무중단(Zero Packet Loss)"**을 실현합니다.

나아가 **엔터프라이즈 8-스위치 5-구역(백본, 사용자망, 서버망, 관리망, 격리망) 제로트러스트 마이크로 세그멘테이션**과 감염 단말 대상 **L4 안전 패치 다운로드 채널**을 구축하여 국정원 국가사이버안보센터 N²SF 기준에 부합하는 종합 자율 관제 플랫폼으로 고도화되었습니다.

---

## ⚡ 2. 핵심 성능 스펙 (Verified System Specs)

실제 분산 테스트베드(GCP VM `34.50.17.220` / OVS 8-스위치 5-구역 엔터프라이즈 토폴로지)에서 실측 검증된 정량적 스펙입니다:

| 성능 지표 | 실측 검증 수치 | 비고 |
| :--- | :--- :--- | :--- |
| **초고속 방어 반응 속도** | **1.4 ~ 2.5 ms** | 이상 경보 수신 후 In_port 격리 및 우회 플로우 설치 완료까지 |
| **정상 트래픽 가용성** | **손실률 0.0% (Zero Loss)** | 대규모 공격 중에도 정상 호스트 통신 무유실 유지 |
| **왕복 네트워크 지연시간 (RTT)** | **평균 0.07 ms** | 커널 레벨 Native OVS + netns 환경 실측 지연시간 |
| **동적 제로트러스트 망 분리** | **4-Table 파이프라인** | Table 0(카운트) ➔ Table 1(망정책) ➔ Table 2(미터링) ➔ Table 3(포워딩) |
| **단말 단위 동적 격리 & 치료** | **L4 안전 치료 채널** | 침해 단말 QUARANTINE 즉각 강등 및 관리 패치서버(10.0.0.253:80) 연동 |
| **대규모 엔터프라이즈 확장** | **8-Switch 5-Zone** | 백본 S1·S2, 사용자 S3·S4, 서버 S5·S6, 관리 S7, 격리 S8 (11개 호스트) |
| **극한 내구성 스트레스 실증** | **952k PPS (초당 95만 패킷)** | 952k PPS 폭격 시 서버 유출 0개, 총 **858만 개 패킷 완벽 차단** |
| **데이터 플레인 독립성** | **Mininet 100% 탈피** | 순수 커널 OVS 2.17 + Linux Network Namespace 기반 상용급 구축 |
| **이상 탐지 확정 시간** | **1.7 ~ 2.5 초** | 1초 주기 실시간 카운트 집계 엔진 기준 |
| **지원 공격 유형 분류** | **6종 정밀 분류** | SYN/UDP/ICMP Flood, Port Scan, Slow HTTP, 내부 확산 |
| **테스트 슈트 통과율** | **298 / 298 (100% Pass)** | API, 하네스, 모델, 컨트롤러, 망분리, UI 전수 검증 |
| **관제탑 웹 대시보드 성능** | **60 FPS 무지연 렌더링** | 1600px 와이드스크린, 5대 존 핀 고정, 1-Hop Focus & Dimming, 텔레메트리 카드 그리드 |

---

## 🏛️ 3. 시스템 아키텍처 (Architecture)

### 3.1 논리 계층 아키텍처
```
+-----------------------------------------------------------------------------------+
|                        [Layer 4: 웹 관제탑 (Frontend)]                            |
|  - React 18.3 (Vite) + Tailwind CSS + Lucide Icons + Nginx 1.25 Alpine            |
|  - vis-network 9.1: 1600px 와이드스크린, 5-Zone 캔버스 클러스터링, 노드 핀 고정,      |
|    1-Hop Focus & Dimming, 계층형 뷰 토글, 동적 L4 치료선                          |
|  - ApexCharts 3.54: 실시간 BPP / PPS 시계열 차트 & 이상치 스코어 스트리밍          |
|  - Event Timeline: 실시간 보안 알림 피드 & 비상 수동 격리/복원 제어 패널           |
|  - PortStatsPanel: 5대 보안 존 필터 탭, 반응형 6열 미니 텔레메트리 카드 그리드 & 상세 토글|
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
|  - Docker (Python 3.8 격리), OpenFlow 1.3 표준 4-테이블 파이프라인                 |
|    (Table 0: Counting ➔ Table 1: Policy ➔ Table 2: Police ➔ Table 3: Forwarding) |
|  - NetworkX Dijkstra: Core S1-S2 백본 & 엣지 스위치 간 선제적 자율 우회 프로비저닝   |
|  - FSM 상태머신: Normal → Under Attack → Mitigated → Restoring (플래핑 방지)      |
|  - Circuit Breaker & Whitelist Guard: AI 장애 보호 및 서버/관리망 영구 보호        |
+-----------------------------------------------------------------------------------+
                                        ▲ OpenFlow 1.3
+-----------------------------------------------------------------------------------+
|                        [Layer 0: Data Plane (Native Linux OVS)]                   |
|  - Enterprise 8-Switch 5-Zone Topology (S1~S8, Host 11대, 물리 패치서버 1대)        |
|    (Core S1·S2, User S3·S4, Server S5·S6, Admin S7, Quarantine S8) - 단일 표준망 전환|
+-----------------------------------------------------------------------------------+
```

### 3.2 엔터프라이즈 8-스위치 5-구역 토폴로지 (Enterprise 8-Switch 5-Zone)
```text
                   ================ [BACKBONE ZONE] ================
                   |                                               |
                   |      +---------------+   (Trunk)   +---------------+  |
                   |      |   S1 (Core 1) |<----------->|   S2 (Core 2) |  |
                   |      |   DPID: 1     |             |   DPID: 2     |  |
                   |      +---------------+             +---------------+  |
                   |        |     |     |                 |     |     |    |
                   =========|=====|=====|=================|=====|=====|=====
                            |     |     |                 |     |     |
         +------------------+     |     +-----------+     |     |     +------------------+
         |                        |                 |     |     |                        |
         v                        v                 v     v     v                        v
  [USER ZONE A]            [SERVER ZONE A]      [ADMIN ZONE]   [QUARANTINE ZONE]  [USER ZONE B]   [SERVER ZONE B]
+---------------+        +---------------+    +---------------+ +---------------+ +---------------+ +---------------+
|   S3 (User)   |        |  S5 (Server)  |    |   S7 (Admin)  | |S8 (Quarantine)| |   S4 (User)   | |  S6 (Server)  |
|   DPID: 3     |        |   DPID: 5     |    |   DPID: 7     | |   DPID: 8     | |   DPID: 4     | |   DPID: 6     |
+---------------+        +---------------+    +---------------+ +---------------+ +---------------+ +---------------+
  | (p1)   | (p2)          | (p1)   | (p2)      | (p1)   | (p2)   | (p1)            | (p1)   | (p2)   | (p1)   | (p2)
  |        |               |        |           |        |        |                 |        |        |        |
  h1       h2              h5       h6       h_admin  h_patch   h_sink              h3       h4       h7       h8
(10.0.0.1)(10.0.0.2)     (10.0.0.11)(10.0.0.12)(10.0.0.254)(10.0.0.253)(10.0.0.250) (10.0.0.3)(10.0.0.4)(10.0.0.21)(10.0.0.22)
[Legit]  [Attacker]      [Web]    [API]       [Admin]  [Patch]  [Sinkhole]        [Legit]  [Attacker][DB]     [Backup]
                                                        ^             |
                                                        |== L4 Safe ==|
                                                           (Port 80)
```

---

## 🛠️ 4. 기술 스택 및 확정 버전 (Golden Version Matrix)

| 계층 | 컴포넌트 | 확정 버전 | 실행 환경 | 주요 역할 |
|:---|:---|:---|:---|:---|
| **OS** | **Ubuntu Linux** | **22.04 LTS** | Native / GCP VM | 시스템 기본 운영체제 |
| **Data Plane** | **Open vSwitch (OVS)** | **2.17.x** | Host Native | OpenFlow 1.3 가상 스위칭 (엔터프라이즈 8-Switch 5-Zone 표준망) |
| **Control Plane** | **Ryu Controller** | **4.34** | Docker (`python:3.8-slim`) | OpenFlow 1.3 제어, 4단 테이블 파이프라인 및 선제적 Dijkstra 우회 라우팅 |
| **IPC Bus** | **Redis** | **7.2-alpine** | Docker 컨테이너 | Ryu-AI-FastAPI 간 4채널 고속 메시지 브로커 |
| **AI / Model** | **Scikit-learn** | **1.3.2** | Docker (`python:3.10-slim`) | Isolation Forest 이상 탐지 및 Criteria 분류 엔진 |
| | **Scapy** | **2.5.0** | Python 3.10 | 공격/정상 트래픽 모의 주입 및 패킷 분석 |
| **Web Backend**| **FastAPI** | **0.109.2** | Docker (`python:3.10-slim`) | 비동기 WebSocket Hub 및 REST 관제 API |
| | **Uvicorn** | **0.27.1** | Python 3.10 | 고성능 비동기 ASGI 서버 |
| | **Pydantic** | **2.6.1** | Python 3.10 | IPC 메시지 계약(Contracts) 검증 및 직렬화 |
| **Web Frontend**| **Nginx (Reverse Proxy)** | **1.25-alpine** | Docker 컨테이너 | 포트 80 단일 엔드포인트 SPA 서빙 및 API/WS 리버스 프록시 |
| | **React** | **18.3.1** | Multi-stage 빌드 | 관제탑 SPA 프론트엔드 (dist) |
| | **vis-network** | **9.1.13** | npm | 5대 보안 존 클러스터링 & 동적 네트워크 토폴로지 실시간 렌더링 |
| | **ApexCharts** | **3.54.1** | npm | BPP / PPS 시계열 트래픽 모니터링 차트 |
| | **Tailwind CSS**| **3.4.19** | npm | 반응형 관제탑 다크 테마 스타일링 |

---

## 📂 5. 프로젝트 디렉토리 구조

```text
Self_Defending_SDN_Tower/
├── docker-compose.yml                     # All-in-One 프로덕션 5대 서비스(Redis, Ryu, API, AI, UI Nginx) 오케스트레이션
├── pyproject.toml                         # Python 3.10 (uv) 의존성 및 린트/테스트 설정
├── .cursorrules                           # AI 에이전트 개발 수칙 인덱스 및 핵심 수칙
│
├── config/                                # 🌐 네트워크 토폴로지 및 보안 존 설정 SSOT
│   ├── topology.yaml                      # 8-Switch 5-Zone 엔터프라이즈 토폴로지 기본 설정
│   ├── topology_profiles.yaml             # 다이아몬드 4SW / 엔터프라이즈 8SW 듀얼 프로파일
│   └── zones.yaml                         # 5대 존 정의, L4 허용 규칙, Hard Whitelist 정책
│
├── rules/                                 # 🤖 AI 에이전트 개발 규칙 (환경, 아키텍처, 계약, 품질)
│
├── docs/                                  # 6대 핵심 기술 및 프로젝트 문서
│   ├── thesis/                            # 🎓 학사 졸업논문 원고 (thesis_draft.md)
│   ├── manual/                            # 🖥️ 관제탑 시스템 운영자 매뉴얼 (operator_manual.md)
│   ├── specs/                             # 🔍 6종 공격 판단 기준, 방어 시나리오, IPC 통신 규격
│   ├── verification/                      # ✅ 952k 극한 테스트 실측 검증 보고서 및 데이터셋 (data/)
│   ├── presentation/                      # 📊 최종 발표 슬라이드, 데모 런북, PPT 프롬프트
│   ├── planning/                          # 📐 종합 로드맵 (ROADMAP.md), 상세 구현 계획서(Phase 6-B ~ 6-C-2)
│   └── archive/                           # 📦 완료/아카이브된 초기 기획 및 전환 문서
│
├── api/                                   # FastAPI 관제탑 백엔드 (REST / WebSocket / Redis Bridge, Dockerfile.api)
├── ui/                                    # React 18 SPA + Nginx 1.25 Alpine 리버스 프록시 (Dockerfile.ui, nginx.conf)
├── harness/                               # IPC 계약 스키마(contracts/), 안전 가드레일(safety/), 토폴로지 로더(topology/)
├── ryu/                                   # Ryu 4.34 컨트롤러 앱 및 Dijkstra 우회 엔진
├── pipeline/                              # 실시간 피처 추출기 및 CSV 로거
├── model/                                 # Isolation Forest 탐지 모델, Criteria 분류 엔진 (Dockerfile.ai)
├── traffic/                               # Scapy 정상/공격 트래픽 생성기 (flood, scan, slowhttp, spread)
├── scripts/                               # Native OVS(setup_large_ovs.sh), 원클릭 경량 배포(deploy_remote.sh), VM 제어 도구
├── archive/                               # 📦 Mininet 레거시 다이아몬드 토폴로지 보관소
└── tests/                                 # 298개 단위/통합/벤치마크 테스트 스위트 (100% Pass)
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
* 🏢 **대규모 8-스위치 인프라 확장 계획서 (Phase 6-C):** [`docs/planning/phase_6c_detailed_plan.md`](docs/planning/phase_6c_detailed_plan.md)
* 🎨 **웹 관제탑 UI 전면 개편 계획서 (Phase 6-C-2):** [`docs/planning/phase_6c_2_detailed_plan.md`](docs/planning/phase_6c_2_detailed_plan.md)
* 🚀 **원클릭 경량 무중단 배포 파이프라인 계획서 (Phase 6-C-3):** [`docs/planning/phase_6c_3_detailed_plan.md`](docs/planning/phase_6c_3_detailed_plan.md)
* ⚙️ **8-스위치 운영 안정화 및 도구 정규화 계획서 (Phase 6-C-4):** [`docs/planning/phase_6c_4_detailed_plan.md`](docs/planning/phase_6c_4_detailed_plan.md)
* 🖥️ **웹 관제탑 가독성 & UI/UX 고도화 계획서 (Phase 6-C-5):** [`docs/planning/phase_6c_5_detailed_plan.md`](docs/planning/phase_6c_5_detailed_plan.md)

---

## 🚀 7. 빠른 시작 (Getting Started)

### 7.1 [권장] 원격 클라우드 VM 원클릭 경량 배포 (Phase 6-C-3 & 6-C-5)
로컬에서 개발 및 테스트를 완료한 자산을 GCP VM에 격리 필터(.deployignore)를 거쳐 **5초 만에 원클릭 무중단 배포**합니다.

```bash
# 원격 VM으로 경량 패키징 선별 동기화 ➔ 5대 컨테이너 자동 재빌드/기동 ➔ 헬스체크 검증
./scripts/deploy_remote.sh <원격_VM_외부IP>

# 실시간 관제 및 데모 시나리오 원격 실행
./scripts/vm_demo_controller.sh status <원격_VM_외부IP>
./scripts/vm_demo_controller.sh ping_start <원격_VM_외부IP>
./scripts/vm_demo_controller.sh attack_syn <원격_VM_외부IP>
```

### 7.2 로컬 Native 8-스위치 프로덕션 실행
Redis, Ryu 컨트롤러, FastAPI 백엔드, AI 워커, Nginx 프론트엔드까지 **단 한 번의 명령으로 전체 5대 컨테이너와 8-Switch 5-Zone 커널 OVS 토폴로지를 자동 기동**합니다.

```bash
# 1. 8-스위치 5-구역 Native OVS 토폴로지 및 물리 패치서버 기동 (root 권한 필요)
sudo ./scripts/setup_large_ovs.sh

# 2. 전체 서비스 컨테이너 일괄 빌드 및 기동
docker compose up -d --build

# 3. 상태 확인 (5대 컨테이너 Health & OVS 브릿지 연결 상태)
docker compose ps
curl -s http://localhost/api/health

# 4. 브라우저 접속
# → 웹 관제탑 UI (표준 포트 80): http://localhost  (외부 VM: http://<외부IP>/)
# → 하위 호환 포트: http://localhost:5173
# → 토폴로지 API: http://localhost/api/topology

# 5. 토폴로지 및 컨테이너 종료/정리
docker compose down
sudo ./scripts/cleanup_large_ovs.sh
```

### 7.3 개발 및 테스트 스위트 실행
```bash
# Python 가상환경 및 의존성 동기화
uv sync

# 298개 전체 테스트 스위트 실행 (100% Pass)
uv run pytest -v

# 백엔드 개발 실행 (Mock 모드)
uv run uvicorn api.main:app --reload --port 8000

# UI Vite 개발 서버 실행
cd ui && npm run dev
```

---

## 👥 8. 팀 역할 분담

| 역할 | 담당자 | 주요 기여 내용 |
|:---:|:---:|:---|
| **Tech Lead** | **박시현** | • SDN 데이터 플레인 및 테스트 하네스 아키텍처 총괄 설계<br>• Ryu OpenFlow 1.3 코어 컨트롤러 및 Dijkstra 우회 라우팅 구현<br>• 시스템 간 IPC 스키마 동결 및 전체 회귀 테스트 체계 구축 |
| **Domain Dev & QA** | **유재민** | • Isolation Forest 이상 탐지 및 6종 공격 Criteria 분류 엔진 구현<br>• Scapy 기반 현실적 모의 패킷 발생기(Flood, Scan, Slow HTTP, Spread) 제작<br>• 952k PPS 극한 벤치마크 수행 및 정량 검증 데이터셋 추출 |
| **PM & Tech Writer** | **김관우** | • React 관제탑 대시보드(vis-network, ApexCharts) 및 FastAPI 백엔드 구현<br>• 4단계 자율 방어 정책 시나리오 기획 및 프로젝트 마일스톤 관리<br>• 최종 학술 논문(`thesis_draft.md`) 및 발표 자료 제작 총괄 |
