# 🌐 [제1편] 컴퓨터 네트워크 기초 & SDN / OpenFlow 1.3 핵심 원리

> 🏠 [학습 가이드 목차로 돌아가기](./README.md) | ➡️ [제2편: Mininet & OVS 실무 기초](./02_Mininet_and_OpenvSwitch.md)

본 문서는 전통적인 컴퓨터 네트워킹의 동작 원리부터 시작하여, 본 프로젝트의 핵심 기반인 **SDN(Software-Defined Networking)**과 **OpenFlow 1.3** 프로토콜의 메커니즘을 상세히 다룹니다.

---

## 1. 네트워크 기초 지식 (Network Prerequisite)

### 1.1 OSI 7계층과 TCP/IP 4계층 요약

SDN 프로그래밍을 하려면 패킷이 각 계층을 통과할 때 어떤 헤더가 붙고 식별되는지 정확히 알아야 합니다.

| 계층 (OSI / TCP/IP) | PDU 명칭 | 주요 프로토콜 | 식별자 (주소) | 본 프로젝트에서의 역할 |
|---|---|---|---|---|
| **L4 전송 계층** (Transport) | Segment | TCP, UDP, ICMP | 포트 번호 (Port 80, 443 등) | SYN Flooding 공격 패킷 판별, TCP 플래그(`flags="S"`) 식별 |
| **L3 네트워크 계층** (Internet) | Packet | IPv4, IPv6, ARP | IP 주소 (10.0.0.1 등) | 라우팅 경로 결정, IP 스푸핑 공격 발생 계층 |
| **L2 데이터링크 계층** (Link) | Frame | 이더넷 (Ethernet) | MAC 주소 (00:00:00:...) | 스위치 포워딩, 브로드캐스트 스톰(ARP Storm) 방지 |
| **L1 물리 계층** (Physical) | Bit | 케이블, 광섬유 | 물리 포트 (Port 1, 2...) | In_port 기반 물리적 격리 방어 지점 |

### 1.2 TCP 3-Way Handshake와 SYN Flooding의 기원
1. **정상적인 연결 수립:**
   - 클라이언트 $\to$ 서버: `SYN` (연결 요청)
   - 서버 $\to$ 클라이언트: `SYN-ACK` (요청 수락 및 확인)
   - 클라이언트 $\to$ 서버: `ACK` (연결 확정) $\to$ **ESTABLISHED 상태**
2. **SYN Flooding 공격의 원리:**
   - 공격자가 수많은 `SYN` 패킷을 전송하면서, 서버의 `SYN-ACK`에 대해 마지막 `ACK`를 고의로 보내지 않거나 가짜 IP로 변조합니다.
   - 서버는 응답을 기다리며 대기 큐(Backlog Queue)에 미완결 연결(Half-open connection) 상태로 리소스를 유지하다가 결국 큐가 꽉 차 정상 사용자의 연결을 거부하게 됩니다.

---

## 2. 전통적 네트워크 vs SDN (Software-Defined Networking)

### 2.1 전통적 네트워크 장비의 구조와 한계
전통적인 네트워크 장비(Cisco, Juniper 등의 L2/L3 스위치 및 라우터)는 장비 한 대 안에 **두 가지 평면(Plane)**이 함께 들어있습니다:
1. **Control Plane (제어 평면 - 두뇌):** OSPF, BGP, STP 등의 라우팅/스패닝트리 프로토콜을 실행하여 "패킷을 어디로 보낼지 경로를 계산"하는 소프트웨어/CPU 영역.
2. **Data Plane (데이터 평면 - 근육):** 계산된 포워딩 테이블(FIB)을 ASIC/하드웨어 칩셋에 올려두고 "들어온 패킷을 지정된 포트로 초고속 전송(전달)"하는 영역.

> ❌ **전통 네트워크의 문제점:**  
> 제어 평면이 수천 대의 장비에 분산되어 있어서, 전체 네트워크의 정책을 바꾸거나 특정 공격을 실시간으로 차단/우회하려면 수백 대의 장비에 일일이 CLI 명령어를 입력해야 했습니다. 벤더 종속적이며 유연성이 떨어집니다.

### 2.2 SDN의 핵심 개념: 두뇌와 근육의 물리적 분리
SDN은 **제어 평면(Control Plane)**을 스위치에서 떼어내어 중앙의 고성능 서버(SDN Controller)로 모으고, 스위치는 단순한 패킷 포워딩 머신인 **데이터 평면(Data Plane)** 역할만 수행하도록 만듭니다.

