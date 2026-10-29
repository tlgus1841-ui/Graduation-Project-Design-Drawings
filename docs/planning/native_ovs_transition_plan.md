# 🚀 [구현 계획서] 순수 OVS 단독 구동 전환 (Native OVS Transition Plan)
> **Phase 6-A 마일스톤: Mininet 의존성 완전 제거 및 상용급 커널 OVS 데이터 플레인 구축**  
> 문서 버전: v1.0 | 작성일: 2026-10-29 | 작성자: 박시현 (Tech Lead)

---

## 1. 추진 배경 및 상용화 목적

### 1.1 Mininet 제거의 기술적 배경
* **에뮬레이터 종속성 탈피:** Mininet은 교육/연구용 파이썬 래퍼 도구로, 상용 환경(엔터프라이즈 데이터센터, 클라우드 VM, Kubernetes CNI)에서는 사용할 수 없습니다.
* **패킷 포워딩 성능 한계:** Mininet의 프로세스 소켓 관리 오버헤드로 인해 초당 수십만 패킷(PPS) 이상의 극한 DDoS 스트레스 환경에서 CPU 낭비가 발생합니다.
* **환경 호환성 및 설치 간소화:** `apt install mininet`은 파이썬 구버전 및 커널 모듈 의존성 문제를 자주 일으키나, 순수 OVS(`openvswitch-switch`)와 리눅스 기본 유틸리티(`iproute2`)는 모든 리눅스 배포판의 표준 패키지입니다.

### 1.2 핵심 전환 목표
1. **Zero-Code Modification:** 기존 Ryu 4.34 컨트롤러, AI 이상 탐지 엔진, FastAPI 백엔드, React 웹 관제탑 코드를 **단 1줄도 수정하지 않고 100% 호환** 유지.
2. **원클릭 자동화 스크립트:** 리눅스 쉘 스크립트 2종(`setup_native_ovs.sh`, `teardown_native_ovs.sh`)만으로 4-스위치 다이아몬드 토폴로지 완벽 기동 및 클린업.
3. **네이티브 트래픽 제어:** Mininet CLI 대신 표준 Linux Network Namespace(`ip netns exec`)를 활용한 직관적인 트래픽 주입 환경 구축.

---

## 2. 시스템 아키텍처 및 토폴로지 설계

기존 `DiamondTopo`의 OpenFlow 포트 번호(1~4번), DPID(1~4번), 호스트 IP 및 MAC 주소를 그대로 보존합니다.

```
       [ns_legit] (10.0.0.1)             [ns_attacker] (10.0.0.2)
     (00:00:00:00:00:01)               (00:00:00:00:00:02)
            │                                   │
            │ (veth_legit-s1)                   │ (veth_att-s1)
            ▼ ofport: 1                         ▼ ofport: 2
     +-------------------------------------------------------------+
     |                 OVS Bridge s1 (DPID: 1)                     |
     |                     Ingress Switch                          |
     +-------------------------------------------------------------+
            │ ofport: 3                         │ ofport: 4
            │ (s1-s2)                           │ (s1-s3)
            ▼                                   ▼
     +---------------+                   +---------------+
     | S2 (DPID: 2)  |                   | S3 (DPID: 3)  |
     | Primary Path  |                   |  Bypass Path  |
     | (s2-s1: ofp 1)|                   | (s3-s1: ofp 1)|
     +---------------+                   +---------------+
            │ ofport: 2                         │ ofport: 2
            │ (s2-s4)                           │ (s3-s4)
            ▼                                   ▼
     +-------------------------------------------------------------+
     |                 OVS Bridge s4 (DPID: 4)                     |
     |                      Egress Switch                          |
     +-------------------------------------------------------------+
            ▲ ofport: 2 (from S2)               ▲ ofport: 3 (from S3)
            │
            │ ofport: 1 (veth_srv-s4)
            ▼
       [ns_server] (10.0.0.4)
     (00:00:00:00:00:04)
```

