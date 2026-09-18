# 🛡️ [제4편] 네트워크 보안: IP Spoofing, SYN Flooding & In_port 격리 방어

> ⬅️ [제3편: Ryu SDN 컨트롤러 아키텍처](./03_Ryu_SDN_Controller.md) | 🏠 [목차](./README.md) | ➡️ [제5편: AI 이상 탐지 & 5대 피처](./05_AI_Anomaly_Detection_and_Features.md)

본 문서는 네트워크 보안의 핵심 위협인 **DDoS 공격(SYN Flooding)**과 **IP 위변조(IP Spoofing)**의 작동 메커니즘, Scapy를 이용한 모의 트래픽 조작 기법, 그리고 본 프로젝트의 핵심 방어 전략인 **In_port(진입 포트) 격리 방어**의 수학적/논리적 필요성을 학습합니다.

---

## 1. DDoS 공격과 IP Spoofing의 작동 원리

### 1.1 TCP SYN Flooding 공격
TCP 프로토콜은 신뢰성 있는 전송을 위해 3-Way Handshake를 거칩니다.

1. **정상 시나리오:**
   - 클라이언트 $\to$ 서버: `SYN`
   - 서버 $\to$ 클라이언트: `SYN-ACK` (서버 메모리의 **Backlog Queue(백로그 큐)**에 하프 오픈(Half-Open) 세션 할당)
   - 클라이언트 $\to$ 서버: `ACK` (연결 확정 및 자원 소모 정상화)
2. **SYN Flooding 공격 시나리오:**
   - 공격자는 초당 수천~수만 개의 `SYN` 패킷을 서버의 80번(HTTP) 포트로 전송합니다.
   - 서버는 각각의 SYN 패킷마다 백로그 큐 메모리를 할당하고 `SYN-ACK`를 보내지만, 공격자는 고의로 마지막 `ACK`를 보내지 않습니다.
   - 서버의 백로그 큐(`net.ipv4.tcp_max_syn_backlog`)가 수초 만에 가득 차고(SYN Queue Exhaustion), 서버는 일반 정상 사용자의 접속 시도를 모두 드랍하게 됩니다.

---

### 1.2 IP Spoofing (IP 주소 위변조)
IP 헤더(L3)의 `Source IP` 필드는 패킷을 생성하는 운영체제나 프로그램이 임의의 32비트 정수를 적어 넣을 수 있는 구조적 취약점을 지닙니다.

공격자는 출발지 IP를 `1.1.1.1`, `8.8.8.8`, `123.45.67.89` 등 전 세계의 무작위 가짜 IP로 매 패킷마다 변조하여 발송합니다:
1. **역추적 불가:** 서버가 응답(`SYN-ACK`)을 가짜 IP로 보내므로 실제 공격자의 위치가 은닉됩니다.
2. **반사/증폭 효과:** 불필요한 네트워크 트래픽이 제3자에게 흩어집니다.

---

## 2. 전통적 IP 차단 vs SDN In_port 격리 차단 비교

### 2.1 왜 IP 기반 차단(Blacklist)은 SDN 환경에서 자살행위인가?

공격자가 초당 5,000개의 패킷을 무작위 변조 IP로 전송한다고 가정해 봅시다:

| 구분 | 전통적 IP 차단 방식 (Blacklist) | 본 프로젝트의 In_port 격리 방식 |
|---|---|---|
| **매칭 조건** | `match = OFPMatch(ipv4_src="가짜 IP")` | `match = OFPMatch(in_port=2)` |
| **생성되는 플로우 규칙 수** | **초당 5,000개의 신규 규칙 생성** | **단 1개의 규칙 생성** |
| **스위치 메모리(TCAM) 영향** | 수초 만에 메모리 고갈 (**Flow Table Overflow**) | 메모리 사용량 거의 제로 |
| **컨트롤러 부하** | 매초 5,000개의 `Packet-In` 발생으로 컨트롤러 마비 | 스위치 레벨에서 즉시 Drop (컨트롤러 부하 0%) |
| **방어 성공 여부** | ❌ **완전 실패 (공격 우회 및 장비 다운)** |  **완벽 차단 (100% 드랍)** |

> 💡 **In_port 차단의 본질:**  
> 공격자가 L3 헤더의 IP 주소를 제아무리 수천만 번 바꾸더라도, 패킷이 스위치에 물리적/가상으로 들어오는 **"전선(인그레스 포트)"**은 바꿀 수 없습니다!  
> S1 스위치의 2번 포트에 공격자 호스트가 꽂혀 있다면, `in_port=2, Action=Drop` 규칙 하나만 넣으면 공격 패킷은 스위치 입구에서 100% 폐기됩니다.

---

### 2.2 [매우 중요] Access Port vs Trunk Port 구분 원칙

In_port 차단을 적용할 때 절대로 범해서는 안 되는 치명적 실수가 있습니다:

1. **Access Port (단말 연결 포트):**
   - 단말 호스트(H_legit, H_attacker, H_server)가 1:1로 직접 물려 있는 종단 포트.
   - **이 포트는 차단(Drop)해도 다른 정상 사용자의 통신에 전혀 영향을 주지 않습니다.**
