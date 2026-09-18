# 🧠 [제3편] Ryu 컨트롤러 아키텍처 & 동적 라우팅 프로그래밍

> ⬅️ [제2편: Mininet & OVS 실무 기초](./02_Mininet_and_OpenvSwitch.md) | 🏠 [목차](./README.md) | ➡️ [제4편: 네트워크 보안 & In_port 방어](./04_Network_Security_and_DDoS_Defense.md)

본 문서는 파이썬 기반의 오픈소스 SDN 컨트롤러인 **Ryu 4.34**의 내부 아키텍처, 비동기 이벤트 루프(`eventlet`), OpenFlow 1.3 메시지 처리 기법, 그리고 Dijkstra 알고리즘을 활용한 동적 라우팅 구현 원리를 심층 학습합니다.

---

## 1. Ryu 컨트롤러의 핵심 아키텍처

Ryu는 일본의 NTT 연구소에서 개발한 컴포넌트 기반의 SDN 컨트롤러 프레임워크입니다.

### 1.1 내부 동시성 모델: `eventlet` (그린 스레드)
- Ryu는 OS 네이티브 멀티스레딩 대신 파이썬의 **`eventlet` (Greenlet 기반 코루틴)**을 사용하여 단일 프로세스 안에서 수천 개의 스위치 연결을 처리합니다.
- **협력적 멀티태스킹(Cooperative Multitasking):** I/O 대기(소켓 송수신, `hub.sleep()`)가 발생할 때만 다른 작업으로 제어권을 양보합니다.

> ⚠️ **매우 중요한 아키텍처 제약사항:**  
> Scikit-learn 추론(`model.predict()`)이나 무거운 `for` 루프와 같은 **CPU-bound 블로킹 연산**을 Ryu 내부 스레드에서 직접 실행하면, Ryu의 전체 이벤트 루프가 멈춰버립니다.  
> 스위치는 주기적으로 컨트롤러에 `Echo Request`를 보내 생존을 확인하는데, 컨트롤러가 제때 `Echo Reply`를 주지 못하면 스위치는 컨트롤러가 다운된 것으로 판단하여 **스위치 연결 해제(Switch Disconnect)** 사태가 발생합니다.  
> 👉 **이것이 AI 머신러닝 추론을 Ryu 내부가 아닌 별도의 Python 3.10 독립 프로세스(AI Worker)로 분리하고 Redis로 통신하는 이유입니다.**

### 1.2 왜 Docker (`python:3.8-slim`) 컨테이너로 격리하는가?
- Ryu 4.34 공식 라이브러리는 최신 파이썬 3.10+ 환경에서 설치가 불가능합니다.
  1. `collections.abc` 모듈 임포트 경로 변경으로 인한 `SyntaxError`
  2. 파이썬 3.10 이상의 C-API 변경으로 인한 구형 `greenlet` 컴파일 실패
- 따라서 Ryu 컨트롤러는 **`python:3.8-slim` Docker 컨테이너**로 완전히 격리하고, `--net=host` 모드로 호스트의 OVS 스위치 및 Redis와 통신하도록 설계합니다.

---

## 2. Ryu 애플리케이션의 기본 뼈대

Ryu의 모든 애플리케이션은 `ryu.base.app_manager.RyuApp`을 상속받아 작성됩니다.

### 2.1 이벤트 데코레이터 (`@set_ev_cls`)
컨트롤러는 OpenFlow 이벤트가 발생했을 때 이를 가로채는 핸들러 함수를 등록합니다:
```python
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ipv4, arp, tcp
from ryu.lib import hub

class SimpleSwitch13(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]  # OpenFlow 1.3 사용 명시

    def __init__(self, *args, **kwargs):
        super(SimpleSwitch13, self).__init__(*args, **kwargs)
```

- `CONFIG_DISPATCHER`: 스위치가 최초 접속하여 핸드셰이크가 진행되는 초기 설정 단계
- `MAIN_DISPATCHER`: 핸드셰이크가 완료되어 정상적으로 패킷을 주고받는 운영 단계

---

## 3. 핵심 OpenFlow 1.3 처리 파이프라인

### 3.1 Table-Miss 기본 엔트리 주입 (핸드셰이크 시점)
스위치가 컨트롤러에 처음 연결되면(`EventOFPSwitchFeatures`), 모르는 패킷을 컨트롤러에 전송하도록 `Priority 0` 엔트리를 심습니다:

```python
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # 1. Match: 아무 조건도 없음 (모든 패킷 매칭)
        match = parser.OFPMatch()

        # 2. Action: 컨트롤러로 올려보내기 (OFPP_CONTROLLER)
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]

        # 3. 플로우 테이블 0번에 Priority 0으로 설치
        self.add_flow(datapath, priority=0, match=match, actions=actions)

    def add_flow(self, datapath, priority, match, actions, idle_timeout=0, hard_timeout=0):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Action을 감싸는 명령어(Instruction) 생성
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]

        # FlowMod 메시지 생성 및 스위치에 송신
        mod = parser.OFPFlowMod(
            datapath=datapath, priority=priority, match=match,
            instructions=inst, idle_timeout=idle_timeout, hard_timeout=hard_timeout
        )
        datapath.send_msg(mod)
```