### 2.1 엄격한 포트 핀 고정 (OpenFlow Port Pinning)
OVS는 인터페이스 추가 순서에 따라 포트 번호가 가변될 수 있으므로, 포트 추가 시 `ofport_request` 옵션을 강제하여 포트 번호의 일관성을 보장합니다:

| 스위치 (DPID) | OpenFlow Port | 연결 대상 (Interface Name) | 설명 |
|:---|:---:|:---|:---|
| **S1 (1)** | **1** | `s1-legit` (peer: `veth_legit` in `ns_legit`) | 정상 호스트 H_legit 유입 포트 |
| | **2** | `s1-attacker` (peer: `veth_att` in `ns_attacker`) | 공격자 H_attacker 유입 포트 (차단 대상) |
| | **3** | `s1-s2` (peer: `s2-s1`) | Primary 주 경로 트렁크 포트 |
| | **4** | `s1-s3` (peer: `s3-s1`) | Bypass 우회 경로 트렁크 포트 |
| **S2 (2)** | **1** | `s2-s1` (peer: `s1-s2`) | S1 인입 포트 |
| | **2** | `s2-s4` (peer: `s4-s2`) | S4 인출 포트 (주 경로) |
| **S3 (3)** | **1** | `s3-s1` (peer: `s1-s3`) | S1 인입 포트 |
| | **2** | `s3-s4` (peer: `s4-s3`) | S4 인출 포트 (우회 경로) |
| **S4 (4)** | **1** | `s4-server` (peer: `veth_srv` in `ns_server`) | 목적지 서버 H_server 인출 포트 |
| | **2** | `s4-s2` (peer: `s2-s4`) | S2 인입 포트 |
| | **3** | `s4-s3` (peer: `s3-s4`) | S3 인입 포트 |

---

## 3. 상세 스크립트 구현 명세

### 3.1 토폴로지 기동 스크립트: `scripts/setup_native_ovs.sh`

