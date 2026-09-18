# 🛡️ Self-Defending SDN Tower 프로젝트 학습 가이드 (Master Study Guide)

> **프로젝트 공식 명칭:** SDN 기반 분산 트래픽 이상 탐지 및 자동 라우팅 관제 시스템  
> **프로젝트 영문 명칭:** SDN-based Distributed Traffic Anomaly Detection and Autonomous Rerouting Web Monitoring System  
> **문서 목적:** 본 프로젝트를 성공적으로 구현하기 위해 팀원들이 반드시 이해하고 습득해야 할 핵심 기초 이론, 기술 스택, 아키텍처 원리 및 실전 디버깅 지식을 체계적으로 정리한 종합 학습서입니다.

---

## 🧭 1. 프로젝트 전체 그림 한눈에 보기

### 1.1 해결하고자 하는 문제 (Why this project?)
전통적인 하드웨어 기반 네트워크(L2/L3 스위치, 라우터)는 다음과 같은 구조적 한계를 지닙니다:
1. **중앙 가시성 결여:** 트래픽 폭주나 공격 발생 시 네트워크 전체 상태를 한눈에 파악하기 어렵고, 장비마다 CLI로 개별 접속해 상태를 확인해야 합니다.
2. **IP 스푸핑(변조) DDoS 취약성:** 공격자가 발신지 IP(Source IP)를 무작위로 위조하여 패킷을 쏟아부을 때, 전통적인 방화벽/ACL 방식으로 공격 IP를 차단하면 플로우 테이블 메모리가 고갈(Flow Table Overflow)되거나 차단 정책이 무력화됩니다.
3. **경로 재설정의 지연:** 특정 링크가 마비되었을 때 패킷 루프 없이 정상 트래픽을 우회(Failover/Rerouting)시키는 데 수 초에서 수십 초가 소요됩니다.

### 1.2 우리의 해결 솔루션 (Self-Defending Architecture)
본 프로젝트는 **SDN(Software-Defined Networking)**과 **경량 머신러닝(Isolation Forest)**을 결합하여 이 문제를 해결합니다:
- **Control Plane & Data Plane 분리:** 중앙 컨트롤러(Ryu)가 가상 스위치(OVS)의 플로우 테이블을 중앙 집중식으로 프로그래밍합니다.
- **In_port 기반 IP 스푸핑 원천 무력화:** IP 주소가 수만 번 바뀌더라도, 공격 패킷이 유입되는 **스위치의 진입 물리/가상 포트(`in_port`)**를 식별하여 `Priority 100 Drop` 규칙을 주입함으로써 플로우 테이블 폭발을 방지합니다.
- **Dijkstra 기반 무유실 다중 홉 우회 라우팅:** 공격받는 링크를 경유하던 정상 트래픽을 대체 경로로 신속하게 우회시킵니다.
- **실시간 웹 관제탑(Control Tower):** WebSocket을 통해 네트워크 토폴로지, 실시간 트래픽(PPS/BPS), 보안 경보 및 수동 제어 인터페이스를 웹 브라우저에서 실시간으로 시각화합니다.

```
+-------------------------------------------------------------------------+
|                        웹 관제탑 (Frontend: React 18)                   |
|   - 인터랙티브 토폴로지 맵 (vis-network)                                  |
|   - 실시간 트래픽/메트릭 대시보드 (ApexCharts / Chart.js)                 |
|   - 실시간 보안 경보 타임라인 & 수동 포트 격리/복원 제어 패널             |
+-------------------------------------------------------------------------+
                                    ▲ WebSocket / REST API
                                    ▼
+-------------------------------------------------------------------------+
|                        웹 백엔드 (FastAPI / Python 3.10)                |
|   - 비동기 ASGI 서버 (WebSocket Hub - Stale Connection 방어)           |
|   - REST API 엔드포인트 & Pydantic v2 계약 스키마 검증                  |
+-------------------------------------------------------------------------+
                                    ▲ IPC (Redis Pub/Sub 7.2)
                                    ▼
+-------------------------------------------------------------------------+
|       SDN 제어 평면 (Docker: Python 3.8 / Ryu 4.34, --net=host 모드)    |
|   - Dijkstra 알고리즘 기반 동적 라우팅 엔진                             |
|   - 2-Tier 모니터링: 1차 포트 통계(주기 2초) → 2차 In_port/Flow 분석   |
|   - 플로우 라이프사이클 관리: In_port Drop, 우회 플로우 주입, FSM 복구 |
|   - LLDP 기반 네트워크 토폴로지 자동 탐색 및 루프 방지                  |
+-------------------------------------------------------------------------+
            ▲ Port/Flow Stats 수집           │ OpenFlow 1.3 Rules
            │                               ▼
+-----------------------+       +-----------------------------------------+
|  AI 이상 탐지 워커    |       |        데이터 평면 (Data Plane: Linux)   |
| (Python 3.10 독립실행)|       | - Mininet 2.3+ 가상 네트워크 토폴로지    |
| - Isolation Forest    |<======| - Open vSwitch (OVS 2.17.x) 스위치군    |
| - 5대 SDN 파생 피처   |       | - 가상 호스트군 (H_legit, H_attacker)   |
| - Redis Alert 송출    |       | - Scapy 정상/공격 트래픽 생성기         |
+-----------------------+       +-----------------------------------------+
```

