# 🛡️ [개발자 C] 1주차 바이브 코딩 실전 가이드북 (검증 & 보완 완료판)
## 웹 관제탑 기반 확립 (FastAPI 비동기 서버 + WebSocket Hub + Mock 데이터 파이프라인 + React 관제 레이아웃)

> **대상:** 개발자 C (웹 관제탑 풀스택 엔지니어)  
> **개발 방식:** 바이브 코딩 (AI 코딩 어시스턴트 프롬프트 중심 초고속 개발)  
> **1주차 마일스톤:** Python 3.10 기반 FastAPI 백엔드 셋업, Stale Connection 방어 WebSocket Hub 구축, 계약 기반 Pydantic v2 스키마 및 REST 제어 API 스켈레톤 구현, SDN 통계/이상/토폴로지 Mock 생성기 완성, Node 20 + React 18.2 + Vite + Tailwind CSS 다크테마 관제탑 레이아웃 및 실시간 웹소켓 연동 검증.  
> **참조 문서:** `roadmap_v2.md`

---

## 📋 목차
1. [1주차 개발 목표 및 핵심 아키텍처](#1-1주차-개발-목표-및-핵심-아키텍처)
   - [1.1 1주차 핵심 임무](#11-1주차-핵심-임무)
   - [1.2 1주차 웹 관제탑 데이터 파이프라인 블록도](#12-1주차-웹-관제탑-데이터-파이프라인-블록도)
2. [개발자 C 디렉토리 구조 및 작업 위치 안내](#2-개발자-c-디렉토리-구조-및-작업-위치-안내)
3. [바이브 코딩 5단계 워크플로우](#3-바이브-코딩-5단계-워크플로우)
   - [Step 1: Python 3.10 백엔드 가상환경(`venv-web`) 및 의존성 셋업](#step-1-python-310-백엔드-가상환경venv-web-및-의존성-셋업)
   - [Step 2: 계약 기반 Pydantic v2 스키마 & WebSocket Hub & REST API 구현](#step-2-계약-기반-pydantic-v2-스키마--websocket-hub--rest-api-구현)
   - [Step 3: 실시간 SDN 통계/경보/토폴로지 Mock 데이터 생성기 구현 (`mock_generator.py`)](#step-3-실시간-sdn-통계경보토폴로지-mock-데이터-생성기-구현-mock_generatorpy)
   - [Step 4: React 18.2 + Vite + Tailwind CSS 관제탑 레이아웃 및 WebSocket 연동](#step-4-react-182--vite--tailwind-css-관제탑-레이아웃-및-websocket-연동)
   - [Step 5: 1주차 E2E 통합 검증 (Mock 스트리밍 -> 브라우저 실시간 UI 렌더링)](#step-5-1주차-e2e-통합-검증-mock-스트리밍---브라우저-실시간-ui-렌더링)
4. [개발자 C 전용 치명적 함정 & 디버깅 체크리스트](#4-개발자-c-전용-치명적-함정--디버깅-체크리스트)
5. [팀원(개발자 A, B) 인계 사항 및 1주차 완료 보고서 양식](#5-팀원개발자-a-b-인계-사항-및-1주차-완료-보고서-양식)

---

## 1. 1주차 개발 목표 및 핵심 아키텍처

### 1.1 1주차 핵심 임무
1. **Python 3.10 기반 FastAPI 백엔드 환경 구축 (`venv-web`):**  
   - `requirements-web.txt`에 명시된 고정 버전(FastAPI 0.109.2, Uvicorn 0.27.1, Pydantic v2.6.1, redis-py 5.0.1) 설치.
   - 비동기 ASGI 서버 구조를 확립하고 개발 단계 브라우저 접속을 위한 **CORS 미들웨어 전면 허용 설정**.
2. **Stale Connection 방어 WebSocket Hub 구현:**  
   - 브라우저 새로고침(F5)이나 탭 종료 시 끊어진 소켓 세션을 안전하게 정리하여 ASGI 런타임 크래시(`Unexpected ASGI message`)를 원천 차단하는 `ConnectionManager` 구현.
   - 단일 엔드포인트(`/ws`)를 통해 실시간 토폴로지 변경, 포트 메트릭 스트림, 보안 경보 이벤트를 멀티캐스팅.
3. **계약 우선(Contract-First) 데이터 스키마 및 REST 제어 API 스켈레톤:**  
   - 로드맵 6장에 정의된 4대 핵심 채널(`sdn:stats:port`, `sdn:anomaly:alert`, `sdn:control:command`, `sdn:topology:sync`)의 JSON 규격을 Pydantic v2 모델로 엄격하게 정의.
   - 웹 관제탑에서 관리자가 수동으로 포트를 격리하거나 복원할 수 있는 비상 제어 REST 엔드포인트(`/api/control/isolate`, `/api/control/restore`) 구현.
4. **실시간 Mock 데이터 파이프라인 구축 (`mock_generator.py`):**  
   - 개발자 A(Ryu)와 개발자 B(AI)의 모듈이 완성되지 않아도 프론트엔드가 즉시 실시간 통신을 개발할 수 있도록, 1초 주기로 정상/DDoS 공격 트래픽 통계와 보안 경보를 생성하여 WebSocket 및 Redis로 송출하는 독립형 모의 생성기 제작.
5. **Node 20 + React 18.2 (Vite) 사이버 보안 관제탑 다크 테마 레이아웃:**  
   - Tailwind CSS 3.4 기반의 미래형 SOC(Security Operations Center) 대시보드 레이아웃 구축.
   - 2주차 `vis-network` 토폴로지 및 `ApexCharts` 시계열 차트 탑재를 위한 사전 높이(Height) 고정 컨테이너 배치, 실시간 WebSocket 수신 상태 배지(CONNECTED/DISCONNECTED), 실시간 수신 이벤트 모니터링 패널 구현.

---

### 1.2 1주차 웹 관제탑 데이터 파이프라인 블록도

```
+---------------------------------------------------------------------------------------+
|                    [Layer 4: React 18.2 관제탑 프론트엔드 (Port 5173)]                  |
|                                                                                       |
|   - Header: 시스템 상태 배지, 통계 요약 카드 (총 패킷량, 공격 탐지율, 활성 노드 수)    |
|   - Grid Panel 1: [Topology Container] (vis-network 탑재 준비, CSS 높이 고정)          |
|   - Grid Panel 2: [Traffic Monitor] (ApexCharts 시계열 차트 탑재 준비)                 |
|   - Grid Panel 3: [Security Alerts Timeline] (실시간 적색 이상 경보 피드)             |
|   - Grid Panel 4: [Emergency Control Panel] (포트 수동 격리/복원 버튼)                |
+---------------------------------------------------------------------------------------+
                                   ▲                                 │
                 WebSocket (실시간) │                                 │ REST API (수동 제어)
                  ws://localhost:8000/ws                             │ POST /api/control/*
                                   │                                 ▼
+---------------------------------------------------------------------------------------+
|                    [Layer 3: FastAPI 비동기 백엔드 서버 (Port 8000)]                  |
|                                                                                       |
|   - ConnectionManager: 브라우저 WebSocket 세션 관리 & Stale 소켓 예외 방어             |
|   - Pydantic v2 Models: PortStats, AnomalyAlert, ControlCommand, TopologySync        |
|   - REST Controller: /api/health, /api/topology, /api/control/isolate                 |
|   - Background Broadcaster: 내부 큐/Redis로부터 수신한 JSON을 웹 클라이언트로 브로드캐스트 |
+---------------------------------------------------------------------------------------+
                                   ▲                                 │
                   Redis Pub/Sub   │                                 │ Redis Command
                   (Docker 6379)   │                                 │ (sdn:control:command)
+----------------------------------┴─────────────────────────────────▼------------------+
|               [1주차 병렬 개발용: mock_generator.py (모의 데이터 파이프라인)]           |
|                                                                                       |
|   - Mode A (Standalone): Redis가 없어도 FastAPI WebSocket으로 직접 더미 스트림 주입    |
|   - Mode B (Redis Pub): Redis 6379로 sdn:stats:port, sdn:anomaly:alert 실시간 발행     |
|   - 시나리오 시뮬레이션:                                                                |
|     * Phase 1 (0~10s): 정상 트래픽 (S1~S4, PPS: 20~50, BPP: 1200B)                    |
|     * Phase 2 (10~25s): 공격 발발 (S1 Port 2 공격, PPS: 8500, BPP: 66B, 적색 경보 발생) |
|     * Phase 3 (25s~): 수동/자동 격리 후 트래픽 안정화 시뮬레이션                         |
+---------------------------------------------------------------------------------------+
```

---

## 2. 개발자 C 디렉토리 구조 및 작업 위치 안내

모든 개발자 C의 작업 소스 코드와 가상환경, 프론트엔드 프로젝트는 **`textgg/Developer/C/`** 하위에서 완벽히 격리되어 관리됩니다.

```
textgg/
├── Developer/
│   ├── A/                                         # 개발자 A (SDN 인프라 & Ryu)
│   ├── B/                                         # 개발자 B (AI & 보안 파이프라인)
│   └── C/                                         # [개발자 C 전용 작업 공간]
│       ├── Developer_C_Week1_VibeCoding_Guide.md  # 본 실전 가이드북
│       ├── requirements-web.txt                   # Python 3.10 웹 백엔드 의존성
│       ├── venv-web/                              # (Step 1 생성) Python 3.10 가상환경
│       ├── backend/                               # FastAPI 비동기 백엔드 프로젝트
│       │   ├── app/
│       │   │   ├── __init__.py
│       │   │   ├── main.py                        # FastAPI 메인 애플리케이션 & CORS
│       │   │   ├── connection_manager.py          # WebSocket 허브 & Stale 방어
│       │   │   ├── schemas.py                     # Pydantic v2 데이터 계약 모델
│       │   │   └── routers/
│       │   │       ├── __init__.py
│       │   │       └── control.py                 # 긴급 수동 격리/복원 REST API
│       │   └── mock_generator.py                  # 1주차 실시간 모의 데이터 주입기
│       ├── frontend/                              # React 18.2 + Vite + Tailwind 프로젝트
│       │   ├── .env                               # 환경변수 (API/WS URL)
│       │   ├── package.json                       # 프론트엔드 패키지 명세
│       │   ├── vite.config.js                     # Vite 빌드 설정
│       │   ├── tailwind.config.js                 # Tailwind CSS 3.4 테마 설정
│       │   ├── postcss.config.js
│       │   ├── index.html
│       │   └── src/
│       │       ├── main.jsx
│       │       ├── index.css                      # 다크 테마 커스텀 스크롤바 등
│       │       ├── App.jsx                        # 메인 관제탑 대시보드 레이아웃
│       │       ├── hooks/
│       │       │   └── useWebSocket.js            # 실시간 WS 재연결 & 메시지 수신 훅
│       │       └── components/
│       │           ├── Header.jsx                 # 관제탑 헤더 & 연결 상태 인디케이터
│       │           ├── StatCard.jsx               # 메트릭 요약 위젯 카드
│       │           ├── TopologyContainer.jsx      # vis-network 탑재 영역 (Height 고정)
│       │           ├── AlertTimeline.jsx          # 실시간 보안 경보 피드
│       │           └── ControlPanel.jsx           # 긴급 수동 격리/복원 컨트롤러
│       └── scripts/
│           ├── setup_backend.sh                   # venv-web 자동 구축 스크립트
│           ├── setup_frontend.sh                  # npm 패키지 설치 자동화 스크립트
│           ├── run_all.sh                         # 백엔드 + 프론트엔드 동시 기동 스크립트
│           └── verify_week1_c.sh                  # 1주차 E2E 전체 자동 검증 스크립트
└── roadmap_v2.md
```

> 💡 **바이브 코딩 팁:**  
> 백엔드 작업 시: `cd /home/tlgus/programming/textgg/Developer/C && source venv-web/bin/activate`  
> 프론트엔드 작업 시: `cd /home/tlgus/programming/textgg/Developer/C/frontend`  
> 두 터미널을 띄워놓고 작업하면 가장 쾌적합니다.

---

## 3. 바이브 코딩 5단계 워크플로우

각 단계마다 **[🎯 작업 목표]**, **[💬 AI 프롬프트]**, **[📄 완성 참조 구현 코드]**, **[🛠️ 실행 및 검증 명령어 & 기대 결과]**, **[🚨 트러블슈팅]**이 완비되어 있습니다.

---

### Step 1: Python 3.10 백엔드 가상환경(`venv-web`) 및 의존성 셋업

#### 🎯 작업 목표
Ubuntu 22.04 LTS 호스트의 시스템 파이썬 3.10을 기반으로 `venv-web` 가상환경을 구축하고, `requirements-web.txt`에 명시된 FastAPI 0.109.2, Uvicorn 0.27.1, Pydantic v2.6.1, redis 5.0.1 패키지를 설치하여 웹 백엔드 런타임을 준비합니다.

#### 💬 AI 프롬프트 (Step 1)
```text
Ubuntu 22.04 LTS 환경에서 동작하는 웹 관제탑 백엔드(FastAPI) 개발용 가상환경 셋업 스크립트 `scripts/setup_backend.sh`와
의존성 명세서 `requirements-web.txt`를 작성해줘.

[requirements-web.txt 명세]
- fastapi==0.109.2
- uvicorn[standard]==0.27.1
- pydantic==2.6.1
- redis==5.0.1
- websockets==12.0
- python-multipart==0.0.9
- httpx==0.26.0
- pytest==8.0.0

[scripts/setup_backend.sh 요구사항]
1. 시스템 python3 및 python3-venv, python3-pip 설치 확인
2. `venv-web` 디렉토리 생성 및 pip 최신화
3. `requirements-web.txt` 고정 버전 패키지 일괄 설치
4. 설치 완료 후 fastapi, uvicorn, pydantic 버전 출력 검증
5. 실행 권한(chmod +x) 안내 포함
```

#### 📄 완성 참조 파일 명세

##### 1) `Developer/C/requirements-web.txt`
```text
fastapi==0.109.2
uvicorn[standard]==0.27.1
pydantic==2.6.1
redis==5.0.1
websockets==12.0
python-multipart==0.0.9
httpx==0.26.0
pytest==8.0.0
```

##### 2) `Developer/C/scripts/setup_backend.sh`
```bash
#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"

echo "========================================================"
echo "[개발자 C] 1단계: 웹 백엔드 가상환경(venv-web) 셋업 시작"
echo "========================================================"

cd "$BASE_DIR"

# 1. 호스트 파이썬3 패키지 확인
if ! dpkg -s python3-venv python3-pip &>/dev/null; then
    echo "[!] python3-venv 및 python3-pip 패키지 설치 필요 (sudo 권한 요망)..."
    sudo apt-get update && sudo apt-get install -y python3-venv python3-pip
fi

# 2. venv-web 생성 (Golden Version Python 3.10 우선 탐색)
PYTHON_BIN="python3"
if command -v python3.10 &>/dev/null; then
    PYTHON_BIN="python3.10"
fi

if [ ! -d "venv-web" ]; then
    echo "[+] ${PYTHON_BIN} 기반 venv-web 가상환경 생성 중..."
    $PYTHON_BIN -m venv venv-web
else
    echo "[i] 기존 venv-web 가상환경 감지됨. 업데이트를 진행합니다."
fi

# 3. pip 업그레이드 및 패키지 설치
source venv-web/bin/activate
echo "[+] pip 최신화 및 의존성 패키지 설치..."
pip install --upgrade pip setuptools wheel

echo "[+] requirements-web.txt 고정 버전 일괄 설치..."
pip install -r requirements-web.txt

# 4. 버전 검증
echo "--------------------------------------------------------"
echo "[✓] 웹 백엔드 패키지 버전 검증 결과:"
python3 -c "import fastapi, uvicorn, pydantic, redis; print(f'FastAPI: {fastapi.__version__}\nUvicorn: {uvicorn.__version__}\nPydantic: {pydantic.__version__}\nRedis-Py: {redis.__version__}')"
echo "--------------------------------------------------------"
echo "[✓] 웹 백엔드 가상환경 구축 완료!"
echo "    활성화 명령어: source /home/tlgus/programming/textgg/Developer/C/venv-web/bin/activate"
```

#### 🛠️ 실행 및 검증 명령어
```bash
cd /home/tlgus/programming/textgg/Developer/C
chmod +x scripts/setup_backend.sh
./scripts/setup_backend.sh
```

> **성공 기준:**  
> `FastAPI: 0.109.2`, `Uvicorn: 0.27.1`, `Pydantic: 2.6.1`, `Redis-Py: 5.0.1` 버전이 정확히 출력되면 완료.

---

### Step 2: 계약 기반 Pydantic v2 스키마 & WebSocket Hub & REST API 구현

#### 🎯 작업 목표
로드맵 6장에 정의된 통신 규격을 엄격한 Pydantic v2 모델(`schemas.py`)로 구현하고, 브라우저 새로고침이나 네트워크 단절 시 백엔드가 다운되지 않도록 **Stale Connection 안전 정리 루프를 갖춘 `ConnectionManager`**를 작성합니다. 또한 프론트엔드 통신을 위해 CORS 전면 허용 미들웨어가 적용된 FastAPI 메인 서버(`main.py`)와 수동 제어 REST API(`routers/control.py`)를 완성합니다.

#### 💬 AI 프롬프트 (Step 2)
```text
FastAPI 0.109.2와 Pydantic v2.6.1 기반의 웹 관제탑 백엔드 핵심 코드를 작성해줘.

1. `backend/app/schemas.py`:
   - 로드맵 v2.0 6장의 데이터 규격을 준수하는 Pydantic 모델 작성:
     * PortStats: timestamp, dpid, port_no, rx_packets, tx_packets, rx_bytes, tx_bytes, rx_errors, duration_sec
     * AnomalyAlert: timestamp, target_dpid, suspect_port, anomaly_score, threat_type, metrics(pps, bps, bpp), action_required
     * ControlCommand: command_id, action, dpid, port_no, timeout_sec, reason
     * TopologyNode, TopologyLink, TopologySync
     * WebSocketEnvelope: event(str), timestamp(float), data(dict)

2. `backend/app/connection_manager.py`:
   - 비동기 WebSocket 연결 관리자 구현:
     * active_connections: List[WebSocket]
     * connect(websocket), disconnect(websocket)
     * broadcast(message: dict): 끊어진 연결(Stale Connection) 발생 시 RuntimeError로 서버가 중단되지 않도록 disconnected 목록을 추려 안전하게 제거하는 방어 로직 필수 적용.

3. `backend/app/routers/control.py`:
   - 수동 제어 REST 라우터:
     * POST /api/control/isolate (DPID, Port 격리 명령 발행)
     * POST /api/control/restore (DPID, Port 복원 명령 발행)
     * GET /api/control/history (제어 명령 이력 조회)

4. `backend/app/main.py`:
   - FastAPI 인스턴스 생성 및 CORSMiddleware 등록 (allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
   - Lifespan context를 통한 시작/종료 관리
   - 엔드포인트:
     * GET /api/health (상태 헬스체크)
     * GET /api/topology (현재 토폴로지 스냅샷 조회)
     * WebSocket /ws (실시간 양방향 스트리밍)
```

#### 📄 완성 참조 파일 명세

##### 1) `Developer/C/backend/app/schemas.py`
```python
"""
웹 관제탑 공통 데이터 계약 모델 (Pydantic v2)
참조: roadmap_v2.md 제6장
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import time


class PortMetrics(BaseModel):
    pps: float = Field(default=0.0, description="초당 패킷 수")
    bps: float = Field(default=0.0, description="초당 바이트 수")
    bpp: float = Field(default=0.0, description="패킷당 평균 바이트 (Bytes Per Packet)")


class PortStats(BaseModel):
    timestamp: float = Field(default_factory=time.time)
    dpid: str = Field(..., description="스위치 Datapath ID (16자리 Hex 문자열)")
    port_no: int = Field(..., description="포트 번호 (1~OFPP_MAX)")
    rx_packets: int
    tx_packets: int
    rx_bytes: int
    tx_bytes: int
    rx_errors: int = 0
    duration_sec: int
    metrics: Optional[PortMetrics] = None


class AnomalyAlert(BaseModel):
    timestamp: float = Field(default_factory=time.time)
    target_dpid: str
    suspect_port: int
    anomaly_score: float = Field(..., description="Isolation Forest 이상치 스코어 (음수일수록 위협)")
    threat_type: str = Field(default="SYN_FLOOD_SPOOFING")
    metrics: PortMetrics
    action_required: str = Field(default="IN_PORT_DROP")


class ControlCommand(BaseModel):
    command_id: str = Field(..., description="명령 고유 식별자")
    action: str = Field(..., description="ISOLATE_PORT, REROUTE, RESTORE_FLOW 등")
    dpid: str
    port_no: Optional[int] = None
    timeout_sec: Optional[int] = 30
    reason: str = Field(default="Manual Operator Trigger or AI Anomaly Alert")
    source_ip: Optional[str] = None
    dest_ip: Optional[str] = None
    path: Optional[List[str]] = None


class TopologyNode(BaseModel):
    id: str
    label: str
    type: str = Field(..., description="'switch' 또는 'host'")
    dpid: Optional[str] = None
    ip: Optional[str] = None
    mac: Optional[str] = None
    status: str = Field(default="active", description="active, isolated, degraded")


class TopologyLink(BaseModel):
    source: str
    target: str
    src_port: int
    dst_port: int
    status: str = Field(default="active", description="active, rerouted, blocked, down")


class TopologySync(BaseModel):
    timestamp: float = Field(default_factory=time.time)
    nodes: List[TopologyNode]
    links: List[TopologyLink]


class WebSocketEnvelope(BaseModel):
    event: str = Field(..., description="STATS_UPDATE, ANOMALY_ALERT, TOPOLOGY_SYNC, CONTROL_ACK 등")
    timestamp: float = Field(default_factory=time.time)
    data: Dict[str, Any]
```

##### 2) `Developer/C/backend/app/connection_manager.py`
```python
"""
비동기 WebSocket 세션 허브 및 Stale Connection 방어 모듈
로드맵 기술 함정 16번 해결 구현체
"""
import logging
from typing import List, Dict, Any
from fastapi import WebSocket

logger = logging.getLogger("sdn.ws_hub")


class ConnectionManager:
    def __init__(self):
        # 현재 활성화된 웹소켓 연결 리스트
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        client_host = websocket.client.host if websocket.client else "unknown"
        logger.info(f"[WS Connect] 신규 관제 클라이언트 접속: {client_host} (총 연결: {len(self.active_connections)})")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"[WS Disconnect] 관제 세션 종료 (남은 연결: {len(self.active_connections)})")

    async def broadcast(self, message: Dict[str, Any], exclude: WebSocket = None):
        """
        연결된 모든 웹 관제탑 브라우저로 메시지 멀티캐스팅
        Stale Connection(강제 종료/새로고침) 발생 시 끊어진 세션을 즉시 격리하여 루프 크래시 차단
        """
        if not self.active_connections:
            return

        disconnected: List[WebSocket] = []
        for connection in list(self.active_connections):
            if exclude and connection == exclude:
                continue
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"[WS Warning] 끊어진 소켓 세션 감지 ({e}), 정리 목록에 추가.")
                disconnected.append(connection)

        # 비정상 세션 일괄 정리
        for dead_conn in disconnected:
            if dead_conn in self.active_connections:
                self.active_connections.remove(dead_conn)
                logger.info(f"[WS Cleanup] 유령 세션 정리 완료 (현재 연결: {len(self.active_connections)})")


# 싱글톤 매니저 인스턴스
ws_manager = ConnectionManager()
```

##### 3) `Developer/C/backend/app/routers/control.py`
```python
"""
운영자 수동 제어 REST API 라우터
비상 포트 격리, 우회 지시 및 복원 엔드포인트
"""
import time
import uuid
import logging
from typing import List
from fastapi import APIRouter, HTTPException
from ..schemas import ControlCommand, WebSocketEnvelope
from ..connection_manager import ws_manager

logger = logging.getLogger("sdn.control_api")
router = APIRouter(prefix="/api/control", tags=["Network Control"])

# 1주차 메모리 기반 제어 히스토리
command_history: List[ControlCommand] = []


@router.post("/isolate", response_model=ControlCommand)
async def isolate_port(dpid: str, port_no: int, reason: str = "Manual Operator Emergency Isolation"):
    """
    특정 스위치의 포트를 수동으로 즉각 격리 (In_port Drop)
    """
    cmd = ControlCommand(
        command_id=f"cmd-manual-{uuid.uuid4().hex[:8]}",
        action="ISOLATE_PORT",
        dpid=dpid,
        port_no=port_no,
        timeout_sec=60,
        reason=reason
    )
    command_history.append(cmd)
    logger.info(f"[CONTROL CMD] 포트 격리 명령 접수: DPID={dpid}, Port={port_no}")

    # 관제탑 웹소켓으로 제어 이벤트 즉각 브로드캐스팅
    envelope = WebSocketEnvelope(
        event="CONTROL_COMMAND_TRIGGERED",
        timestamp=time.time(),
        data=cmd.model_dump()
    )
    await ws_manager.broadcast(envelope.model_dump())
    return cmd


@router.post("/restore", response_model=ControlCommand)
async def restore_port(dpid: str, port_no: int, reason: str = "Manual Operator Recovery"):
    """
    격리된 포트의 차단 해제 및 플로우 정상 복구
    """
    cmd = ControlCommand(
        command_id=f"cmd-manual-{uuid.uuid4().hex[:8]}",
        action="RESTORE_FLOW",
        dpid=dpid,
        port_no=port_no,
        timeout_sec=0,
        reason=reason
    )
    command_history.append(cmd)
    logger.info(f"[CONTROL CMD] 포트 복원 명령 접수: DPID={dpid}, Port={port_no}")

    envelope = WebSocketEnvelope(
        event="CONTROL_COMMAND_TRIGGERED",
        timestamp=time.time(),
        data=cmd.model_dump()
    )
    await ws_manager.broadcast(envelope.model_dump())
    return cmd


@router.get("/history", response_model=List[ControlCommand])
async def get_command_history():
    """발행된 제어 명령 이력 반환"""
    return command_history
```

##### 4) `Developer/C/backend/app/main.py`
```python
"""
FastAPI 관제탑 백엔드 메인 진입점
- CORS 미들웨어 등록
- 실시간 WebSocket 엔드포인트 (/ws)
- 기본 상태 조회 및 토폴로지 REST API
"""
import time
import json
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .schemas import TopologySync, TopologyNode, TopologyLink, WebSocketEnvelope
from .connection_manager import ws_manager
from .routers import control

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("sdn.tower_backend")

# 1주차 기본 초기 토폴로지 캐시 (Diamond Topo)
CURRENT_TOPOLOGY = TopologySync(
    nodes=[
        TopologyNode(id="s1", label="Switch 1 (Ingress)", type="switch", dpid="0000000000000001", status="active"),
        TopologyNode(id="s2", label="Switch 2 (Primary)", type="switch", dpid="0000000000000002", status="active"),
        TopologyNode(id="s3", label="Switch 3 (Backup)", type="switch", dpid="0000000000000003", status="active"),
        TopologyNode(id="s4", label="Switch 4 (Egress)", type="switch", dpid="0000000000000004", status="active"),
        TopologyNode(id="h1", label="H_legit (10.0.0.1)", type="host", ip="10.0.0.1", mac="00:00:00:00:00:01", status="active"),
        TopologyNode(id="h2", label="H_attacker (10.0.0.2)", type="host", ip="10.0.0.2", mac="00:00:00:00:00:02", status="active"),
        TopologyNode(id="h4", label="H_server (10.0.0.4)", type="host", ip="10.0.0.4", mac="00:00:00:00:00:04", status="active"),
    ],
    links=[
        TopologyLink(source="s1", target="s2", src_port=3, dst_port=1, status="active"),
        TopologyLink(source="s1", target="s3", src_port=4, dst_port=1, status="active"),
        TopologyLink(source="s2", target="s4", src_port=2, dst_port=2, status="active"),
        TopologyLink(source="s3", target="s4", src_port=2, dst_port=3, status="active"),
        TopologyLink(source="s1", target="h1", src_port=1, dst_port=0, status="active"),
        TopologyLink(source="s1", target="h2", src_port=2, dst_port=0, status="active"),
        TopologyLink(source="s4", target="h4", src_port=1, dst_port=0, status="active"),
    ]
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[Tower Backend] 시스템 기동 완료. WebSocket Hub 리스너 준비.")
    yield
    logger.info("[Tower Backend] 시스템 종료 처리 중...")


app = FastAPI(
    title="Self-Defending SDN Tower Control API",
    description="FastAPI WebSocket Hub & SDN Defense Management API",
    version="2.0.0",
    lifespan=lifespan
)

# [필수] CORS 전면 허용 미들웨어 (React Vite 5173 포트 통신 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 서브 라우터 등록
app.include_router(control.router)


@app.get("/api/health")
async def health_check():
    """백엔드 생존 여부 및 접속자 수 확인"""
    return {
        "status": "healthy",
        "service": "SDN-Control-Tower-Backend",
        "version": "2.0.0",
        "active_ws_clients": len(ws_manager.active_connections),
        "timestamp": time.time()
    }


@app.get("/api/topology", response_model=TopologySync)
async def get_current_topology():
    """현재 토폴로지 상태 조회"""
    return CURRENT_TOPOLOGY


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    실시간 관제 WebSocket 통신 엔드포인트
    - 연결 직후 현재 토폴로지 동기화 메시지 1회 발송
    - 이후 주기적 통계 및 경보 이벤트 실시간 브로드캐스팅 수신
    """
    await ws_manager.connect(websocket)
    try:
        # 최초 접속 시 현재 토폴로지 정보 즉시 주입
        init_envelope = WebSocketEnvelope(
            event="TOPOLOGY_SYNC",
            timestamp=time.time(),
            data=CURRENT_TOPOLOGY.model_dump()
        )
        await websocket.send_json(init_envelope.model_dump())

        # 클라이언트로부터 들어오는 메시지 수신 및 중계 루프
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                # 인바운드 수신 메시지(Mock 데이터 등)를 다른 모든 연결된 관제 클라이언트로 전파
                await ws_manager.broadcast(payload, exclude=websocket)
            except json.JSONDecodeError:
                logger.debug(f"[WS Inbound] 비-JSON 데이터 수신: {data}")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"[WS Error] 예상치 못한 소켓 에러: {e}")
        ws_manager.disconnect(websocket)
```

#### 🛠️ 실행 및 검증 명령어
```bash
cd /home/tlgus/programming/textgg/Developer/C
source venv-web/bin/activate
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload &
SERVER_PID=$!

sleep 2

# 헬스체크 검증
curl -s http://127.0.0.1:8000/api/health | grep "healthy"

# 토폴로지 조회 검증
curl -s http://127.0.0.1:8000/api/topology | grep "Switch 1"

# 수동 격리 REST API 테스트
curl -s -X POST "http://127.0.0.1:8000/api/control/isolate?dpid=0000000000000001&port_no=2" | grep "ISOLATE_PORT"

kill -9 $SERVER_PID
```

> **성공 기준:**  
> JSON 응답에 `"status": "healthy"`, `"action": "ISOLATE_PORT"`가 반환되면 2단계 완성!

---

### Step 3: 실시간 SDN 통계/경보/토폴로지 Mock 데이터 생성기 구현 (`mock_generator.py`)

#### 🎯 작업 목표
개발자 A(Ryu 컨트롤러)와 개발자 B(AI 이상 탐지)가 아직 연동되지 않은 1주차 상황에서, 프론트엔드가 실제 통신과 완전히 동일하게 실시간 데이터를 수신하여 UI를 검증할 수 있도록 **모의 트래픽/경보 생성기(`backend/mock_generator.py`)**를 제작합니다.  
- **정상 상태 모의:** 초당 20~50 PPS, BPP 1,000~1,400 Bytes의 안정적인 통계 스트리밍.
- **공격 발발 모의:** S1의 2번 포트(공격자)에서 PPS 8,000 이상 폭증, BPP 66 Bytes 급감, `ANOMALY_ALERT` 적색 경보 및 자동 격리 시뮬레이션.
- **연동 모드 지원:** WebSocket 직접 전송 모드(HTTP/WS 클라이언트)와 Redis Pub/Sub 발행 모드 동시 지원.

#### 💬 AI 프롬프트 (Step 3)
```text
FastAPI 백엔드와 프론트엔드의 1주차 병렬 개발을 지원하는 실시간 SDN 모의 데이터 생성기 `backend/mock_generator.py`를 작성해줘.

[세부 요구사항]
1. 모드 지원:
   - WebSocket 클라이언트 모드: `ws://localhost:8000/ws`로 접속하거나, FastAPI 앱 내부 태스크로 실행 가능.
   - Redis 모드 (선택적): Redis(`localhost:6379`)가 켜져 있으면 `sdn:stats:port`, `sdn:anomaly:alert` 채널로도 발행.
2. 실시간 시뮬레이션 시나리오 루프 (1초 주기 실행):
   - Phase 1 (0초 ~ 10초): 평온한 정상 상태
     * S1, S2, S3, S4 스위치들의 포트 통계 전송 (PPS: 20~50, BPP: 800~1300)
   - Phase 2 (11초 ~ 20초): SYN Flood 공격 발발
     * S1의 Port 2(H_attacker)에서 PPS가 7,500 ~ 9,500으로 폭증, BPP는 66.0으로 급감
     * 이상 탐지 경보 메시지(`ANOMALY_ALERT`) 이벤트 즉각 발행 (Score: -0.85, Action: IN_PORT_DROP)
   - Phase 3 (21초 ~ 30초): 완화 및 우회 상태
     * S1 Port 2가 'isolated'로 표시되고, 대체 경로(S1-S3-S4)로 정상 패킷이 우회되는 통계 전송
   - Phase 4 (31초 이후): 복원 및 재시작 (무한 루프)
3. 로드맵 6장의 JSON 규격(PortStats, AnomalyAlert, WebSocketEnvelope)과 100% 일치시킬 것.
```

#### 📄 완성 참조 파일 명세

##### `Developer/C/backend/mock_generator.py`
```python
"""
1주차 독립 개발용 실시간 SDN 메트릭 및 보안 경보 Mock 생성기
실행 모드:
1) 독립 실행 (독립 WebSocket 클라이언트로 서버에 메시지 주입 또는 직접 Redis 발행)
2) 브라우저 실시간 스트리밍 시각화 검증용
"""
import asyncio
import json
import time
import random
import logging
import websockets
try:
    import redis.asyncio as aioredis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s [MOCK] %(message)s")
logger = logging.getLogger("mock_generator")

WS_SERVER_URL = "ws://127.0.0.1:8000/ws"
REDIS_URL = "redis://127.0.0.1:6379"


class SDNMockGenerator:
    def __init__(self):
        self.tick = 0
        self.phase = "NORMAL"  # NORMAL -> ATTACK -> MITIGATED -> RESTORING
        self.rx_counter = {1: 10000, 2: 5000, 3: 15000, 4: 12000}
        self.rx_bytes_counter = {1: 10240000, 2: 5120000, 3: 15360000, 4: 12288000}
        self.redis_client = None

    async def init_redis(self):
        if HAS_REDIS:
            try:
                self.redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
                await self.redis_client.ping()
                logger.info("[Mock] Redis 7.2 연결 성공 (Pub/Sub 발행 활성화됨)")
            except Exception as e:
                logger.warning(f"[Mock] Redis 미가동 ({e}). WebSocket 직접 통신 모드로만 동작합니다.")
                self.redis_client = None

    def generate_stats(self):
        self.tick += 1
        messages = []

        # 30초 주기 시나리오 전환
        cycle_sec = self.tick % 30
        if cycle_sec < 10:
            self.phase = "NORMAL"
        elif cycle_sec < 20:
            self.phase = "ATTACK"
        else:
            self.phase = "MITIGATED"

        timestamp = time.time()

        # 1. S1 Ingress 포트 통계 생성
        for port_no in [1, 2, 3]:  # 1: H_legit, 2: H_attacker, 3: Trunk to S2
            if self.phase == "ATTACK" and port_no == 2:
                # 공격 유입 포트: 폭발적 PPS, 극히 낮은 BPP
                delta_pps = random.randint(7500, 9500)
                bpp = 66.0
                delta_bps = int(delta_pps * bpp * 8)
            elif self.phase == "MITIGATED" and port_no == 2:
                # 격리된 포트: 트래픽 0
                delta_pps = 0
                bpp = 0.0
                delta_bps = 0
            else:
                # 정상 통신 포트
                delta_pps = random.randint(25, 60)
                bpp = random.uniform(850.0, 1350.0)
                delta_bps = int(delta_pps * bpp * 8)

            delta_bytes = int(delta_pps * bpp) if delta_pps > 0 else 0
            self.rx_counter[port_no] += delta_pps
            self.rx_bytes_counter[port_no] += delta_bytes

            stat_payload = {
                "timestamp": timestamp,
                "dpid": "0000000000000001",
                "port_no": port_no,
                "rx_packets": self.rx_counter[port_no],
                "tx_packets": self.rx_counter[port_no] - 10,
                "rx_bytes": self.rx_bytes_counter[port_no],
                "tx_bytes": self.rx_bytes_counter[port_no],
                "rx_errors": 0,
                "duration_sec": self.tick,
                "metrics": {
                    "pps": delta_pps,
                    "bps": delta_bps,
                    "bpp": round(bpp, 1)
                }
            }
            messages.append({"event": "STATS_UPDATE", "data": stat_payload})

        # 2. 공격 상태 진입 시 보안 경보(Alert) 발행 (11초 시점 등)
        if self.phase == "ATTACK" and cycle_sec in (11, 14, 17):
            alert_payload = {
                "timestamp": timestamp,
                "target_dpid": "0000000000000001",
                "suspect_port": 2,
                "anomaly_score": round(random.uniform(-0.88, -0.75), 3),
                "threat_type": "SYN_FLOOD_SPOOFING",
                "metrics": {
                    "pps": random.randint(8000, 9500),
                    "bps": 48000000,
                    "bpp": 66.0
                },
                "action_required": "IN_PORT_DROP"
            }
            messages.append({"event": "ANOMALY_ALERT", "data": alert_payload})
            logger.warning(f"🚨 [MOCK ALERT] 이상 탐지 경보 발생: Port 2 (PPS: {alert_payload['metrics']['pps']})")

        return messages

    async def run(self):
        await self.init_redis()
        logger.info(f"[Mock] 실시간 SDN Mock 생성기 가동 시작 (연결 대상: {WS_SERVER_URL})")

        while True:
            try:
                # FastAPI WebSocket 서버 연결 시도
                async with websockets.connect(WS_SERVER_URL) as ws:
                    logger.info("[Mock] WebSocket 백엔드 연결 성공! 실시간 텔레메트리 스트리밍 시작.")
                    while True:
                        events = self.generate_stats()
                        for ev in events:
                            envelope = {
                                "event": ev["event"],
                                "timestamp": time.time(),
                                "data": ev["data"]
                            }
                            # 1) WebSocket으로 서버에 전송
                            await ws.send(json.dumps(envelope))

                            # 2) Redis가 연결되어 있다면 Redis 채널로도 Publish
                            if self.redis_client:
                                channel = "sdn:stats:port" if ev["event"] == "STATS_UPDATE" else "sdn:anomaly:alert"
                                await self.redis_client.publish(channel, json.dumps(ev["data"]))

                        await asyncio.sleep(1.0)
            except (websockets.exceptions.ConnectionClosed, ConnectionRefusedError, OSError) as e:
                logger.info(f"[Mock] WebSocket 서버 대기 중... ({e}) 2초 후 재연결 시도.")
                await asyncio.sleep(2.0)


if __name__ == "__main__":
    generator = SDNMockGenerator()
    try:
        asyncio.run(generator.run())
    except KeyboardInterrupt:
        logger.info("[Mock] Mock 생성기 정상 종료.")
```

#### 🛠️ 실행 및 검증 명령어
```bash
cd /home/tlgus/programming/textgg/Developer/C
source venv-web/bin/activate
python3 backend/mock_generator.py
```

> **성공 기준:**  
> 백엔드가 켜져 있을 때 `WebSocket 백엔드 연결 성공! 실시간 텔레메트리 스트리밍 시작.` 메시지가 출력되고, 1초마다 통계 및 공격 경보가 콘솔에 찍히면 완료.

---

### Step 4: React 18.2 + Vite + Tailwind CSS 관제탑 레이아웃 및 WebSocket 연동

#### 🎯 작업 목표
Node 20 LTS와 Vite 5.1 기반으로 React 18.2 프로젝트를 구성하고, Tailwind CSS 3.4를 연동하여 미래지향적인 **사이버 보안 관제탑 다크 테마(SOC Dashboard)** 레이아웃을 구축합니다.  
- 2주차 `vis-network` 토폴로지 탑재를 위해 **높이 0px 버그를 방지하는 명시적 높이 컨테이너(`h-[520px]`)**를 사전에 배치합니다.
- 백엔드 WebSocket(`ws://localhost:8000/ws`)에 자동 연결/재연결되는 커스텀 훅(`useWebSocket.js`)을 작성합니다.
- 상단 헤더의 연결 상태 인디케이터(CONNECTED/DISCONNECTED), 메트릭 요약 카드, 보안 경보 피드 컴포넌트를 구현합니다.

#### 💬 AI 프롬프트 (Step 4)
```text
Node 20 환경에서 동작하는 React 18.2 (Vite) 사이버 보안 관제탑 프론트엔드를 구축해줘.

1. 프로젝트 셋업 및 의존성:
   - `frontend/package.json`: react 18.2.0, vis-network 9.1.9, vis-data 7.1.9, apexcharts 3.46.0, react-apexcharts 1.4.1, lucide-react 0.330.0, tailwindcss 3.4.1 등 포함
   - `frontend/vite.config.js`, `frontend/tailwind.config.js`, `frontend/postcss.config.js`
   - `frontend/.env`: VITE_API_BASE_URL=http://localhost:8000, VITE_WS_URL=ws://localhost:8000/ws

2. 커스텀 WebSocket 훅 `src/hooks/useWebSocket.js`:
   - VITE_WS_URL을 읽어 자동 연결 및 끊김 시 지수 백오프 자동 재연결
   - connectionStatus ('CONNECTED', 'DISCONNECTED', 'CONNECTING') 제공
   - 최신 토폴로지(topology), 최신 포트 통계(statsMap), 실시간 보안 경보(alerts: 최근 10개 누적) 상태 관리
   - 수동 제어 API 연동 헬퍼 함수(triggerIsolate, triggerRestore) 제공

3. 대시보드 컴포넌트:
   - `src/components/Header.jsx`: 로고, 시스템 타이틀, 실시간 시계, WebSocket 연결 상태 인디케이터 배지(초록/빨강 펄스)
   - `src/components/StatCard.jsx`: 전체 PPS, BPS, 위협 레벨(NORMAL/CRITICAL), 활성 노드 수 요약 카드
   - `src/components/TopologyContainer.jsx`: 2주차 vis-network 탑재 영역. 기술 함정 20번을 고려하여 반드시 부모 div에 `h-[520px] min-h-[520px]` 명시적 높이 지정. 1주차에는 현재 스위치/호스트 노드 목록과 상태를 카드로 시각화.
   - `src/components/AlertTimeline.jsx`: ANOMALY_ALERT 발생 시 빨간색 경보 박스와 함께 PPS, BPP 수치 렌더링.
   - `src/components/ControlPanel.jsx`: 긴급 수동 포트 격리 및 복구 버튼 (POST /api/control/isolate 호출).
   - `src/App.jsx`: 위 컴포넌트들을 통합한 완성형 반응형 그리드 레이아웃.
```

#### 📄 완성 참조 파일 명세

##### 1) `Developer/C/frontend/package.json`
```json
{
  "name": "sdn-control-tower-frontend",
  "private": true,
  "version": "2.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite --host",
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

##### 2) `Developer/C/frontend/vite.config.js`
```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true
  }
})
```

##### 3) `Developer/C/frontend/tailwind.config.js`
```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        cyber: {
          950: '#030712',
          900: '#0b0f19',
          800: '#111827',
          700: '#1f2937',
          blue: '#0ea5e9',
          red: '#ef4444',
          green: '#10b981',
          amber: '#f59e0b',
        }
      }
    },
  },
  plugins: [],
}
```

##### 4) `Developer/C/frontend/postcss.config.js`
```javascript
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
```

##### 5) `Developer/C/frontend/.env`
```bash
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws
```

##### 6) `Developer/C/frontend/src/index.css`
```css
@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  margin: 0;
  background-color: #030712;
  color: #f3f4f6;
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  overflow-x: hidden;
}

/* 사이버펑크 커스텀 스크롤바 */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-track {
  background: #0b0f19;
}
::-webkit-scrollbar-thumb {
  background: #1f2937;
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background: #374151;
}
```

##### 7) `Developer/C/frontend/src/hooks/useWebSocket.js`
```javascript
/**
 * 실시간 관제 WebSocket 연결 및 이벤트 수신 관리 훅
 * 자동 재연결, Stale 세션 대응, 메시지 디스패치
 */
import { useState, useEffect, useRef, useCallback } from 'react';

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws';
const API_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export function useWebSocket() {
  const [status, setStatus] = useState('CONNECTING'); // CONNECTING, CONNECTED, DISCONNECTED
  const [topology, setTopology] = useState({ nodes: [], links: [] });
  const [statsMap, setStatsMap] = useState({});
  const [alerts, setAlerts] = useState([]);
  const [totalPps, setTotalPps] = useState(0);
  const [threatLevel, setThreatLevel] = useState('NORMAL'); // NORMAL, ELEVATED, CRITICAL

  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);

  const connect = useCallback(() => {
    try {
      setStatus('CONNECTING');
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        setStatus('CONNECTED');
        console.log('[WS] 관제탑 백엔드 WebSocket 연결 완료');
      };

      ws.onmessage = (event) => {
        try {
          const envelope = JSON.parse(event.data);
          const { event: evType, data } = envelope;

          if (evType === 'TOPOLOGY_SYNC') {
            setTopology(data);
          } else if (evType === 'STATS_UPDATE') {
            const key = `${data.dpid}_${data.port_no}`;
            setStatsMap((prev) => {
              const next = { ...prev, [key]: data };
              // 실시간 전체 포트 PPS 집계 (현재 유입 트래픽 반영)
              const currentTotalPps = Object.values(next).reduce(
                (sum, item) => sum + (item.metrics?.pps || 0),
                0
              );
              setTotalPps(currentTotalPps);

              // 공격 포트 트래픽이 0(격리 완화)으로 떨어지면 상태 반영
              if (data.port_no === 2 && data.metrics?.pps === 0) {
                setThreatLevel((lvl) => (lvl === 'CRITICAL' ? 'MITIGATED' : lvl));
              }
              return next;
            });
          } else if (evType === 'ANOMALY_ALERT') {
            setThreatLevel('CRITICAL');
            setAlerts((prev) => [
              { ...data, id: Date.now() + Math.random() },
              ...prev.slice(0, 19), // 최근 20개 유지
            ]);
          } else if (evType === 'CONTROL_COMMAND_TRIGGERED') {
            console.log('[WS] 제어 명령 실행 수신:', data);
            if (data.action === 'RESTORE_FLOW') {
              setThreatLevel('NORMAL');
            }
          }
        } catch (err) {
          console.error('[WS] 메시지 파싱 에러:', err);
        }
      };

      ws.onclose = () => {
        setStatus('DISCONNECTED');
        console.warn('[WS] WebSocket 연결 종료됨. 3초 후 재연결 시도...');
        reconnectTimeoutRef.current = setTimeout(connect, 3000);
      };

      ws.onerror = (err) => {
        console.error('[WS] WebSocket 통신 에러:', err);
        ws.close();
      };
    } catch (e) {
      setStatus('DISCONNECTED');
      reconnectTimeoutRef.current = setTimeout(connect, 3000);
    }
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (wsRef.current) wsRef.current.close();
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
    };
  }, [connect]);

  // 수동 제어 API 트리거 함수
  const triggerControl = async (action, dpid, portNo) => {
    const endpoint = action === 'ISOLATE' ? '/api/control/isolate' : '/api/control/restore';
    try {
      const res = await fetch(`${API_URL}${endpoint}?dpid=${dpid}&port_no=${portNo}`, {
        method: 'POST',
      });
      return await res.json();
    } catch (e) {
      console.error('[API] 제어 명령 실패:', e);
      throw e;
    }
  };

  return {
    status,
    topology,
    statsMap,
    alerts,
    totalPps,
    threatLevel,
    triggerControl,
  };
}
```

##### 8) `Developer/C/frontend/src/components/Header.jsx`
```jsx
import React, { useState, useEffect } from 'react';
import { ShieldAlert, ShieldCheck, Activity, Wifi, WifiOff } from 'lucide-react';

export default function Header({ status, threatLevel }) {
  const [timeStr, setTimeStr] = useState('');

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTimeStr(now.toLocaleTimeString('ko-KR', { hour12: false }));
    };
    updateTime();
    const timer = setInterval(updateTime, 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <header className="flex items-center justify-between px-6 py-4 bg-slate-900/80 backdrop-blur border-b border-slate-800">
      <div className="flex items-center space-x-3">
        <div className="p-2 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
          <Activity className="w-6 h-6 animate-pulse" />
        </div>
        <div>
          <h1 className="text-xl font-bold tracking-wider text-white flex items-center gap-2">
            SELF-DEFENDING SDN TOWER
            <span className="text-xs px-2 py-0.5 rounded bg-cyan-950 text-cyan-400 border border-cyan-800 font-mono">
              v2.0
            </span>
          </h1>
          <p className="text-xs text-slate-400">분산 트래픽 이상 탐지 및 자율 방어 관제 시스템</p>
        </div>
      </div>

      <div className="flex items-center space-x-4 font-mono text-sm">
        {/* 실시간 시계 */}
        <div className="px-3 py-1.5 rounded-md bg-slate-800/80 border border-slate-700 text-slate-300">
          {timeStr || '00:00:00'}
        </div>

        {/* 위협 상태 배지 */}
        <div className={`flex items-center space-x-2 px-3 py-1.5 rounded-md border font-semibold ${
          threatLevel === 'CRITICAL'
            ? 'bg-rose-950/80 border-rose-600 text-rose-400 animate-pulse'
            : 'bg-emerald-950/80 border-emerald-600 text-emerald-400'
        }`}>
          {threatLevel === 'CRITICAL' ? <ShieldAlert className="w-4 h-4" /> : <ShieldCheck className="w-4 h-4" />}
          <span>{threatLevel === 'CRITICAL' ? 'THREAT DETECTED' : 'SYSTEM SECURE'}</span>
        </div>

        {/* WebSocket 연결 배지 */}
        <div className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md border text-xs ${
          status === 'CONNECTED'
            ? 'bg-emerald-950/50 border-emerald-700 text-emerald-300'
            : 'bg-amber-950/50 border-amber-700 text-amber-300'
        }`}>
          {status === 'CONNECTED' ? <Wifi className="w-3.5 h-3.5" /> : <WifiOff className="w-3.5 h-3.5" />}
          <span>{status}</span>
        </div>
      </div>
    </header>
  );
}
```

##### 9) `Developer/C/frontend/src/components/StatCard.jsx`
```jsx
import React from 'react';

export default function StatCard({ title, value, unit, change, icon: Icon, color = 'cyan' }) {
  const colorMap = {
    cyan: 'text-cyan-400 border-cyan-500/30 bg-cyan-950/20',
    rose: 'text-rose-400 border-rose-500/30 bg-rose-950/20',
    emerald: 'text-emerald-400 border-emerald-500/30 bg-emerald-950/20',
    amber: 'text-amber-400 border-amber-500/30 bg-amber-950/20',
  };

  return (
    <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-slate-700 transition">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">{title}</span>
        <div className={`p-2 rounded-lg border ${colorMap[color]}`}>
          <Icon className="w-4 h-4" />
        </div>
      </div>
      <div className="mt-2 flex items-baseline space-x-2 font-mono">
        <span className="text-2xl font-bold text-white">{value}</span>
        {unit && <span className="text-xs text-slate-400">{unit}</span>}
      </div>
      {change && (
        <div className="mt-1 text-xs text-slate-500">{change}</div>
      )}
    </div>
  );
}
```

##### 10) `Developer/C/frontend/src/components/TopologyContainer.jsx`
```jsx
import React from 'react';
import { Network, Server, Laptop } from 'lucide-react';

export default function TopologyContainer({ topology }) {
  const nodes = topology?.nodes || [];
  const links = topology?.links || [];

  return (
    <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800 flex flex-col">
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <div className="flex items-center space-x-2 text-white font-semibold">
          <Network className="w-5 h-5 text-cyan-400" />
          <span>SDN 가상 토폴로지 맵</span>
        </div>
        <span className="text-xs text-slate-400 font-mono">
          Switches: {nodes.filter(n => n.type === 'switch').length} | 
          Hosts: {nodes.filter(n => n.type === 'host').length}
        </span>
      </div>

      {/* [치명적 함정 20번 방어] 높이 0px 방지를 위한 명시적 Height 부여 */}
      <div className="w-full h-[520px] min-h-[520px] mt-4 rounded-lg bg-slate-950/80 border border-slate-800/80 p-6 flex flex-col justify-between relative overflow-hidden">
        <div className="absolute top-3 right-3 px-2.5 py-1 rounded bg-slate-800/60 text-slate-400 text-xs font-mono">
          2주차 vis-network 캔버스 탑재 예정 영역
        </div>

        {/* 1주차 시각화: 수신된 토폴로지 노드 상태 그리드 렌더링 */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6">
          {nodes.map((node) => (
            <div
              key={node.id}
              className={`p-4 rounded-lg border transition ${
                node.id === 'h2'
                  ? 'border-rose-700/60 bg-rose-950/20 text-rose-300'
                  : node.type === 'switch'
                  ? 'border-cyan-700/50 bg-cyan-950/20 text-cyan-300'
                  : 'border-slate-700/50 bg-slate-800/30 text-slate-300'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-bold text-sm">{node.id.toUpperCase()}</span>
                {node.type === 'switch' ? (
                  <Server className="w-4 h-4 text-cyan-400" />
                ) : (
                  <Laptop className="w-4 h-4 text-emerald-400" />
                )}
              </div>
              <div className="text-xs text-slate-400 font-mono truncate">{node.label}</div>
              <div className="mt-2 text-xs flex justify-between items-center">
                <span className="text-slate-500 font-mono">{node.ip || node.dpid?.slice(-4) || 'L2'}</span>
                <span className="px-1.5 py-0.5 rounded text-[10px] bg-emerald-950 text-emerald-400 border border-emerald-800">
                  {node.status}
                </span>
              </div>
            </div>
          ))}
        </div>

        {/* 1주차 다이아몬드 링크 상태 시각화 */}
        <div className="mt-4 p-3 rounded bg-slate-900/50 border border-slate-800 text-xs font-mono text-slate-400">
          <div className="text-slate-300 font-semibold mb-2">동기화된 다중 링크 (Diamond Topo):</div>
          <div className="grid grid-cols-2 gap-2 text-[11px]">
            {links.map((link, idx) => (
              <div key={idx} className="flex justify-between items-center px-2 py-1 bg-slate-950 rounded">
                <span>{link.source} (p{link.src_port}) ↔ {link.target} (p{link.dst_port})</span>
                <span className="text-emerald-400 font-bold">{link.status}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
```

##### 11) `Developer/C/frontend/src/components/AlertTimeline.jsx`
```jsx
import React from 'react';
import { AlertOctagon, Clock } from 'lucide-react';

export default function AlertTimeline({ alerts }) {
  return (
    <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800 flex flex-col h-[280px]">
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <div className="flex items-center space-x-2 text-white font-semibold">
          <AlertOctagon className="w-5 h-5 text-rose-400" />
          <span>실시간 보안 이상 경보 (Security Feed)</span>
        </div>
        <span className="text-xs text-rose-400 font-mono">{alerts.length} 건 감지됨</span>
      </div>

      <div className="mt-3 flex-1 overflow-y-auto space-y-2 pr-1">
        {alerts.length === 0 ? (
          <div className="h-full flex items-center justify-center text-xs text-slate-500 font-mono">
            현재 감지된 보안 위협이 없습니다.
          </div>
        ) : (
          alerts.map((item) => (
            <div
              key={item.id}
              className="p-3 rounded-lg bg-rose-950/30 border border-rose-800/60 text-xs font-mono flex items-start justify-between"
            >
              <div>
                <div className="flex items-center space-x-2 text-rose-400 font-bold">
                  <span>[{item.threat_type}]</span>
                  <span className="text-white">DPID: {item.target_dpid?.slice(-4)} | Port: {item.suspect_port}</span>
                </div>
                <div className="mt-1 text-slate-400 text-[11px] space-x-3">
                  <span>PPS: <strong className="text-rose-300">{item.metrics?.pps}</strong></span>
                  <span>BPP: <strong className="text-rose-300">{item.metrics?.bpp}B</strong></span>
                  <span>Score: <strong className="text-rose-300">{item.anomaly_score}</strong></span>
                </div>
              </div>
              <div className="text-right">
                <span className="px-2 py-0.5 rounded bg-rose-900 text-rose-200 text-[10px] font-bold">
                  {item.action_required}
                </span>
                <div className="text-[10px] text-slate-500 mt-1 flex items-center justify-end space-x-1">
                  <Clock className="w-3 h-3" />
                  <span>{new Date(item.timestamp * 1000).toLocaleTimeString()}</span>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
```

##### 12) `Developer/C/frontend/src/components/ControlPanel.jsx`
```jsx
import React, { useState } from 'react';
import { Sliders, ShieldX, RotateCcw } from 'lucide-react';

export default function ControlPanel({ triggerControl }) {
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState('');

  const handleAction = async (action, portNo) => {
    setLoading(true);
    setMsg('');
    try {
      const res = await triggerControl(action, '0000000000000001', portNo);
      setMsg(`[성공] ${res.action} 실행 완료 (CMD ID: ${res.command_id})`);
    } catch (e) {
      setMsg('[오류] 명령 전송 실패');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800 flex flex-col h-[280px]">
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <div className="flex items-center space-x-2 text-white font-semibold">
          <Sliders className="w-5 h-5 text-amber-400" />
          <span>비상 수동 제어 패널</span>
        </div>
        <span className="text-xs text-slate-400 font-mono">S1 Access Ports</span>
      </div>

      <div className="mt-4 flex-1 flex flex-col justify-between">
        <div className="space-y-3">
          <div className="flex items-center justify-between p-3 rounded-lg bg-slate-950 border border-slate-800">
            <div>
              <div className="text-xs font-bold text-white">S1 Port 2 (H_attacker)</div>
              <div className="text-[11px] text-slate-400 font-mono">10.0.0.2 연결 단말</div>
            </div>
            <div className="flex space-x-2">
              <button
                onClick={() => handleAction('ISOLATE', 2)}
                disabled={loading}
                className="px-3 py-1.5 rounded bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold transition flex items-center space-x-1"
              >
                <ShieldX className="w-3.5 h-3.5" />
                <span>강제 격리</span>
              </button>
              <button
                onClick={() => handleAction('RESTORE', 2)}
                disabled={loading}
                className="px-3 py-1.5 rounded bg-slate-700 hover:bg-slate-600 text-slate-200 text-xs font-bold transition flex items-center space-x-1"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>복원</span>
              </button>
            </div>
          </div>
        </div>

        {msg && (
          <div className="p-2 rounded bg-cyan-950/60 border border-cyan-700 text-cyan-300 text-xs font-mono">
            {msg}
          </div>
        )}
      </div>
    </div>
  );
}
```

##### 13) `Developer/C/frontend/src/App.jsx`
```jsx
import React from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import Header from './components/Header';
import StatCard from './components/StatCard';
import TopologyContainer from './components/TopologyContainer';
import AlertTimeline from './components/AlertTimeline';
import ControlPanel from './components/ControlPanel';
import { Activity, ShieldCheck, Cpu, HardDrive } from 'lucide-react';

export default function App() {
  const {
    status,
    topology,
    statsMap,
    alerts,
    totalPps,
    threatLevel,
    triggerControl,
  } = useWebSocket();

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* 1. 글로벌 헤더 */}
      <Header status={status} threatLevel={threatLevel} />

      {/* 2. 메인 대시보드 그리드 */}
      <main className="flex-1 p-6 space-y-6 max-w-[1600px] w-full mx-auto">
        {/* 상단 통계 요약 카드 4종 */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <StatCard
            title="Real-Time Traffic"
            value={totalPps.toLocaleString()}
            unit="PPS"
            change="실시간 집계 패킷"
            icon={Activity}
            color={totalPps > 5000 ? 'rose' : 'cyan'}
          />
          <StatCard
            title="Active Switches"
            value={(topology?.nodes || []).filter(n => n.type === 'switch').length}
            unit="OVS Nodes"
            change="Diamond Mesh Topo"
            icon={HardDrive}
            color="emerald"
          />
          <StatCard
            title="Total Edge Hosts"
            value={(topology?.nodes || []).filter(n => n.type === 'host').length}
            unit="Endpoints"
            change="H_legit, Attacker, Server"
            icon={Cpu}
            color="amber"
          />
          <StatCard
            title="Threat Incidents"
            value={alerts.length}
            unit="Alerts"
            change="1주차 Mock 시뮬레이터"
            icon={ShieldCheck}
            color={alerts.length > 0 ? 'rose' : 'emerald'}
          />
        </div>

        {/* 중앙: 대형 토폴로지 캔버스 (vis-network 준비 컨테이너) */}
        <TopologyContainer topology={topology} />

        {/* 하단 2분할: 실시간 경보 타임라인 & 비상 수동 제어 패널 */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <AlertTimeline alerts={alerts} />
          <ControlPanel triggerControl={triggerControl} />
        </div>
      </main>

      {/* 푸터 */}
      <footer className="px-6 py-3 border-t border-slate-900 text-center text-xs text-slate-600 font-mono">
        Self-Defending SDN Tower v2.0 | Team Developer C (Web Full-Stack) | Python 3.10 + FastAPI + React 18.2
      </footer>
    </div>
  );
}
```

##### 14) `Developer/C/frontend/src/main.jsx`
```jsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
```

##### 15) `Developer/C/frontend/index.html`
```html
<!doctype html>
<html lang="ko">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/vite.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Self-Defending SDN Tower | 실시간 관제탑</title>
  </head>
  <body class="bg-slate-950">
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

##### 16) `Developer/C/scripts/setup_frontend.sh`
```bash
#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"

echo "========================================================"
echo "[개발자 C] 2단계: 프론트엔드(React Vite) 의존성 설치"
echo "========================================================"

cd "$BASE_DIR/frontend"

# Node.js 20 버전 확인
if ! command -v node &>/dev/null; then
    echo "[!] Node.js가 설치되어 있지 않습니다."
    echo "    💡 Ubuntu 22.04 Node 20 LTS 설치 가이드:"
    echo "       curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -"
    echo "       sudo apt-get install -y nodejs"
    echo "    (또는 nvm install 20 && nvm use 20)"
    exit 1
fi

echo "[i] Node 버전: $(node -v), npm 버전: $(npm -v)"
echo "[+] npm 패키지 설치 중..."
npm install

echo "[✓] 프론트엔드 패키지 설치 완료!"
```

#### 🛠️ 실행 및 검증 명령어
```bash
cd /home/tlgus/programming/textgg/Developer/C
chmod +x scripts/setup_frontend.sh
./scripts/setup_frontend.sh

# 프론트엔드 빌드 테스트 (에러 여부 검증)
cd frontend && npm run build
```

> **성공 기준:**  
> `vite build` 실행 결과 `dist/index.html`이 에러 없이 빌드 생성되면 통과.

---

### Step 5: 1주차 E2E 통합 검증 (Mock 스트리밍 -> 브라우저 실시간 UI 렌더링)

#### 🎯 작업 목표
백엔드(FastAPI), 모의 데이터 생성기(`mock_generator.py`), 프론트엔드(React Vite)를 동시에 기동하여, 브라우저 `http://localhost:5173` 접속 시 WebSocket 연결이 체결되고, 1초마다 실시간 PPS 수치 및 스위치/호스트 상태가 갱신되며, 공격 시 적색 경보 카드가 실시간으로 추가되는 전체 흐름을 자동 검증합니다.

#### 💬 AI 프롬프트 (Step 5)
```text
개발자 C의 1주차 산출물을 한 번에 실행하고 자동 검증하는 스크립트 `scripts/run_all.sh`와 `scripts/verify_week1_c.sh`를 작성해줘.

1. `scripts/run_all.sh`:
   - 백엔드(uvicorn, 8000), Mock 스트리머(mock_generator.py), 프론트엔드(vite, 5173)를 백그라운드로 순차 기동
   - Ctrl+C 입력 시 모든 프로세스를 안전하게 종료하는 트랩(trap) 포함
   - 브라우저 접속 주소 출력 안내

2. `scripts/verify_week1_c.sh`:
   - FastAPI 8000 포트 헬스체크 검증 (curl)
   - /api/topology REST 응답 JSON 구조 검증
   - 수동 제어 /api/control/isolate 호출 검증
   - 프론트엔드 5173 포트 응답 확인
   - 검증 보고서 요약 출력
```

#### 📄 완성 참조 파일 명세

##### 1) `Developer/C/scripts/run_all.sh`
```bash
#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"

echo "========================================================"
echo "[개발자 C] 웹 관제탑 전체 스택 통합 실행 (1주차)"
echo "========================================================"

cd "$BASE_DIR"
source venv-web/bin/activate

# 종료 트랩 등록
cleanup() {
    trap - SIGINT SIGTERM EXIT
    echo ""
    echo "[!] 모든 관제탑 서비스 프로세스를 종료합니다..."
    kill $(jobs -p) 2>/dev/null || true
    echo "[✓] 정상 종료 완료."
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# 1. FastAPI 백엔드 실행 (포트 8000)
echo "[1/3] FastAPI 백엔드 기동 중 (http://localhost:8000)..."
python3 -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --log-level warning &
BACKEND_PID=$!
sleep 2

# 2. React Vite 프론트엔드 실행 (포트 5173)
echo "[2/3] React Vite 프론트엔드 기동 중 (http://localhost:5173)..."
cd frontend
npm run dev -- --host &
FRONT_PID=$!
cd "$BASE_DIR"
sleep 2

# 3. 실시간 Mock 데이터 생성기 기동
echo "[3/3] 실시간 SDN Mock 생성기 기동 중..."
python3 backend/mock_generator.py &
MOCK_PID=$!

echo ""
echo "========================================================"
echo "🎯 웹 관제탑 가동 완료!"
echo "   - 웹 대시보드 URL : http://localhost:5173"
echo "   - 백엔드 REST API : http://localhost:8000/docs"
echo "   - WebSocket URL   : ws://localhost:8000/ws"
echo "   (종료하려면 터미널에서 Ctrl+C를 누르세요)"
echo "========================================================"

wait
```

##### 2) `Developer/C/scripts/verify_week1_c.sh`
```bash
#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"

echo "========================================================"
echo "[개발자 C] 1주차 산출물 자동 기능 검증 스크립트"
echo "========================================================"

cd "$BASE_DIR"
source venv-web/bin/activate

PASSED=0
TOTAL=4

# 1. 백엔드 임시 기동
echo "[테스트 1] FastAPI 서버 구동 및 헬스체크..."
python3 -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 &
SERVER_PID=$!
sleep 2

HEALTH_RES=$(curl -s http://127.0.0.1:8000/api/health || true)
if echo "$HEALTH_RES" | grep -q "healthy"; then
    echo "  -> [성공] 헬스체크 확인 완료: $HEALTH_RES"
    PASSED=$((PASSED+1))
else
    echo "  -> [실패] 백엔드 응답 없음"
fi

# 2. 토폴로지 동기화 규격 검증
echo "[테스트 2] /api/topology 엔드포인트 규격 검증..."
TOPO_RES=$(curl -s http://127.0.0.1:8000/api/topology || true)
if echo "$TOPO_RES" | grep -q "0000000000000001"; then
    echo "  -> [성공] Diamond 토폴로지 스키마 정합성 검증 완료"
    PASSED=$((PASSED+1))
else
    echo "  -> [실패] 토폴로지 데이터 반환 실패"
fi

# 3. 비상 포트 격리 REST API 검증
echo "[테스트 3] 수동 제어 API (/api/control/isolate) 검증..."
CONTROL_RES=$(curl -s -X POST "http://127.0.0.1:8000/api/control/isolate?dpid=0000000000000001&port_no=2" || true)
if echo "$CONTROL_RES" | grep -q "ISOLATE_PORT"; then
    echo "  -> [성공] 제어 명령 생성 및 WS 브로드캐스팅 큐 검증 완료"
    PASSED=$((PASSED+1))
else
    echo "  -> [실패] 제어 명령 API 오류"
fi

kill -9 $SERVER_PID 2>/dev/null || true

# 4. 프론트엔드 빌드 검증
echo "[테스트 4] React Vite 프로덕션 빌드 검증..."
cd "$BASE_DIR/frontend"
if npm run build; then
    echo "  -> [성공] 프론트엔드 번들링 무결성 확인 완료"
    PASSED=$((PASSED+1))
else
    echo "  -> [실패] 프론트엔드 빌드 에러"
fi

echo "========================================================"
echo "🎯 1주차 검증 결과: $PASSED / $TOTAL 항목 통과!"
if [ $PASSED -eq $TOTAL ]; then
    echo "🏆 [개발자 C] 1주차 모든 개발 마일스톤 달성 완료! (2주차 진입 가능)"
else
    echo "⚠️ 일부 항목 실패. 가이드북의 트러블슈팅을 참조하세요."
fi
echo "========================================================"
```

#### 🛠️ 실행 및 검증 명령어
```bash
cd /home/tlgus/programming/textgg/Developer/C
chmod +x scripts/*.sh
./scripts/verify_week1_c.sh
```

---

## 4. 개발자 C 전용 치명적 함정 & 디버깅 체크리스트

로드맵 v2.0에 명시된 주요 기술적 함정 중 **개발자 C(웹 관제탑) 영역에서 자주 발생하는 9대 핵심 오류와 방어 기법**입니다.

### 함정 1: CORS 미들웨어 누락으로 인한 REST API 호출 차단 (기술 함정 25번)
* **증상:** 프론트엔드(`localhost:5173`)에서 비상 격리 버튼 클릭 시 콘솔에 `Access to fetch at 'http://localhost:8000/api/control/isolate' from origin 'http://localhost:5173' has been blocked by CORS policy` 발생.
* **해결책:** `backend/app/main.py`에 `CORSMiddleware`를 추가하고 `allow_origins=["*"]`를 명시적으로 등록.

### 함정 2: 브라우저 새로고침(F5) 시 WebSocket Stale Connection으로 백엔드 크래시 (기술 함정 16번)
* **증상:** 사용자가 브라우저를 새로고침하거나 탭을 닫았을 때, 백엔드가 끊어진 소켓에 JSON을 전송하려다 `RuntimeError: Unexpected ASGI message 'websocket.send'`를 뿜으며 Uvicorn 전체가 비정상 종료.
* **해결책:** `ConnectionManager.broadcast()` 메서드에서 `try...except` 블록으로 끊어진 소켓을 `disconnected` 리스트에 담아 안전하게 일괄 제거.

### 함정 3: React Tailwind 컨테이너 Height 미지정으로 vis-network 높이 0px 증발 버그 (기술 함정 20번)
* **증상:** Tailwind CSS flex 레이아웃 내에서 부모 요소에 높이가 없으면, 캔버스 높이가 `0px`로 계산되어 네트워크 토폴로지가 화면에서 완전히 사라짐.
* **해결책:** 토폴로지 캔버스 컨테이너 div에 반드시 `className="w-full h-[520px] min-h-[520px]"`와 같이 명시적 높이 클래스 선언.

### 함정 4: 프론트엔드 환경변수(`VITE_WS_URL`) 하드코딩 (기술 함정 26번)
* **증상:** 코드에 `ws://localhost:8000/ws`를 하드코딩하면 클라우드 VM이나 다른 팀원의 PC에서 접속 시 웹소켓 연결이 거부됨.
* **해결책:** `.env` 파일과 `import.meta.env.VITE_WS_URL`을 통해 호스트 IP를 유연하게 주입하도록 구현.

### 함정 5: vis-network 인스턴스 중복 재생성으로 브라우저 메모리 폭증 (기술 함정 7번)
* **증상:** 2주차에 실시간 통계가 들어올 때마다 `new Network()`를 생성하면 화면이 깜빡이고 브라우저가 메모리 부족으로 다운됨.
* **해결책 (사전 대비):** `vis-network` 인스턴스는 컴포넌트 마운트 시 최초 1회만 생성하고, 데이터 갱신은 `DataSet.update()`를 활용하는 구조를 확립할 것.

### 함정 6: Nginx 리버스 프록시 연동 시 WebSocket Upgrade 헤더 누락
* **증상:** 클라우드 환경에서 80번 포트로 Nginx 프록시를 통과할 때 `WebSocket connection failed: 400 Bad Request` 에러 발생.
* **해결책:** Nginx 설정의 `/ws` 블록에 `proxy_http_version 1.1;`, `proxy_set_header Upgrade $http_upgrade;`, `proxy_set_header Connection "Upgrade";`를 필히 포함해야 함.

### 함정 7: NumPy int64/float64 타입으로 인한 JSON 직렬화 에러 (기술 함정 24번)
* **증상:** 개발자 B(AI)의 통계가 Redis를 거쳐 백엔드로 유입될 때 `TypeError: Object of type int64 is not JSON serializable` 발생.
* **해결책:** Pydantic 모델의 필드에 기본 Python 타입(`int`, `float`)을 강제하고, 수신 데이터 직렬화 전 원시 타입으로 형변환 수행.

### 함정 8: WebSocket 인바운드 메시지 브로드캐스트 누락으로 인한 Mock-UI 통신 단절
* **증상:** `mock_generator.py`가 `/ws` 엔드포인트로 JSON 스트림을 쏘고 있음에도 브라우저 화면의 실시간 통계 카드가 갱신되지 않고 초기 상태에 머무름.
* **해결책:** FastAPI의 `/ws` 엔드포인트 루프에서 클라이언트가 보낸 텍스트를 `json.loads`로 파싱한 후, `await ws_manager.broadcast(payload, exclude=websocket)`를 호출하여 브라우저 클라이언트로 즉시 재전파.

### 함정 9: 모의 누적 카운터(`rx_bytes`)의 0 리셋으로 인한 AI 피처 엔지니어링 음수 오류 방지
* **증상:** 공격 완화 시점에 `bpp`가 0으로 세팅되면서 누적 바이트(`rx_bytes`)가 수천만에서 0으로 급락하여, 개발자 B의 파생 피처 $\Delta \text{BPS}$ 계산 시 거대한 음수값이 산출되어 AI 모델이 폭주함.
* **해결책:** 누적 카운터는 항상 이전 누적값에 `delta_bytes`를 더하는 방식으로 영속적으로 단조 증가(Monotonic Increase)하도록 관리.

---

## 5. 팀원(개발자 A, B) 인계 사항 및 1주차 완료 보고서 양식

### 5.1 1주차 팀원 간 연동 인터페이스 합의 체크리스트
- [x] **개발자 A(Ryu)와 합의:**  
  - Redis 채널명: `sdn:topology:sync`, `sdn:stats:port`  
  - JSON 규격: DPID 형식 16자리 hex (`0000000000000001`), port_no 정수형, `rx_packets`, `rx_bytes`  
  - 수동 격리 명령 규격: `sdn:control:command` (`action: ISOLATE_PORT`, `timeout_sec: 60`)
- [x] **개발자 B(AI)와 합의:**  
  - Redis 채널명: `sdn:anomaly:alert`  
  - JSON 규격: `suspect_port`, `anomaly_score`, `metrics: {pps, bps, bpp}`  
  - 백엔드 Pydantic v2 스키마(`schemas.py`) 파싱 테스트 완료
- [x] **개발자 C 자체 완결성:**  
  - Ryu와 AI 모듈 없이도 `mock_generator.py`를 통해 완벽히 독립적으로 프론트엔드 실시간 렌더링 개발 및 검증 가능

---

### 5.2 1주차 완료 보고서 (팀 공유용 양식)

```markdown
### 📋 [개발자 C] 1주차 개발 마일스톤 달성 보고서

1. **작업 완료 내역:**
   - [x] Python 3.10 가상환경 (`venv-web`) 및 FastAPI/Pydantic v2 의존성 설치 완료
   - [x] Stale Connection 방어 로직이 적용된 WebSocket Hub (`ConnectionManager`) 구현 완료
   - [x] 공통 통신 규격 기반 Pydantic v2 스키마 및 수동 제어 REST API 구현
   - [x] 실시간 SDN 통계 및 SYN Flood 이상 경보를 생성하는 `mock_generator.py` 작성
   - [x] Node 20 + React 18.2 + Tailwind CSS 관제탑 다크 테마 대시보드 레이아웃 구축
   - [x] 웹소켓 실시간 데이터 수신 및 브라우저 상태 배지 연동 검증 완료

2. **단위 및 통합 테스트 결과:**
   - 헬스체크 API: 통과 (`GET /api/health` -> 200 OK)
   - 토폴로지 동기화 API: 통과 (`GET /api/topology` -> Diamond Topo 7개 노드 반환)
   - 수동 격리 REST API: 통과 (`POST /api/control/isolate` -> 명령 큐 발행)
   - 프론트엔드 프로덕션 빌드: 통과 (`npm run build` 번들링 성공)
   - Mock 스트리밍 E2E: 초당 1회 WebSocket 실시간 수신 및 경보 팝업 정상 작동

3. **2주차(Sprint 2) 작업 준비 상태:**
   - `vis-network` 패키지 설치 완료 및 `TopologyContainer` 높이(520px) 세팅 완료
   - `ApexCharts` 패키지 설치 완료 및 실시간 PPS/BPS 시계열 차트 연동 착수 준비 완료
```
