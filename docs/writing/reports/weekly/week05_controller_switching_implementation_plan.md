# 📘 [Tech Lead] 5주차 구현 계획서 — OpenFlow 1.3 L2/L3 스위칭 및 다이아몬드 무루프 포워딩 (`ryu/app/controller.py`)

> **담당자:** 박시현 (22101489 / Tech Lead & 시스템 아키텍트)  
> **해당 기간:** 5주차 (2026.09.28 ~ 2026.10.04)  
> **상위 근거 문서:** [`schedule_and_milestones.md`](../../../planning/schedule_and_milestones.md), [`roadmap_v2.md`](../../../planning/roadmap_v2.md), [`phase2_core_sdn_infra.md`](../../../guides/dev_a_tech_lead/phase2_core_sdn_infra.md)

---

## 1. 목적 및 배경

4주차에 구축된 4-스위치 다이아몬드 가상 토폴로지([`topo/diamond_topo.py`](../../../../topo/diamond_topo.py))는 S1에서 S4로 가는 경로가 두 갈래(S2 기본 경로, S3 우회 경로)로 분기되는 다중 경로 구조를 가집니다. 일반적인 L2 학습 스위치(Learning Switch) 알고리즘을 그대로 적용할 경우, 브로드캐스트 패킷(ARP Request)이 루프를 돌며 증폭되는 **ARP 브로드캐스트 스톰(Broadcast Storm)**이 발생하여 네트워크 대역폭과 제어 평면이 즉각 마비됩니다.

본 5주차 과제는 다음을 완수하는 것을 핵심 목표로 합니다:
1. 다이아몬드 토폴로지 내 브로드캐스트 스톰을 원천 차단하는 **Proxy ARP 메커니즘** 탑재.
2. 기본 최단 경로(S1-S2-S4)를 통한 무루프 유니캐스트 포워딩 규칙 선제적 주입.
3. 가상 인프라(Mininet)와 Ryu 컨트롤러(Docker) 간 연동을 통해 **`pingall` 100% 무유실 통신(Loss 0%)** 달성.
4. 향후 6주차 텔레메트리 파이프라인(포트 통계 주기 수집) 및 9~10주차 다중 홉 우회 라우팅 확장을 위한 컨트롤러 코어 아키텍처 확립.

---

## 2. 요구사항 정의 (Definition of Done, DoD)

| # | 요구사항 항목 | 상세 내용 | 검증 기준 |
|:---:|:---|:---|:---|
| **R1** | **OpenFlow 1.3 핸드셰이크** | 스위치 접속 시 `EventOFPSwitchFeatures` 처리 및 Table-Miss(Priority 0) 기본 플로우 설치 | S1~S4 연결 즉시 Table-Miss 엔트리 OVS 확인 |
| **R2** | **Proxy ARP 스톰 차단** | 스위치 간 ARP 패킷 플러딩 금지. 컨트롤러가 호스트 IP-MAC 테이블을 조회하여 즉시 유니캐스트 ARP Reply 응답 | ARP Request 브로드캐스트 스톰 발생 0건 |
| **R3** | **IPv4 유니캐스트 포워딩** | 기본 경로(S1 $\leftrightarrow$ S2 $\leftrightarrow$ S4) 기반 Flow Mod(Priority 10) 설치 및 첫 패킷 PacketOut 무유실 전송 | `eth_type=0x0800` 정합성 및 플로우 테이블 등록 |
| **R4** | **`pingall` 무유실 달성** | `H_legit`(10.0.0.1), `H_attacker`(10.0.0.2), `H_server`(10.0.0.4) 상호 간 ICMP 통신 무유실 | Mininet `pingall` 성공률 **100% (Loss 0%)** |
| **R5** | **컨테이너 격리 런타임** | Ryu 4.34 및 Python 3.8 런타임을 Docker 컨테이너(`ryu-controller`)로 무충돌 구동 | `docker-compose up` 단일 명령 안정 가동 |
| **R6** | **6주차 텔레메트리 확장 슬롯** | 비차단 Eventlet 루프 기반 2초 주기 포트 통계 요청(`OFPPortStatsRequest`) 구조 사전 설계 | Eventlet 스레드 안전성 및 핸들러 슬롯 확보 |

---

## 3. 상세 아키텍처 및 설계

