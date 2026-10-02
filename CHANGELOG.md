# 📝 Project Changelog & Collaboration Worklog
> **Self-Defending SDN Tower (SDN 기반 분산 트래픽 이상 탐지 및 자율 라우팅 관제 시스템)**  
> 팀원(박시현, 유재민, 김관우) 및 AI 에이전트 간의 작업 변경 이력, 인수인계 메모, 브레이킹 체인지를 추적하는 공식 기록 문서(SSOT)입니다.

---

## 📌 AI 에이전트 & 팀원 작성 가이드 (Writing Rules)
1. **기록 시점:** 코드 작성/수정, 아키텍처/폴더 변경, 인터페이스 수정 작업 완료 직후.
2. **작성 위치:** 항상 아래 최신 항목 목록의 **맨 위(최상단)** 에 새로운 블록을 추가합니다.
3. **필수 항목:** 날짜, 작업자(세션/에이전트명), 작업 유형, 변경 파일 목록, 상세 변경 내용, Breaking Changes 여부, 다음 작업자 인수인계 메모.

---

## 📋 변경 이력 (Latest Changes)

### [2026-10-03] docs(guides): 3인 Phase 실전 가이드북에 주차별(Weekly) 핵심 목표 & DoD 브레이크다운 명시
* **작업자:** 박시현 (Tech Lead) with Antigravity AI Agent
* **작업 유형:** `Docs` / `Refactor`
* **주요 변경 파일:**
  - `docs/guides/README.md`: 16주차 전 주차 3인 주차별 핵심 목표 퀵 매트릭스(Weekly Quick Roadmap) 신설
  - `docs/guides/dev_a_tech_lead/phase2_core_mock_harness.md`: 박시현 Phase 2(4~7주차) 한 줄 핵심 미션, 대상 파일, 정량적 DoD, 팀원 연계 포인트 표 신설
  - `docs/guides/dev_b_domain_qa/phase2_traffic_features_model.md`: 유재민 Phase 2(4~7주차) 한 줄 핵심 미션, 대상 파일, 정량적 DoD, 팀원 연계 포인트 표 신설
  - `docs/guides/dev_c_pm_writer/phase2_defense_scenario_web_spec.md`: 김관우 Phase 2(4~7주차) 한 줄 핵심 미션, 대상 파일, 정량적 DoD, 팀원 연계 포인트 표 신설
* **변경 사유 및 배경:**
  - 4주 단위 묶음(Phase) 서술로 인해 주차별(Weekly) 실행 타임라인과 팀원별 필수 목표가 흐려지던 문제를 해결하고, 팀원 누구나 접속 시 "이번 주차에 정확히 무엇을 완료해야 하는지" 1초 만에 파악할 수 있도록 표준화.
* **영향 범위 및 주의사항:**
  - 소스코드 영향 없음. 문서 가독성 및 팀원 간 주차별 협업 명확성 대폭 향상.

### [2026-10-03] docs(plan): 박시현(Tech Lead) 6주차 2-Tier 텔레메트리 파이프라인 및 Redis 통계 발행 구현 계획서 작성
* **작업자:** 박시현 (Tech Lead) with Antigravity AI Agent
* **작업 유형:** `Docs` / `Plan`
* **주요 변경 파일:**
  - `docs/writing/reports/weekly/week06_telemetry_pipeline_implementation_plan.md`: (신규 생성) Ryu 2초 주기 비차단 포트 통계 수집(`OFPPortStatsRequest`), Pydantic SSOT(`PortStatsMessage`) 직렬화, Redis `sdn:stats:port` 채널 발행 및 장애 격리 가드레일 계획서 수립
* **변경 사유 및 배경:**
  - 5주차 스위칭 완료에 이어, AI Worker(유재민의 피처 추출기) 및 관제탑 웹(김관우의 실시간 차트)으로 실시간 포트 통계를 무중단 스트리밍하기 위한 6주차 텔레메트리 설계 확립.
* **영향 범위 및 주의사항:**
  - 기존 소스코드에 영향 없음.
* **다음 작업자 인수인계 메모:**
  - 유재민 (Domain Dev)은 본 계획서의 `PortStatsMessage` 규격을 기반으로 6주차 `feature_extractor.py` 구독기 개발 가능.

### [2026-10-03] feat(ryu): 박시현(Tech Lead) 5주차 OpenFlow 1.3 L2/L3 스위칭 및 다이아몬드 무루프 포워딩 구현 완료
* **작업자:** 박시현 (Tech Lead) with Antigravity AI Agent
* **작업 유형:** `Feat` / `Test`
* **주요 변경 파일:**
  - `ryu/app/controller.py`: Proxy ARP 미등록 호스트 스톰 억제 강화, 유입 포트 동일 루프백(Hairpinning) 방어 가드(`out_port == in_port`), OpenFlow 1.3 `eth_type=0x0800` 명시 Flow Mod(Priority 10) 및 첫 패킷 PacketOut 무유실 포워딩 완성
  - `topo/diamond_topo.py`: Mininet 미설치 환경 대응 fallback Topo에 `switches()`, `hosts()` 헬퍼 추가
  - `tests/ryu/test_controller_logic.py`: (신규 생성) 5주차 컨트롤러 핵심 로직 단위 테스트 7종 추가 (DiamondTopo 정합성, S1-S2-S4 기본 경로 연속성, Proxy ARP, 미등록 IP 스톰 억제, FlowMod/PacketOut, 루프백 가드)
  - `tests/ryu/__init__.py`: 신규 패키지 선언
