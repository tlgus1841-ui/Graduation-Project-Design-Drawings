# 🛡️ [개발자 A] 1주차 바이브 코딩 실전 가이드북 (검증 & 보완 완료판)
## SDN 인프라 & 제어 평면 기반 확립 (Mininet + Ryu OF 1.3 + Docker + Redis)

> **대상:** 개발자 A (SDN & 인프라 엔지니어)  
> **개발 방식:** 바이브 코딩 (AI 코딩 어시스턴트 프롬프트 중심 개발)  
> **1주차 마일스톤:** 다중 경로(다이아몬드) 가상 네트워크 토폴로지 구축, Ryu Docker 및 Redis 컨테이너 구동, OpenFlow 1.3 기반 루프 방지 L2/L3 스위칭 구현 (`pingall` 100% 무유실 성공), 토폴로지 동기화 규격 검증  
> **참조 문서:** `Self-Defending_SDN_Tower_Roadmap_v2.md`

---

## 📋 목차
1. [1주차 개발 목표 및 핵심 아키텍처](#1-1주차-개발-목표-및-핵심-아키텍처)
2. [개발자 A 디렉토리 구조 및 작업 위치 안내](#2-개발자-a-디렉토리-구조-및-작업-위치-안내)
3. [바이브 코딩 5단계 워크플로우](#3-바이브-코딩-5단계-워크플로우)
   - [Step 1: 호스트 인프라 및 OS 커널 셋업](#step-1-호스트-인프라-및-os-커널-셋업)
   - [Step 2: Docker 기반 Ryu 4.34 & Redis 브로커 격리 환경 구축](#step-2-docker-기반-ryu-434--redis-브로커-격리-환경-구축)
   - [Step 3: 다중 경로 다이아몬드 토폴로지 구현 (`topo/diamond_topo.py`)](#step-3-다중-경로-다이아몬드-토폴로지-구현-topodiamond_topopy)
   - [Step 4: OpenFlow 1.3 스위칭 & 루프 방지 컨트롤러 구현 (`ryu/app/controller.py`)](#step-4-openflow-13-스위칭--루프-방지-컨트롤러-구현-ryuappcontrollerpy)
   - [Step 5: 1주차 E2E 검증 (`pingall` & 토폴로지 Redis 동기화)](#step-5-1주차-e2e-검증-pingall--토폴로지-redis-동기화)
4. [개발자 A 전용 치명적 함정 & 디버깅 체크리스트](#4-개발자-a-전용-치명적-함정--디버깅-체크리스트)
5. [팀원(개발자 B, C) 인계 사항 및 1주차 완료 보고서 양식](#5-팀원개발자-b-c-인계-사항-및-1주차-완료-보고서-양식)

---

## 1. 1주차 개발 목표 및 핵심 아키텍처

### 1.1 1주차 핵심 임무
1. **Ubuntu 22.04 LTS 호스트 환경 세팅:** Mininet 2.3+ 및 Open vSwitch(OVS 2.17.x) 네이티브 설치, OVS 기본 컨트롤러 데몬 비활성화, 커널 IP 스푸핑 필터(`rp_filter`) 해제.
2. **Ryu Controller & Redis 컨테이너화:** Python 3.8 환경으로 격리된 Ryu 4.34 Docker 빌드 및 Docker Compose 기반 고속 IPC Redis 7.2 배포 (`network_mode: host`).
3. **Diamond 토폴로지 에뮬레이션:** S1(Ingress), S2(기본 경로), S3(우회 경로), S4(Egress) 및 호스트군(H_legit, H_attacker, H_server)이 배치된 OpenFlow 1.3 다중 경로 토폴로지 구축 (링크 포트 번호 명시적 고정).
4. **루프 없는 L2/L3 스위칭 구현:** 다이아몬드 구조의 물리적 루프에서 **ARP Broadcast Storm**이 발생하지 않도록 방어하는 Ryu 4.34 스위칭 애플리케이션 작성, `handle_ipv4` 최단 경로 라우팅 등록 및 `pingall` 무유실 성공.
5. **토폴로지 데이터 동기화:** 웹 관제탑(개발자 C)이 구독할 수 있도록 스위치/호스트/링크 정보를 Redis 채널(`sdn:topology:sync`)에 전송할 수 있는 기반 마련.

### 1.2 1주차 시스템 블록도
```
+--------------------------------------------------------------------------------+
|                        Host OS: Ubuntu 22.04.4 LTS                             |
|                                                                                |
|  [Docker Container 1: sdn-redis]     [Docker Container 2: sdn-ryu]            |
|   - image: redis:7.2-alpine           - base: python:3.8-slim                  |
|   - port: 6379 (Host Network)         - Ryu 4.34 + Eventlet 0.30.2             |
|                                       - app/controller.py                      |
|                                       - port: 6653 (OpenFlow), 8080 (REST)     |
|                                              ▲                                 |
|                                              │ OpenFlow 1.3 (TCP 6653)         |
|  [Mininet 2.3+ / OVS 2.17 Native]            ▼                                 |
|                                                                                |
|          H_legit (10.0.0.1, p1)      H_attacker (10.0.0.2, p2)                 |
|                      \                  /                                      |
|                       [  Switch S1  ] (Ingress)                                |
|                        /          \                                            |
|          (Trunk: p3)  /            \  (Trunk: p4)                              |
|            [ Switch S2 ]          [ Switch S3 ]  <-- 우회 예비 경로            |
|            (기본 최단 경로)              \                                     |
|                       \                  /  (Trunk: p2)                        |
|          (Trunk: p2)   \                /                                      |
|                       [  Switch S4  ] (Egress)                                 |
|                              │ (Access: p1)                                    |
|                      H_server (10.0.0.4, p1)                                   |
+--------------------------------------------------------------------------------+
```

---

## 2. 개발자 A 디렉토리 구조 및 작업 위치 안내

현재 작업 공간이 역할별 디렉토리(`A/`, `B/`, `C/`)로 분리되어 있으므로, **개발자 A의 모든 코드는 `textgg/A/` 하위에서 관리**하거나 프로젝트 루트에서 심볼릭 링크로 연결하여 실행합니다.

```
textgg/
├── A/                              # [개발자 A 전용 작업 공간]
│   ├── Developer_A_Week1_VibeCoding_Guide.md
│   ├── docker-compose.yml          # Redis & Ryu 컨테이너 실행 명세
│   ├── ryu/
│   │   ├── Dockerfile.ryu          # Python 3.8 격리 빌드 명세
│   │   └── app/
│   │       ├── __init__.py
│   │       └── controller.py       # L2/L3 스위칭 & ARP Proxy 방어 컨트롤러
│   ├── topo/
│   │   ├── __init__.py
│   │   └── diamond_topo.py         # 포트 번호 고정 Mininet 토폴로지
│   └── scripts/
│       ├── setup_host.sh           # 커널 파라미터 & Mininet 설치 스크립트
│       ├── clean_mininet.sh        # OVS 좀비 프로세스 청소 스크립트
│       └── verify_week1.sh         # 1주차 최종 E2E 자동 검증 스크립트
├── B/                              # 개발자 B (AI & 보안)
├── C/                              # 개발자 C (웹 관제탑)
└── Self-Defending_SDN_Tower_Roadmap_v2.md
```

> 💡 **바이브 코딩 팁:** 터미널에서 작업할 때는 항상 `cd /home/tlgus/programming/textgg/A`로 진입한 후 명령어를 실행하세요.

---

## 3. 바이브 코딩 5단계 워크플로우

각 단계마다 **[💬 AI 프롬프트]**, **[사전 지식 및 제약조건]**, **[검증 명령어 & 예상 결과]**, **[에러 발생 시 대처 프롬프트]**가 완비되어 있습니다. 그대로 복사하여 AI 어시스턴트에 입력하세요.

---

### Step 1: 호스트 인프라 및 OS 커널 셋업

#### 🎯 작업 목표
Ubuntu 22.04 LTS 호스트 환경에 Mininet, Open vSwitch를 설치하고, Scapy IP 스푸핑 패킷 전송을 위해 리눅스 커널의 역방향 경로 필터링(`rp_filter`)을 비활성화합니다.  
**[핵심 주의]** `openvswitch-testcontroller`가 설치되면 포트 6653을 자동으로 점유하므로 이를 비활성화해야 Ryu가 정상 구동됩니다.

#### 💬 AI 프롬프트 (Step 1)
```text
Ubuntu 22.04 LTS 환경에서 Mininet 2.3+ 및 Open vSwitch(OVS 2.17)를 설치하고,
SDN IP 스푸핑 실습을 위해 커널 파라미터 rp_filter를 비활성화하는 호스트 초기 셋업 스크립트 `scripts/setup_host.sh`와
네트워크 청소 스크립트 `scripts/clean_mininet.sh`를 작성해줘.

[scripts/setup_host.sh 세부 요구사항]
1. apt update 및 mininet, openvswitch-switch, net-tools, iproute2, curl, git 설치
   - 주의: openvswitch-testcontroller 서비스가 실행되면 6653 포트를 선점하므로,
     설치 후 반드시 `systemctl stop openvswitch-testcontroller 2>/dev/null || true` 및
     `systemctl disable openvswitch-testcontroller 2>/dev/null || true` 명령을 포함할 것.
2. OVS 서비스(systemctl restart openvswitch-switch) 확인 및 활성화
3. IP Spoofing 패킷의 리눅스 커널 드랍 방지 (영구 적용 및 즉시 적용):
   - sysctl -w net.ipv4.conf.all.rp_filter=0
   - sysctl -w net.ipv4.conf.default.rp_filter=0
   - /etc/sysctl.d/99-sdn.conf 파일에 위 설정 추가

[scripts/clean_mininet.sh 세부 요구사항]
1. `mn -c` 로 잔여 가상 인터페이스 및 링크 정리
2. `killall -9 ovs-testcontroller ryu-manager 2>/dev/null || true`
3. `systemctl restart openvswitch-switch` 로 OVS 브리지 데몬 리셋
4. 실행 권한 부여(chmod +x) 안내 포함
```

#### 🛠️ 실행 및 검증 명령어
```bash
cd /home/tlgus/programming/textgg/A
chmod +x scripts/setup_host.sh scripts/clean_mininet.sh
sudo ./scripts/setup_host.sh

# rp_filter 비활성화 확인 (모두 0이어야 함)
sysctl net.ipv4.conf.all.rp_filter net.ipv4.conf.default.rp_filter

# OVS 서비스 가동 상태 확인
sudo ovs-vsctl show
```

> **성공 기준:** `net.ipv4.conf.all.rp_filter = 0`이 출력되고, `ovs-vsctl show` 실행 시 UUID와 함께 에러 없이 표시되면 완료.

---

### Step 2: Docker 기반 Ryu 4.34 & Redis 브로커 격리 환경 구축

#### 🎯 작업 목표
Ryu Controller는 Python 3.9+에서 의존성(`eventlet`, `greenlet`) 충돌이 발생하므로 공식 `python:3.8-slim` Docker 컨테이너로 격리합니다. 또한 Mininet OVS(`127.0.0.1:6653`)와의 무중단 통신을 위해 `network_mode: host`로 구성합니다.

#### 💬 AI 프롬프트 (Step 2)
```text
`A/` 디렉토리 하위에 Ryu 4.34 컨트롤러와 Redis 7.2 메시지 브로커를 구동하기 위한
`ryu/Dockerfile.ryu` 와 `docker-compose.yml`을 작성해줘.

[Dockerfile.ryu 필수 제약사항]
1. Base Image: python:3.8-slim
2. 빌드 필수 도구: gcc, git, libxml2-dev, libxslt1-dev, zlib1g-dev
3. Pip 의존성 버전 정확히 고정:
   - eventlet==0.30.2
   - greenlet==1.1.2
   - tinyrpc==1.0.4
   - routes==2.5.1
   - webob==1.8.7
   - networkx==2.5.1
   - redis==5.0.1
   - ryu==4.34
4. 포트 노출: EXPOSE 6653 8080
5. WORKDIR: /app

[docker-compose.yml 필수 제약사항]
1. Version: '3.8'
2. 서비스 1: redis-broker
   - image: redis:7.2-alpine
   - container_name: sdn-redis
   - network_mode: host
   - command: redis-server --port 6379 --appendonly no
   - restart: always
3. 서비스 2: ryu-controller
   - build context: ./ryu, dockerfile: Dockerfile.ryu
   - container_name: sdn-ryu
   - network_mode: host (OVS 127.0.0.1 직접 통신 필수!)
   - volumes: ./ryu/app:/app
   - command: ryu-manager --ofp-tcp-listen-port 6653 --observe-links /app/controller.py
   - depends_on: redis-broker
   - restart: unless-stopped
```

#### 🛠️ 실행 및 검증 명령어
```bash
cd /home/tlgus/programming/textgg/A

# 1. 초기 더미 컨트롤러 파일 생성 (컨테이너 최초 실행 시 크래시 방지)
mkdir -p ryu/app
cat << 'EOF' > ryu/app/controller.py
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3

class DummyController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    def __init__(self, *args, **kwargs):
        super(DummyController, self).__init__(*args, **kwargs)
        self.logger.info(">>> Ryu 4.34 Initialized with OpenFlow 1.3! <<<")
EOF

# 2. Docker Compose 빌드 및 실행
docker compose build
docker compose up -d

# 3. 로그 및 리스닝 포트(6653, 6379) 확인
docker compose logs -f ryu-controller
sudo ss -tlpn | grep -E '6653|6379'
```

> **성공 기준:** 
> - `docker compose ps`에서 `sdn-redis`, `sdn-ryu` 모두 `Up` 상태.
> - `ss` 또는 `netstat`에서 `0.0.0.0:6653` 및 `0.0.0.0:6379`가 LISTEN 상태로 확인됨.

---

### Step 3: 다중 경로 다이아몬드 토폴로지 구현 (`topo/diamond_topo.py`)

#### 🎯 작업 목표
4개의 Open vSwitch(`s1`, `s2`, `s3`, `s4`)와 3개의 단말 호스트(`h_legit`, `h_attacker`, `h_server`)로 구성된 다이아몬드 토폴로지를 Mininet Python API로 작성합니다.  
**[핵심 주의]** Mininet에서 링크 추가 순서에 따라 포트가 꼬이지 않도록, `net.addLink` 호출 시 `port1=...`, `port2=...`를 반드시 명시적으로 지정해야 합니다.

#### 💬 AI 프롬프트 (Step 3)
```text
Mininet Python API를 사용하여 4개의 스위치와 3개의 호스트로 구성된 다중 경로 다이아몬드 토폴로지
스크립트 `topo/diamond_topo.py`를 작성해줘.

[토폴로지 아키텍처 사양]
1. 스위치 (OVS 4대):
   - s1 (Ingress), s2 (Upper Primary), s3 (Lower Bypass), s4 (Egress)
   - [필수] 모든 스위치는 OpenFlow 1.3을 사용해야 함.
     `protocols='OpenFlow13'` 파라미터를 가진 커스텀 Switch 클래스(OpenFlow13Switch)를 만들어 net.addSwitch의 cls로 지정할 것.
   - 각 스위치 dpid 명시:
     s1: "0000000000000001", s2: "0000000000000002", s3: "0000000000000003", s4: "0000000000000004"

2. 호스트 (3대):
   - h_legit: IP="10.0.0.1/24", MAC="00:00:00:00:00:01"
   - h_attacker: IP="10.0.0.2/24", MAC="00:00:00:00:00:02"
   - h_server: IP="10.0.0.4/24", MAC="00:00:00:00:00:04"

3. [가장 중요] 링크 연결 시 포트 번호 명시적 고정 (port1, port2 파라미터 필수):
   - net.addLink(s1, h_legit, port1=1, port2=0)     # S1:1 (Access) <-> h_legit
   - net.addLink(s1, h_attacker, port1=2, port2=0)  # S1:2 (Access) <-> h_attacker
   - net.addLink(s1, s2, port1=3, port2=1)          # S1:3 (Trunk)  <-> S2:1 (Trunk)
   - net.addLink(s1, s3, port1=4, port2=1)          # S1:4 (Trunk)  <-> S3:1 (Trunk)
   - net.addLink(s2, s4, port1=2, port2=2)          # S2:2 (Trunk)  <-> S4:2 (Trunk)
   - net.addLink(s3, s4, port1=2, port2=3)          # S3:2 (Trunk)  <-> S4:3 (Trunk)
   - net.addLink(s4, h_server, port1=1, port2=0)    # S4:1 (Access) <-> h_server

4. 컨트롤러 설정:
   - RemoteController(name='c0', ip='127.0.0.1', port=6653)

5. 실행 함수:
   - CLI(net) 모드로 대화형 쉘 진입
   - 스크립트 실행 시작 시 자동으로 기존 토폴로지를 청소하는 clean_mininet() 호출 포함
```

#### 🛠️ 실행 및 검증 명령어
```bash
cd /home/tlgus/programming/textgg/A

# 1. Mininet 실행 (sudo 권한 필요)
sudo -E env "PATH=$PATH" python3 topo/diamond_topo.py

# 2. Mininet CLI 진입 후 포트/링크 확인
mininet> links
mininet> net
mininet> dump

# 3. Ryu 컨테이너 로그에서 4개 스위치 연결 핸드셰이크 확인 (다른 터미널)
docker compose logs --tail=20 ryu-controller
```

> **성공 기준:** Ryu 로그에 `EventOFPSwitchFeatures`가 발생하며 DPID 1, 2, 3, 4가 모두 정상 연결되고, `OFPH_HELLO_FAILED` 에러가 없어야 함.

---

### Step 4: OpenFlow 1.3 스위칭 & 루프 방지 컨트롤러 구현 (`ryu/app/controller.py`)

#### 🎯 작업 목표
다이아몬드 토폴로지(`s1-s2-s4-s3-s1`)의 루프 환경에서 **ARP Broadcast Storm을 원천 차단(Proxy ARP)**하고, 정상 트래픽을 위한 **IPv4 기본 최단 경로(S1-S2-S4) 포워딩(`handle_ipv4`)**을 완벽히 구현합니다.

#### 💬 AI 프롬프트 (Step 4)
```text
Ryu 4.34 (OpenFlow 1.3) 기반의 컨트롤러 어플리케이션 `ryu/app/controller.py`를 완성해줘.
다이아몬드 토폴로지에서 루프 브로드캐스트 스톰 없이 `pingall`이 100% 무유실 통과해야 해.

[세부 구현 명세]
1. OpenFlow 1.3 규격:
   - `OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]`
   - Switch 연결 시 `Priority 0 Table-Miss Flow` 등록:
     Match: 빈 매치, Action: `OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)`

2. 조기 필터링 (Early Return):
   - `eth = pkt.get_protocol(ethernet.ethernet)`
   - `if not eth or eth.ethertype in (ether_types.ETH_TYPE_LLDP, 0x86dd): return` (IndexError 및 불필요 패킷 방어)

3. [재난 방어] Proxy ARP 구현:
   - self.arp_table = {
       "10.0.0.1": {"mac": "00:00:00:00:00:01", "dpid": 1, "port": 1},
       "10.0.0.2": {"mac": "00:00:00:00:00:02", "dpid": 1, "port": 2},
       "10.0.0.4": {"mac": "00:00:00:00:00:04", "dpid": 4, "port": 1},
     }
   - ARP REQUEST가 오면 절대 플러딩(OFPP_FLOOD)하지 말고, dst_ip가 arp_table에 있으면
     Ryu가 직접 ARP REPLY 패킷을 빌드하여 해당 in_port로 OFPPacketOut 전송.

4. [핵심 포워딩] `handle_ipv4` 최단 경로 라우팅 (S1 <-> S2 <-> S4):
   - 목적지별 스위치 포워딩 테이블 정의:
     - S1: 10.0.0.1 -> Port 1, 10.0.0.2 -> Port 2, 10.0.0.4 -> Port 3 (S2 방향)
     - S2: 10.0.0.1/10.0.0.2 -> Port 1 (S1 방향), 10.0.0.4 -> Port 2 (S4 방향)
     - S3: 10.0.0.1/10.0.0.2 -> Port 1, 10.0.0.4 -> Port 2 (예비 우회 경로)
     - S4: 10.0.0.1/10.0.0.2 -> Port 2 (S2 방향), 10.0.0.4 -> Port 1 (H_server 방향)
   - 패킷 매칭 시 반드시 `eth_type=0x0800, ipv4_dst=dst_ip` 명시 (누락 시 OFPBMC_BAD_PREREQ 발생!).
   - 플로우 등록 우선순위: `Priority = 10`, `idle_timeout = 60`
   - 첫 패킷 손실 방지를 위해 등록과 동시에 `OFPPacketOut(buffer_id=OFP_NO_BUFFER, data=msg.data)` 실행.

5. 로깅:
   - switch features, proxy arp 응답, flow rule 설치 로그 출력.
```

#### 📄 완성 참조 구현 코드 (`ryu/app/controller.py`)
아래 코드는 검증을 통과한 `controller.py`의 완전한 구현체입니다:

```python
import eventlet
eventlet.monkey_patch()

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3, ether_types
from ryu.lib.packet import packet, ethernet, arp, ipv4

class SelfDefendingSDNController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SelfDefendingSDNController, self).__init__(*args, **kwargs)
        # 호스트 정적 매핑 테이블
        self.arp_table = {
            "10.0.0.1": {"mac": "00:00:00:00:00:01", "dpid": 1, "port": 1},
            "10.0.0.2": {"mac": "00:00:00:00:00:02", "dpid": 1, "port": 2},
            "10.0.0.4": {"mac": "00:00:00:00:00:04", "dpid": 4, "port": 1},
        }
        # 기본 최단 경로 라우팅 맵: {dpid: {dst_ip: out_port}}
        self.routing_table = {
            1: {"10.0.0.1": 1, "10.0.0.2": 2, "10.0.0.4": 3},  # S1 -> S4: Port 3 (S2행)
            2: {"10.0.0.1": 1, "10.0.0.2": 1, "10.0.0.4": 2},  # S2 -> S4: Port 2, -> S1: Port 1
            3: {"10.0.0.1": 1, "10.0.0.2": 1, "10.0.0.4": 2},  # S3 (우회용)
            4: {"10.0.0.1": 2, "10.0.0.2": 2, "10.0.0.4": 1},  # S4 -> S1: Port 2 (S2행), -> H_server: Port 1
        }
        self.logger.info(">>> Self-Defending SDN Controller Week 1 Initialized! <<<")

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Table-Miss Flow (Priority 0) 등록
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, priority=0, match=match, actions=actions)
        self.logger.info(f"Switch S{datapath.id} Connected. Table-Miss Installed.")

    def add_flow(self, datapath, priority, match, actions, idle_timeout=0, hard_timeout=0):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(
            datapath=datapath, priority=priority,
            match=match, instructions=inst,
            idle_timeout=idle_timeout, hard_timeout=hard_timeout
        )
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        dpid = datapath.id
        in_port = msg.match['in_port']
        pkt = packet.Packet(msg.data)
        
        # [방어 1] LLDP 및 IPv6 무시 (IndexError 방어)
        eth = pkt.get_protocol(ethernet.ethernet)
        if not eth or eth.ethertype in (ether_types.ETH_TYPE_LLDP, 0x86dd):
            return

        # [방어 2] ARP 브로드캐스트 스톰 방어 (Proxy ARP)
        arp_pkt = pkt.get_protocol(arp.arp)
        if arp_pkt:
            self.handle_arp(datapath, in_port, eth, arp_pkt)
            return

        # [방어 3] IPv4 패킷 유니캐스트 최단 경로 포워딩
        ip_pkt = pkt.get_protocol(ipv4.ipv4)
        if ip_pkt:
            self.handle_ipv4(datapath, in_port, eth, ip_pkt, msg.data)

    def handle_arp(self, datapath, in_port, eth, arp_pkt):
        if arp_pkt.opcode == arp.ARP_REQUEST:
            target_ip = arp_pkt.dst_ip
            if target_ip in self.arp_table:
                reply_mac = self.arp_table[target_ip]["mac"]
                self.send_arp_reply(datapath, reply_mac, target_ip, eth.src, arp_pkt.src_ip, in_port)
                self.logger.info(f"[Proxy ARP] S{datapath.id}:P{in_port} Answered for {target_ip}")

    def send_arp_reply(self, datapath, src_mac, src_ip, dst_mac, dst_ip, out_port):
        pkt = packet.Packet()
        pkt.add_protocol(ethernet.ethernet(ethertype=ether_types.ETH_TYPE_ARP, dst=dst_mac, src=src_mac))
        pkt.add_protocol(arp.arp(
            opcode=arp.ARP_REPLY,
            src_mac=src_mac, src_ip=src_ip,
            dst_mac=dst_mac, dst_ip=dst_ip
        ))
        pkt.serialize()
        actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]
        out = datapath.ofproto_parser.OFPPacketOut(
            datapath=datapath, buffer_id=datapath.ofproto.OFP_NO_BUFFER,
            in_port=datapath.ofproto.OFPP_CONTROLLER, actions=actions, data=pkt.data
        )
        datapath.send_msg(out)

    def handle_ipv4(self, datapath, in_port, eth, ip_pkt, data):
        dpid = datapath.id
        dst_ip = ip_pkt.dst_ip
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        if dpid not in self.routing_table or dst_ip not in self.routing_table[dpid]:
            return

        out_port = self.routing_table[dpid][dst_ip]
        actions = [parser.OFPActionOutput(out_port)]

        # [필수 조건] eth_type=0x0800 반드시 선언
        match = parser.OFPMatch(eth_type=0x0800, ipv4_dst=dst_ip)
        self.add_flow(datapath, priority=10, match=match, actions=actions, idle_timeout=60)
        self.logger.info(f"[Flow Mod] S{dpid}: dst {dst_ip} -> OutPort {out_port}")

        # 첫 패킷 무유실 포워딩
        out = parser.OFPPacketOut(
            datapath=datapath, buffer_id=ofproto.OFP_NO_BUFFER,
            in_port=in_port, actions=actions, data=data
        )
        datapath.send_msg(out)
```

---

### Step 5: 1주차 E2E 검증 (`pingall` & 토폴로지 Redis 동기화)

#### 🎯 작업 목표
컨트롤러에 Redis 토폴로지 발행 로직을 붙이고, Mininet 환경에서 `pingall`이 100% 성공(0% dropped)하는지 최종 검증합니다.

#### 💬 AI 프롬프트 (Step 5)
```text
`controller.py`에 스위치 4대가 모두 연결되었을 때 Redis `sdn:topology:sync` 채널로
토폴로지 노드/링크 JSON을 발행하는 로직을 추가하고,
1주차 전체 동작을 한 번에 검증하는 쉘 스크립트 `scripts/verify_week1.sh`를 작성해줘.

[Redis 토폴로지 발행 명세]
- Redis 호스트: 127.0.0.1:6379 (db=0)
- 채널: `sdn:topology:sync`
- JSON 포맷:
  {
    "nodes": [
      {"id": "s1", "label": "Switch 1 (Ingress)", "type": "switch", "dpid": "0000000000000001"},
      {"id": "s2", "label": "Switch 2 (Primary)", "type": "switch", "dpid": "0000000000000002"},
      {"id": "s3", "label": "Switch 3 (Bypass)", "type": "switch", "dpid": "0000000000000003"},
      {"id": "s4", "label": "Switch 4 (Egress)", "type": "switch", "dpid": "0000000000000004"},
      {"id": "h_legit", "label": "Host Legit", "type": "host", "ip": "10.0.0.1", "mac": "00:00:00:00:00:01"},
      {"id": "h_attacker", "label": "Host Attacker", "type": "host", "ip": "10.0.0.2", "mac": "00:00:00:00:00:02"},
      {"id": "h_server", "label": "Server", "type": "host", "ip": "10.0.0.4", "mac": "00:00:00:00:00:04"}
    ],
    "links": [
      {"source": "s1", "target": "h_legit", "src_port": 1, "dst_port": 0, "status": "active"},
      {"source": "s1", "target": "h_attacker", "src_port": 2, "dst_port": 0, "status": "active"},
      {"source": "s1", "target": "s2", "src_port": 3, "dst_port": 1, "status": "active"},
      {"source": "s1", "target": "s3", "src_port": 4, "dst_port": 1, "status": "active"},
      {"source": "s2", "target": "s4", "src_port": 2, "dst_port": 2, "status": "active"},
      {"source": "s3", "target": "s4", "src_port": 2, "dst_port": 3, "status": "active"},
      {"source": "s4", "target": "h_server", "src_port": 1, "dst_port": 0, "status": "active"}
    ]
  }

[verify_week1.sh 검증 단계]
1. `sudo ./scripts/clean_mininet.sh`
2. `docker compose restart ryu-controller`
3. 3초 대기 후 Mininet 실행하여 pingall 테스트
4. 0% dropped 확인 시 "[SUCCESS] Week 1 Milestone Achieved!" 출력
```

#### 🛠️ 실행 및 최종 검증
```bash
cd /home/tlgus/programming/textgg/A

# 1. 컨트롤러 재기동
docker compose restart ryu-controller

# 2. Mininet 실행
sudo -E env "PATH=$PATH" python3 topo/diamond_topo.py

# 3. Mininet 대화형 CLI에서 통신 테스트
mininet> pingall
# [결과 확인]
# *** Ping: testing ping reachability
# h_legit -> h_attacker h_server 
# h_attacker -> h_legit h_server 
# h_server -> h_legit h_attacker 
# *** Results: 0% dropped (6/6 received)

# 4. 스위치 플로우 테이블 검증 (Priority 10 확인)
mininet> sh ovs-ofctl dump-flows s1 -O OpenFlow13

# 5. Redis 동기화 메시지 수신 확인 (별도 터미널)
docker exec -it sdn-redis redis-cli SUBSCRIBE sdn:topology:sync
```

> **🎉 최종 1주차 성공 판정:**  
> `pingall` 결과 **`Results: 0% dropped (6/6 received)`** 가 출력되면 1주차 개발자 A의 임무는 완벽히 완수된 것입니다!

---

## 4. 개발자 A 전용 치명적 함정 & 디버깅 체크리스트

| # | 문제 현상 / 에러 메시지 | 근본 원인 | 해결책 및 즉시 조치법 |
|---|---|---|---|
| **1** | `pingall` 시 CPU 100% 치솟고 Mininet 먹통 | 루프로 인한 **ARP Broadcast Storm** | Ryu에서 `OFPP_FLOOD`를 금지하고, `self.handle_arp`의 Proxy ARP 로직이 적용되어 있는지 확인. |
| **2** | Ryu 컨테이너 시작 시 `Address already in use` (6653) | 호스트의 `openvswitch-testcontroller` 데몬이 포트 점유 | `sudo systemctl stop openvswitch-testcontroller && sudo systemctl disable openvswitch-testcontroller` |
| **3** | 스위치 연결 실패: `OFPH_HELLO_FAILED: Version mismatch` | OVS 스위치가 OpenFlow 1.0으로 접속 시도 | `diamond_topo.py`에서 `cls=OpenFlow13Switch` (`protocols='OpenFlow13'`) 누락 여부 확인. |
| **4** | 플로우 추가 시 `OFPBMC_BAD_PREREQ` 에러 | IPv4 매칭 시 `eth_type=0x0800` 누락 | `OFPMatch(eth_type=0x0800, ipv4_dst=dst_ip)`로 수정. |
| **5** | S4 스위치 연결 후 호스트 통신 실패 | Mininet `addLink` 시 포트 번호 미지정으로 포트 뒤바뀜 | `port1=...`, `port2=...` 명시적 파라미터 확인. |
| **6** | Ryu 로그에 `IndexError: list index out of range` 도배 | LLDP/IPv6 패킷 파싱 에러 | `eth = pkt.get_protocol(ethernet.ethernet); if not eth or eth.ethertype in (ETH_TYPE_LLDP, 0x86dd): return` |
| **7** | `sudo python3 topo/diamond_topo.py` 실행 시 모듈 에러 | sudo 실행 시 PATH 및 가상환경 유실 | `sudo -E env "PATH=$PATH" python3 topo/diamond_topo.py` 로 실행. |

---

## 5. 팀원(개발자 B, C) 인계 사항 및 1주차 완료 보고서 양식

### 5.1 개발자 B (AI & 보안)에게 인계할 정보
1. **토폴로지 호스트 네임스페이스 접근 방법:**
   - Scapy 공격 및 정상 트래픽 생성 스크립트는 Mininet 호스트 네임스페이스 안에서 구동해야 OVS 가상 스위치로 주입됩니다.
   - 실행 방법:
     ```bash
     mininet> h_attacker python3 traffic_attack.py &
     mininet> h_legit python3 traffic_normal.py &
     ```
2. **단말 IP 및 MAC 주소:**
   - H_legit: `10.0.0.1` (`00:00:00:00:00:01`) -> S1:Port 1
   - H_attacker: `10.0.0.2` (`00:00:00:00:00:02`) -> S1:Port 2
   - H_server: `10.0.0.4` (`00:00:00:00:00:04`) -> S4:Port 1

### 5.2 개발자 C (웹 관제탑)에게 인계할 정보
1. **Redis 채널 통신:**
   - Redis 포트 `6379`가 호스트 네트워크로 개방되어 있음.
   - 토폴로지 동기화 채널: `sdn:topology:sync`
2. **DPID 규격:**
   - S1: `0000000000000001`, S2: `0000000000000002`, S3: `0000000000000003`, S4: `0000000000000004`

---

### 5.3 [주간 회의용] 개발자 A 1주차 완료 보고 양식 (슬랙/노션 공유용)
```markdown
### 🚀 [개발자 A] 1주차 SDN 인프라 & 제어 평면 개발 완료 보고

1. **완료 작업 요약:**
   - [x] Ubuntu 22.04 호스트 환경 구축 (Mininet 2.3+ & OVS 2.17.x, rp_filter 해제, OVS 데몬 정리)
   - [x] Docker 기반 Ryu 4.34 (OF 1.3) 및 Redis 7.2 컨테이너 환경 격리 배포 완료
   - [x] 다중 경로 다이아몬드 토폴로지(`topo/diamond_topo.py`) 구축 (포트 고정: S1-S4, 호스트 3대)
   - [x] OpenFlow 1.3 컨트롤러(`ryu/app/controller.py`) 구현 (Table-Miss, Proxy ARP, L3 최단 경로)
   - [x] 다이아몬드 루프 내 ARP Broadcast Storm 차단 및 `pingall` 100% 성공(0% dropped) 검증 완료
   - [x] Redis 토폴로지 동기화 규격(`sdn:topology:sync`) 메시지 연동 준비 완료

2. **2주차 개발 계획:**
   - Ryu 2-Tier 포트 통계 수집기(`OFPPortStatsRequest`, 2초 주기) 구현
   - 수집된 실시간 포트 메트릭 Redis(`sdn:stats:port`) 스트리밍
   - 단일 스위치 진입 포트 차단(`Priority 100 In_port Drop`) 기능 단위 테스트

3. **팀원 공유 사항:**
   - Redis 브로커 `127.0.0.1:6379` 정상 구동 중
   - Mininet 실행 시 `sudo -E env "PATH=$PATH" python3 topo/diamond_topo.py` 사용 요망
```
