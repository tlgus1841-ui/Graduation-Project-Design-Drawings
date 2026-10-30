# 🧭 Self-Defending SDN Tower: 종합 로드맵 (ROADMAP)
> **SDN 기반 분산 트래픽 이상 탐지 및 자율 라우팅 관제 시스템**  
> 본 문서는 시스템 아키텍처, 기 개발 완료된 핵심 성과(축약 요약), 그리고 향후 상용화 로드맵을 정의합니다.

---

## 1. 시스템 아키텍처 및 확정 기술 스택

```
+-----------------------------------------------------------------------------------+
|                        [Layer 4: 웹 관제탑 (Frontend)]                            |
|  - React 18.3 (Vite) + Tailwind CSS + Lucide Icons                                |
|  - vis-network 9.1: 실시간 네트워크 토폴로지 (노드 상태, 링크 트래픽, 우회 활성화)   |
|  - ApexCharts 3.54: 실시간 BPP/PPS 시계열 차트 & 이상치 스코어                      |
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
| **All-in-One 배포<br>(Phase 6-B 완결)** | • 5대 서비스 단일 Compose 패키징<br>• 포트 80 Nginx 프로덕션 서빙<br>• tmux 완전 제거 및 원클릭 자율 복구 | • Redis, Ryu, FastAPI, AI Worker, UI Nginx 5개 서비스 단일 `docker-compose.yml` 오케스트레이션<br>• Vite Dev Server 탈피 ➔ Nginx 1.25 Alpine 리버스 프록시 및 React Multi-stage SPA 고속 정적 서빙<br>• 포트 80 단일 엔드포인트(/, /api/, /ws) 일원화 및 CORS 원천 제거 (포트 5173 하위 호환)<br>• `condition: service_healthy` 의존성 파이프라인 및 원클릭 런처(`prod_stack.sh`) 구축<br>• GCP 실환경 VM(`34.64.79.240`) 배포 및 500 PPS SYN 공격 자율 방어 E2E 실증 완료 | **완료**<br>(Verified) |
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
| **5. 소프트웨어 정의 동적 망 분리<br>(Dynamic Zero-Trust Segmentation)** | 단일 서브넷(10.0.0.x) 플랫 구조로 침해 시 내부 확산(Lateral Movement) 취약, 포트 일괄 차단으로 인한 정상 호스트 단절 | • 용도별 논리 Zone 분리 (`USER`, `SERVER`, `ADMIN`, `QUARANTINE`)<br>• Default-Deny 기반 제로 트러스트 마이크로 세그멘테이션<br>• OpenFlow 4-테이블 파이프라인 (Table 1 정책 테이블 신설) | • IP 대역 변경 없는 OpenFlow 컨트롤러 정책 기반 논리 망 분리<br>• 침해 단말(MAC/IP) 단위 동적 격리망(`QUARANTINE`) 즉각 강등<br>• 차단 패킷 `ZONE_DENY` 신호화로 무증상 랜섬웨어 확산 탐지<br>• 관리자 수동 복귀 승인 체계 및 국정원 N²SF 가이드라인 부합 |

---

### 3.2 단계별 상용화 실행 마일스톤 (Phases)

엔지니어링 의존성과 리스크를 최소화하고, 빠른 완성도와 시연 효과를 극대화하기 위해 재정렬된 3단계 실행 로드맵입니다.

```
[1단계: 즉시 실행 - 운영 안정화 및 소프트웨어 정의 제로 트러스트 망 분리]
  ├── [Phase 6-B] 올인원 Docker Compose 패키징 & 프로덕션 서빙 ── [완료 (Verified)]
  │     ├── OVS / Ryu / Redis / FastAPI / AI Worker / UI 무중단 단일 컨테이너 패키징 완료
  │     ├── tmux 수동 백그라운드 세션 의존성 완전 제거 (docker compose up -d 원클릭 자동 복구)
  │     ├── 웹 프론트엔드 프로덕션 빌드 서빙 (Vite Dev Server 탈피 ➔ Nginx 1.25 Alpine 리버스 프록시)
  │     ├── 포트 80 단일 엔드포인트(/, /api/, /ws) 일원화 및 실환경 VM(34.64.79.240) 검증 완료
  │     └── [상세 실행 계획서](docker_compose_production_plan.md) 기준 5단계 마일스톤 전수 구현/검증 완료
  └── [Phase 6-B-2] 소프트웨어 정의 동적 망 분리 (Dynamic Micro-segmentation) ── [완료 (Verified)]
        ├── 4-Switch 다이아몬드 환경 완성(옵션 A): 4단 OpenFlow 파이프라인(Table 0~3) 개편 및 282개 테스트 전원 통과
        ├── 4-Zone 논리 망 모델: USER(업무망), SERVER(서버망), ADMIN(관리망 10.0.0.254), QUARANTINE(격리망)
        ├── OpenFlow 4-Table 파이프라인 신설: Table 0(카운팅) ➔ Table 1(망정책/Source Guard) ➔ Table 2(미터링) ➔ Table 3(포워딩)
        ├── Default-Deny & Ingress Enforcement: 사용자 간 통신(SMB 445, RDP 3389) 전면 차단 및 OS 멀티캐스트 Silent Drop
        ├── 무증상 확산 탐지: 차단 패킷 통계를 `ZONE_DENY` 신호로 집계하여 CriteriaEngine 이상 탐지 엔진 연동
        ├── 호스트(MAC/IP) 단위 동적 격리: 내부 확산 시 해당 단말만 QUARANTINE으로 즉각 격리 (정상 사용자 무영향)
        ├── 관리자 통제권 일원화: 관제탑 비상 제어와 동일한 최고 관리자(Admin) 권한으로 격리 해제(Release) 일원화 및 필수 사유 감사 로그 보장
        ├── 관리망·업데이트 서버 전략 확정: 현 4-스위치에서는 정책상의 논리 호스트(10.0.0.254)로 무결성 검증 완료, 물리 컨테이너는 차기 토폴로지 확장에 배정
        └── [상세 실행 계획서](dynamic_segmentation_detailed_plan.md) 기준 5단계 마일스톤 전수 구현 및 E2E 실증 완료