```bash
#!/usr/bin/env bash
# ==============================================================================
# Self-Defending SDN Tower: Native OVS 4-Switch Diamond Topology Setup
# ==============================================================================
set -euo pipefail

CTRL_IP="${CTRL_IP:-127.0.0.1}"
CTRL_PORT="${CTRL_PORT:-6633}"

echo ">>> [1/5] OVS 브릿지 4개 생성 및 OpenFlow 1.3 설정..."
for sw in s1 s2 s3 s4; do
  ovs-vsctl --may-exist add-br "$sw"
  ovs-vsctl set bridge "$sw" protocols=OpenFlow13
  ovs-vsctl set-fail-mode "$sw" secure
done

# DPID 고정 (16자리 16진수)
ovs-vsctl set bridge s1 other-config:datapath-id=0000000000000001
ovs-vsctl set bridge s2 other-config:datapath-id=0000000000000002
ovs-vsctl set bridge s3 other-config:datapath-id=0000000000000003
ovs-vsctl set bridge s4 other-config:datapath-id=0000000000000004

echo ">>> [2/5] Ryu SDN 컨트롤러 연결..."
for sw in s1 s2 s3 s4; do
  ovs-vsctl set-controller "$sw" "tcp:${CTRL_IP}:${CTRL_PORT}"
done

echo ">>> [3/5] 스위치 간 트렁크 veth 페어 생성 및 연결..."
# S1 <-> S2 (S1 ofp:3, S2 ofp:1)
ip link add s1-s2 type veth peer name s2-s1
ovs-vsctl add-port s1 s1-s2 -- set Interface s1-s2 ofport_request=3
ovs-vsctl add-port s2 s2-s1 -- set Interface s2-s1 ofport_request=1
ip link set s1-s2 up && ip link set s2-s1 up

# S1 <-> S3 (S1 ofp:4, S3 ofp:1)
ip link add s1-s3 type veth peer name s3-s1
ovs-vsctl add-port s1 s1-s3 -- set Interface s1-s3 ofport_request=4
ovs-vsctl add-port s3 s3-s1 -- set Interface s3-s1 ofport_request=1
ip link set s1-s3 up && ip link set s3-s1 up

# S2 <-> S4 (S2 ofp:2, S4 ofp:2)
ip link add s2-s4 type veth peer name s4-s2
ovs-vsctl add-port s2 s2-s4 -- set Interface s2-s4 ofport_request=2
ovs-vsctl add-port s4 s4-s2 -- set Interface s4-s2 ofport_request=2
ip link set s2-s4 up && ip link set s4-s2 up

# S3 <-> S4 (S3 ofp:2, S4 ofp:3)
ip link add s3-s4 type veth peer name s4-s3
ovs-vsctl add-port s3 s3-s4 -- set Interface s3-s4 ofport_request=2
ovs-vsctl add-port s4 s4-s3 -- set Interface s4-s3 ofport_request=3
ip link set s3-s4 up && ip link set s4-s3 up

echo ">>> [4/5] 호스트 네임스페이스 및 veth 연결..."
# H_legit (10.0.0.1, 00:00:00:00:00:01) -> S1 ofport: 1
ip netns add ns_legit
ip link add veth_legit type veth peer name s1-legit
ip link set veth_legit netns ns_legit
ovs-vsctl add-port s1 s1-legit -- set Interface s1-legit ofport_request=1
ip link set s1-legit up

ip netns exec ns_legit ip link set lo up
ip netns exec ns_legit ip link set veth_legit address 00:00:00:00:00:01
ip netns exec ns_legit ip addr add 10.0.0.1/24 dev veth_legit
ip netns exec ns_legit ip link set veth_legit up

# H_attacker (10.0.0.2, 00:00:00:00:00:02) -> S1 ofport: 2
ip netns add ns_attacker
ip link add veth_att type veth peer name s1-attacker
ip link set veth_att netns ns_attacker
ovs-vsctl add-port s1 s1-attacker -- set Interface s1-attacker ofport_request=2
ip link set s1-attacker up

ip netns exec ns_attacker ip link set lo up
ip netns exec ns_attacker ip link set veth_att address 00:00:00:00:00:02
ip netns exec ns_attacker ip addr add 10.0.0.2/24 dev veth_att
ip netns exec ns_attacker ip link set veth_att up

# H_server (10.0.0.4, 00:00:00:00:00:04) -> S4 ofport: 1
ip netns add ns_server
ip link add veth_srv type veth peer name s4-server
ip link set veth_srv netns ns_server
ovs-vsctl add-port s4 s4-server -- set Interface s4-server ofport_request=1
ip link set s4-server up

ip netns exec ns_server ip link set lo up
ip netns exec ns_server ip link set veth_srv address 00:00:00:00:00:04
ip netns exec ns_server ip addr add 10.0.0.4/24 dev veth_srv
ip netns exec ns_server ip link set veth_srv up

echo ">>> [5/5] ARP 정적 테이블 구성 (초기 브로드캐스트 스톰 방지)..."
ip netns exec ns_legit arp -s 10.0.0.4 00:00:00:00:00:04
ip netns exec ns_attacker arp -s 10.0.0.4 00:00:00:00:00:04
ip netns exec ns_server arp -s 10.0.0.1 00:00:00:00:00:01
ip netns exec ns_server arp -s 10.0.0.2 00:00:00:00:00:02

echo "=== ✅ Native OVS 4-스위치 토폴로지 구축 완료 ==="
```

### 3.2 토폴로지 정리 스크립트: `scripts/teardown_native_ovs.sh`

