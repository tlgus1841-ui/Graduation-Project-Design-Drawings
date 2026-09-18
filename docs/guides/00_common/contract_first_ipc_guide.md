# 📡 [공통] Contract-First IPC 및 Pydantic v2 스키마 규격 가이드
> **문서 대상:** 전 팀원 (박시현, 유재민, 김관우)  
> **기준 규칙:** `docs/planning/ai_harness_engineering_plan.md`, `docs/planning/roadmap_v2.md`  
> **핵심 목적:** Ryu 컨트롤러, AI Worker, FastAPI 웹소켓 간 데이터 통신 불일치를 원천 차단하는 단일 진실 공급원(SSOT) 스키마 관리 표준

---

## 1. Contract-First 패러다임이란?

본 시스템은 분산 마이크로서비스 구조(Docker Ryu ➔ Redis ➔ AI Worker ➔ FastAPI ➔ React)를 가집니다. 각 모듈이 개별적으로 JSON 형식을 파싱하면 필드명 오타 하나로 전체 시스템이 마비됩니다.
따라서 **`harness/contracts/sdn_events.py`에 Pydantic v2 모델을 단일 진실 공급원(SSOT)으로 먼저 정의하고, 모든 개발자가 이를 임포트하여 직렬화/역직렬화**합니다.

---

## 2. 4대 핵심 Redis 채널 명세

| Redis 채널명 | 송신자 (Publisher) | 수신자 (Subscriber) | 주기 / 발생 조건 | 데이터 스키마 모델명 |
|---|---|---|---|---|
| `sdn:stats:port` | Ryu Controller | AI Worker, FastAPI | 2초 주기 Polling | `PortStatsMessage` |
| `sdn:anomaly:alert` | AI Worker | Ryu, FastAPI | 이상 감지 즉시 | `AnomalyAlertMessage` |
| `sdn:control:command` | AI Worker / Web UI | Ryu Controller | 방어/복원/수동 제어 시 | `ControlCommandMessage` |
| `sdn:topology:sync` | Ryu Controller | FastAPI / React Web | 토폴로지 변경 시 | `TopologySyncMessage` |

---

## 3. Pydantic v2 표준 계약 코드 (`harness/contracts/sdn_events.py`)

```python
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class PortStatItem(BaseModel):
    dpid: int = Field(..., description="스위치 Datapath ID (1: S1, 2: S2, ...)")
    port_no: int = Field(..., description="스위치 포트 번호")
    rx_packets: int = Field(..., description="수신 누적 패킷 수")
    tx_packets: int = Field(..., description="송신 누적 패킷 수")
    rx_bytes: int = Field(..., description="수신 누적 바이트 수")
    tx_bytes: int = Field(..., description="송신 누적 바이트 수")
    rx_errors: int = Field(0, description="수신 에러 패킷 수")
    duration_sec: int = Field(..., description="포트 활성 지속 시간 (초)")

class PortStatsMessage(BaseModel):
    timestamp: float = Field(default_factory=lambda: datetime.utcnow().timestamp())
    dpid: int
    stats: List[PortStatItem]

class AnomalyAlertMessage(BaseModel):
    timestamp: float = Field(default_factory=lambda: datetime.utcnow().timestamp())
    dpid: int
    in_port: int
    threat_type: str = Field("SYN_FLOOD_SPOOFING", description="위협 유형")
    score: float = Field(..., description="이상치 스코어 (-1.0 ~ 0.0)")
    pps: float = Field(..., description="초당 패킷 수 (ΔPPS)")
    bps: float = Field(..., description="초당 바이트 수 (ΔBPS)")
    bpp: float = Field(..., description="패킷당 바이트 수 (BPP)")

class ControlCommandMessage(BaseModel):
    timestamp: float = Field(default_factory=lambda: datetime.utcnow().timestamp())
    command_id: str
    action: str = Field(..., description="ISOLATE | RESTORE | REROUTE")
    target_dpid: int
    target_port: int
    reason: str
    priority: int = 100
```

---

## 4. 모듈별 검증 및 테스트 하네스 활용법

### 4.1 메시지 검증 예시
```python
# 송신 시 (AI Worker)
alert = AnomalyAlertMessage(
    dpid=1,
    in_port=2,
    score=-0.65,
    pps=4500.0,
    bps=2880000.0,
    bpp=64.0
)
redis_client.publish("sdn:anomaly:alert", alert.model_dump_json())

# 수신 시 (Ryu / FastAPI)
raw_data = redis_client.get_message()
parsed_alert = AnomalyAlertMessage.model_validate_json(raw_data['data'])
print(f"공격 탐지: Switch {parsed_alert.dpid} In_port {parsed_alert.in_port}")
```

### 4.2 Mock IPC 버스 검증 러너
개발 단계에서 Mininet이나 실제 Redis 없이도 `tests/harness/test_mock_ipc.py`를 통해 모든 스키마의 유효성을 0.1초 만에 검증할 수 있습니다:
```bash
uv run pytest tests/harness/test_mock_ipc.py -v
```
