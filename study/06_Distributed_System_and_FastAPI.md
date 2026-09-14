# ⚡ [제6편] 분산 시스템 IPC(Redis Pub/Sub) & FastAPI 비동기 WebSocket

> ⬅️ [제5편: AI 이상 탐지 & 5대 피처](./05_AI_Anomaly_Detection_and_Features.md) | 🏠 [목차](./README.md) | ➡️ [제7편: 웹 관제탑 프론트엔드 React](./07_Frontend_Visualization_React.md)

본 문서는 독립된 마이크로서비스들(Ryu, AI Worker, FastAPI) 간의 초고속 데이터 교환을 담당하는 **Redis Pub/Sub IPC**와, 웹 브라우저로 실시간 메트릭을 브로드캐스팅하는 **FastAPI 비동기 WebSocket Hub**의 아키텍처 및 구현 원리를 학습합니다.

---

## 1. 분산 마이크로서비스 아키텍처와 IPC

### 1.1 왜 모놀리식(단일 프로세스)이 아닌 분산 구조인가?
앞서 살펴본 바와 같이, 세 가지 핵심 구성요소는 각기 다른 런타임 요구사항과 블로킹 특성을 지닙니다:
1. **Ryu Controller:** Python 3.8 환경 필수, Eventlet 코루틴 기반 (I/O 친화적, CPU 블로킹에 취약).
2. **AI Anomaly Worker:** Python 3.10 환경, Scikit-learn CPU-bound 수치 연산 집중.
3. **Web Backend:** Python 3.10 환경, Asyncio 기반 수백 명의 웹소켓 클라이언트 동시 서빙.

이들을 하나의 파이썬 프로세스로 묶는 것은 의존성 충돌 및 이벤트 루프 동결(Freezing)로 인해 불가능합니다. 따라서 **프로세스를 완전히 분리하고, 초고속 IPC(Inter-Process Communication) 버스를 통해 연결**해야 합니다.

---

### 1.2 Redis Pub/Sub 메시지 브로커의 선택 이유
- **인메모리(In-Memory) 초고속 속도:** 메시지 전달 지연시간이 0.1~0.5ms 내외로 네트워크 실시간 관제에 지장을 주지 않습니다.
- **발행-구독(Publish/Subscribe) 완전 분리:** 컨트롤러(Ryu)는 누가 데이터를 받는지 알 필요 없이 Redis 채널로 던지기만(`PUBLISH`) 하면 되고, AI Worker와 FastAPI는 관심 있는 채널만 구독(`SUBSCRIBE`)합니다.

```
       [ Ryu Controller (Docker Python 3.8) ]
                         │
                         │ PUBLISH (sdn:stats:port)
                         ▼
        +───────────────────────────────────+
        │    Redis 7.2 IPC Message Broker   │
        +───────────────────────────────────+
          ▲                               ▲
          │ SUBSCRIBE                     │ SUBSCRIBE
          ▼                               ▼
[ AI Worker (Host Python 3.10) ]   [ FastAPI Backend (Host Python 3.10) ]
  - Isolation Forest 추론            - WebSocket Hub (브라우저 중계)
  - PUBLISH (sdn:anomaly:alert)     - REST API 수동 제어 수신
```

### 1.3 합의된 4대 표준 Redis 채널 스펙 (Contract)
1. `sdn:stats:port`: Ryu가 2초마다 발행하는 포트별 누적 통계 (`dpid`, `port_no`, `rx_packets`, `rx_bytes`)
2. `sdn:anomaly:alert`: AI Worker가 이상 감지 시 발행하는 보안 경보 (`dpid`, `attacker_port`, `anomaly_score`, `state`)
3. `sdn:control:command`: FastAPI 웹 관제탑에서 관리자가 수동 격리/복원 명령을 내릴 때 Ryu로 전송하는 제어 채널
4. `sdn:topology:sync`: 스위치 연결 상태, 링크 링크 상태 및 현재 활성 경로(기본/우회) 정보 동기화 채널

---

## 2. FastAPI 비동기(Asyncio) 아키텍처

