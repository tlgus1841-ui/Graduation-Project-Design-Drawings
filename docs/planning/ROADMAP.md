# 🧭 Self-Defending SDN Tower: 종합 로드맵 (ROADMAP)
> **SDN 기반 분산 트래픽 이상 탐지 및 자율 라우팅 관제 시스템**  
> 본 문서는 시스템 아키텍처, 기 개발 완료된 핵심 성과(축약 요약), 그리고 향후 상용화 로드맵을 정의합니다.

---

## 1. 시스템 아키텍처 및 확정 기술 스택

```
+-----------------------------------------------------------------------------------+
|                        [Layer 4: 웹 관제탑 (Frontend)]                            |
|  - React 18.2 (Vite) + Tailwind CSS + Lucide Icons                                |
|  - vis-network 9.1: 실시간 네트워크 토폴로지 (노드 상태, 링크 트래픽, 우회 활성화)   |
|  - ApexCharts 3.46: 실시간 BPP/PPS 시계열 차트 & 이상치 스코어                      |
|  - Event Timeline: 실시간 보안 알림 & 비상 수동 격리/복원 제어 패널               |
+-----------------------------------------------------------------------------------+
                                        ▲ WebSocket (실시간 브로드캐스팅)
                                        ▼ REST API (관리자 수동 제어 / Relearn 승인)
+-----------------------------------------------------------------------------------+
|                        [Layer 3: 관제 백엔드 (FastAPI)]                           |
|  - Python 3.10, FastAPI 0.109, Uvicorn 0.27                                       |
|  - Asyncio 기반 고속 WebSocket Hub (클라이언트 멀티캐스팅)                        |
|  - Redis Bridge: 4채널 구독 (stats, alert, command, flowcount) → Pydantic 스키마 검증 |
|  - Manual Control: 비상 격리/복원 및 60초 자동 격리 지연(Hold) 안전 제어            |
+-----------------------------------------------------------------------------------+
                                        ▲▼ Redis 7.2 Pub/Sub (고속 IPC 버스)
+-----------------------------------------------------------------------------------+
|                        [Layer 2: AI 이상 탐지 및 분류 엔진]                       |
|  - Isolation Forest: 실시간 BPP, ΔPPS 기반 이상치 탐지                             |
|  - Criteria Engine: 1초 주기 실측 카운트 기반 6종 공격 정밀 분류 (학술 논문 출처 반영)|
|    (SYN/UDP/ICMP Flood, Port Scan, Slow HTTP, 내부 확산)                          |
|  - EwmaDetector & Contamination Tuning: Flash Crowd(정상 급증) 오탐 방지          |
+-----------------------------------------------------------------------------------+
                                        ▲ 텔레메트리 발행 / ▼ 플로우 제어 명령
+-----------------------------------------------------------------------------------+
|                        [Layer 1: SDN 컨트롤러 (Ryu 4.34)]                         |
|  - Docker (Python 3.8 격리), OpenFlow 1.3 표준                                    |
|  - NetworkX Dijkstra: S1-S2-S4(주 경로) ↔ S1-S3-S4(우회 경로) 선제적 프로비저닝   |
|  - FSM 상태머신: Normal → Under Attack → Mitigated → Restoring (플래핑 방지)      |
|  - Circuit Breaker: AI 장애 시 컨트롤러 보호 및 안전 모드 전환                    |
+-----------------------------------------------------------------------------------+
                                        ▲ OpenFlow 1.3
+-----------------------------------------------------------------------------------+
|                        [Layer 0: Data Plane (OVS 토폴로지)]                       |
|  - 4-Switch Diamond Topology (S1: Ingress, S2: Primary, S3: Bypass, S4: Egress)   |
|  - Host: H_legit (10.0.0.1), H_attacker (10.0.0.2), H_server (10.0.0.4)           |
+-----------------------------------------------------------------------------------+
```

---

## 2. 개발 완료 성과 축약 요약 (Phase 1 ~ Phase 6-A 완결)