* **상세 변경 내용 및 성과:**
  - 호스트 Python 3.10 가상환경에서도 격리된 Ryu 모듈을 동적 모킹 로드하여 컨트롤러 핵심 스위칭 및 방어 로직을 100% 검증할 수 있는 단위 테스트 스위트 구축.
  - flake8 (79자 준수) 및 mypy 0건 통과.
  - 전체 회귀 테스트 통과: **49 / 49 tests passed (100% Pass, 0.66s)**
* **영향 범위 및 주의사항 (Breaking Changes):**
  - 기존 API, 트래픽 생성기, 하네스에 영향 없음. 호환성 100% 유지.
* **다음 작업자 인수인계 메모:**
  - 5주차 SDN 제어 평면 스위칭 구현 및 단위 테스트 검증이 완료되었으므로, 다음 6주차 과제인 **2-Tier 텔레메트리 파이프라인 (Ryu 2초 주기 `OFPPortStatsRequest` $\rightarrow$ Redis `sdn:stats:port` 발행 및 `feature_extractor.py` 연동)**으로 자연스럽게 전환 가능.

### [2026-10-03] docs(plan): 박시현(Tech Lead) 5주차 OpenFlow 1.3 L2/L3 스위칭 구현 계획서 작성
* **작업자:** 박시현 (Tech Lead) with Antigravity AI Agent
* **작업 유형:** `Docs` / `Plan`
* **주요 변경 파일:**
  - `docs/writing/reports/weekly/week05_controller_switching_implementation_plan.md`: (신규 생성) Ryu 컨트롤러 OpenFlow 1.3 L2/L3 스위칭, Proxy ARP 스톰 방어, pingall 100% 무유실 검증 계획서 수립
* **변경 사유 및 배경:**
  - 4주차 다이아몬드 토폴로지 구축에 이어, 다중 경로 내 ARP 브로드캐스트 스톰을 차단하고 기본 경로(S1-S2-S4) 무루프 포워딩 및 pingall 무유실 달성을 위한 5주차 정밀 구현 로드맵 확립.
* **영향 범위 및 주의사항:**
  - 기존 소스코드 및 타 팀원 작업물에 영향 없음.
* **다음 작업자 인수인계 메모:**
  - 계획서에 명시된 4대 검증 시나리오(TC-1~TC-4)에 따라 Docker 기반 Ryu 컨트롤러와 Mininet 연동 테스트 착수.

### [2026-10-03] merge & refactor: 팀원 작업물(공격기, 관제탑 UI, Redis 브리지) 통합 및 신규 폴더 체계 재정리
* **작업자:** 박시현 (Tech Lead) with Antigravity AI Agent
* **작업 유형:** `Merge` / `Refactor` / `Docs`
* **주요 변경 및 병합 내역:**
  - **유재민 (Domain Dev & QA) 작업 병합 (`origin/main`):**
    - `traffic/checksum_utils.py`: Scapy IP/TCP 체크섬 강제 재계산 공용 유틸 추가 및 `traffic_normal.py` 리팩토링
    - `traffic/traffic_attack.py`: 5주차 H_attacker $\rightarrow$ H_server 무작위 IP 스푸핑 SYN Flood(1,000~5,000 PPS) 공격기 추가
    - `tests/traffic/test_traffic_attack.py`: 공격기 단위 테스트 6종 추가
  - **김관우 (PM & 관제탑 웹) 작업 병합 (`origin/claude/quirky-cerf-h51gg3`):**
    - `ui/`: React 18 + Vite 5 + Tailwind CSS 3.4 기반 관제탑 웹 프론트엔드 (토폴로지 vis-network, 실시간 차트 ApexCharts)
    - `api/redis_bridge.py`: Redis Pub/Sub 4개 채널을 WebSocket으로 실시간 중계하는 Live 모드 브리지
    - `api/redis_replay.py`: Ryu 미구동 상태에서 Redis 더미 시나리오를 발행하는 시뮬레이터
    - `tests/api/test_redis_bridge.py`: fakeredis 기반 브리지 단위 테스트
  - **폴더 구조 표준화 재정리 (신규 docs 규칙 적용):**
    - `reports/week05_progress_report.md` $\rightarrow$ `docs/writing/reports/weekly/week05_progress_report.md`
    - `reports/week06_progress_report.md` $\rightarrow$ `docs/writing/reports/weekly/week06_progress_report.md`
    - `reports/week07_progress_report.md` $\rightarrow$ `docs/writing/reports/weekly/week07_progress_report.md`
    - `docs/guides/dev_b_domain_qa/week05_traffic_attack_implementation_plan.md` $\rightarrow$ `docs/writing/reports/weekly/week05_traffic_attack_implementation_plan.md`
    - 루트의 불필요한 `reports/` 임시 디렉토리 정리 삭제
    - `README.md`: 프로젝트 트리 및 실행 가이드 최신화 완료 (충돌 해결)
