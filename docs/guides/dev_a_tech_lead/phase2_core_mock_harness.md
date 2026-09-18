# 📘 [Tech Lead] Phase 2: 코어 모듈 구현 & Mock 하네스 실전 가이드
> **담당자:** 박시현 (22101489 / Tech Lead)  
> **해당 기간:** 4주차 ~ 7주차 (2026.09.21 ~ 2026.10.18)  
> **핵심 산출물:** `topo/diamond_topo.py`, `ryu/app/controller.py`, `tests/harness/test_mock_ipc.py`, `harness/contracts/sdn_events.py`  
> **선행 조건:** Phase 1 마일스톤(Docker Ryu 셋업, uv 가상환경, Redis 컨테이너) 완료

---

## 1. Phase 2 개발 목표 및 완료 기준 (Definition of Done)

- [ ] **4주차 DoD:** Mininet 4-스위치 다이아몬드 토폴로지(S1, S2, S3, S4) 에뮬레이션 성공 및 `test_mock_ipc.py` 하네스 테스트 100% 통과
- [ ] **5주차 DoD:** Ryu OpenFlow 1.3 스위칭 애플리케이션 탑재, 다이아몬드 구조 내 ARP Broadcast Storm 차단, `pingall` 100% 무유실 달성
- [ ] **6주차 DoD:** Ryu 백그라운드 2초 주기 `OFPPortStatsRequest` 폴링 루프 가동, 파싱된 통계 데이터를 Redis `sdn:stats:port`에 안전하게 Publish (Eventlet 블로킹 0건)
- [ ] **7주차 DoD:** 트래픽 급증 시 세부 플로우 질의 트리거 연동 및 토폴로지 동적 상태 관리 스켈레톤 완성

---

## 2. 주차별 작업 위치 및 파일 매트릭스

| 주차 | 생성/수정 대상 파일 | 역할 및 설명 |
|:---:|:---|:---|
| **4주차** | `topo/diamond_topo.py` | S1(Ingress), S2(기본), S3(우회), S4(Egress) 및 호스트군 포트 번호 명시적 고정 토폴로지 |
| **4주차** | `tests/harness/test_mock_ipc.py` | Mininet 없이 0.1초 만에 Redis 채널 직렬화/역직렬화를 검증하는 Mock 테스트 하네스 |
| **5주차** | `ryu/app/controller.py` | OpenFlow 1.3 기반 L2/L3 스위칭, `handle_arp` 루프 차단, 최단 경로 flow_mod 주입 |
| **6주차** | `ryu/app/telemetry.py` | Eventlet 비차단 소켓 모드로 2초마다 포트 통계를 수집하여 Redis에 브로드캐스팅하는 모듈 |
| **7주차** | `tests/harness/test_headless_topology.py` | Headless 환경에서 5-스위치 토폴로지 플로우 테이블 주입 로직을 가상 검증하는 하네스 |

---

## 3. 주차별 실전 바이브 코딩 5-Step 워크플로우

### [4주차] 다이아몬드 토폴로지 및 Mock IPC 테스트 하네스

#### Step 1: 고정 포트 다이아몬드 토폴로지 (`topo/diamond_topo.py`)
AI 코딩 에이전트에 아래 프롬프트를 입력하여 토폴로지를 생성합니다.

```markdown
당신은 Self-Defending SDN Tower의 Tech Lead 박시현입니다.
Ubuntu 22.04 LTS, Mininet 2.3+ 환경에서 구동될 4-스위치 다이아몬드 토폴로지 `topo/diamond_topo.py`를 작성해 주세요.

[토폴로지 물리 포트 고정 규칙]
1. Switch S1 (Ingress, DPID 1):
   - Port 1: H_legit (10.0.0.1, MAC 00:00:00:00:00:01)
   - Port 2: H_attacker (10.0.0.2, MAC 00:00:00:00:00:02)
   - Port 3: Switch S2 (Trunk)
   - Port 4: Switch S3 (Trunk, 우회 예비 경로)
2. Switch S2 (Primary, DPID 2):
   - Port 1: Switch S1 연결
   - Port 2: Switch S4 연결
3. Switch S3 (Backup Bypass, DPID 3):
   - Port 1: Switch S1 연결
   - Port 2: Switch S4 연결
4. Switch S4 (Egress, DPID 4):
   - Port 1: H_server (10.0.0.4, MAC 00:00:00:00:00:04)
   - Port 2: Switch S2 연결
   - Port 3: Switch S3 연결

[제약사항]
- Mininet `Topo` 클래스를 상속받아 구현할 것.
- RemoteController (127.0.0.1:6653, OpenFlow 1.3)를 지정할 것.
- 실행 스크립트 작성 시 CLI 모드로 진입할 수 있도록 if __name__ == '__main__': 포함.
```