### 3.2 패킷 수신 및 파싱 (`EventOFPPacketIn`)
스위치가 모르는 패킷을 컨트롤러에 올리면 패킷 헤더를 분석합니다:

```python
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        # Ryu 패킷 파서로 헤더 계층별 분해
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        ip_pkt = pkt.get_protocol(ipv4.ipv4)
        tcp_pkt = pkt.get_protocol(tcp.tcp)

        # 예: IPv4 패킷인 경우 출발지/목적지 IP 추출
        if ip_pkt:
            src_ip = ip_pkt.src
            dst_ip = ip_pkt.dst
            # 최단 경로 계산 후 FlowMod 주입 및 PacketOut 실행
```

---

## 4. 2-Tier 계층형 모니터링 & In_port 방어

### 4.1 2-Tier 모니터링의 구현 원리
네트워크에 존재하는 모든 스위치의 모든 플로우를 매초 전수 조사하면 컨트롤러와 제어 채널의 CPU 부하가 폭증합니다. 따라서 **2단계 계층형 파이프라인**을 적용합니다:

1. **1차 모니터링 (포트 단위 경량 폴링):**
   - 2초 주기로 `OFPPortStatsRequest`를 보냅니다.
   - 각 포트의 `rx_bytes`, `rx_packets` 변화율($\Delta \text{PPS}, \Delta \text{BPS}$)을 계산합니다.
2. **2차 모니터링 (이상 진입 포트 정밀 분석):**
   - 1차 모니터링에서 특정 포트(예: 1번 또는 2번 포트)의 PPS가 위험 임계치를 초과하면, 해당 스위치에 대해서만 상세 플로우 통계(`OFPFlowStatsRequest`)를 질의합니다.

```python
    # Ryu 내부 주기적 백그라운드 워커 실행
    def _monitor(self):
        while True:
            for dp in self.datapaths.values():
                self._request_port_stats(dp)
            hub.sleep(2)  # 2초 주기 휴식 (eventlet 친화적 슬립)

    def _request_port_stats(self, datapath):
        parser = datapath.ofproto_parser
        # 포트 통계 요청 메시지 전송
        req = parser.OFPPortStatsRequest(datapath, 0, datapath.ofproto.OFPP_ANY)
        datapath.send_msg(req)
```

### 4.2 In_port 기반 긴급 차단 플로우 주입
이상 탐지 엔진(AI Worker)으로부터 공격자 감지 알림이 오면, 컨트롤러는 해당 진입 포트(`in_port`)를 드랍하는 최고 우선순위 플로우를 설치합니다:

```python
    def block_ingress_port(self, datapath, port_no, timeout=15):
        parser = datapath.ofproto_parser
        
        # 1. Match: 공격 트래픽이 들어오는 해당 포트 매칭
        match = parser.OFPMatch(in_port=port_no)
        
        # 2. Actions: 빈 리스트 [] -> 매칭된 패킷 즉시 폐기 (Drop)
        actions = []
        
        # 3. Priority 100 (일반 포워딩보다 훨씬 높은 우선순위), Idle Timeout 15초
        self.add_flow(datapath, priority=100, match=match, actions=actions,
                      idle_timeout=timeout)
        self.logger.warning(f"🚨 [DEFENSE] Switch {datapath.id} In_port {port_no} BLOCKED (Priority 100, Timeout {timeout}s)")
```

---

## 5. Dijkstra 최단 경로 라우팅과 다중 홉 우회

Ryu 컨트롤러는 토폴로지 디스커버리 모듈을 통해 스위치 간의 연결 링크를 감지하고, 이를 `networkx.Graph` 구조체로 변환합니다.

### 5.1 최단 경로 탐색
```python
import networkx as nx

class PathManager:
    def __init__(self):
        self.graph = nx.Graph()

    def get_shortest_path(self, src_switch, dst_switch):
        # Dijkstra 알고리즘으로 홉 수가 가장 적은 최단 경로 계산
        try:
            return nx.shortest_path(self.graph, src_switch, dst_switch)
        except nx.NetworkXNoPath:
            return None
```

- **평상시 경로:** `S1 -> S2 -> S4` (2 홉)
- **우회 경로 (S2 링크 공격 마비 시):** S2 링크의 가중치를 무한대로 변경하거나 배제하여 `S1 -> S3 -> S4` (2 홉)로 재계산.
- **다중 홉 프로비저닝 순서:**
  1. 먼저 목적지 스위치 쪽(S3, S4)에 우회 플로우 엔트리를 주입합니다.
  2. 마지막으로 시작 스위치(S1)의 포워딩 출력을 우회 포트로 전환합니다.  
  *(역순으로 설치하면 중간 스위치에서 패킷이 드랍되는 것을 완벽히 방지할 수 있습니다.)*

---

> ⬅️ [제2편: Mininet & OVS 실무 기초](./02_Mininet_and_OpenvSwitch.md) | 🏠 [목차](./README.md) | ➡️ [제4편: 네트워크 보안 & In_port 방어](./04_Network_Security_and_DDoS_Defense.md)