16주차에 걸쳐 구현 및 실환경(GCP VM)에서 검증 완료된 핵심 기능 요약입니다. (단위/통합 테스트 **267개 전원 통과**)

| 영역 | 개발 완료 항목 | 세부 구현 성과 (축약) | 상태 |
| :--- | :--- | :--- | :---: |
| **Native Data Plane<br>(Phase 6-A 완결)** | • Mininet 의존성 완전 제거<br>• 리눅스 커널 OVS 2.17 단독 구동<br>• Linux netns 4-스위치 토폴로지 | • 교육용 에뮬레이터 탈피, 순수 커널 OVS 및 `ip netns` 기반 프로덕션 환경 구축<br>• 왕복 지연시간(RTT) **평균 0.07 ms** 달성, 정상 트래픽 손실률 **0.0% (무유실)**<br>• 원클릭 토폴로지 기동/정리 스크립트(`setup_native_ovs.sh`, `teardown_native_ovs.sh`)<br>• 6종 트래픽 주입 및 VM 원격 제어 도구(`native_attack.sh`, `vm_demo_controller.sh`) 구축 | **완료**<br>(Verified) |
| **Data Plane & 컨트롤러** | • 다이아몬드 토폴로지 구축<br>• 선제적 우회 라우팅<br>• FSM 플래핑 방지 | • S1-S2-S4(기본) 및 S1-S3-S4(우회) 엄격한 포트 핀 고정 구현<br>• Dijkstra 기반 선제적 `OFPFC_ADD` 경로 프로비저닝<br>• 차단 및 우회 전환 시간 **1.4 ~ 2.5 ms** 완료 달성<br>• 공격 중 정상 트래픽 손실 **0.0%** (무유실 라우팅) | **완료**<br>(Verified) |
| **AI 탐지 & 분류 엔진** | • Isolation Forest 탐지<br>• 6종 공격 세분화 분류<br>• 1초 주기 실측 카운트<br>• 기준선 재학습 제어 | • 실제 OVS 패킷 크기(BPP) 및 증분(ΔPPS) 관측 신호 적용<br>• SYN/UDP/ICMP Flood, Port Scan, Slow HTTP, 내부 확산 정밀 분류<br>• 미완료 요청 추적(`unfinished_requests`)으로 Slow HTTP 탐지 시간 **7.7초** 단축<br>• 1초 단위 실시간 카운트 집계로 탐지 시간 대폭 단축 (1.7~2.5초)<br>• 관리자 승인 기반 EWMA 기준선 재학습(Relearn) 파이프라인 | **완료**<br>(Verified) |
| **관제탑 웹 백엔드 & UI** | • 비동기 WebSocket Hub<br>• 실시간 토폴로지 시각화<br>• 비상 수동 제어 패널 | • FastAPI-Redis 비동기 브릿지 및 연결 풀 자동 관리<br>• vis-network 기반 실시간 스위치/호스트 상태 및 링크 우회 렌더링<br>• 비상 격리/복구 시 포커스 안정화 및 60초 보호 홀드 장치<br>• UI 렌더링 60 FPS 유지 및 이상 징후 실시간 알림 피드 | **완료**<br>(Verified) |
| **안전성 & 극한 검증** | • 서킷 브레이커<br>• 화이트리스트 가드<br>• 952k PPS 극한 스트레스 | • AI 오작동/메시지 폭주 시 자동 차단하는 3단계 서킷 브레이커<br>• 트렁크 링크 보호 및 서버 IP 영구 보호 화이트리스트<br>• 초당 **95만 패킷(952k PPS)** 폭격 시 858만 개 완벽 차단 실증<br>• **267개 단위/통합 테스트 전수 통과 (100% Pass)** | **완료**<br>(Verified) |

---

## 3. 🚀 향후 상용화 로드맵 (Commercialization Roadmap)

연구/프로토타입 수준을 넘어 엔터프라이즈 및 클라우드 환경 배포를 위한 상용화 필수 요건 및 차세대 마일스톤입니다.