2. **Trunk Port (스위치 간 상호 연결 포트):**
   - 스위치와 스위치를 연결하는 간선 링크 포트 (예: S1-S2, S1-S3).
   - 수많은 호스트의 트래픽이 멀티플렉싱(다중화)되어 함께 지나갑니다.
   - 🚨 **트렁크 포트를 In_port Drop으로 차단하면 공격 트래픽뿐만 아니라 그 링크를 지나던 모든 정상 트래픽까지 동반 살상(Collateral Damage)됩니다.**

> 👉 **설계 원칙:**  
> 컨트롤러는 포트가 단말과 연결된 **Access Port**인지, 스위치 간 연결된 **Trunk Port**인지 토폴로지 정보를 통해 사전에 분류하고, **오직 Access Port에 대해서만 In_port Drop을 실행**해야 합니다.

---

## 3. Scapy 기반 트래픽 조작 실무

Scapy는 파이썬 기반의 강력한 대화형 패킷 조작 라이브러리로, L2부터 L7까지 모든 헤더 필드를 자유자재로 조합할 수 있습니다.

### 3.1 Scapy 레이어 결합 문법 (`/` 연산자)
```python
from scapy.all import Ether, IP, TCP, Raw

# Ethernet(L2) / IP(L3) / TCP(L4) / Payload(L7) 스택 쌓기
pkt = Ether(src="00:00:00:00:00:01", dst="00:00:00:00:00:04") / \
      IP(src="10.0.0.1", dst="10.0.0.4") / \
      TCP(sport=12345, dport=80, flags="S") / \
      Raw(load="Hello SDN")
```

### 3.2 정상 트래픽 vs 공격 트래픽의 핵심 특성 (피처 차이)

| 메트릭 | 정상 트래픽 (`traffic_normal.py`) | DDoS 공격 트래픽 (`traffic_attack.py`) |
|---|---|---|
| **BPP (Bytes Per Packet)** | **500 ~ 1,400 Bytes** (HTTP 페이로드로 인해 큼) | **54 ~ 74 Bytes** (헤더만 있는 초소형 패킷) |
| **PPS (Packets Per Second)** | **10 ~ 100 PPS** (안정적이고 완만함) | **1,000 ~ 10,000 PPS** (순식간에 폭증) |
| **TCP Flags** | 주로 `PA` (Push+Ack), `A` (Ack) 혼합 | **오직 `S` (SYN)**만 집중 발생 |
| **발신지 IP 패턴** | 일정한 서브넷(10.0.0.1) 유지 | 매 패킷마다 완전히 무작위(Randomized) |

### 3.3 Scapy 공격기 핵심 코드 구조
```python
import random
from scapy.all import IP, TCP, sendp, Ether

def generate_random_ip():
    # 사설 대역을 제외한 임의의 공인 IPv4 주소 생성
    return f"{random.randint(1, 223)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"

def run_syn_flood(target_ip="10.0.0.4", target_port=80, iface="h2-eth0"):
    while True:
        spoofed_ip = generate_random_ip()
        sport = random.randint(1024, 65535)
        
        # 초소형 SYN 패킷 빌드
        pkt = Ether() / IP(src=spoofed_ip, dst=target_ip) / TCP(sport=sport, dport=target_port, flags="S")
        
        # [중요] 체크섬 재계산 강제화
        del pkt[IP].chksum
        del pkt[TCP].chksum
        
        sendp(pkt, iface=iface, verbose=False)
```

---

## 4. 리눅스 환경 실전 함정 2가지

### 4.1 체크섬 오프로딩 (Checksum Offload) 이슈
- 가상 이더넷(`veth`) 환경에서 리눅스 커널은 성능 향상을 위해 L4 체크섬 계산을 생략하고 하드웨어(NIC)로 넘기는 "Checksum Offloading"을 사용합니다.
- Scapy로 패킷을 수동 조작할 때 체크섬 필드를 비워두거나 명시적으로 재계산하지 않으면, 수신측 OVS 스위치나 커널 스택이 **"Checksum Error"로 패킷을 사전에 버려버려** 공격 시연 자체가 안 될 수 있습니다.
- **해결책:** 패킷 생성 직후 `del pkt[IP].chksum`, `del pkt[TCP].chksum`을 실행하여 Scapy가 직접 올바른 체크섬을 계산하도록 강제합니다.

### 4.2 커널의 역방향 경로 필터링 (`rp_filter`)
- 최신 우분투 커널은 보안을 위해 `rp_filter`(Reverse Path Filtering)가 기본 활성화되어 있습니다. 들어온 패킷의 출발지 IP가 라우팅 테이블과 맞지 않으면(스푸핑된 패킷이면) 커널이 자동으로 패킷을 버립니다.
- 모의 공격 테스트 시 호스트 리눅스에서 `rp_filter`를 완화해야 패킷이 정상적으로 Mininet 가상 네트워크 안에서 흐릅니다:
  ```bash
  sudo sysctl -w net.ipv4.conf.all.rp_filter=0
  sudo sysctl -w net.ipv4.conf.default.rp_filter=0
  ```

---

> ⬅️ [제3편: Ryu SDN 컨트롤러 아키텍처](./03_Ryu_SDN_Controller.md) | 🏠 [목차](./README.md) | ➡️ [제5편: AI 이상 탐지 & 5대 피처](./05_AI_Anomaly_Detection_and_Features.md)
