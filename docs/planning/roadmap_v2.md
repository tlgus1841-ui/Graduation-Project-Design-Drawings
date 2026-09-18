# SDN 기반 분산 트래픽 이상 탐지 및 자동 라우팅 관제 시스템 (Self-Defending SDN Tower)
## 3인 협업 최적화 설계서 및 개정 로드맵 (v2.0)

---

## 1. 기술 스택 및 버전 확정 매트릭스 (Golden Version Matrix)

SDN 프로젝트(Ryu + Mininet + FastAPI + ML + React)는 **버전 불일치로 인한 의존성 지옥(Dependency Hell)**이 가장 빈번하게 발생하는 분야입니다. 3명이 개발할 때 환경 차이로 인한 오류를 100% 차단하기 위해 **공통 표준 버전을 다음과 같이 엄격히 고정**합니다.

### 1.1 컴포넌트별 확정 버전 표

| 계층 | 컴포넌트 | 확정 버전 | 런타임 환경 | 선정 및 버전 고정 이유 (핵심 기술 근거) |
|---|---|---|---|---|
| **OS** | **Host OS** | **Ubuntu 22.04.4 LTS** | Native Linux (Bare-metal / VM) | Mininet 2.3+과 OVS 2.17이 `apt`로 가장 안정적으로 빌드/구동되는 LTS 버전 |
| **Data Plane** | **Mininet** | **2.3.0+** | Host OS Native (`apt install mininet`) | SDN 가상 토폴로지 에뮬레이션 표준 |
| | **Open vSwitch (OVS)** | **2.17.x** | Host OS Native | Ubuntu 22.04 기본 패키지로 커널 모듈 충돌 없음, OpenFlow 1.3 완벽 지원 |
| | **OpenFlow** | **OpenFlow 1.3** | 프로토콜 표준 | 멀티 테이블, 포트/플로우 통계, Metering 기능 지원 |
| **Control Plane** | **Ryu Controller** | **4.34** | **Docker (`python:3.8-slim`)**<br>`--net=host` 모드 | **[중요]** Ryu는 Python 3.9+에서 `eventlet`/`greenlet`/`collections.abc` 충돌로 빌드 실패함. **Python 3.8 환경에 완벽 격리 필수** |
| | **eventlet** | **0.30.2** | Docker Python 3.8 내 pip | 0.33+ 버전의 허브 블로킹 버그 방지 |
| | **networkx** | **2.5.1** | Docker Python 3.8 내 pip | Ryu Python 3.8 환경과 의존성 충돌 없는 Dijkstra 알고리즘 라이브러리 |
| **IPC Bus** | **Redis** | **7.2-alpine** | **Docker 컨테이너** | Ryu-AI-FastAPI 간 고속 Pub/Sub 메시징 및 명령 큐 (포트: 6379) |
| **AI / ML** | **Language** | **Python 3.10.12** | **Host venv (`venv-ai`)** | Ubuntu 22.04 시스템 기본 파이썬으로 팀원 누구나 10초 만에 동일 환경 구축 가능 |
| | **Scikit-learn** | **1.3.2** | Python 3.10 pip | 경량 Isolation Forest 추론 검증된 안정 버전 |
| | **NumPy / Pandas** | **NumPy 1.24.3 / Pandas 2.1.4** | Python 3.10 pip | 피처 엔지니어링 계산 일관성 보장 |
| | **Scapy** | **2.5.0** | Python 3.10 pip | IP Spoofing, SYN Flood, HTTP 모의 패킷 생성 표준 |
| **Web Backend** | **Language** | **Python 3.10.12** | **Host venv (`venv-web`)** | Asyncio 기반 비동기 웹소켓 고속 처리 |
| | **FastAPI** | **0.109.2** | Python 3.10 pip | 비동기 WebSocket & REST API 서빙 |
| | **Uvicorn** | **0.27.1** | Python 3.10 pip | 고성능 ASGI 서버 |
| | **Pydantic** | **v2.6.1** | Python 3.10 pip | 고속 데이터 검증 및 직렬화 |
| | **redis-py** | **5.0.1** | Python 3.10 pip | `redis.asyncio`를 통한 비동기 채널 구독 |
| **Web Frontend** | **Node.js** | **20.x LTS (Iron)** | Native / nvm | 장기 지원 LTS 버전으로 npm 패키지 호환성 최상 |
| | **React** | **18.2.0** | npm | React 19의 외부 라이브러리 호환성 리스크 방지 (18이 가장 안정적) |
| | **Vite** | **5.1.x** | npm | 초고속 HMR 번들러 |
| | **vis-network** | **9.1.9** | npm | 동적 네트워크 토폴로지 렌더링 표준 |
| | **ApexCharts** | **3.46.0** | npm | 실시간 트래픽 시계열 차트 & 게이지 시각화 |
| | **Tailwind CSS** | **3.4.1** | npm | 반응형 관제탑 대시보드 UI 스타일링 |

---

### 1.2 왜 "Python 3.8(Docker)"과 "Python 3.10(Host venv)"으로 이원화하는가?

1. **Ryu Controller의 한계:**
   - Ryu 공식 저장소는 수년 전 개발이 멈추었으며, Python 3.10 이상에서는 `collections`의 추상 클래스 이동, `async` 예약어 변경, C-확장 모듈인 `greenlet` 컴파일 에러로 인해 네이티브 설치가 100% 실패합니다.
   - 따라서 Ryu는 **`python:3.8-slim` 공식 Docker 컨테이너**로 완전히 격리하여 구동하는 것이 오픈소스 SDN 진영의 골든 스탠다드입니다.
2. **AI 및 웹 백엔드의 최신성 확보:**
   - 반면 Scikit-learn, FastAPI, Pydantic v2 등은 Python 3.8에 대한 지원을 이미 종료(EOL)했거나 구형 버전만 제공합니다.
   - Ubuntu 22.04 LTS의 네이티브 파이썬은 **Python 3.10.12**이므로, 호스트 OS 환경에서 별도 PPA 추가나 pyenv 빌드 없이 `python3 -m venv` 명령어로 누구나 즉시 통일된 환경을 구축할 수 있습니다.

---

## 2. 기존 기획서의 핵심 오류 및 기술적 한계점 분석

기존 기획서(v1.0)는 핵심 아이디어는 우수하나, **SDN/Ryu 내부 동작 원리, OpenFlow 1.3 스펙, 동시성 모델, 데이터셋 현실성, 3인 협업 구조** 측면에서 실제 구현 시 심각한 장애를 유발할 수 있는 여러 기술적 오류와 병목이 존재합니다.

### 2.1 [치명적 오류] Ryu(Eventlet) 내부 동기 AI 추론 시 컨트롤러 마비
* **기존 기획의 오류:** "Isolation Forest 모델을 Ryu 백그라운드 스레드에 탑재하여 실시간 추론"
* **원인:** Ryu는 파이썬의 `eventlet` 기반 코루틴(그린 스레드) 환경에서 동작합니다. Scikit-learn의 Isolation Forest 추론(`model.predict()`, numpy 연산)은 CPU-bound 블로킹 연산입니다. 이를 Ryu 프로세스 안에서 직접 실행하면 **Ryu의 이벤트 루프가 멈춰 스위치와의 OpenFlow Keepalive(Echo Request/Reply) 교환이 실패하고, OVS 스위치 연결이 끊어지는 재앙(Switch Disconnect)**이 발생합니다.
* **해결책:** AI 추론 엔진을 Ryu 내부 스레드가 아닌 **독립적인 Python 프로세스(AI Inference Worker)**로 분리합니다. Ryu는 통계만 수집하여 Redis에 빠르게 Publish하고, AI Worker가 Redis를 구독하여 추론한 뒤 제어 명령만 Redis 또는 Ryu REST API로 전달하는 **비동기 마이크로서비스 구조**를 채택합니다.