```
[ 전통적 네트워크 ]                       [ SDN (소프트웨어 정의 네트워킹) ]
+-------------------------+             +-------------------------------------+
|  스위치 / 라우터 A      |             |         중앙 SDN 컨트롤러           |
|  [Control] 두뇌 (OSPF)  |             |      (Brain: Ryu Controller)        |
|  [Data]    근육 (ASIC)  |             +-------------------------------------+
+-------------------------+                                ▲
             │ 분산 협상                                   │ OpenFlow 프로토콜
+-------------------------+                                ▼
|  스위치 / 라우터 B      |             +-------------------------------------+
|  [Control] 두뇌 (OSPF)  |             |      단순 포워딩 스위치군 (OVS)      |
|  [Data]    근육 (ASIC)  |             |   [Switch 1]  [Switch 2]  [Switch 3]|
+-------------------------+             +-------------------------------------+
```

- **Northbound API:** 컨트롤러와 상위 비즈니스 애플리케이션(FastAPI, 웹 UI, AI 엔진) 간의 통신 인터페이스 (주로 REST API, WebSocket).
- **Southbound API:** 컨트롤러와 하위 가상/물리 스위치(OVS) 간의 통신 표준 프로토콜 (가장 대표적인 표준이 **OpenFlow**).

---

## 3. OpenFlow 1.3 프로토콜 완벽 해부

OpenFlow는 SDN 컨트롤러가 스위치의 **플로우 테이블(Flow Table)**을 원격으로 직접 제어(조회, 추가, 수정, 삭제)할 수 있게 해주는 국제 표준 프로토콜입니다. 본 프로젝트는 가장 완성도 높은 **OpenFlow 1.3** 버전을 사용합니다.

### 3.1 플로우 테이블(Flow Table)과 플로우 엔트리(Flow Entry)
OVS 스위치는 내부에 1개 이상의 플로우 테이블(Table 0, Table 1, ...)을 가지고 있으며, 테이블 내부에는 규칙들의 집합인 **플로우 엔트리(Flow Entry)**가 저장되어 있습니다.

하나의 플로우 엔트리는 다음 핵심 필드로 구성됩니다:
1. **Match Fields (조건식):** 패킷이 이 규칙에 부합하는지 검사하는 조건
   - `in_port`: 패킷이 들어온 스위치 포트 번호
   - `eth_type`: 이더넷 프레임 타입 (0x0800: IPv4, 0x0806: ARP)
   - `ipv4_src / ipv4_dst`: 출발지/목적지 IP 주소
   - `ip_proto`: 4계층 프로토콜 (6: TCP, 17: UDP, 1: ICMP)
   - `tcp_dst`: 목적지 포트 번호 (80, 443 등)
2. **Priority (우선순위):** `0 ~ 65535` 사이의 정수. 숫자가 높을수록 우선적으로 매칭됩니다.
   - 예: `Priority 100` (In_port Drop 차단 규칙)은 `Priority 1` (일반 포워딩 규칙)보다 먼저 실행됩니다.
3. **Instructions / Actions (동작):** 매칭된 패킷에 수행할 작업
   - `OFPActionOutput(port)`: 특정 포트로 패킷 전송
   - `OFPActionOutput(OFPP_FLOOD)`: 들어온 포트를 제외한 모든 활성 포트로 브로드캐스트
   - 아무 Action도 주지 않음: **Drop (패킷 폐기)**
4. **Timeouts (수명 관리):**
   - **Idle Timeout:** 지정된 초 동안 해당 규칙에 매칭되는 패킷이 단 1개도 들어오지 않으면 규칙 자동 삭제.
   - **Hard Timeout:** 트래픽 유입 여부와 무관하게 규칙이 생성된 지 지정된 초가 지나면 무조건 자동 삭제.
5. **Counters (통계 카운터):**
   - 해당 규칙에 매칭되어 지나간 누적 패킷 수(`packet_count`) 및 누적 바이트 수(`byte_count`).

---

### 3.2 핵심 OpenFlow 메시지 흐름

