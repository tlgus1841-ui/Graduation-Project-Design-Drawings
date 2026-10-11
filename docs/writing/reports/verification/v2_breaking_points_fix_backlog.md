# V2 고도화 백로그: 극한 부하 테스트(952k PPS)에서 발굴된 파괴점(Breaking Points) 및 수정 설계서

- **작성일**: 2026-10-11
- **문서 목적**: Week 16 프로토타입 발표에서는 **극한 스트레스 테스트를 통해 스스로 규명한 한계점 및 엔지니어링 분석 사례**로 활용하고, 발표 직후 **V2 고도화 단계에서 즉시 코드로 패치하기 위한 작업 지시서(Actionable Backlog)**로 기록함.
- **연관 보고서**: [week16_stress_limit_test_report.md](file:///home/tlgus/programming/Self_Defending_SDN_Tower/docs/writing/reports/verification/week16_stress_limit_test_report.md)

---

## 📋 파괴점(Breaking Point) 요약 목록

| ID | 우선순위 | 파괴점 명칭 | 발생 조건 | 증상 및 보안 영향 | 상태 |
| :---: | :---: | :--- | :--- | :--- | :---: |
| **BP-01** | **P0 (Critical)** | **`CircuitBreaker`의 Heartbeat 경보 카운팅으로 인한 조기 차단 해제 (`RESTORE`)** | 2.0초 내 `sdn:anomaly:alert` 6건 이상 수신 시 (멀티 워커, 다중 포트 동시 공격, 또는 95만 PPS CPU 지연 버스트) | 이미 격리된(`MITIGATED`) 포트의 유지 경보(Heartbeat)까지 서킷 브레이커가 차단하여 `FlappingFSM`이 `6.88초` 만에 공격자 포트를 다시 열어버림 | 📌 발표 후 수정 대기 |
| **BP-02** | **P1 (High)** | **2.0초 고정 폴링 주기로 인한 초기 `3.22초` 무방비 관통 구간 (Pre-Isolation Window)** | 초고속 DDoS (`763k ~ 952k PPS`) 유입 시 첫 2틱(약 3.22초) 동안 추론 대기 | 차단 룰(`Priority 100 Drop`)이 내려가기 전 첫 3.22초 동안 약 **866,018 패킷**이 서버(`H_server`)로 관통함 | 📌 발표 후 수정 대기 |
| **BP-03** | **P1 (High)** | **목적지 IP(`ipv4_dst`) 랜덤 스푸핑 시 Table-Miss `Packet-In` 컨트롤러 마비 취약점** | 공격자가 출발지뿐만 아니라 미등록 목적지 IP(`10.0.0.5 ~ 10.255.255.254`)까지 무작위로 변조하여 공격할 때 | 매 패킷이 OVS `priority=0 (CONTROLLER)` 룰을 타고 Ryu [`packet_in_handler`](file:///home/tlgus/programming/Self_Defending_SDN_Tower/ryu/app/controller.py#L571-L592)로 유입되어 Python Eventlet 루프 포화 | 📌 발표 후 수정 대기 |
| **BP-04** | **P2 (Medium)** | **AI 추론 워커(`inference_worker.py`) 중복 실행 방지 락(PID/Redis Lock) 부재** | 백그라운드에서 워커 프로세스가 2개 이상 중복 기동될 때 | 동일한 `sdn:stats:port` 메시지에 대해 N배의 중복 `sdn:anomaly:alert`가 발행되어 **BP-01(서킷 브레이커 Trip)**을 즉시 유발함 | 📌 발표 후 수정 대기 |

---

## 🛠️ 상세 원인 및 추후 코드 수정 가이드 (Patch Blueprints)

### 1. [BP-01] `CircuitBreaker` 검사 위치 이동 및 Heartbeat 분리

#### 🔍 문제 코드 위치
- 파일: [`ryu/app/controller.py`](file:///home/tlgus/programming/Self_Defending_SDN_Tower/ryu/app/controller.py#L498-L544) (`_handle_redis_message`)

```python
# 현재 코드 (ryu/app/controller.py:498-518)
if channel == REDIS_CHANNEL_ANOMALY_ALERT:
    alert = AnomalyAlertMessage.model_validate_json(data_str)
    # ❌ 문제점: 이미 격리된 포트에 대한 단순 Heartbeat 연장 경보나 화이트리스트 포트 경보까지
    # 무조건 record_command()를 호출하여 2초 내 6회 도달 시 서킷 브레이커를 OPEN 시킴!
    if not self.circuit_breaker.record_command():
        self.logger.error(
            f"[CircuitBreaker] Alert rejected! Status: {self.circuit_breaker.get_status()}"
        )
        return
```

#### ✅ 추후 수정 코드 (V2 패치안)
`already_mitigated` 상태인 타깃의 반복 경보는 **새로운 제어 명령(FlowMod)을 발생시키지 않는 순수 Heartbeat**이므로, 서킷 브레이커 카운트(`record_command()`)를 소모하지 않고 곧바로 `self.fsm.trigger_anomaly()`만 호출하도록 순서를 변경합니다.

```python
# 수정안 (ryu/app/controller.py)
if channel == REDIS_CHANNEL_ANOMALY_ALERT:
    alert = AnomalyAlertMessage.model_validate_json(data_str)
    if not self.whitelist_guard.can_isolate(alert.dpid, alert.in_port):
        return

    target_key = f"{alert.dpid}:{alert.in_port}"
    already_mitigated = (
        self.fsm.get_state() != DefenseState.NORMAL
        and target_key in self.fsm.mitigated_targets
    )

    if already_mitigated:
        # ✅ 이미 격리된 포트: 서킷 브레이커 카운트 차감 없이 FSM 쿨다운 타이머(Heartbeat)만 연장
        prev_state = self.fsm.get_state()
        self.fsm.trigger_anomaly(alert.dpid, alert.in_port, threat_info=alert.model_dump())
        if prev_state != DefenseState.MITIGATED:
            self._publish_topology_sync("MITIGATED")
        return

    # ✅ 신규 격리/우회 명령을 실제로 실행할 때만 서킷 브레이커 빈도 검사 수행
    if not self.circuit_breaker.record_command():
        self.logger.error(
            f"[CircuitBreaker] Alert rejected! Status: {self.circuit_breaker.get_status()}"
        )
        return

    self.isolate_port(alert.dpid, alert.in_port, priority=100)
    ...
```

---

### 2. [BP-02] 초기 3.22초 관통 패킷 억제를 위한 OVS Meter Table(대역폭 속도 제한) 및 폴링 적응형 가속

#### 🔍 문제 코드 위치
- 파일: [`ryu/app/controller.py`](file:///home/tlgus/programming/Self_Defending_SDN_Tower/ryu/app/controller.py#L139-L150) (`_monitor_loop`)

#### ✅ 추후 수정 방향 (V2 패치안)
1. **적응형 텔레메트리 폴링(Adaptive Polling)**: 평소에는 `2.0초` 주기로 폴링하다가 `delta_pps > 500` 이상 급증이 감지되면 폴링 주기를 `0.5초`로 단축하여 탐지 시간을 `3.22초 ➔ 0.8초`로 단축.
2. **Access Port 기본 Meter Band 적용**: OpenFlow 1.3 `OFPMeterMod`(`OFPMF_PKTPS`)를 이용해 호스트 접속 포트(`S1:P1`, `S1:P2`)의 초당 최대 허용 PPS 상한(예: `10,000 PPS`)을 하드웨어/커널 단에서 상시 캡핑하여, 탐지 전 3.22초 동안 86만 패킷이 서버로 쏟아지는 현상을 원천 방지.

---

### 3. [BP-03] 미등록 목적지 IP 스푸핑 방어를 위한 서브넷 가드 플로우 및 `Packet-In` Rate Limiting

#### 🔍 문제 코드 위치
- 파일: [`ryu/app/controller.py`](file:///home/tlgus/programming/Self_Defending_SDN_Tower/ryu/app/controller.py#L229-L261) (`switch_features_handler`), [`handle_ipv4`](file:///home/tlgus/programming/Self_Defending_SDN_Tower/ryu/app/controller.py#L640-L685)

#### ✅ 추후 수정 방향 (V2 패치안)
1. **사전 L3 화이트리스트/블랙홀 플로우 설치**: 스위치 초기 연결 시(`switch_features_handler`), 토폴로지 내 존재하는 유효 호스트 IP(`10.0.0.1 ~ 10.0.0.4`)가 아닌 목적지 패킷이 컨트롤러(`priority=0 -> CONTROLLER`)로 올라오지 않도록, 미등록 목적지 IP 대역에 대해 스위치 자체에서 즉시 폐기하는 저우선순위 Drop 플로우(`priority=5`) 설치.
2. **무명 목적지 단기 부정 캐시(Negative Flow Caching)**: [`handle_ipv4`](file:///home/tlgus/programming/Self_Defending_SDN_Tower/ryu/app/controller.py#L646-L653)에서 `dst_ip not in self.routing_table[dpid]`일 때 그냥 `return`만 하지 않고, `idle_timeout=10, priority=10, actions=[] (Drop)` 플로우를 OVS에 내려 후속 패킷의 Packet-In 유입을 차단.

---

### 4. [BP-04] `model/inference_worker.py` 단일 인스턴스 보장 (Redis / File Lock)

#### 🔍 문제 코드 위치
- 파일: [`model/inference_worker.py`](file:///home/tlgus/programming/Self_Defending_SDN_Tower/model/inference_worker.py#L110-L152) (`run`)

#### ✅ 추후 수정 방향 (V2 패치안)
- 워커 시작 시 `/tmp/sdn_inference_worker.lock` (`fcntl.flock`) 또는 Redis 분산 락(`SET sdn:worker:lock <pid> NX EX 10`)을 획득하도록 하여, 실수로 여러 개의 AI 워커가 동시에 떠서 경보 횟수를 배가시키는 현상을 방지.