FastAPI는 파이썬의 표준 비동기 프로그래밍 모델(`asyncio`)을 기반으로 동작하는 고성능 모던 웹 프레임워크입니다.

### 2.1 동기(Sync) vs 비동기(Async) 처리
- **동기 프레임워크 (Flask 등):** 클라이언트가 웹소켓을 연결하고 있으면 워커 스레드 1개가 해당 소켓에 묶여 다른 요청을 처리하지 못함.
- **비동기 프레임워크 (FastAPI + Uvicorn):** 단일 이벤트 루프에서 I/O 대기 시간(소켓 송수신) 동안 다른 클라이언트의 요청을 논블로킹(Non-blocking)으로 전환 처리하여 수천 개의 동시 웹소켓 연결을 가볍게 유지.

### 2.2 Pydantic v2 계약 우선(Contract-First) 설계
프론트엔드, 백엔드, 컨트롤러가 주고받는 JSON 데이터의 형태를 Pydantic 모델로 엄격하게 정의합니다:

```python
from pydantic import BaseModel, Field
from typing import List

class PortMetric(BaseModel):
    dpid: int
    port_no: int
    delta_pps: float
    delta_bps: float
    bpp: float
    status: str = Field(..., description="NORMAL, CONGESTED, BLOCKED")

class AnomalyAlertMessage(BaseModel):
    timestamp: float
    dpid: int
    target_port: int
    anomaly_score: float
    action_taken: str  # "IN_PORT_DROP", "REROUTED"
```

---

## 3. 실시간 WebSocket Hub와 Stale Connection 방어

웹 관제탑은 1초에도 수십 번의 트래픽 데이터와 경보를 받아야 하므로, 매번 HTTP 요청을 맺고 끊는 폴링 방식 대신 지속적인 양방향 TCP 파이프라인인 **WebSocket**을 사용합니다.

### 3.1 세션 급작스런 종료와 Stale Connection 문제
- 사용자가 웹 브라우저에서 새로고침(F5)을 누르거나 창을 닫으면, 브라우저는 서버에 정상 종료 핸드셰이크를 보낼 틈도 없이 소켓을 끊어버립니다.
- 서버가 닫힌 소켓인지 모르고 `await websocket.send_json(data)`를 실행하면 **`RuntimeError: Unexpected ASGI message`** 예외가 터지며 서버 프로세스가 크래시될 수 있습니다.

### 3.2 안전한 `ConnectionManager` 구현 패턴
```python
from fastapi import WebSocket, WebSocketDisconnect
from typing import Set
import json

class ConnectionManager:
    def __init__(self):
        # 현재 활성화된 웹소켓 연결 세션 집합
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, message: dict):
        # 끊어진 소켓을 안전하게 수집하여 정리하는 Stale 방어 로직
        dead_connections = set()
        for connection in list(self.active_connections):
            try:
                await connection.send_text(json.dumps(message))
            except Exception:
                dead_connections.add(connection)

        # 죽은 세션 일괄 제거
        for dead in dead_connections:
            self.disconnect(dead)

manager = ConnectionManager()
```

---

## 4. 독립 Mock Generator 패턴을 통한 병렬 개발

3명이 협업할 때 웹 개발자(개발자 C)는 Ryu 컨트롤러나 AI 모델이 아직 완성되지 않았더라도 개발을 멈출 필요가 없습니다.

- **`mock_generator.py`:**
  - 1초 간격으로 가상의 정상 트래픽 PPS/BPS 통계를 생성하고,
  - 특정 시간마다 모의 DDoS 공격 발생 및 Anomaly Score 급증 이벤트를 Redis 채널에 스스로 발행해 주는 스크립트입니다.
- 이를 통해 개발자 C는 첫 주차부터 실제 네트워크와 동일한 실시간 데이터 스트림을 웹 대시보드 화면에 띄우고 테스트할 수 있습니다.

---

> ⬅️ [제5편: AI 이상 탐지 & 5대 피처](./05_AI_Anomaly_Detection_and_Features.md) | 🏠 [목차](./README.md) | ➡️ [제7편: 웹 관제탑 프론트엔드 React](./07_Frontend_Visualization_React.md)
