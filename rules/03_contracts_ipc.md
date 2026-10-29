# 📡 Contracts & IPC Rules (03_contracts_ipc.md)

AI 에이전트는 컴포넌트 간 통신 인터페이스 수정 시 아래 계약(Contract) 규칙을 준수해야 합니다.

---

## 1. Pydantic 스키마 단일 진실 공급원 (SSOT)
* 모든 컴포넌트 간 통신 메시지는 [harness/contracts/sdn_events.py](file:///home/tlgus/programming/Self_Defending_SDN_Tower/harness/contracts/sdn_events.py)의 Pydantic v2 모델을 기준으로 직렬화/역직렬화해야 합니다.
* 임의의 비표준 딕셔너리(`dict`)나 규격 외 JSON을 채널에 직접 발행하지 마십시오.
* 스키마 필드를 수정하거나 추가할 경우, 반드시 기존 필드의 하위 호환성을 유지해야 합니다.

---

## 2. Redis 4대 핵심 채널 규격

| 채널명 | 메시지 모델 | 송신자 | 수신자 | 주기/조건 |
|:---|:---|:---|:---|:---|
| `sdn:stats:port` | `PortStatsMessage` | Ryu Controller | AI Feature Extractor, Web Hub | 2초 주기 |
| `sdn:stats:flowcount` | `FlowCountStatsMessage` | Ryu Controller | Criteria Engine | 1초 주기 |
| `sdn:anomaly:alert` | `AnomalyAlertMessage` | AI Inference Worker | Ryu Controller, Web Hub | 이상 감지 시 즉시 |
| `sdn:control:command` | `ControlCommandMessage` | AI Worker / Web API | Ryu Controller | 포트 격리/우회/복구 명령 |

---

## 3. 웹 관제탑(FastAPI & UI) 연동 규칙
* FastAPI 백엔드는 `redis_bridge.py`를 통해 Redis 채널을 구독하고 Pydantic 검증을 거친 후 WebSocket(`/ws`)으로 클라이언트에 멀티캐스팅합니다.
* 비상 수동 제어 API(`/api/control/manual`)는 유효한 사유(reason)와 포트 번호 검증을 거쳐 `sdn:control:command`로 전달됩니다.
* 수동 복원된 포트는 자동 재격리 방지를 위한 60초 보호 홀드(`auto_isolation_hold_sec`)를 보장해야 합니다.