---

## 📚 2. 학습 영역별 상세 커리큘럼 인덱스

본 스터디 폴더에는 영역별로 깊이 있게 공부할 수 있도록 세분화된 가이드가 마련되어 있습니다:

| 번호 | 문서 파일명 | 핵심 학습 주제 | 주요 타겟 |
|:---:|---|---|:---:|
| **01** | [`01_Network_and_SDN_Fundamentals.md`](./01_Network_and_SDN_Fundamentals.md) | 컴퓨터 네트워크 기초, OSI 7계층, SDN 개념, OpenFlow 1.3 프로토콜 | 전체 공통 |
| **02** | [`02_Mininet_and_OpenvSwitch.md`](./02_Mininet_and_OpenvSwitch.md) | Mininet 토폴로지 구축, Linux 네트워크 네임스페이스, OVS 스위치 및 CLI | 개발자 A, B |
| **03** | [`03_Ryu_SDN_Controller.md`](./03_Ryu_SDN_Controller.md) | Ryu 컨트롤러 구조, Eventlet 이벤트 루프, FlowMod 제어, Dijkstra 알고리즘 | 개발자 A |
| **04** | [`04_Network_Security_and_DDoS_Defense.md`](./04_Network_Security_and_DDoS_Defense.md) | SYN Flooding, IP Spoofing, Scapy 패킷 조작, In_port 차단 vs IP 차단 | 개발자 B |
| **05** | [`05_AI_Anomaly_Detection_and_Features.md`](./05_AI_Anomaly_Detection_and_Features.md) | 비지도 이상 탐지, Isolation Forest 원리, 5대 SDN 파생 피처, FSM 복구 | 개발자 B |
| **06** | [`06_Distributed_System_and_FastAPI.md`](./06_Distributed_System_and_FastAPI.md) | 분산 IPC(Redis Pub/Sub), FastAPI 비동기(Asyncio), WebSocket Hub | 개발자 C |
| **07** | [`07_Frontend_Visualization_React.md`](./07_Frontend_Visualization_React.md) | React 18, Vite, Tailwind CSS, vis-network 토폴로지 렌더링, ApexCharts | 개발자 C |
| **08** | [`08_Environment_and_Troubleshooting.md`](./08_Environment_and_Troubleshooting.md) | Docker `--net=host`, Linux 커널(`rp_filter`), uv 패키지 매니저, 치명적 함정 7가지 | 전체 공통 |

---

## 👥 3. 역할별 맞춤 학습 로드맵

### 🅰️ 개발자 A (SDN 인프라 & 제어 평면 엔지니어)
- **실무 가이드북:** [`week1_vibe_guide.md`](../guides/dev_a_sdn_infra/week1_vibe_guide.md)
- **주요 담당:** Mininet Diamond 토폴로지, Ryu OpenFlow 1.3 애플리케이션, L2/L3 스위칭 & 루프 방지, Dijkstra 동적 라우팅, Docker 배포
- **권장 학습 순서:**
  1. [`01_Network_and_SDN_Fundamentals.md`](./01_Network_and_SDN_Fundamentals.md): OpenFlow 1.3 메시지 규격(Packet-In, Flow-Mod, PortStats) 완벽 이해
  2. [`02_Mininet_and_OpenvSwitch.md`](./02_Mininet_and_OpenvSwitch.md): Mininet CLI 실습 및 OVS 플로우 덤프 분석
  3. [`03_Ryu_SDN_Controller.md`](./03_Ryu_SDN_Controller.md): Ryu 이벤트 핸들러 작성법, Table-Miss 플로우 엔트리, NetworkX 그래프 알고리즘
  4. [`08_Environment_and_Troubleshooting.md`](./08_Environment_and_Troubleshooting.md): Docker `--net=host` 모드의 이유, ARP Broadcast Storm 방지책 숙지