### 3.1 상용 엔터프라이즈 환경 4대 필수 요건 (Production Requirements)

| 요건 | 학술/PoC 한계점 | 상용 엔터프라이즈 요구치 (Production Spec) | 당사 구현/대응 전략 |
| :--- | :--- | :--- | :--- |
| **1. 컨트롤러 생존성<br>(HA & Anti-DoS)** | 단일 컨트롤러 다운 시 전체 네트워크 마비, 대량 Packet-In 시 CPU 고갈 | • 스위치 하드웨어 레이트 리밋(Rate Limiting)<br>• 3대 이상 컨트롤러 클러스터링(Raft 합의 기반 즉각 Failover) | • Warning 단계 스위치 미터링 룰 적용<br>• Raft 기반 분산 컨트롤러 클러스터링 전환 |
| **2. 오탐 방지 및<br>정상 사용자 보호** | 단순 임계치 초과 차단으로 타임세일/정상 급증 시 고객 차단 사고 | • 다단계 정화(SYN Cookie, CAPTCHA, 스크러빙 센터 우회)<br>• 결제/인증/DNS 등 핵심 비즈니스 트래픽 절대 화이트리스트 | • Flash Crowd 오탐 방지(EwmaDetector + BPP)<br>• 영구 화이트리스트 가드(`whitelist_guard.py`)<br>• 정상 트래픽 무유실 우회(0.0% Loss) 실증 |
| **3. 심층 방어<br>(L7 가시성 & SFC)** | L2~L4 헤더만 검사하여 80/443 정상 포트로 위장한 웹 공격(SQLi 등) 미탐 | • **SFC (Service Function Chaining)** 도입<br>• 의심 플로우만 가상 WAF/IPS(Suricata)로 동적 라우팅하여 L7 정밀 검사 | • SDN 기반 선택적 트래픽 스티어링(Dynamic Rerouting)<br>• WAF/IPS 컨테이너 연동 체인 구축 |
| **4. 로깅 및 컴플라이언스<br>(Compliance & SIEM)** | 단순 로컬 파일/콘솔 로깅에 의존, 침해 사고 증적 위변조 취약 | • SIEM 연동 (Kafka ➔ Splunk / ElasticSearch 실시간 전송)<br>• ISMS-P, ISO27001 규제 준수를 위한 WORM 무결성 감사 보관 | • Redis 실시간 이벤트 버스 및 WebSocket 피드<br>• 엔터프라이즈 SIEM 수집 파이프라인 확장 |
| **5. 소프트웨어 정의 망 분리<br>(Zero-Trust Segmentation)** | 단일 서브넷(10.0.0.x) 플랫 구조로 침해 시 내부 확산(Lateral Movement) 취약 | • 용도별 논리 격벽(업무망/인터넷망/서버망/격리망)<br>• Default-Deny 기반 제로 트러스트 마이크로 세그멘테이션 | • OVS 커널 VLAN 태깅 기반 무손실(0.07ms RTT 유지) 망 분리<br>• 침해 단말 Quarantine Zone(VLAN 99) 동적 강등 격리<br>• 금융/공공 ISMS-P 망간 분리 규정 충족 |

---

### 3.2 단계별 상용화 실행 마일스톤 (Phases)

엔지니어링 의존성과 리스크를 최소화하고, 빠른 완성도와 시연 효과를 극대화하기 위해 재정렬된 3단계 실행 로드맵입니다.