#### 1) Table-Miss (기본 규칙)와 Packet-In
- 스위치가 부팅되면 컨트롤러는 `Priority 0` (가장 낮은 우선순위)의 **Table-Miss 엔트리**를 스위치에 설치합니다.
- 스위치에 도착한 패킷이 기존 어떤 플로우 규칙과도 맞지 않으면, Table-Miss 규칙에 따라 스위치는 컨트롤러에게 **`OFPT_PACKET_IN`** 메시지를 보냅니다.
- 의미: *"이 패킷을 어디로 보내야 할지 모르겠으니 컨트롤러님께서 경로를 알려주세요!"*

#### 2) Packet-Out과 Flow-Mod
- 컨트롤러는 수신한 패킷의 출발지/목적지 정보를 학습(Learning)하거나 최단 경로(Dijkstra)를 계산합니다.
- **`OFPT_FLOW_MOD` (Flow Modification):**
  - 스위치에게 플로우 엔트리를 추가(`OFPFC_ADD`), 수정(`OFPFC_MODIFY`), 삭제(`OFPFC_DELETE`)하도록 명령합니다.
  - *"앞으로 이 목적지로 가는 패킷은 나한테 묻지 말고 2번 포트로 즉시 보내라!"*
- **`OFPT_PACKET_OUT`:**
  - 현재 컨트롤러가 들고 있는 첫 번째 패킷을 스위치의 특정 포트로 즉시 밀어내어 전송을 완료시킵니다.

#### 3) Port / Flow 통계 질의 (PortStatsRequest / Reply)
- 컨트롤러가 주기적으로(본 프로젝트에서는 2초 간격) 스위치에 **`OFPPortStatsRequest`**를 보냅니다.
- 스위치는 각 포트의 누적 송수신 패킷 수(`rx_packets`, `tx_packets`), 누적 바이트 수(`rx_bytes`, `tx_bytes`), 에러 수 등을 담은 **`OFPPortStatsReply`**로 응답합니다.
- 이 통계 데이터가 AI 이상 탐지 엔진의 원천 데이터가 됩니다.

```
[ Switch (OVS) ]                                  [ Controller (Ryu) ]
       │                                                   │
       │ ─── 1. OFPT_PORT_STATS_REQUEST ─────────────────> │ (주기 2초 폴링)
       │ <── 2. OFPT_PORT_STATS_REPLY (rx_bytes, ...) ─── │
       │                                                   │
[신규 패킷 도착]                                           │
       │ ─── 3. OFPT_PACKET_IN (모르는 목적지) ──────────> │
       │                                                   │ (Dijkstra 계산)
       │ <── 4. OFPT_FLOW_MOD (OFPFC_ADD: 규칙 등록) ───── │
       │ <── 5. OFPT_PACKET_OUT (첫 패킷 방출) ─────────── │
```

---

## 4. 본 프로젝트에서 주의해야 할 OpenFlow 원리

### 4.1 `OFPFC_MODIFY`의 한계와 다중 홉 우회 라우팅
- `OFPFC_MODIFY`는 **해당 스위치 내부의 기존 규칙 Action만 변경**합니다.
- 다이아몬드 토폴로지(S1-S2-S4 기본 경로, S1-S3-S4 우회 경로)에서 우회 경로를 활성화하려면:
  1. 중간 스위치인 **S3**에도 패킷을 S4로 넘겨주는 규칙이 먼저 주입(`OFPFC_ADD`)되어 있어야 합니다.
  2. 그런 다음 진입 스위치 **S1**에서 목적지 방향 출력을 S2(포트 2)에서 S3(포트 3)으로 전환해야 트래픽이 유실 없이 흐릅니다.

### 4.2 ARP Broadcast Storm (브로드캐스트 스톰) 위험
- 네트워크 토폴로지에 루프(다이아몬드 순환 구조)가 있을 때, 호스트가 목적지 MAC 주소를 찾기 위해 `ARP Request` 브로드캐스트 패킷을 보내면 스위치들이 패킷을 무한히 복제하여 네트워크 전체 대역폭이 100% 고갈되는 현상이 발생합니다.
- **해결책:** Ryu 컨트롤러에서 ARP 패킷을 단순 FLOOD하지 않고, 컨트롤러가 ARP 매핑 테이블을 직접 응답(Proxy ARP)하거나 신장 트리(Spanning Tree)/LLDP 기반으로 루프 포트를 차단해야 합니다.

---

> 🏠 [학습 가이드 목차로 돌아가기](./README.md) | ➡️ [제2편: Mininet & OVS 실무 기초](./02_Mininet_and_OpenvSwitch.md)