### 3.1 4-스위치 다이아몬드 고정 포트 및 라우팅 매핑

[`topo/diamond_topo.py`](../../../../topo/diamond_topo.py)에 확정된 하드웨어 핀닝에 따라 라우팅 테이블(`self.routing_table`)을 엄격히 고정합니다.

```text
                  +---------------+
                  |  S2 (Primary) |
             +--->|  DPID: 2      |---+
             |    +---------------+   |
             |                        |
             | (p3: S2)               | (p2: S2)
     +---------------+          +---------------+
     |  S1 (Ingress) |          |  S4 (Egress)  |
     |  DPID: 1      |          |  DPID: 4      |
     +---------------+          +---------------+
       | (p1)   | (p2)            | (p1)
       |        |                 |
     H_legit  H_attacker        H_server
       | (p4: S3)               | (p3: S3)
       |                        |
       |    +---------------+   |
       +--->|  S3 (Bypass)  |---+
            |  DPID: 3      |
            +---------------+
```

* **호스트 고정 매핑 (`self.arp_table`):**
  - `10.0.0.1` (`H_legit`): MAC `00:00:00:00:00:01`, 위치 S1 Port 1
  - `10.0.0.2` (`H_attacker`): MAC `00:00:00:00:00:02`, 위치 S1 Port 2
  - `10.0.0.4` (`H_server`): MAC `00:00:00:00:00:04`, 위치 S4 Port 1

* **5주차 기본 최단 경로 라우팅 테이블 (`self.routing_table`):**
  ```python
  self.routing_table = {
      1: {"10.0.0.1": 1, "10.0.0.2": 2, "10.0.0.4": 3},  # S1 -> S4 방향은 Port 3 (S2행)
      2: {"10.0.0.1": 1, "10.0.0.2": 1, "10.0.0.4": 2},  # S2 -> S4: Port 2, -> S1: Port 1
      3: {"10.0.0.1": 1, "10.0.0.2": 1, "10.0.0.4": 2},  # S3 (우회 대기)
      4: {"10.0.0.1": 2, "10.0.0.2": 2, "10.0.0.4": 1},  # S4 -> S1 방향은 Port 2 (S2행)
  }
  ```

### 3.2 Proxy ARP 메커니즘 (스톰 방지 원리)

1. 호스트가 상대방의 MAC 주소를 알기 위해 `ARP_REQUEST`를 브로드캐스트(`FF:FF:FF:FF:FF:FF`)로 송출.
2. Ingress 스위치 S1의 Table-Miss 플로우에 의해 패킷이 컨트롤러로 인입(`Packet-In`).
3. 컨트롤러는 패킷을 다른 포트로 플러딩(`OFPP_FLOOD`)하지 않고, 패킷의 `dst_ip`를 파싱.
4. `self.arp_table`에 등록된 대상이면 컨트롤러가 직접 `ARP_REPLY` 패킷을 조립하여 요청이 들어온 포트(`in_port`)로 단독 유니캐스트 전송.
5. **결과:** 스위치 간 트렁크 링크(S1-S2, S1-S3, S2-S4, S3-S4)로 ARP 패킷이 전파되지 않아 루프가 원천 차단됨.

### 3.3 Flow Mod 엔트리 표준 규격

* **Flow Table-Miss (기본 규칙):**
  - Priority: `0`
  - Match: `OFPMatch()` (모든 패킷)
  - Action: `OFPActionOutput(OFPP_CONTROLLER, OFPCML_NO_BUFFER)`
* **IPv4 유니캐스트 포워딩 규칙:**
  - Priority: `10`
  - Match: `OFPMatch(eth_type=0x0800, ipv4_dst=dst_ip)` (⚠️ `eth_type=0x0800` 필수 선언)
  - Action: `OFPActionOutput(out_port)`
  - Timeout: `idle_timeout=60`, `hard_timeout=0`

### 3.4 Dockerfile.ryu 및 컨테이너 실행 아키텍처

* **호환성 격리:** Ryu의 Eventlet/Python 3.8 종속성을 메인 호스트(Python 3.10)와 격리하기 위해 Docker 컨테이너 사용.
* **네트워크 모드:** `--net=host`를 사용하여 Mininet의 OVS가 로컬 호스트 포트(`6653`/`6633`)로 직접 OpenFlow 연결을 수립하도록 보장.