### 2.2 [OpenFlow 스펙 오류] `OFPFC_MODIFY`를 통한 다중 홉 우회 경로 설정 불가
* **기존 기획의 오류:** "기존 정상 경로 엔트리를 명시적으로 수정(`OFPFC_MODIFY`)하여 우회 경로 전환"
* **원인:** OpenFlow 스펙상 `OFPFC_MODIFY`는 **기존 플로우 엔트리와 Match 조건(IP, Port 등)이 정확히 일치하는 단일 스위치 내부의 Action(출력 포트)만 변경**합니다. 네트워크 토폴로지에서 경로를 우회하려면 패킷이 지나가는 **새로운 경유 스위치들(Intermediate Switches)에도 플로우 엔트리가 미리 존재하거나 새로 주입(`OFPFC_ADD`)**되어야 합니다. 시작 스위치 하나만 `OFPFC_MODIFY`한다고 해서 전체 우회 경로가 마법처럼 동작하지 않으며, 중간 스위치에서 패킷이 드랍(Drop)됩니다.
* **해결책:** Dijkstra 알고리즘으로 계산된 대체 경로상의 모든 스위치에 우회 플로우(`OFPFC_ADD`, 더 높은 Priority 또는 우회 매칭)를 선제적으로 설치한 뒤, 진입 스위치의 포워딩 경로를 전환하는 **다중 홉 플로우 프로비저닝 파이프라인**을 구축합니다.

### 2.3 [설계 오류] 단순 타임아웃 차등에 의존한 자가 복구의 플래핑(Flapping) 위험
* **기존 기획의 오류:** "In_port Drop Timeout(15초) > 우회 플로우 Timeout(10초) 설정으로 공격 종료 시 자동 롤백"
* **원인:** 공격자가 20초 이상 공격을 지속할 경우, 우회 플로우가 10초 만에 만료되어 패킷이 다시 원래의 혼잡 링크로 흘러 들어가고, In_port Drop 또한 15초 만에 만료되어 공격 패킷이 다시 폭주합니다. 이로 인해 통신 품질이 극도로 불안정해지는 **라우팅 플래핑(Route Flapping)**이 발생합니다.
* **해결책:** 수동적 타임아웃에만 의존하지 않고, **명시적 상태 관리 머신(FSM: Normal -> Under Attack -> Mitigated -> Restoring)**을 도입합니다. AI Worker/Ryu가 공격 트래픽의 지속 여부를 주기적으로 확인하여 공격 지속 시 차단 규칙의 수명을 연장(Heartbeat)하고, 공격이 소멸된 것을 감지했을 때 안전하게 기본 경로로 복귀시키는 능동형 복구 메커니즘을 적용합니다.

### 2.4 [데이터셋 괴리] CIC-DDoS2019 데이터셋과 Ryu 통계 피처 간 불일치
* **기존 기획의 오류:** "CIC-DDoS2019의 선별 피처로 Isolation Forest 사전 학습"
* **원인:** CIC-DDoS2019는 pcap 패킷 캡처 기반으로 추출된 80여 개 L4~L7 피처(예: TCP 플래그 비율, 전방/후방 패킷 간격, 윈도우 크기 등)로 이루어져 있습니다. 반면 Ryu의 OpenFlow 1.3 `OFPPortStats` 및 `OFPFlowStats`에서 실시간으로 얻을 수 있는 정보는 `packet_count`, `byte_count`, `duration_sec`, `duration_nsec` 등 극히 기초적인 누적 카운터뿐입니다.
* **해결책:** 사전 수집된 무거운 공개 데이터셋에 억지로 의존하기보다, **SDN 환경에서 즉시 계산 가능한 5대 표준 파생 피처**(초당 패킷 수 $\Delta \text{PPS}$, 초당 바이트 수 $\Delta \text{BPS}$, 평균 패킷 크기 $\text{BPP}$, 단위 시간당 활성 플로우 수, 포트 사용률 변화율)를 정의하고, Scapy로 직접 생성한 정상/DDoS 트래픽을 토폴로지에서 수집하여 모델을 학습시킵니다.

### 2.5 [협업 병목] 순차적(Waterfall) 로드맵으로 인한 3인 개발 정체
* **기존 기획의 오류:** 1단계 인프라 $\to$ 2단계 메트릭 수집 $\to$ 3단계 AI $\to$ 4단계 웹 $\to$ 5단계 시연
* **원인:** 이 구조는 1~3단계(Ryu 및 AI)가 완성될 때까지 웹 개발자(백엔드/프론트엔드)가 대기해야 하며, AI 개발자도 Mininet 환경이 완성될 때까지 데이터를 다루지 못해 전체 일정이 지연됩니다.
* **해결책:** **계약 우선(Contract-First) 인터페이스 설계(Redis Channel, WebSocket JSON Schema, REST API)**를 가장 먼저 확정하고, **Mock Generator**를 도입하여 3인이 첫날부터 병렬로 개발할 수 있도록 로드맵을 재구성합니다.

---

## 3. 개선된 시스템 아키텍처 (v2.0)

```
+-----------------------------------------------------------------------------------+
|                        [Layer 4: 웹 관제탑 (Frontend)]                            |
|  - React 18.2 (Vite) + Tailwind CSS 3.4 + Lucide Icons                            |
|  - vis-network 9.1: 실시간 네트워크 토폴로지 (노드 상태, 링크 트래픽, 차단 표시)   |
|  - ApexCharts 3.46: 실시간 PPS/BPS 시계열 차트 & 이상치 스코어 게이지              |
|  - Event Timeline: 실시간 보안 알림 & 비상 수동 격리/복원 제어 패널               |
+-----------------------------------------------------------------------------------+
                                        ▲ WebSocket (실시간 브로드캐스팅)
                                        ▼ REST API (관리자 수동 제어)
+-----------------------------------------------------------------------------------+
|                        [Layer 3: 웹 관제 백엔드 (FastAPI)]                         |
|  - Python 3.10 (venv-web), FastAPI 0.109, Uvicorn 0.27                            |
|  - Asyncio 기반 고속 WebSocket Hub (연결 클라이언트 멀티캐스팅)                    |
|  - REST Control Controller (포트 격리 해제, 수동 우회, 임계치 조정)                |
|  - Redis Subscriber & Command Dispatcher                                          |
+-----------------------------------------------------------------------------------+
                                        ▲ Redis Pub/Sub & Command Queue
                                        ▼ (고속 IPC 메시지 버스: Redis 7.2 Container)
+------------------------------------+      +---------------------------------------+
|  [Layer 2-B: AI 이상 탐지 워커]    |      |    [Layer 2-A: SDN 제어 평면 (Ryu)]   |
|  - Python 3.10 (venv-ai)           |      |  - Docker (Python 3.8, --net=host)    |
|  - Scikit-learn 1.3 IsolationForest|      |  - Ryu 4.34 (OpenFlow 1.3)            |
|  - Redis 'sdn:stats' 실시간 구독    |      |  - 2-Tier 모니터링 (Port -> Flow)     |
|  - 실시간 피처 엔지니어링 (PPS,BPS)|      |  - NetworkX 2.5.1 Dijkstra 동적 라우팅|
|  - 이상 탐지 시 'sdn:alert' 및     | ===> |  - Access In_port Drop (Priority 100) |
|    'sdn:cmd:reroute' 발행          |      |  - 다중 홉 우회 프로비저닝 (OFPFC_ADD)|
|  - Scapy 2.5.0 모의 트래픽 주입    |      |  - LLDP 토폴로지 자동 탐색기          |
+------------------------------------+      +---------------------------------------+
                                                            ▲ OpenFlow 1.3 (TCP 6653)
                                                            ▼ (Flow Mod, Stats Req/Rep)
+-----------------------------------------------------------------------------------+
|                         [Layer 1: 데이터 평면 (Data Plane)]                       |
|  - Host OS: Ubuntu 22.04 LTS (네이티브 Mininet 2.3+)                              |
|  - Open vSwitch (OVS 2.17): 5개 스위치 다중 경로 (Diamond/Mesh) 토폴로지          |
|  - 호스트 군: H_legit (정상 통신 단말), H_attacker (Scapy 공격 단말), H_server    |
+-----------------------------------------------------------------------------------+
```