[2단계: 중기 과제 - 기술적 차별성 & 대규모 토폴로지 확장]
  ├── [Phase 6-C] 대규모 토폴로지 확장 & 물리 관리망 컨테이너 정식 배포
  │     ├── 스위치 8~10개, 가상 PC 10~15대 규모의 존(Zone) 기반 Native OVS 토폴로지 확장
  │     │     (백본 S1·S2, 사용자망 S3·S4, 서버망 S5·S6, 관리망 S7, 격리망 S8)
  │     ├── 관리망(ADMIN) 전용 물리/컨테이너 업데이트·패치 서버(10.0.0.253) 정식 배포
  │     ├── 웹 관제탑 UI 전면 개편 (존 기반 토폴로지 맵 & 물리 계층 레이아웃)
  │     │     • vis-network 물리 좌표 하드코딩 탈피 및 존(Zone)별 배경 클러스터링(파랑/초록/보라/주황)
  │     │     • 관리망·패치 서버 노드 및 격리 호스트 L4 통신 제한선(점선) 시각화
  │     │     • 다중 노드(20개 이상) 안정적 렌더링을 위한 계층형(Hierarchical) 레이아웃 지원
  │     └── 다중 인그레스 스위치 간 분산 망 분리 정책 동기화 검증
  ├── [Phase 6-D] IPv6 Dual-Stack 지원 및 대규모 주소 스푸핑 방어
  │     ├── IPv4 / IPv6 듀얼 스택 지원 (ICMPv6 Neighbor Discovery / Proxy ND 파서 구현)
  │     ├── IPv6 초거대 주소 공간($2^{64}$개) 무작위 변조 공격 시 In_port 단일 룰 방어 실증
  │     ├── IPv6 기본 헤더(40B) 반영 AI BPP(Bytes Per Packet) 임계값 동적 보정
  │     └── 관제탑 UI IPv6 토폴로지 및 트래픽 시각화 확장
  └── [Phase 6-E] 엔터프라이즈 모니터링 & 프로브 안정화
        ├── 프로브 & 텔레메트리 로그 순환(Log Rotation) 및 백그라운드 데몬 생명주기 안정화
        ├── Prometheus / Grafana 메트릭 익스포터 연동
        └── Kubernetes OVS-CNI 연동 환경 검증

