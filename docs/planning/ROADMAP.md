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

## 2. 개발 완료 성과 축약 요약 (Phase 1 ~ Phase 5 완결)

16주차에 걸쳐 구현 및 검증된 핵심 기능 요약입니다. (단위/통합 테스트 **265개 전원 통과**)

| 영역 | 개발 완료 항목 | 세부 구현 성과 (축약) | 상태 |
| :--- | :--- | :--- | :---: |
| **Data Plane & 컨트롤러** | • 다이아몬드 토폴로지 구축<br>• 선제적 우회 라우팅<br>• FSM 플래핑 방지 | • S1-S2-S4(기본) 및 S1-S3-S4(우회) 엄격한 포트 핀 고정 구현<br>• Dijkstra 기반 선제적 `OFPFC_ADD` 경로 프로비저닝<br>• 차단 및 우회 전환 시간 **1.4 ~ 2.5 ms** 완료 달성<br>• 공격 중 정상 트래픽 손실 **0.0%** (무유실 라우팅) | **완료**<br>(Verified) |
| **AI 탐지 & 분류 엔진** | • Isolation Forest 탐지<br>• 6종 공격 세분화 분류<br>• 1초 주기 실측 카운트<br>• 기준선 재학습 제어 | • 실제 OVS 패킷 크기(BPP) 및 증분(ΔPPS) 관측 신호 적용<br>• SYN/UDP/ICMP Flood, Port Scan, Slow HTTP, 내부 확산 정밀 분류<br>• INFOCOM/IEEE S&P 등 검증된 7편의 논문 수식 반영<br>• 1초 단위 실시간 카운트 집계로 탐지 시간 대폭 단축 (1.7~2.5초)<br>• 관리자 승인 기반 EWMA 기준선 재학습(Relearn) 파이프라인 | **완료**<br>(Verified) |
| **관제탑 웹 백엔드 & UI** | • 비동기 WebSocket Hub<br>• 실시간 토폴로지 시각화<br>• 비상 수동 제어 패널 | • FastAPI-Redis 비동기 브릿지 및 연결 풀 자동 관리<br>• vis-network 기반 실시간 스위치/호스트 상태 및 링크 우회 렌더링<br>• 비상 격리/복구 시 포커스 안정화 및 60초 보호 홀드 장치<br>• UI 렌더링 60 FPS 유지 및 이상 징후 실시간 알림 피드 | **완료**<br>(Verified) |
| **안전성 & 극한 검증** | • 서킷 브레이커<br>• 화이트리스트 가드<br>• 952k PPS 극한 스트레스 | • AI 오작동/메시지 폭주 시 자동 차단하는 3단계 서킷 브레이커<br>• 트렁크 링크 보호 및 서버 IP 영구 보호 화이트리스트<br>• 초당 **95만 패킷(952k PPS)** 폭격 시 858만 개 완벽 차단 실증<br>• **265개 단위/통합 테스트 전수 통과 (100% Pass)** | **완료**<br>(Verified) |

---

## 3. 🚀 향후 상용화 로드맵 (Commercialization Roadmap)

연구/프로토타입 수준을 넘어 엔터프라이즈 및 클라우드 환경 배포를 위한 차세대 마일스톤입니다.

```
[Phase 6-A] 순수 OVS 단독 구동 전환 (In Progress)
  ├── Mininet 의존성 완전 제거 (Host/Container Native)
  ├── Linux Network Namespace(ip netns) 기반 4-스위치 다이아몬드 토폴로지 구축
  └── setup_native_ovs.sh / teardown_native_ovs.sh 스크립트 표준화

[Phase 6-B] 클라우드 / 컨테이너 오케스트레이션 고도화
  ├── Docker Compose 단일 패키징 (OVS + Ryu + Redis + FastAPI + UI 올인원 컨테이너화)
  ├── Kubernetes OVS-CNI 연동 환경 검증
  └── Prometheus / Grafana 메트릭 익스포터 연동

[Phase 6-C] 패킷 처리 고속화 및 분산 확장
  ├── eBPF / XDP 기반 커널 레벨 1차 패킷 필터링 연동 검토 (Tbps 급 방어)
  ├── 다중 Ingress 스위치 분산 관제 클러스터 확장
  └── 실시간 위협 인텔리전스(TI) 피드 자동 차단 룰 연동
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