---

## 4. 3인 팀 역할 분담 (R&R: Roles & Responsibilities)

| 담당 | 역할 | 담당 영역 | 작업 환경 및 도구 |
|---|---|---|---|
| **개발자 A** | **SDN & 인프라 엔지니어** | Mininet 토폴로지, Ryu 컨트롤러, OpenFlow 프로토콜, 동적 라우팅 및 플로우 제어 | Ubuntu 22.04, Mininet 2.3, OVS 2.17, Docker(Python 3.8, Ryu 4.34) |
| **개발자 B** | **AI & 보안 파이프라인 엔지니어** | 모의 공격/정상 트래픽 생성, 실시간 피처 엔지니어링, 이상 탐지 모델, AI 추론 워커 | Python 3.10(`venv-ai`), Scapy 2.5, Scikit-learn 1.3, Pandas, Redis |
| **개발자 C** | **웹 관제탑 풀스택 엔지니어** | FastAPI 비동기 서버, WebSocket 브릿지, React 관제 대시보드, 토폴로지/차트 시각화 | Python 3.10(`venv-web`), FastAPI, Node 20 LTS, React 18.2, vis-network |

---

## 5. 팀 공통 개발 환경 셋업 파일 명세 (Setup Manifests)

팀원 3명이 각자 머신에서 즉시 복사하여 동일한 환경을 10분 내에 구축할 수 있도록 설정 파일 규격을 제공합니다.

### 5.1 Docker Compose 명세 (`docker-compose.yml`)
프로젝트 루트에서 Redis 브로커와 Ryu 컨트롤러를 한 번에 실행합니다:

```yaml
version: '3.8'

services:
  # 1. 메시지 브로커 (Redis)
  redis-broker:
    image: redis:7.2-alpine
    container_name: sdn-redis
    restart: always
    network_mode: host
    command: redis-server --port 6379 --appendonly no

  # 2. SDN 제어 평면 (Ryu Controller) - 개발자 A
  ryu-controller:
    build:
      context: ./ryu
      dockerfile: Dockerfile.ryu
    container_name: sdn-ryu
    restart: unless-stopped
    network_mode: host
    volumes:
      - ./ryu/app:/app
    command: ryu-manager --ofp-tcp-listen-port 6653 --observe-links /app/controller.py
    depends_on:
      - redis-broker
```

### 5.2 Ryu Dockerfile (`ryu/Dockerfile.ryu`)
```dockerfile
FROM python:3.8-slim

WORKDIR /app

# 빌드 필수 도구 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    git \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Ryu 핵심 의존성 버전 고정 설치
RUN pip install --no-cache-dir \
    eventlet==0.30.2 \
    greenlet==1.1.2 \
    tinyrpc==1.0.4 \
    routes==2.5.1 \
    webob==1.8.7 \
    networkx==2.5.1 \
    redis==5.0.1 \
    ryu==4.34

EXPOSE 6653 8080
```

### 5.3 AI 워커 의존성 (`requirements-ai.txt` - Python 3.10)
```text
scikit-learn==1.3.2
scapy==2.5.0
pandas==2.1.4
numpy==1.24.3
redis==5.0.1
joblib==1.3.2
```

### 5.4 웹 백엔드 의존성 (`requirements-web.txt` - Python 3.10)
```text
fastapi==0.109.2
uvicorn[standard]==0.27.1
pydantic==2.6.1
redis==5.0.1
websockets==12.0
python-multipart==0.0.9
```

### 5.5 웹 프론트엔드 의존성 (`frontend/package.json`)
```json
{
  "name": "sdn-control-tower",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "vis-network": "^9.1.9",
    "vis-data": "^7.1.9",
    "apexcharts": "^3.46.0",
    "react-apexcharts": "^1.4.1",
    "lucide-react": "^0.330.0",
    "clsx": "^2.1.0",
    "tailwind-merge": "^2.2.1"
  },
  "devDependencies": {
    "@types/react": "^18.2.56",
    "@types/react-dom": "^18.2.19",
    "@vitejs/plugin-react": "^4.2.1",
    "autoprefixer": "^10.4.17",
    "postcss": "^8.4.35",
    "tailwindcss": "^3.4.1",
    "vite": "^5.1.4"
  }
}
```

---

## 6. 공통 통신 인터페이스 규격 (Data Contract)

3인 병렬 개발을 위해 첫 주에 반드시 동결(Freeze)해야 하는 통신 데이터 규격입니다.

### 6.1 Redis Pub/Sub 채널 구조
| 채널명 | 송신자 | 수신자 | 목적 |
|---|---|---|---|
| `sdn:stats:port` | 개발자 A (Ryu) | 개발자 B (AI), 개발자 C (FastAPI) | 주기적 포트 통계 스트리밍 |
| `sdn:anomaly:alert` | 개발자 B (AI) | 개발자 A (Ryu), 개발자 C (FastAPI) | 이상 탐지 알림 및 분석 결과 |
| `sdn:control:command` | 개발자 B (AI), 개발자 C (FastAPI) | 개발자 A (Ryu) | 플로우 제어 (차단, 우회, 복원) |
| `sdn:topology:sync` | 개발자 A (Ryu) | 개발자 C (FastAPI) | 토폴로지 노드/링크 상태 초기화 |

---

### 6.2 주요 JSON 메시지 포맷

#### 1) 포트 통계 메시지 (`sdn:stats:port`)
```json
{
  "timestamp": 1773468000.123,
  "dpid": "0000000000000001",
  "port_no": 1,
  "rx_packets": 14200,
  "tx_packets": 14150,
  "rx_bytes": 10245000,
  "tx_bytes": 10210000,
  "rx_errors": 0,
  "duration_sec": 45
}
```

#### 2) 이상 탐지 알림 메시지 (`sdn:anomaly:alert`)
```json
{
  "timestamp": 1773468010.500,
  "target_dpid": "0000000000000001",
  "suspect_port": 1,
  "anomaly_score": -0.78,
  "threat_type": "SYN_FLOOD_SPOOFING",
  "metrics": {
    "pps": 8500,
    "bps": 45000000,
    "bpp": 66.1
  },
  "action_required": "IN_PORT_DROP"
}
```

#### 3) 플로우 제어 명령 메시지 (`sdn:control:command`)
```json
{
  "command_id": "cmd-20260911-001",
  "action": "ISOLATE_PORT",
  "dpid": "0000000000000001",
  "port_no": 1,
  "timeout_sec": 30,
  "reason": "AI Anomaly Detection Triggered"
}
```
*(우회 명령일 경우: `"action": "REROUTE"`, `"source_ip": "10.0.0.1"`, `"dest_ip": "10.0.0.2"`, `"path": ["s1", "s3", "s2"]`)*

#### 4) 토폴로지 동기화 메시지 (`sdn:topology:sync`)
```json
{
  "nodes": [
    {"id": "s1", "label": "Switch 1", "type": "switch", "dpid": "0000000000000001"},
    {"id": "s2", "label": "Switch 2", "type": "switch", "dpid": "0000000000000002"},
    {"id": "h1", "label": "Host 1 (Legit)", "type": "host", "ip": "10.0.0.1", "mac": "00:00:00:00:00:01"},
    {"id": "h2", "label": "Host 2 (Attacker)", "type": "host", "ip": "10.0.0.2", "mac": "00:00:00:00:00:02"}
  ],
  "links": [
    {"source": "s1", "target": "s2", "src_port": 2, "dst_port": 1, "status": "active"},
    {"source": "s1", "target": "h1", "src_port": 1, "dst_port": 0, "status": "active"}
  ]
}
```