[3단계: 장기 과제 - 대규모 엔터프라이즈 확장 및 심층 방어]
  └── [Phase 6-F] 엔터프라이즈 심층 방어(SFC) 및 고가용성 클러스터링
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
| **Web Frontend** | **React / Tailwind** | **18.3 / 3.4** | Vite 번들러 | 실시간 관제탑 대시보드 UI |

---

## 5. 단계별 개발 타임라인 및 실행 일정 검토 (Timeline & Feasibility)

졸업작품/최종 프로젝트 심사 및 시연 일정을 고려한 현실적인 소요 시간과 엔지니어링 타임라인 검토 결과입니다.

```
+----------------------------------------------------------------------------------------------------+
| Phase 6-B-2: 동적 망 분리 (완료)               [  완료  ] (282개 테스트 100% Pass 실증 완료)      |
+----------------------------------------------------------------------------------------------------+
| Phase 6-C: 대규모 토폴로지 확장 & 웹 UI 개편   [ 1 ~ 1.5주 ] (핵심 시각화 & 최종 데모 완성형)      |
+----------------------------------------------------------------------------------------------------+
| Phase 6-D: IPv6 듀얼스택 지원                  [ 1주 ] (학술/논문 추가 성과용 선택 과제)          |
+----------------------------------------------------------------------------------------------------+
| Phase 6-E: 프로브 & 모니터링 안정화            [ 0.5주 ] (운영 안정화 보조 과제)                  |
+----------------------------------------------------------------------------------------------------+
| Phase 6-F: 엔터프라이즈 SFC 및 HA              [ 2 ~ 3주 ] (차기 연구 및 상용화 장기 과제)         |
+----------------------------------------------------------------------------------------------------+
```

### 5.1 타임라인 상세 소요 분석

1. **Phase 6-C (8-스위치 확장 + 물리 패치서버 + 웹 UI 개편): 약 5 ~ 7일 소요**
   * **1~2일차**: 토폴로지 설정 파일(`topology_profiles.yaml`) 분리 및 컨트롤러 로더 구현 (기존 4-스위치 테스트 100% 보호).
   * **3~4일차**: Native OVS 8-스위치 배포 스크립트(`setup_large_ovs.sh`) 및 패치서버 컨테이너 배포.
   * **5~7일차**: **웹 UI 토폴로지 맵 전면 개편** (vis-network 존별 배경 클러스터링, 계층형 레이아웃, 패치서버 렌더링).
   * *효과*: 최종 데모 시연 및 영상/보고서에 들어갈 **가장 완성도 높은 "보안 관제탑 비주얼"** 완성.

2. **Phase 6-D (IPv6 Dual-Stack): 약 5일 소요**
   * Ryu 컨트롤러 내 IPv6 ICMPv6 ND(Neighbor Discovery) 파서 및 L4 플로우 테이블 확장.
   * *효과*: 기술적 깊이와 논문/특허 작성 시 이론적 차별점 확보.

3. **Phase 6-E & 6-F (운영 안정화 & SFC 장기 과제)**
   * 실제 심사 및 데모 이후 클라우드 상용화 단계에서 진행하는 장기 마일스톤.