#### Step 2: Mock IPC 버스 테스트 하네스 (`tests/harness/test_mock_ipc.py`)
```bash
# 하네스 단위 테스트 실행
uv run pytest tests/harness/test_mock_ipc.py -v
```

---

### [5주차] Ryu OpenFlow 1.3 스위칭 & 루프 방지 컨트롤러 (`ryu/app/controller.py`)

#### Step 1: ARP Broadcast Storm 방어 및 최단 경로 플로우 설치
다이아몬드 토폴로지(S1-S2-S4, S1-S3-S4)는 물리적 루프를 포함하므로 표준 `simple_switch_13.py`를 그대로 실행하면 ARP 패킷이 무한 순환하여 OVS와 컨트롤러가 즉시 다운됩니다.

```markdown
당신은 Self-Defending SDN Tower의 Tech Lead 박시현입니다.
Ryu 4.34 (Python 3.8 Docker) 기반의 OpenFlow 1.3 스위칭 컨트롤러 `ryu/app/controller.py`를 구현해 주세요.

[요구사항]
1. Table-miss Flow Entry 등록: Priority 0, Action=OFPP_CONTROLLER
2. ARP Broadcast Storm 방어:
   - S1에서 ARP 패킷 수신 시, Trunk 포트 양쪽(Port 3, Port 4)으로 무차별 Flooding하지 않고 기본 경로인 Port 3(S2 방향)으로만 전송하거나 Ingress 포트를 제외한 단일 포트로 제한할 것.
3. IPv4 최단 경로 포워딩:
   - 기본 상태에서 H_legit/H_attacker ➔ H_server 패킷은 S1 ➔ S2 ➔ S4 경로를 이용하도록 Priority 10 유니캐스트 플로우 설치.
4. 절대 금지 수칙:
   - time.sleep() 절대 사용 금지 (hub.sleep() 사용 또는 완전 비동기 처리)
   - 컨트롤러 핸들러 내부에서 무거운 계산 로직 작성 금지.
```

#### Step 2: 검증 실행 (`pingall`)
```bash
# Mininet 실행 및 검증
sudo mn --custom topo/diamond_topo.py --topo diamond --controller remote,ip=127.0.0.1,port=6653 --switch ovsk,protocols=OpenFlow13
mininet> pingall
# 100% 무유실 (0% dropped) 확인 필수!
```

---

### [6주차 & 7주차] 2-Tier 텔레메트리 파이프라인 연동

#### Step 1: 2초 주기 포트 통계 수집 및 Redis Publish
Ryu `hub.spawn()`을 사용하여 2초 주기로 `OFPPortStatsRequest`를 보내고, 응답 수신 시 `harness/contracts/sdn_events.py`의 `PortStatsMessage` 규격에 맞춰 JSON 직렬화 후 Redis `sdn:stats:port`에 전송합니다.

```python
# Eventlet 안전 Redis 발행 로직 예시
import json
import redis
from ryu.lib import hub

class TelemetryManager:
    def __init__(self):
        # host 모드이므로 localhost:6379 접속
        self.r = redis.Redis(host='127.0.0.1', port=6379, db=0)

    def publish_stats(self, dpid, stats_data):
        payload = {
            "timestamp": hub.time(),
            "dpid": dpid,
            "stats": stats_data
        }
        self.r.publish("sdn:stats:port", json.dumps(payload))
```

---

## 4. 치명적 함정 & 하네스 가드레일 (Gotchas)

1. **Docker `--net=host` 누락:** Ryu 컨테이너 실행 시 `--net=host`를 누락하면 Mininet OVS(포트 6653)와 Redis(포트 6379)와 통신하지 못합니다. 반드시 호스트 네트워크 모드로 띄워야 합니다.
2. **ARP Storm에 의한 스위치 마비:** 다이아몬드 경로에서 포트 Flooding 시 0.5초 만에 수십만 개의 패킷이 컨트롤러로 밀려옵니다. ARP 처리 시 출력 포트를 정적으로 제한하거나 Spanning Tree 프로토콜을 모사해야 합니다.

---

## 5. 팀원 인계 사항 및 A4 주간 보고서 예시 문구

### 5.1 인계 사항
- **유재민 (Domain Dev & QA):** `diamond_topo.py`의 포트 번호(H_legit=p1, H_attacker=p2)가 고정되었으므로, Scapy 스크립트 실행 시 해당 인터페이스를 타깃으로 설정하십시오.
- **김관우 (PM & Tech Writer):** `pingall` 무유실 캡처 화면 및 `test_mock_ipc.py` 통과 로그를 전달합니다.

### 5.2 A4 주간 보고서 기재 문구
> "Tech Lead (박시현): 4-스위치 다이아몬드 토폴로지 구축 및 루프 차단 OpenFlow 1.3 컨트롤러 개발 완료. `pingall` 100% 무유실 통신 달성 및 Redis 2초 주기 포트 통계 수집 파이프라인 연동 완료."