---

## 7. 주차별 3인 병렬 개발 로드맵 (5주 완성 스프린트)

```
[주차]        개발자 A (SDN)             개발자 B (AI/보안)           개발자 C (웹 관제탑)
-----------------------------------------------------------------------------------------
1주차     Mininet 토폴로지 구축      Scapy 트래픽 생성기 제작     FastAPI Mock 서버 구축
(기반)    Ryu 기본 스위칭 & LLDP     트래픽 수집 스크립트 작성    React 대시보드 레이아웃
           └────── [1주차 말: Redis 채널 규격 및 통신 프로토콜 전원 합의] ──────┘

2주차     Ryu 포트 통계 폴러 구현    실시간 피처 추출기 개발      vis-network 토폴로지 맵
(단위엔진) Redis Stats Publish      Isolation Forest 모델 학습   ApexCharts 실시간 차트
          단일 스위치 Drop 테스트     더미 데이터 기반 추론 검증   WebSocket 수신 연동

3주차     Dijkstra 우회 라우팅 엔진   AI 워커(독립 프로세스) 완성  FastAPI-Redis 브릿지 연동
(1차통합)  Redis 제어 명령 수신기     Redis 경보/명령 발행 연동    실시간 이벤트 로그 UI
          └───────────── [3주차 말: Ryu - AI - Backend 3자 통합 테스트] ─────────────┘

4주차     In_port 격리 + 다중 우회   정상/DDoS 동시 주입 시나리오  수동 비상 차단 API 연동
(E2E통합)  타임아웃 및 자가복구 구현   탐지 정밀도(F1) 최적화       토폴로지 색상 동적 갱신
          └─────── [4주차 말: 전 시나리오 E2E 통합 테스트 (공격-탐지-우회-복구)] ───────┘

5주차     예외 처리 (링크 단절 대응)  추론 레이턴시 튜닝 (<50ms)   대시보드 UI/UX 완성
(시연준비) 최종 발표 시연 리허설     시연용 공격 스크립트 패키징  시연 동영상 및 최종 보고서
```

---

## 8. 단계별 상세 실행 가이드

### Sprint 1: 인프라 및 기반 프로토콜 확립 (1주차)
* **목표:** 환경 구성 완료, 공통 규격 정의, Mock 서버를 통한 독립 개발 환경 조성.
* **개발자 A:**
  - Ubuntu 22.04 호스트에 Mininet 2.3+ 설치 및 OVS 2.17 정상 구동 확인.
  - Python 3.8 Ryu Docker 컨테이너 빌드 및 `--net=host` 모드로 OVS 통신(`127.0.0.1:6653`) 검증.
  - 다중 경로 토폴로지(`diamond_topo.py`) 작성 (S1-S2, S1-S3, S2-S4, S3-S4).
* **개발자 B:**
  - Python 3.10 가상환경(`venv-ai`) 생성 및 `requirements-ai.txt` 설치.
  - Scapy를 활용한 정상 트래픽 생성 스크립트(`traffic_normal.py`) 작성.
  - Scapy 랜덤 IP 변조 SYN Flooding 공격 스크립트(`traffic_attack.py`) 작성.
* **개발자 C:**
  - Python 3.10 가상환경(`venv-web`) 생성 및 `requirements-web.txt` 설치.
  - FastAPI 프로젝트 셋업 및 WebSocket 엔드포인트 구현.
  - 토폴로지/통계 더미 데이터를 생성해 WebSocket으로 1초마다 전송하는 `mock_generator.py` 작성.
  - Node 20 LTS 기반 React (Vite) 프로젝트 생성, Tailwind CSS 세팅, 기본 대시보드 레이아웃 잡기.

---

### Sprint 2: 각 도메인 핵심 엔진 구현 (2주차)
* **목표:** 각자의 컴포넌트를 독립적으로 동작 가능한 수준까지 완성.
* **개발자 A:**
  - Ryu의 `hub.spawn`을 활용해 2초마다 `OFPPortStatsRequest`를 브로드캐스팅하는 모니터링 루프 구현.
  - `OFPPortStatsReply` 수신 시 바이트/패킷 카운터를 추출하여 Redis `sdn:stats:port`로 Publish.
  - OVS 포트 번호(`port_no`)와 연결된 호스트 MAC/IP 매핑 테이블 동적 생성.
* **개발자 B:**
  - Redis `sdn:stats:port` 채널 구독 모듈 구현.
  - 이전 틱과 현재 틱의 차이를 이용해 $\Delta \text{PPS}$, $\Delta \text{BPS}$, $\text{BPP}$ 계산 로직 작성.
  - 정상 및 공격 트래픽 데이터를 파일로 로깅하여 Isolation Forest 모델 사전 학습.
* **개발자 C:**
  - React에서 `vis-network`를 사용해 가상 스위치 및 호스트를 그래프로 렌더링.
  - `ApexCharts`를 연동하여 가상 메트릭(PPS/BPS) 실시간 스트리밍 차트 구현.
  - Mock 데이터를 받아 그래프 노드 색상이 변하고 차트가 갱신되는 UI 검증 완료.

---

### Sprint 3: 1차 통합 및 비동기 IPC 연동 (3주차)
* **목표:** Ryu, AI Worker, FastAPI 간의 Redis 메시지 연동 확인.
* **개발자 A:**
  - NetworkX 라이브러리를 연동하여 S1에서 S4로 가는 최단 경로(기본: S1-S2-S4)와 대체 경로(우회: S1-S3-S4) 계산.
  - Redis `sdn:control:command` 채널을 구독하는 이벤트 루프를 Ryu 백그라운드 태스크로 추가.
* **개발자 B:**
  - 독립 프로세스 `ai_worker.py` 완성: 실시간 통계 수신 $\to$ 피처 정규화 $\to$ Isolation Forest 추론 $\to$ 이상 감지 시 Redis `sdn:anomaly:alert` 및 제어 명령 발행.
  - 스코어 임계값(Threshold) 튜닝을 통해 False Positive(정상 트래픽 오탐) 최소화.
* **개발자 C:**
  - FastAPI에 Redis Pub/Sub 리스너를 결합하여 실제 Ryu/AI 데이터가 들어오면 즉시 브라우저로 중계하도록 전환.
  - 대시보드에 보안 이벤트 타임라인 컴포넌트 추가 (공격 감지 시 빨간색 경보 팝업).

---

### Sprint 4: E2E 통합 및 자율 방어/복구 파이프라인 완성 (4주차)
* **목표:** 공격 주입부터 탐지, 차단, 우회, 복구까지 전 자동화 시나리오 검증.
* **협업 작업:**
  1. **공격 주입:** H_attacker에서 Scapy로 랜덤 IP 변조 SYN Flooding 발사.
  2. **1차 감지:** Ryu가 S1 포트 통계에서 PPS/BPS 급증 수집 $\to$ Redis 발행.
  3. **2차 정밀 분석:** AI Worker가 BPP 급감 및 PPS 폭증을 감지하여 `ANOMALY_DETECTED` 판정.
  4. **Access In_port 격리:** Ryu가 공격자가 연결된 S1의 1번 포트에 `Priority 100 Drop` 규칙 설치 (정상 트렁크 포트는 영향 없음).
  5. **다중 홉 우회 라우팅:** 혼잡 링크를 경유하던 H_legit의 통신 플로우를 대체 경로(S1-S3-S4)로 전환.
  6. **웹 관제탑 시각화:** 대시보드 토폴로지에서 공격 포트가 붉은색 X로 표시되고, 우회 링크가 활성화되며, 실시간 PPS 차트가 피크 후 안정화되는 모습 확인.
  7. **자가 복구 검증:** 공격 중단 $\to$ AI Worker가 트래픽 정상화 감지 $\to$ 차단 플로우 제거 및 원래 경로로 무중단 복귀.