* **영향 범위 및 주의사항 (Breaking Changes):**
  - 소스코드 로직 파괴 없음. 주간 보고서 파일들이 일원화된 `docs/writing/reports/weekly/`로 이동됨.
* **다음 작업자 인수인계 메모:**
  - 팀원들의 코드가 로컬 작업 트리에 정상 통합되었으므로, 정리된 표준 폴더 구조 기준으로 5주차 Ryu 스위칭 및 E2E 연동 작업 진행 가능.

### [2026-10-03] docs: 문서 및 집필 환경 폴더 구조 최적화 & 기획서 병합
* **작업자:** 박시현 (Tech Lead) with Antigravity AI Agent
* **작업 유형:** `Refactor` / `Docs`
* **주요 변경 파일:**
  - `CHANGELOG.md`: (신규 생성) 팀원 & AI 에이전트 협업 추적 로그 파일 신설
  - `.cursorrules`: AI 에이전트 작업 기록 강제 수칙 (§3) 추가 및 디렉토리 권한 최신화
  - `docs/writing/proposal/project_proposal.md`: 공식 기획서 본문에 `why_self_defending_sdn.md`(선정 당위성, 후보군 비교, 심사위원 Q&A) 병합 통합
  - `docs/writing/thesis/thesis_draft.md`: (신규 생성) PM/Writer용 졸업논문 초안 템플릿 생성
  - `docs/writing/presentations/ppt_slide_deck_outline.md`: 발표 슬라이드 아웃라인 이동
  - `docs/writing/reports/weekly/week04_traffic_normal_plan.md`: 4주차 완료 계획서 이동
  - `docs/archive/v1_guides/*`: `docs/guides/archive_v1`에서 통합 아카이브 폴더로 격리
  - `docs/archive/v1_proposal/*`: v1 제안서 및 병합 원본 파일(`why_self_defending_sdn_raw.md`) 격리
* **변경 사유 및 배경:**
  - 분산되어 있던 기획/제안서, 발표자료, 보고서, 논문 문서를 `docs/writing/` 아래로 일원화하여 집필 속도 및 접근성 극대화.
  - 레거시 v1 문서들을 `docs/archive/` 단일 디렉토리로 격리하여 최신 문서와의 혼동 방지.
  - 다수의 AI 에이전트가 코딩을 수행할 때 작업 맥락이 유실되지 않도록 표준 로깅 체계 정립.
* **영향 범위 및 주의사항 (Breaking Changes):**
  - **소스코드 영향 없음:** `api/`, `harness/`, `ryu/`, `topo/`, `traffic/`, `tests/` 등 모든 소스코드 및 가상환경은 무변경 유지됨.
* **확정된 디렉토리 구조:**
  ```text
  Self_Defending_SDN_Tower/
  ├── CHANGELOG.md                           # 팀원 & AI 에이전트 변경 이력/인수인계 SSOT
  ├── .cursorrules                           # AI 에이전트 작업 기록 강제 수칙 연동
  ├── docs/
  │   ├── writing/                           # [집필 전용] 기획서, 주간보고서, 논문, 발표
  │   │   ├── proposal/                      # 공식 졸업작품 기획서 (project_proposal.md)
  │   │   ├── reports/weekly/                # 주간 계획/보고서 (week04_traffic_normal_plan.md)
  │   │   ├── thesis/                        # 학술 논문 초안 (thesis_draft.md)
  │   │   └── presentations/                 # 발표 PPT 아웃라인 (ppt_slide_deck_outline.md)
  │   ├── planning/                          # 아키텍처 로드맵, 16주차 일정, 하네스 계획
  │   ├── specs/                             # 4대 공격 및 방어 시나리오 명세서
  │   ├── guides/                            # 3인 역할별 Phase 1~6 실전 가이드북
  │   ├── study/                             # CS/SDN/보안 8대 기술 학습서
  │   └── archive/                           # 구버전 v1 파일 격리 보관소
  │       ├── v1_proposal/                   # v1 제안서 및 병합 원본 파일
  │       └── v1_guides/                     # v1 초기 가이드
  └── (api / harness / ryu / topo / traffic / tests)  # 소스코드 영역 (무변경)
  ```
* **다음 작업자/에이전트 인수인계 메모:**
  - **김관우 (PM & Writer):** `docs/writing/proposal/project_proposal.md`를 단일 기획서로 참조 가능하며, `docs/writing/thesis/thesis_draft.md`에서 논문 작성 시작 가능.
  - **유재민 (Domain Dev & QA):** 4주차 정상 트래픽 생성이 완료되었으므로, 5주차 공격기(`traffic_attack.py`) 작성 착수 시 `docs/guides/dev_b_domain_qa/` 참조.
  - **박시현 (Tech Lead):** 5주차 Ryu L2/L3 스위칭 및 다이아몬드 무루프 포워딩 착수.

---
