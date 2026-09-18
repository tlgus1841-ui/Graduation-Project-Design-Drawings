# 🛠️ [제2편] Mininet 가상 토폴로지 & OVS(Open vSwitch) 실무 기초

> ⬅️ [제1편: 네트워크 기초 & OpenFlow 1.3](./01_Network_and_SDN_Fundamentals.md) | 🏠 [목차](./README.md) | ➡️ [제3편: Ryu SDN 컨트롤러 아키텍처](./03_Ryu_SDN_Controller.md)

본 문서는 Mininet이 리눅스 환경에서 가상 네트워크를 에뮬레이션하는 내부 메커니즘과, 소프트웨어 스위치인 Open vSwitch(OVS)를 다루는 실무 명령어 및 기법을 다룹니다.

---

## 1. Mininet의 내부 동작 원리

Mininet은 하드웨어 가상머신(VMware, VirtualBox 등)처럼 무거운 OS 전체를 여러 개 띄우는 것이 아니라, **리눅스 커널의 경량 가상화 기능**을 활용하여 단일 PC에서 수백 개의 스위치와 호스트를 초고속으로 생성하는 네트워크 에뮬레이터입니다.

### 1.1 핵심 가상화 기술 2가지

1. **네트워크 네임스페이스 (Network Namespace, `netns`):**
   - 호스트(H_legit, H_attacker, H_server)는 각각 독립된 리눅스 네트워크 네임스페이스를 가집니다.
   - 각 호스트는 자신만의 독립된 IP 라우팅 테이블, ARP 캐시 테이블, 소켓 리스트, 네트워크 인터페이스(`eth0`, `lo`)를 가집니다. 따라서 `H_legit`에서 띄운 프로세스는 `H_attacker`의 네트워크 환경과 철저히 격리됩니다.
2. **가상 이더넷 페어 (Virtual Ethernet Pair, `veth`):**
   - 두 끝단이 연결된 "가상 랜선(Virtual Patch Cord)"입니다.
   - 한쪽 끝(`h1-eth0`)은 호스트 네임스페이스 안으로 들어가고, 반대쪽 끝(`s1-eth1`)은 OVS 가상 브리지(스위치)에 꽂힙니다.

```
[ Host Namespace: H_legit ]                 [ Host OS: Root Namespace ]
+-------------------------+                 +-------------------------------+
| IP: 10.0.0.1            |                 |  OVS Switch: S1               |
| MAC: 00:00:00:00:00:01  |                 |  (Bridge: s1)                 |
| Interface: h1-eth0      |                 |  Port 1: s1-eth1              |
+------------│------------+                 +---------------│---------------+
             │                                              │
             └─────────────── [ veth pair ] ────────────────┘
                              (가상 랜선)
```

---

## 2. 우리 프로젝트의 다이아몬드(Diamond) 토폴로지

본 프로젝트의 토폴로지는 **DDoS 공격 방어 및 자율 우회 라우팅(Autonomous Rerouting)**을 시연하기 위해 최적화된 다이아몬드 구조입니다.

### 2.1 토폴로지 구성도
```
         [H_legit] (10.0.0.1, Port 1)     [H_attacker] (10.0.0.2, Port 2)
              \                                /
               \                              /
             +----------------------------------+
             |       Switch S1 (Ingress)        |
             +----------------------------------+
                   | (Port 3)            | (Port 4)
                   |                     |
                   ▼ [기본 경로]          ▼ [우회 경로]
             +------------+        +------------+
             | Switch S2  |        | Switch S3  |
             +------------+        +------------+
                   |                     |
                   | (Port 2)            | (Port 2)
                   ▼                     ▼
             +----------------------------------+
             |       Switch S4 (Egress)         |
             +----------------------------------+
                              │ (Port 1)
                              ▼
                         [H_server] (10.0.0.4)
```

### 2.2 포트 번호 고정(Explicit Port Pinning)의 중요성
Mininet 파이썬 스크립트 작성 시, 링크를 연결할 때 포트 번호를 지정하지 않으면 Mininet이 자동으로 1, 2, 3... 순서대로 부여합니다. 이 경우 스위치 생성 순서에 따라 포트 번호가 바뀌어 컨트롤러의 라우팅 코드가 꼬이게 됩니다.
따라서 **`port1`, `port2`를 코드에 명시적으로 고정**해야 합니다:

```python
# topo/diamond_topo.py 핵심 발췌 예시
from mininet.topo import Topo

class DiamondTopo(Topo):
    def build(self):
        # 1. 스위치 4대 생성 (OpenFlow 1.3 지정)
        s1 = self.addSwitch('s1', protocols='OpenFlow13')
        s2 = self.addSwitch('s2', protocols='OpenFlow13')
        s3 = self.addSwitch('s3', protocols='OpenFlow13')
        s4 = self.addSwitch('s4', protocols='OpenFlow13')

        # 2. 호스트 3대 생성 (고정 IP / MAC 부여)
        h_legit = self.addHost('h_legit', ip='10.0.0.1/24', mac='00:00:00:00:00:01')
        h_attacker = self.addHost('h_attacker', ip='10.0.0.2/24', mac='00:00:00:00:00:02')
        h_server = self.addHost('h_server', ip='10.0.0.4/24', mac='00:00:00:00:00:04')

        # 3. 호스트 - S1 연결 (액세스 포트 고정: S1:1 <-> h_legit, S1:2 <-> h_attacker)
        self.addLink(s1, h_legit, port1=1, port2=0)     # S1:1 (Access) <-> h_legit:0
        self.addLink(s1, h_attacker, port1=2, port2=0)  # S1:2 (Access) <-> h_attacker:0

        # 4. 스위치 간 트렁크 연결 (다이아몬드 경로 고정)
        self.addLink(s1, s2, port1=3, port2=1)          # S1:3 (Trunk)  <-> S2:1 (Trunk) [기본 경로]
        self.addLink(s1, s3, port1=4, port2=1)          # S1:4 (Trunk)  <-> S3:1 (Trunk) [우회 경로]
        self.addLink(s2, s4, port1=2, port2=2)          # S2:2 (Trunk)  <-> S4:2 (Trunk)
        self.addLink(s3, s4, port1=2, port2=3)          # S3:2 (Trunk)  <-> S4:3 (Trunk)

        # 5. S4 - H_server 연결 (S4:1 <-> h_server)
        self.addLink(s4, h_server, port1=1, port2=0)    # S4:1 (Access) <-> h_server:0
```

---

## 3. Open vSwitch (OVS) 실무 핵심

OVS는 리눅스 커널 레벨에서 동작하는 멀티레이어 고성능 가상 소프트웨어 스위치입니다.

### 3.1 `ofport` (OpenFlow 포트) vs Linux 인터페이스 이름
- 리눅스 OS 레벨에서는 `s1-eth1`, `s1-eth2` 같은 이름으로 보이지만,
- OpenFlow 프로토콜 내부에서는 정수 번호(`port_no: 1, 2, 3...`)로만 통신합니다.
- OVS에서 특정 인터페이스의 `ofport` 번호를 조회하는 명령어:
  ```bash
  sudo ovs-vsctl get Interface s1-eth1 ofport
  # 출력: 1
  ```

### 3.2 필수 OVS 디버깅 명령어 치트시트

#### 1) 스위치 브리지 상태 확인
```bash
# 전체 OVS 브리지, 포트, 컨트롤러 연결 상태 확인
sudo ovs-vsctl show
```

#### 2) 플로우 테이블 실시간 덤프 (가장 중요 ⭐)
컨트롤러가 주입한 플로우 규칙이 실제로 스위치에 적용되었는지 확인할 때 필수적입니다.
```bash
# s1 스위치에 설치된 OpenFlow 1.3 플로우 엔트리 전체 출력
sudo ovs-ofctl -O OpenFlow13 dump-flows s1

# 특정 테이블만 출력하거나 포트 통계 출력
sudo ovs-ofctl -O OpenFlow13 dump-ports s1
```

*출력 결과 해석 예시:*
```text
cookie=0x0, duration=12.4s, table=0, n_packets=150, n_bytes=14700, priority=1,in_port=1,ip,nw_dst=10.0.0.4 actions=output:3
cookie=0x0, duration=2.1s, table=0, n_packets=5000, n_bytes=270000, priority=100,in_port=2 actions=drop
```
- `priority=100, in_port=2 actions=drop`: 2번 포트로 들어오는 패킷은 즉시 폐기(공격 차단).
- `priority=1, in_port=1, ip, nw_dst=10.0.0.4 actions=output:3`: 정상 패킷은 3번 포트(S2 기본 경로)로 포워딩.

---

## 4. Mininet CLI 필수 실무 가이드

Mininet 실행 후 나타나는 `mininet>` 프롬프트에서 사용하는 핵심 명령어입니다.

| 명령어 | 사용 예시 | 설명 |
|---|---|---|
| `nodes` | `mininet> nodes` | 현재 생성된 스위치, 호스트, 컨트롤러 목록 출력 |
| `net` | `mininet> net` | 각 장비 간의 물리적 링크 연결 상태 출력 |
| `dump` | `mininet> dump` | 모든 노드의 IP, MAC, PID 정보 일괄 출력 |
| `pingall` | `mininet> pingall` | 모든 호스트 간의 ping 성공 여부 전수 검사 |
| `<host> ping <dest>` | `mininet> h_legit ping -c 3 h_server` | 특정 호스트에서 목적지로 핑 3개 발송 |
| `<host> <리눅스 명령>`| `mininet> h_server python3 -m http.server 80 &` | 가상 호스트 네임스페이스 안에서 백그라운드 웹서버 기동 |
| `xterm <host>` | `mininet> xterm h_attacker` | 특정 호스트 전용 터미널 GUI 창 띄우기 |
| `exit` / `quit` | `mininet> exit` | Mininet 종료 |

> 🚨 **주의: 좀비 가상 인터페이스 청소 (`mn -c`)**  
> Mininet이 비정상 종료(Ctrl+C 강제 중단 등)되면 백그라운드에 남아있는 veth 인터페이스와 OVS 브리지가 다음 실행을 방해합니다.  
> 반드시 다음 명령어로 청소해야 합니다:
> ```bash
> sudo mn -c
> ```

---

> ⬅️ [제1편: 네트워크 기초 & OpenFlow 1.3](./01_Network_and_SDN_Fundamentals.md) | 🏠 [목차](./README.md) | ➡️ [제3편: Ryu SDN 컨트롤러 아키텍처](./03_Ryu_SDN_Controller.md)