---

### Sprint 5: 성능 최적화, 예외 처리 및 최종 시연 준비 (5주차)
* **목표:** 실패 없는 시연을 위한 방어 코드 작성 및 문서/발표자료 패키징.
* **개발자 A:** 링크 장애(Link Down) 발생 시 자동 감지 및 페일오버 로직 보완, OVS 리셋 스크립트 작성.
* **개발자 B:** 탐지 지연 시간 측정 (목표: 공격 시작 후 3초 이내 탐지 및 차단 명령 발송), F1-Score 95% 이상 검증.
* **개발자 C:** UI 디테일 다듬기 (다크 테마, 통계 요약 카드, 수동 격리/복원 버튼 동작 애니메이션), 화면 녹화 영상 제작.
* **공통:** 최종 발표 슬라이드 및 졸업작품 최종 보고서 작성, 시연 시나리오 리허설 3회 이상 수행.

---

## 9. 주요 기술적 함정 및 방어 코드 가이드

### 1) Ryu와 Redis 간 Eventlet 호환성
* **주의사항:** Ryu 환경에서 일반 동기식 `redis-py`를 직접 호출하면 스레드가 블로킹될 수 있습니다.
* **해결 코드:** `eventlet.monkey_patch()`를 적용하거나, 비차단 소켓 모드로 초기화합니다:
  ```python
  import eventlet
  eventlet.monkey_patch()
  import redis

  # Ryu 컨트롤러 내부
  self.r = redis.Redis(host='127.0.0.1', port=6379, db=0)
  ```

### 2) Trunk 포트 오차단 방지 (Access Port 식별 로직)
* **주의사항:** 공격 트래픽이 여러 스위치를 거쳐갈 때 스위치 간 연결 포트(Trunk Port)를 차단해 버리면 전체 네트워크가 마비됩니다.
* **해결 로직:**
  ```python
  # 개발자 A가 토폴로지 초기화 시 관리하는 테이블
  ACCESS_PORTS = {
      "0000000000000001": [1, 2],  # S1의 1번, 2번 포트는 단말 연결 포트
  }
  TRUNK_PORTS = {
      "0000000000000001": [3],     # S1의 3번 포트는 S2 연결 포트
  }

  def apply_in_port_drop(dpid, in_port):
      if in_port in TRUNK_PORTS.get(dpid, []):
          logger.warning(f"트렁크 포트({in_port}) 차단 시도 거부됨! 우회 라우팅으로 전환합니다.")
          return False
      # Access 포트인 경우에만 Drop 규칙 설치
      install_drop_flow(dpid, in_port, priority=100)
      return True
  ```

### 3) 다중 홉 우회 라우팅 시 플로우 역순 설치 (Reverse Installation)
* **주의사항:** S1 $\to$ S3 $\to$ S4로 경로를 변경할 때, S1부터 플로우를 바꾸면 S3, S4에 아직 규칙이 없어 패킷이 유실됩니다.
* **해결 기법:** 경로의 **도착지 스위치부터 출발지 스위치 방향(역순: S4 $\to$ S3 $\to$ S1)으로 플로우 엔트리를 먼저 설치**한 후 마지막에 S1의 트래픽을 스위칭해야 무중단(Zero Packet Loss) 우회가 보장됩니다.

### 4) Mininet 가상 호스트 네임스페이스 격리 (Scapy 실행 위치)
* **주의사항:** Mininet의 호스트(H_legit, H_attacker)는 리눅스 네트워크 네임스페이스(`netns`)로 격리되어 있습니다. Ubuntu 기본 터미널 쉘에서 `python3 traffic_attack.py`를 그냥 실행하면, Mininet 가상 스위치가 아니라 **개발용 PC의 실제 물리 NIC(eth0, wlan0 등)로 공격 패킷이 전송되어 OVS 토폴로지로 패킷이 전혀 유입되지 않는 치명적 실수**가 발생합니다.
* **해결 방법:**
  - **방법 1 (Mininet CLI):** `mininet> h_attacker python3 traffic_attack.py &`
  - **방법 2 (Python 스크립트):** Mininet 파이썬 객체에서 `h_attacker.cmd("python3 traffic_attack.py &")` 실행
  - **방법 3 (Linux CLI):** Mininet 프로세스의 PID를 찾아 `ip netns exec` 또는 `mnexec -a <pid> python3 traffic_attack.py`로 네임스페이스 진입 후 실행.

### 5) OpenFlow 1.3 IPv4 Match 시 `eth_type=0x0800` 필수 선언
* **주의사항:** OpenFlow 1.3 스펙에서는 IP 주소 매칭(`ipv4_src`, `ipv4_dst`)을 적용할 때 반드시 이더넷 타입이 IPv4(`eth_type=0x0800`)임을 먼저 매치에 선언해야 합니다. 이를 생략하고 `parser.OFPMatch(ipv4_dst='10.0.0.2')`만 작성하면 OVS 스위치가 `OFPBMC_BAD_PREREQ` (Bad Prerequisites) 에러를 뱉고 플로우 추가를 거부합니다.
* **해결 코드:**
  ```python
  # 올바른 IPv4 우회 플로우 Match 작성법
  match = parser.OFPMatch(
      eth_type=0x0800,           # [필수 선행 조건] IPv4 명시
      ipv4_src='10.0.0.1',
      ipv4_dst='10.0.0.2'
  )
  ```

### 6) LLDP 링크 탐색과 Host(단말) 위치 탐색의 차이 (ARP Packet-In 필수)
* **주의사항:** Ryu의 내장 모듈 `ryu.topology.switches`는 스위치 간의 LLDP 패킷 교환으로 스위치 간 링크(Trunk)는 자동으로 탐색하지만, **일반 호스트(H_legit, H_attacker, Server)는 LLDP를 보내지 않으므로 호스트가 어느 스위치 몇 번 포트에 물려있는지 자동으로 알 수 없습니다.**
* **해결 구조:**
  - 호스트가 처음 통신할 때 발생하는 **ARP Request 브로드캐스트 패킷**을 Ryu의 `_packet_in_handler`에서 가로채서 `(host_ip, host_mac) -> (dpid, in_port)` 테이블을 동적으로 학습(Host Learning)해야 호스트 간 Dijkstra 최단 경로 계산이 정상 동작합니다.

### 7) vis-network React 컴포넌트 메모리 누수 및 리렌더링 방지
* **주의사항:** React에서 WebSocket으로 초당 1~2회 메트릭을 수신할 때마다 `new Network(container, data, options)`를 재생성하면 심각한 화면 깜빡임과 브라우저 메모리 누수가 발생합니다.
* **해결 구조:**
  - `vis-network` 인스턴스는 `useEffect`에서 컴포넌트 마운트 시 최초 1회만 생성합니다.
  - 노드/엣지 상태 업데이트는 `vis-data`의 `DataSet.update()` 메서드를 사용하여 변경된 속성(예: `color`, `value`, `dashes`)만 부분 갱신합니다:
  ```javascript
  // React 컴포넌트 내부
  edgesDataSet.current.update({ id: 's1-s2', color: { color: '#ef4444' }, width: 4 });
  ```

### 8) [재난급 함정] 다이아몬드 토폴로지 내 루프(Loop)로 인한 ARP 브로드캐스트 스톰 방지
* **주의사항:** S1-S2, S1-S3, S2-S4, S3-S4와 같은 다중 우회 토폴로지에는 **물리적/논리적 루프(Loop)**가 존재합니다. 호스트가 상대방의 MAC 주소를 찾기 위해 단 1개의 ARP Request(브로드캐스트)를 보내는 순간, Ryu 컨트롤러가 이를 단순 플러딩(`OFPP_FLOOD`) 처리하면 **패킷이 루프를 돌며 무한 증식하는 ARP Broadcast Storm이 발생하여 OVS와 컨트롤러 CPU가 100%로 치솟고 Mininet 전체가 즉각 다운**됩니다.
* **해결 구조 (ARP Proxy & Selective Forwarding):**
  - 컨트롤러는 ARP Request 패킷을 전체 포트로 플러딩하지 않습니다.
  - Ryu가 이미 학습한 호스트 테이블(`arp_table`)에 목적지 IP의 MAC이 존재하면 컨트롤러가 직접 가상 ARP Reply를 작성해 요청 호스트로 응답(Proxy ARP)합니다.
  - 아직 목적지 위치를 모를 경우, 링크(Trunk) 포트 전체로 쏘지 않고 **Dijkstra로 계산된 Spanning Tree 링크 및 단말 연결 Access 포트로만 선별 포워딩**하여 루프를 원천 차단해야 합니다.