```bash
#!/usr/bin/env bash
# ==============================================================================
# Self-Defending SDN Tower: Native OVS Topology Teardown & Clean
# ==============================================================================
echo ">>> OVS 브릿지 삭제..."
for sw in s1 s2 s3 s4; do
  ovs-vsctl --if-exists del-br "$sw"
done

echo ">>> 네트워크 네임스페이스 삭제..."
for ns in ns_legit ns_attacker ns_server; do
  ip netns del "$ns" 2>/dev/null || true
done

echo ">>> 잔여 veth 링크 정리..."
for link in s1-s2 s1-s3 s2-s4 s3-s4 s1-legit s1-attacker s4-server; do
  ip link del "$link" 2>/dev/null || true
done

echo "=== ✅ Native OVS 토폴로지 정리 완료 ==="
```

---

## 4. 트래픽 주입 및 시연 실행 가이드

Mininet CLI 대신 Linux 네임스페이스 명령을 직접 사용하여 백그라운드/포그라운드 트래픽을 주입합니다.

```bash
# 1. 정상 사용자 Ping 테스트
sudo ip netns exec ns_legit ping -c 3 10.0.0.4

# 2. 정상 HTTP/웹 트래픽 생성기 실행
sudo ip netns exec ns_legit python3 -m traffic.normal_user --target 10.0.0.4

# 3. 고속 SYN Flood 공격 트래픽 발사
sudo ip netns exec ns_attacker python3 -m traffic.traffic_flood --target 10.0.0.4 --pps 3000

# 4. 포트 스캔 모의 공격 발사
sudo ip netns exec ns_attacker python3 -m traffic.traffic_scan --target 10.0.0.4 --kind tcp
```

---

## 5. 단계별 검증 및 롤아웃 계획 (Milestones)

| 단계 | 작업 내용 | 검증 기준 및 확인 방법 | 일정 |
|:---:|:---|:---|:---:|
| **Step 1** | `setup_native_ovs.sh` 및 `teardown_native_ovs.sh` 작성 | • `ovs-vsctl show`로 4개 브릿지/포트 번호 확인<br>• `teardown` 후 잔여 인터페이스 0건 확인 | 1일차 |
| **Step 2** | Ryu 컨트롤러 연동 및 기본 L2 포워딩 검증 | • Ryu 컨트롤러 로그에 DPID 1, 2, 3, 4 스위치 연결 확인<br>• `ns_legit`에서 `ns_server`로 Ping 100% 성공 확인 | 1일차 |
| **Step 3** | 실시간 텔레메트리 및 관제탑 웹 UI 연동 | • Ryu가 Redis로 포트 통계(2초) 및 플로우 카운트(1초) 송출 확인<br>• React 관제탑 화면에 4개 스위치 다이아몬드 정상 렌더링 | 2일차 |
| **Step 4** | E2E 자율 방어 및 우회 라우팅 실측 검증 | • `ns_attacker` 공격 주입 시 AI 탐지 확정<br>• S1 ofport 2 즉시 격리 확인<br>• 주 경로(S2) ➔ 우회 경로(S3) 전환 실측 (손실률 0.0%) | 2일차 |
| **Step 5** | 기존 `topo/diamond_topo.py` 래핑 및 회귀 테스트 | • `tests/` 265개 테스트 100% Pass 유지<br>• CI/CD 및 로컬 환경에서 테스트 정상 통과 | 3일차 |

---

## 6. 기대 효과 및 결론

1. **상용 프로덕션 환경 완전 호환:** GCP/AWS 클라우드 VM뿐만 아니라 실제 베어메탈 서버, Linux 컨테이너 환경에서 Mininet 없이 즉시 데모 및 상용 서비스 배포 가능.
2. **소프트웨어 안정성 증대:** Mininet 종료 실패 시 발생하던 OVS 소켓/좀비 프로세스 꼬임 문제를 `teardown_native_ovs.sh`로 1초 만에 완벽 클린업.
3. **핵심 로직 무수정(Zero Risk):** 컨트롤러, AI, 웹 백엔드, 프론트엔드 코드를 전혀 건드리지 않고 인프라 계층만 상용 표준으로 고도화 완료.