```
[1단계: 즉시 실행 - 운영 안정화 및 소프트웨어 정의 제로 트러스트 망 분리] (In Progress / Next)
  ├── [Phase 6-B] 올인원 Docker Compose 패키징 & 프로덕션 서빙
  │     ├── OVS / Ryu / Redis / FastAPI / AI Worker / UI 무중단 단일 컨테이너 패키징
  │     ├── tmux 수동 백그라운드 세션 의존성 완전 제거 (docker compose up -d 원클릭 자동 복구)
  │     └── 웹 프론트엔드 프로덕션 빌드 서빙 (Vite Dev Server 탈피 ➔ Nginx / FastAPI 정적 마운트 최적화)
  └── [Phase 6-B-2] 소프트웨어 정의 제로 트러스트 망 분리 (Micro-segmentation)
        ├── L2 VLAN 기반 3-Tier 용도별 논리 망 분리 (VLAN 10: 외부망, VLAN 20: 업무망, VLAN 30: 서버망)
        ├── Zero-Trust 마이크로 세그멘테이션: Default-Deny(Table-Miss Drop) 및 포트별 최소 권한 통제
        ├── 침해 단말 동적 격리망 강등: 공격 감지 즉시 Quarantine Zone(VLAN 99) 강제 스티어링 (허니팟/포렌식 유도)
        └── 기존 0.07ms 저지연 및 정상 트래픽 손실률 0.0% 성능 100% 유지 보장

[2단계: 중기 과제 - 기술적 차별성 & 대외 경쟁력 확보]
  ├── [Phase 6-C] IPv6 Dual-Stack 지원 및 대규모 주소 스푸핑 방어
  │     ├── IPv4 / IPv6 듀얼 스택 지원 (ICMPv6 Neighbor Discovery / Proxy ND 파서 구현)
  │     ├── IPv6 초거대 주소 공간($2^{64}$개) 무작위 변조 공격 시 In_port 단일 룰 방어 실증
  │     ├── IPv6 기본 헤더(40B) 반영 AI BPP(Bytes Per Packet) 임계값 동적 보정
  │     └── 관제탑 UI IPv6 토폴로지 및 트래픽 시각화 확장
  └── [Phase 6-D] 엔터프라이즈 모니터링 & 프로브 안정화
        ├── 프로브 & 텔레메트리 로그 순환(Log Rotation) 및 백그라운드 데몬 생명주기 안정화
        ├── Prometheus / Grafana 메트릭 익스포터 연동
        └── Kubernetes OVS-CNI 연동 환경 검증

[3단계: 장기 과제 - 대규모 엔터프라이즈 확장 및 심층 방어]
  └── [Phase 6-E] 엔터프라이즈 심층 방어(SFC) 및 고가용성 클러스터링
        ├── Service Function Chaining (SFC): 의심 플로우 대상 WAF/IPS(Suricata) 동적 연동
        ├── Kafka / ElasticSearch 기반 엔터프라이즈 SIEM 로깅 파이프라인 구축
        ├── eBPF / XDP 기반 커널 레벨 1차 패킷 필터링 연동 검토 (Tbps 급 방어)
        └── Raft 기반 다중 컨트롤러 HA 클러스터링 구성 (무중단 페일오버 실증)
```

---

## 4. 컴포넌트별 기술 스택 확정 표

| 계층 | 컴포넌트 | 확정 버전 | 런타임 환경 | 역할 |
|---|---|---|---|---|
| **OS** | **Host OS** | **Ubuntu 22.04 LTS** | Native Linux (GCP VM) | 운영체제 표준 |
| **Data Plane** | **Open vSwitch (OVS)** | **2.17.x** | Host OS Native | 고속 OpenFlow 1.3 데이터 플레인 |
| **Control Plane** | **Ryu Controller** | **4.34** | Docker (`python:3.8-slim`) | OpenFlow 1.3 제어 및 자율 우회 라우팅 |
| **IPC Bus** | **Redis** | **7.2-alpine** | Docker 컨테이너 | 고속 Pub/Sub 메시지 브로커 (포트 6379) |
| **AI Engine** | **Scikit-learn / Criteria** | **1.3.2 / Py 3.10** | Host venv | 6종 공격 이상 탐지 및 실시간 분류 |
| **Web Backend** | **FastAPI** | **0.109.2** | Host venv | 비동기 WebSocket Hub & REST API |
| **Web Frontend** | **React / Tailwind** | **18.2 / 3.4** | Vite 번들러 | 실시간 관제탑 대시보드 UI |