### 9) Mininet OVS 생성 시 `protocols='OpenFlow13'` 누락 방지
* **주의사항:** Mininet 기본 설정으로 `net.addSwitch('s1')`을 호출하면 OVS는 OpenFlow 1.0으로 컨트롤러와 통신을 시도합니다. Ryu 컨트롤러가 OpenFlow 1.3 전용으로 동작할 경우 핸드셰이크 단계에서 `OFPH_HELLO_FAILED` (Version mismatch) 에러가 발생하며 스위치 연결이 실패합니다.
* **해결 코드 (`topology.py`):**
  ```python
  from mininet.node import OVSSwitch

  class OpenFlow13Switch(OVSSwitch):
      def __init__(self, name, **params):
          params['protocols'] = 'OpenFlow13'
          super(OpenFlow13Switch, self).__init__(name, **params)

  # 토폴로지 생성 시 switch 파라미터로 지정
  s1 = net.addSwitch('s1', cls=OpenFlow13Switch)
  ```

### 10) OpenFlow 테이블 계층적 우선순위(Priority Architecture) 확정
* **주의사항:** 플로우 룰 간의 Priority 값이 주먹구구식으로 설정되면, In_port 차단 플로우가 정상 포워딩 플로우에 밀려 패킷이 차단되지 않거나 의도치 않은 패킷 드랍이 발생합니다.
* **우선순위 표준 계층:**
  * `Priority 65535 (최상위)`: **Emergency In_port Drop (공격 진입 포트 무조건 드랍)**
  * `Priority 100`: **Dynamic Reroute Flows (우회 경로 플로우)**
  * `Priority 10`: **Default Shortest Path Flows (기본 최단 경로 정상 포워딩)**
  * `Priority 0 (최하위)`: **Table-Miss Flow (Ryu 컨트롤러로 PacketIn 전송)**

### 11) Linux 커널의 역방향 경로 필터링(`rp_filter`) 해제
* **주의사항:** Linux 커널은 기본적으로 IP 스푸핑 공격을 막기 위해 `rp_filter`(Reverse Path Filtering)가 켜져 있습니다. H_attacker에서 Scapy로 랜덤 가상 IP를 소스로 넣어 패킷을 전송할 때, 리눅스 커널이 이 패킷을 비정상으로 판정하고 **가상 스위치로 전달하기도 전에 커널 레벨에서 폐기(Silent Drop)**해 버립니다.
* **해결 명령어 (Mininet 실행 전 호스트 터미널에서 1회 수행):**
  ```bash
  sudo sysctl -w net.ipv4.conf.all.rp_filter=0
  sudo sysctl -w net.ipv4.conf.default.rp_filter=0
  ```

### 12) `sudo` 실행 시 Python 가상환경(venv) 경로 유지
* **주의사항:** Mininet 스크립트는 네트워크 네임스페이스 생성을 위해 반드시 `sudo` 권한으로 실행해야 합니다. 그러나 일반 `sudo python3 topology.py`를 실행하면 리눅스 시스템 기본 환경변수로 리셋되어 `venv-ai`나 설치된 모듈을 인식하지 못합니다.
* **해결 실행법:**
  ```bash
  # 가상환경이 활성화된 상태에서 -E 플래그로 환경변수 상속
  sudo -E env "PATH=$PATH" python3 topology.py
  ```

### 13) `OFPP_LOCAL` (특수 포트 `4294967294`) 필터링 필수
* **주의사항:** OVS 스위치는 생성될 때 스위치 자체 인터페이스(`s1`)를 위해 `OFPP_LOCAL` (`0xfffffffe` / `4294967294`) 포트를 자동 생성합니다. Ryu가 `OFPPortStatsRequest`를 조회하면 이 특수 포트 통계도 함께 반환됩니다. 이를 필터링하지 않으면 **웹 대시보드에 42억 번 포트가 유령 노드로 렌더링되거나, AI 모델이 이 포트를 이상치로 오판**하여 시스템이 크래시됩니다.
* **해결 코드 (Ryu 통계 핸들러):**
  ```python
  from ryu.ofproto import ofproto_v1_3

  for stat in ev.msg.body:
      if stat.port_no > ofproto_v1_3.OFPP_MAX:  # OFPP_LOCAL 등 예약 특수 포트 제외
          continue
      # 유효한 물리/가상 포트(1, 2, 3...)만 Redis 발행
  ```

### 14) Linux Checksum Offload로 인한 Scapy 패킷 수신 측 폐기 방지
* **주의사항:** Linux의 가상 veth 인터페이스는 성능을 위해 TCP 체크섬 계산을 생략(Checksum Offloading)하는 경우가 많습니다. Scapy로 패킷을 전송할 때 체크섬이 누락되거나 틀리면, 수신 측(Target Server) 리눅스 커널이 **체크섬 오류로 패킷을 조용히 버려(Checksum Failed Drop)** 패킷이 정상 도달하지 않습니다.
* **해결 코드 (Scapy 패킷 전송 시):**
  ```python
  pkt = IP(src=spoofed_ip, dst=target_ip)/TCP(sport=RandShort(), dport=80, flags="S")
  del pkt[IP].chksum   # Scapy가 전송 직전 올바른 체크섬을 강제 재계산하도록 유도
  del pkt[TCP].chksum
  send(pkt, verbose=False)
  ```

### 15) 자가 복구 시 우회 플로우(Priority 100)의 명시적 `OFPFC_DELETE` 필수
* **주의사항:** 공격이 종료되었을 때 In_port 차단만 해제하고 우회 플로우(S1-S3-S4, Priority 100)를 그대로 두면, 기본 최단 경로(Priority 10)가 살아있어도 **더 높은 Priority의 우회 플로우 때문에 트래픽이 원래 최단 경로로 복귀하지 않는 버그**가 발생합니다.
* **해결 로직:**
  - AI 워커가 정상 상태 복귀를 판정하면 Ryu에게 `RESTORE_FLOW` 명령을 전송합니다.
  - Ryu는 우회 경로상의 모든 스위치(S1, S3, S4)에 대해 해당 우회 플로우를 **명시적으로 삭제(`OFPFC_DELETE_STRICT`)**하여 트래픽이 기본 최단 경로(`Priority 10`)로 즉시, 무중단으로 복귀하도록 보장합니다.

### 16) FastAPI WebSocket 비정상 연결 종료(Stale Connection) 방어
* **주의사항:** 브라우저 새로고침(F5)을 하거나 탭을 닫았을 때, 끊어진 WebSocket 연결을 백엔드 목록에서 즉시 정리하지 않으면 다음 Redis 이벤트 브로드캐스트 시 `RuntimeError: Unexpected ASGI message 'websocket.send'`가 발생하여 백엔드 전체가 중단될 수 있습니다.
* **해결 패턴 (`server.py`):**
  ```python
  async def broadcast(self, message: dict):
      disconnected = []
      for connection in self.active_connections:
          try:
              await connection.send_json(message)
          except Exception:
              disconnected.append(connection)
      for conn in disconnected:
          self.active_connections.remove(conn)
  ```