### 🅱️ 개발자 B (AI & 보안 데이터 파이프라인 엔지니어)
- **실무 가이드북:** [`week1_vibe_guide.md`](../guides/dev_b_ai_security/week1_vibe_guide.md)
- **주요 담당:** Scapy 트래픽 생성기(정상 트래픽, Random IP Spoofing SYN Flood), 5대 SDN 파생 피처 엔지니어링, Isolation Forest 모델 학습 및 추론, Redis 연동
- **권장 학습 순서:**
  1. [`01_Network_and_SDN_Fundamentals.md`](./01_Network_and_SDN_Fundamentals.md): TCP 3-way Handshake 및 IP/TCP 패킷 헤더 구조 이해
  2. [`04_Network_Security_and_DDoS_Defense.md`](./04_Network_Security_and_DDoS_Defense.md): Scapy 레이어 스택 조작법, Linux 커널 Checksum Offload 이슈, In_port 차단의 수학적/논리적 필요성
  3. [`05_AI_Anomaly_Detection_and_Features.md`](./05_AI_Anomaly_Detection_and_Features.md): Isolation Forest 동작 원리, 누적 카운터 기반 델타 피처($\Delta \text{PPS}, \Delta \text{BPS}, \text{BPP}$) 계산 공식
  4. [`06_Distributed_System_and_FastAPI.md`](./06_Distributed_System_and_FastAPI.md): Redis Pub/Sub 메시지 발행/구독 규격 이해

### 🅲 개발자 C (웹 관제탑 풀스택 엔지니어)
- **실무 가이드북:** [`week1_vibe_guide.md`](../guides/dev_c_web_control/week1_vibe_guide.md)
- **주요 담당:** FastAPI 비동기 백엔드 서버, WebSocket Hub 브로드캐스터, Mock 데이터 생성기, React 18 + vis-network 대시보드 UI
- **권장 학습 순서:**
  1. [`06_Distributed_System_and_FastAPI.md`](./06_Distributed_System_and_FastAPI.md): Python Asyncio 비동기 프로그래밍, WebSocket 생명주기 및 Stale Connection 방어, Pydantic v2 계약 스키마
  2. [`07_Frontend_Visualization_React.md`](./07_Frontend_Visualization_React.md): React 18 상태 관리, vis-network 노드/엣지 물리 시뮬레이션 제어, 실시간 ApexCharts 렌더링
  3. [`01_Network_and_SDN_Fundamentals.md`](./01_Network_and_SDN_Fundamentals.md): 네트워크 토폴로지 용어(Switch, Host, Port, Ingress, Egress, Link) 개념 습득
  4. [`08_Environment_and_Troubleshooting.md`](./08_Environment_and_Troubleshooting.md): 프로젝트 전체 디버깅 흐름 및 E2E 테스트 방법 숙지

---

## 💡 4. 프로젝트 성공을 위한 핵심 골든 룰 (Golden Rules)

1. **Python 버전 분리 철칙:**
   - **Ryu Controller:** 반드시 `python:3.8-slim` Docker 컨테이너에서 구동 (Python 3.10+에서 Ryu는 greenlet/collections 호환성 문제로 100% 빌드 실패).
   - **AI Worker & FastAPI 백엔드:** Ubuntu 22.04 네이티브인 Python 3.10 환경에서 구동.
2. **Ryu 내부에서 AI 추론 금지:**
   - Ryu의 `eventlet` 코루틴 내부에서 Scikit-learn의 무거운 CPU 연산을 실행하면 이벤트 루프가 멈춰 OVS 스위치 연결이 끊어집니다. 반드시 별도 AI Worker 프로세스로 분리하고 **Redis Pub/Sub**으로 통신합니다.
3. **IP 차단이 아닌 In_port 차단:**
   - IP Spoofing 공격은 패킷마다 출발지 IP가 위조되므로 IP 기반 차단 규칙을 넣으면 OVS 플로우 테이블 메모리가 고갈됩니다. 공격 호스트가 연결된 **액세스 포트(`in_port`)**를 매칭 조건으로 차단해야 합니다.
4. **패키지 매니저 규정:**
   - 호스트 파이썬 환경 작업 시 `uv` 패키지 매니저를 원칙으로 사용합니다 (`uv add`, `uv run`).