---

## 4. 일자별 실행 및 검증 일정 (5주차)

| 일자 | 작업 내용 | 세부 활동 및 체크포인트 | 상태 |
|:---:|:---|:---|:---:|
| **09.28 ~ 09.30** | Docker 인프라 및 베이스라인 구축 | • `ryu/Dockerfile.ryu` 및 `docker-compose.yml` 작성<br>• Ryu 컨트롤러 기본 클래스 스켈레톤 작성 | **완료** |
| **10.01 ~ 10.02** | Proxy ARP 및 IPv4 포워딩 구현 | • `handle_arp()` 및 `send_arp_reply()` 구현<br>• `handle_ipv4()` FlowMod 및 `ip_pkt.dst` 버그 패치 | **완료** |
| **10.03 (오늘)** | 문서 통합 & 단위/E2E 테스트 연동 | • 팀원 작업물(공격기, 관제탑 UI) 병합 및 5주차 계획서 수립<br>• Mininet 연동 통신 무유실(`pingall`) 검증 | **진행 중** |
| **10.04 (마감)** | 5주차 마일스톤 검증 및 6주차 준비 | • OVS 플로우 테이블 덤프 검증 (`ovs-ofctl dump-flows`)<br>• 6주차 텔레메트리(`sdn:stats:port`) 인터페이스 구조 설계 | **예정** |

---

## 5. 검증 및 테스트 시나리오

### TC-1: 스위치 연결 및 Table-Miss 플로우 검증
* **절차:** Docker 컨트롤러 기동 후 Mininet `DiamondTopo` 실행.
* **합격 기준:** S1, S2, S3, S4의 플로우 테이블에 `priority=0, actions=CONTROLLER` 규칙이 4개 스위치 모두에 정상 설치됨.

### TC-2: Proxy ARP 스톰 차단 검증
* **절차:** `H_legit`(h1)에서 `H_server`(h4)로 ARP 요청 발생 시 Wireshark/tcpdump로 트렁크 포트 모니터링.
* **합격 기준:** S2(Port 1) 및 S3(Port 1)로 ARP 브로드캐스트 패킷이 전파되지 않고, S1 Port 1로만 유니캐스트 ARP Reply가 회신됨.

### TC-3: IPv4 유니캐스트 통신 및 `pingall` 무유실 검증
* **절차:** Mininet CLI에서 `pingall` 명령어 실행.
* **합격 기준:** `Results: 0% dropped (6/6 received)` (h1 $\leftrightarrow$ h2, h1 $\leftrightarrow$ h4, h2 $\leftrightarrow$ h4 100% 통신 성공).

### TC-4: OVS FlowMod 등록 검증
* **절차:** `sh ovs-ofctl -O OpenFlow13 dump-flows s1` 실행.
* **합격 기준:** `priority=10,ip,nw_dst=10.0.0.4 actions=output:3` 플로우 엔트리가 정상 등록되고 패킷 카운터가 증가함.

---

## 6. 잠재적 리스크 및 대응 전략 (Risk & Mitigation)

1. **`eth_type` 누락 시 OpenFlow 명세 위반 에러 (OVS Error):**
   * *리스크:* OpenFlow 1.3에서 `ipv4_dst` 필드는 `eth_type=0x0800`이 선행 매칭되지 않으면 유효하지 않은 매치 필드로 거부됨.
   * *대응:* `parser.OFPMatch(eth_type=0x0800, ipv4_dst=dst_ip)` 형태로 엄격히 고정 구현 완료.
2. **Eventlet 코루틴 블로킹 및 OVS Heartbeat 끊김:**
   * *리스크:* 패킷 처리 또는 향후 통계 수집 루프에서 블로킹 I/O 발생 시 Echo Request 타임아웃으로 OVS 세션이 끊김.
   * *대응:* `eventlet.monkey_patch()`를 최상단에 선언하고 동기식 블로킹 호출(time.sleep 등)을 일체 금지하며 `hub.sleep()` 활용.
3. **루프 백 포워딩 방지:**
   * *리스크:* 패킷이 유입된 포트로 다시 송출되어 패킷 바운싱 발생.
   * *대응:* `out_port == in_port`인 경우 패킷을 드롭(무시)하는 안전 가드 적용.