### 17) AI 모델 Cold-Start(초기 가동 직후 오탐) 방지 웜업 구간
* **주의사항:** 시스템 구동 직후 0~10초 사이에는 정상 통계 데이터가 부족하여 Isolation Forest가 정상적인 패킷 흐름을 이상치로 오판할 위험이 있습니다.
* **해결 구조:**
  - 시스템 기동 후 최초 **15초간은 'Baseline Calibration Phase'**로 지정합니다.
  - 이 기간 동안 웹 대시보드에는 `STATUS: SYSTEM CALIBRATING` 상태 배지가 표시되며, 차단 규칙 발행을 유예하고 정상 트래픽 평균 통계만을 수집하여 모델 기준선을 안정화합니다.

### 18) `PacketIn` 핸들러에서 LLDP 및 IPv6 멀티캐스트 조기 필터링 (Early Return)
* **주의사항:** 토폴로지가 기동되면 OVS 스위치에서 LLDP 패킷(`0x88cc`)과 리눅스 커널의 IPv6 이웃 탐색 패킷(`0x86dd`)이 컨트롤러로 쏟아져 들어옵니다. Ryu 핸들러에서 이를 조기에 무시하지 않고 IPv4 파싱(`pkt.get_protocols(ipv4.ipv4)[0]`)을 시도하면 **`IndexError: list index out of range`가 발생하여 컨트롤러 콘솔에 치명적 에러가 도배**됩니다.
* **해결 코드 (`controller.py`):**
  ```python
  @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
  def _packet_in_handler(self, ev):
      msg = ev.msg
      pkt = packet.Packet(msg.data)
      eth = pkt.get_protocols(ethernet.ethernet)[0]

      # LLDP 및 IPv6 패킷은 조기 무시
      if eth.ethertype in (ether_types.ETH_TYPE_LLDP, 0x86dd):
          return
  ```

### 19) OpenFlow 1.3 `OFP_NO_BUFFER`와 첫 패킷 무유실 전송 (`OFPPacketOut`)
* **주의사항:** OpenFlow 1.3에서 플로우 규칙을 설치할 때 `buffer_id=msg.buffer_id`를 무심코 전달하면, 스위치가 패킷을 버퍼링하지 않은 경우(`OFP_NO_BUFFER`) 스위치가 `OFPBRC_BUFFER_UNKNOWN` 에러를 반환합니다. 또한 새 플로우만 깔고 첫 패킷을 방치하면 첫 통신(ARP/HTTP)의 첫 패킷이 유실되어 초기 응답 지연이 발생합니다.
* **해결 패턴:**
  - 플로우 룰 설치 시에는 항상 `buffer_id=ofproto.OFP_NO_BUFFER`로 깔끔하게 규칙만 등록합니다.
  - 현재 컨트롤러에 올라온 원본 데이터(`msg.data`)는 즉시 `OFPPacketOut` 메시지에 담아 해당 출력 포트로 직접 내보내 첫 패킷 손실(Packet Loss)을 0%로 만듭니다.

### 20) React `vis-network` 컨테이너 CSS 높이(Height) 명시 필수
* **주의사항:** `vis-network`의 캔버스는 부모 DOM 요소의 높이를 기준으로 크기를 계산합니다. Tailwind CSS 적용 시 부모 `div`에 높이(`h-[600px]` 또는 `h-full`)가 명시되지 않고 `flex`만 적용되어 있으면, 캔버스 높이가 `0px`로 계산되어 **토폴로지 그래프가 화면에서 완전히 사라져 보이지 않는 버그**가 생깁니다.
* **해결 코드 (`TopologyMap.jsx`):**
  ```jsx
  // 컨테이너에 반드시 명시적 min-height나 height 클래스를 부여
  <div ref={containerRef} className="w-full h-[600px] bg-slate-900 rounded-xl border border-slate-800" />
  ```

### 21) 개발 및 시연 환경 권장 하드웨어 리소스
* **주의사항:** Mininet(5개 OVS), Scapy(초당 수천 패킷 생성), Ryu Docker, Redis, FastAPI, React Vite 브라우저를 1대의 가상머신(VM)에서 동시에 돌릴 경우, CPU 코어가 2개 이하이면 Scapy 프로세스가 단일 코어를 100% 점유하여 OVS 패킷 처리가 멈추거나 핑이 수 초간 튀는 병목이 생깁니다.
* **권장 VM/호스트 사양:**
  * **vCPU:** 최소 **4코어 이상** (권장: 4~6 코어)
  * **RAM:** 최소 **8GB 이상**
  * **OS:** Ubuntu 22.04 LTS 네이티브 또는 VMware/VirtualBox (가상화 가속 VT-x/AMD-V 활성화 필수)

### 22) Dijkstra 우회 계산 시 포화 링크 가중치(Weight Penalty) 동적 갱신 필수
* **주의사항:** NetworkX 그래프에서 링크 가중치를 고정(weight=1)해 두면, S1-S2 링크가 공격 트래픽으로 포화되어도 Dijkstra 알고리즘은 여전히 S1-S2-S4를 '최단 경로'로 반환하여 우회 경로가 절대 도출되지 않습니다.
* **해결 코드 (`controller.py`):**
  ```python
  # 이상 감지된 링크에 임시 페널티 부여
  G[u][v]['weight'] = 999999
  # 대체 우회 경로(S1-S3-S4) 계산
  reroute_path = nx.shortest_path(G, source='s1', target='s4', weight='weight')
  ```

### 23) Mininet 초기 가동 시 ARP 웜업 및 pingall 초기 패킷 드랍 방어
* **주의사항:** Mininet 실행 직후 `mininet> pingall`을 수행하면, 스위치 플로우 테이블과 ARP 캐시가 아직 비어 있어 첫 1회 테스트에서 20%~50%의 패킷 손실이 발생할 수 있습니다. 이는 시스템 장애가 아닌 정상적인 플로우 학습(Table-Miss) 과정입니다.
* **해결 팁:**
  - 시연 시작 전 호스트 스크립트에서 초기 웜업 핑(`h1.cmd('ping -c 2 10.0.0.4')`)을 1회 백그라운드로 실행해 플로우를 예열해 두면 본 시연 시 100% 패킷 성공률을 보여줄 수 있습니다.

### 24) AI Worker의 NumPy 데이터 타입 JSON 직렬화 불가(`TypeError`) 방어
* **주의사항:** Scikit-learn의 `decision_function()`이나 NumPy 계산 결과는 `numpy.float64` 또는 `numpy.int64` 타입입니다. 파이썬 표준 `json.dumps()`는 NumPy 객체를 직렬화할 수 없어 `TypeError: Object of type int64 is not JSON serializable` 에러를 뿜으며 AI 워커가 크래시됩니다.
* **해결 코드 (`ai_worker.py`):**
  ```python
  import json

  # 원시 파이썬 타입(float, int)으로 명시적 형변환
  alert_data = {
      "anomaly_score": float(raw_score),
      "metrics": {
          "pps": int(raw_pps),
          "bps": int(raw_bps),
          "bpp": float(raw_bpp)
      }
  }
  redis_client.publish('sdn:anomaly:alert', json.dumps(alert_data))
  ```

### 25) FastAPI REST API 호출 시 CORS(Cross-Origin) 미들웨어 필수 등록
* **주의사항:** React 개발 서버(`http://localhost:5173`)에서 FastAPI 백엔드(`http://localhost:8000`)의 제어 API(`POST /api/control/isolate`)를 호출할 때, 백엔드에 CORS 설정이 없으면 브라우저가 보안 정책상 요청을 차단(`CORS Error`)하여 웹 대시보드의 비상 격리/복원 버튼이 완전히 먹통이 됩니다.
* **해결 코드 (`server.py`):**
  ```python
  from fastapi.middleware.cors import CORSMiddleware

  app.add_middleware(
      CORSMiddleware,
      allow_origins=["*"],  # 개발 단계 전체 허용
      allow_credentials=True,
      allow_methods=["*"],
      allow_headers=["*"],
  )
  ```

### 26) 프론트엔드 환경변수(`VITE_WS_URL`) 및 웹소켓 포트 일치
* **주의사항:** 프론트엔드 코드에 `ws://localhost:8000/ws` 주소를 하드코딩하면, 배포 환경이나 팀원마다 다른 IP/포트 설정 시 웹소켓 연결이 실패합니다.
* **해결 코드 (`frontend/.env`):**
  ```bash
  VITE_API_BASE_URL=http://localhost:8000
  VITE_WS_URL=ws://localhost:8000/ws
  ```
  코드에서는 `import.meta.env.VITE_WS_URL`을 참조하여 환경별 유연성을 확보합니다.

---

## 10. 최종 시연 시나리오 체크리스트

- [ ] **Step 1. 정상 상태:** H_legit $\to$ Server 간 지속적 iPerf3 또는 HTTP 통신 (대시보드: 전체 녹색, PPS 안정).
- [ ] **Step 2. 공격 발발:** H_attacker가 Scapy로 초당 10,000개의 변조 IP SYN 패킷 전송 (S1의 Access 포트로 유입).
- [ ] **Step 3. 2초 내 알림:** S1 포트 통계 급증 $\to$ AI Worker 이상 판정 $\to$ 관제탑에 적색 경보 팝업 및 알림음.
- [ ] **Step 4. 자율 격리:** S1의 공격 유입 포트 즉각 차단 (`Priority 100 In_port Drop`).
- [ ] **Step 5. 무중단 우회:** 혼잡 링크를 경유하던 H_legit의 통신이 S1-S3-S4 대체 경로로 자동 전환되어 정상 통신 유지 확인.
- [ ] **Step 6. 자가 복구:** 공격 스크립트 중단 $\to$ AI 엔진이 정상 통계 감지 $\to$ 차단 해제 및 기본 최단 경로 복귀.
- [ ] **Step 7. 수동 제어:** 관리자가 웹 대시보드에서 특정 포트를 클릭하여 비상 강제 격리/복원 버튼 동작 확인.

---

## 11. 클라우드(AWS / GCP) 환경 구축 및 운영 가이드

프로젝트 실행 환경을 로컬 PC가 아닌 **클라우드 가상머신(VM)**으로 구성하는 것은 3인 협업과 최종 발표 시연 측면에서 **매우 강력하게 권장되는 전략**입니다.

### 11.1 클라우드 전환의 3대 이점
1. **3인 실시간 동시 원격 개발 (VS Code Remote-SSH):**
   - 개발자 A의 개인 PC에 묶여있지 않고, 클라우드 VM 1대에 팀원 3명이 각자의 SSH 계정으로 동시 접속하여 코딩 및 디버깅을 함께 진행할 수 있습니다.
2. **개발 머신 사양 종속성 탈피:**
   - 팀원들의 개인 노트북 OS(Windows, Mac Apple Silicon 등)나 RAM 용량(8GB 등)에 구애받지 않고, 항상 표준화된 Ubuntu 22.04 환경을 누릴 수 있습니다.
3. **무중단 발표/시연 편의성 극대화:**
   - 최종 발표 시 노트북 핫스팟 연결, 로컬 IP 변경, 포트포워딩 등의 번거로움 없이 **발표장 빔프로젝터 PC나 평가위원 스마트폰에서 `http://<클라우드-공인IP>` 링크 하나로 즉시 대시보드 접속 및 실시간 시연**이 가능합니다.

---

### 11.2 추천 플랫폼 및 인스턴스 사양

| 클라우드 플랫폼 | 추천 인스턴스 타입 | 스펙 | 추천 이유 및 주의사항 |
|---|---|---|---|
| **Google Cloud (GCP)**<br>*(가장 추천)* | **`e2-standard-4`** | 4 vCPU, 16GB RAM | 신규 가입 시 **$300 무료 크레딧** 제공 (프로젝트 기간 내 비용 $0). 네트워크 처리량 우수. |
| **AWS** | **`t3.xlarge`** | 4 vCPU, 16GB RAM | 학생용 AWS Educate / Activate 크레딧 활용 용이. 사용하지 않을 때는 인스턴스 중지(Stop) 필수. |

> [!CAUTION]
> **반드시 x86_64 (Intel/AMD) 아키텍처 인스턴스를 선택하십시오.**
> Oracle Cloud의 무료 ARM(Ampere) 인스턴스나 AWS Graviton(ARM64)을 선택하면, Ryu 및 구형 Python 3.8 wheel 컴파일 시 아키텍처 호환성 에러로 빌드가 실패할 수 있습니다.

---

### 11.3 클라우드 보안 그룹(Security Group) 포트 방화벽 수칙

클라우드 VM에서는 외부 접속을 위해 포트를 열어주어야 하지만, **내부 보안 포트가 퍼블릭 인터넷에 노출되면 즉각 랜섬웨어/채굴봇의 표적**이 됩니다.

| 포트 번호 | 서비스 | 허용 대상(Source) | 목적 및 보안 가이드 |
|---|---|---|---|
| **22** | SSH | 0.0.0.0/0 (또는 팀원 IP) | 팀원 원격 터미널 접속 |
| **80** | Nginx (HTTP) | **0.0.0.0/0 (Anywhere)** | 웹 관제탑 접속 (Nginx 리버스 프록시 적용 시) |
| **5173** | Vite React | 0.0.0.0/0 (Anywhere) | 개발 단계 프론트엔드 직접 접속 |
| **8000** | FastAPI | 0.0.0.0/0 (Anywhere) | 개발 단계 WebSocket 및 REST API 직접 통신 |
| **6653** | OpenFlow | **127.0.0.1 (절대 외부 오픈 금지)** | Mininet OVS $\leftrightarrow$ Ryu 로컬 통신만 허용 |
| **6379** | Redis | **127.0.0.1 (절대 외부 오픈 금지)** | **[경고]** 외부 오픈 시 수 분 내 비트코인 채굴 악성코드 감염됨! |

---

### 11.4 Nginx 단일 포트(80) 리버스 프록시 아키텍처 (클라우드 권장)

클라우드 환경에서는 프론트엔드(5173)와 백엔드(8000)를 별도 포트로 열기보다, **Nginx를 앞단에 두어 80번 포트 하나로 웹 UI와 WebSocket을 함께 서빙**하는 구조가 가장 깔끔하고 브라우저 CORS 문제도 원천 차단됩니다.

```nginx
# /etc/nginx/sites-available/default 예시 설정
server {
    listen 80;
    server_name _;

    # 1. React 정적 빌드 파일 서빙
    location / {
        root /home/ubuntu/programming/textgg/frontend/dist;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # 2. FastAPI REST API 프록시
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
    }

    # 3. WebSocket 실시간 스트림 프록시
    location /ws {
        proxy_pass http://127.0.0.1:8000/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
    }
}
```
* **결과:** 클라우드 공인 IP 하나(`http://<공인IP>`)만으로 브라우저 접속, API 호출, 웹소켓 통신이 포트 번호 없이 완벽하게 동작합니다.

---

### 11.5 클라우드 환경에서의 Mininet 구동 여부 검증
* **Q: 클라우드 VM 안에서 Mininet 가상 네트워크가 정상 동작하는가?**
* **A: 100% 정상 작동합니다.**
  - Mininet은 클라우드 제공업체의 물리/가상 VPC 네트워크망을 건드리는 것이 아니라, **할당받은 단일 Ubuntu VM의 커널 내부에서 리눅스 네트워크 네임스페이스(`veth`)와 OVS 브리지로 독립된 가상 토폴로지를 생성**합니다.
  - 따라서 AWS나 GCP의 보안 정책(L2 브로드캐스트 차단 등)의 영향을 전혀 받지 않으며, 로컬 PC와 완전히 동일하게 구동됩니다.

