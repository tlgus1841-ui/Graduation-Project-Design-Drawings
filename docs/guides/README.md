# 🛡️ Self-Defending SDN Tower: 바이브 코딩 실전 가이드북
> **부제:** 3인 협업 체계 및 듀얼 AI 하네스 엔지니어링 기반 주차별 실전 개발 가이드  
> **기준 문서:** `docs/planning/ai_harness_engineering_plan.md`, `docs/planning/schedule_and_milestones.md`  
> **문서 버전:** v2.0 (2026-09-18 개정)

---

## 👥 1. 개발자 역할 및 가이드북 바로가기

본 가이드는 2026학년도 2학기 졸업작품(캡스톤) 개발을 위해 **3인 전문 분업(R&R)** 및 **듀얼 AI 하네스(Dual Harness)** 아키텍처를 기준으로 작성되었습니다.

| 구분 | Tech Lead: 박시현 (22101489) | Domain Dev & QA: 유재민 (22101498) | PM & Tech Writer: 김관우 (22102237) |
|:---:|:---|:---|:---|
| **역할 정의** | **시스템 아키텍트 & 코어 엔지니어** | **AI/보안 엔지니어 & 품질 보증 (QA)** | **프로젝트 매니저 & 테크니컬 라이터** |
| **핵심 책임** | • 가상 인프라(Mininet) 및 듀얼 하네스 아키텍처 설계<br>• Ryu OpenFlow 1.3 코어 스위칭 & 텔레메트리<br>• In_port 격리, Dijkstra 다중 홉 우회, FSM 플래핑 방지 | • Scapy 가변 정상/랜덤 IP 변조 공격 패킷 생성기<br>• 실시간 5대 SDN 파생 피처 엔지니어링<br>• Isolation Forest 모델 훈련 및 정량 벤치마크 | • 프로젝트 마일스톤 및 A4 주간 진도 보고서 관리<br>• 4단계 방어 시나리오 명세 및 관제 UI/UX 기획/검수<br>• 최종 논문 집필, 10장 PPT 슬라이드 및 시연 총괄 |
| **작업 디렉토리** | `harness/`, `topo/`, `ryu/`, `tests/harness/` | `traffic/`, `pipeline/`, `model/`, `tests/` | `docs/`, `ui/`, `reports/`, 시연 스크립트 |
| **개발 환경** | Ubuntu 22.04 LTS, Docker(`python:3.8-slim`), `uv` | Python 3.10.12 (`.venv`), Scapy, Scikit-learn, `uv` | 문서화 도구, Node 20, React 18, Vite, Tailwind CSS |
| **가이드 대문** | [📘 Tech Lead 가이드](dev_a_tech_lead/dev_a_overview.md) | [📗 Domain QA 가이드](dev_b_domain_qa/dev_b_overview.md) | [📙 PM & Writer 가이드](dev_c_pm_writer/dev_c_overview.md) |

---

## 🧭 2. 3인 공통 엔지니어링 & AI 하네스 규칙 (`00_common/`)

모든 개발자는 코드를 작성하거나 AI 에이전트(Antigravity, Cursor 등)에게 작업을 지시하기 전에 다음 공통 표준을 숙지해야 합니다.

1. **[⚙️ uv 패키지 매니저 & 환경 규칙](00_common/uv_and_environment_guide.md)**
   - `pip install` 및 `python -m venv` 절대 사용 금지.
   - 단일 루트 가상환경 `./.venv` 관리 및 `uv add`, `uv run` 표준 명령어 안내.
2. **[🤖 바이브 코딩 프롬프트 5단계 표준](00_common/vibe_coding_prompt_standard.md)**
   - 골든 매트릭스 주입, Ryu Greenlet 블로킹 방지, Contract-First 검증 등 고품질 코드 생성을 위한 필수 프롬프트 패턴.
3. **[📡 Pydantic v2 계약(Contract) & Redis IPC 규격](00_common/contract_first_ipc_guide.md)**
   - 4대 핵심 Redis 채널(`sdn:stats:port`, `sdn:anomaly:alert`, `sdn:control:command`, `sdn:topology:sync`)의 Pydantic v2 데이터 모델 및 직렬화 표준.
4. **[🐙 실전 Git & GitHub 3인 협업 가이드](00_common/git_collaboration_guide.md)**
   - Collaborator 초대/수락, GitHub PAT 토큰 인증, 3인 디렉토리 격리 수칙 및 충돌 방지 워크플로우.

---

## 📅 3. 16주차 6대 Phase별 가이드 맵

```text
[ Phase 1: 하네스 기반 확립 & 아키텍처 격리 ] ──────────────────────── 1주차 ~ 3주차 (완료)
  - 박시현: [Phase 1 회고록](dev_a_tech_lead/phase1_harness_setup.md)
  - 유재민: [Phase 1 회고록](dev_b_domain_qa/phase1_environment_setup.md)
  - 김관우: [Phase 1 회고록](dev_c_pm_writer/phase1_charter_milestones.md)
       ▼
[ Phase 2: 코어 모듈 구현 & Mock 하네스 기반 병렬 개발 ] ────────────── 4주차 ~ 7주차 (현재 진행 단계)
  - 박시현: [Phase 2 실전 가이드 (토폴로지/스위칭/텔레메트리/Mock)](dev_a_tech_lead/phase2_core_mock_harness.md)
  - 유재민: [Phase 2 실전 가이드 (트래픽 생성기/5대 피처/Isolation Forest)](dev_b_domain_qa/phase2_traffic_features_model.md)
  - 김관우: [Phase 2 실전 가이드 (방어 시나리오 명세/관제탑 UI 검수)](dev_c_pm_writer/phase2_defense_scenario_web_spec.md)
       ▼
[ Phase 3: 중간고사 & 1차 파이프라인 E2E 통합 점검 ] ────────────────── 8주차
  - 박시현: [Phase 3 E2E 파이프라인 통합](dev_a_tech_lead/phase3_midterm_pipeline.md)
  - 유재민: [Phase 3 모델 추론 성능 1차 평가](dev_b_domain_qa/phase3_midterm_evaluation.md)
  - 김관우: [Phase 3 A4 중간 보고서 및 교수님 점검](dev_c_pm_writer/phase3_midterm_report_lead.md)
       ▼
[ Phase 4: AI 런타임 안전 하네스 & 다중 홉 우회 연동 ] ──────────────── 9주차 ~ 11주차
  - 박시현: [Phase 4 In_port 차단 / Dijkstra 우회 / FSM 플래핑 방지](dev_a_tech_lead/phase4_safety_rerouting.md)
  - 유재민: [Phase 4 IP 스푸핑 방어 검증 & 무유실 벤치마크](dev_b_domain_qa/phase4_spoofing_defense_benchmark.md)
  - 김관우: [Phase 4 방어 시나리오 실증 검증서 & UI 감수](dev_c_pm_writer/phase4_mitigation_verification.md)
       ▼
[ Phase 5: 웹 관제탑 연동 & 긴급 서킷 브레이커 고도화 ] ────────────── 12주차 ~ 13주차
  - 공통 연동: [Phase 5 & 6 웹 관제 및 종합 E2E 시연 가이드](dev_a_tech_lead/phase5_6_dashboard_e2e.md)
  - 유재민: [Phase 5 & 6 E2E 레이턴시 프로파일링 & 최종 데이터셋](dev_b_domain_qa/phase5_6_latency_final_dataset.md)
  - 김관우: [Phase 5 & 6 최종 논문 / PPT 슬라이드 / 시연 총괄](dev_c_pm_writer/phase5_6_thesis_ppt_demo.md)
       ▼
[ Phase 6: 종합 E2E 시연 시나리오 검증 & 최종 심사 평가 ] ──────────── 14주차 ~ 16주차
```

### 🎯 3.1 [Phase 연계] 16주차 3인 주차별 핵심 목표 퀵 매트릭스 (Weekly Quick Roadmap)

> **💡 핵심 안내:** 각 개발자는 소속된 **Phase(단계)**의 큰 맥락을 유지하면서, 아래 **주차별(Weekly) 1줄 핵심 목표**를 반드시 달성해야 파이프라인 병목이 발생하지 않습니다.

| Phase | 주차 | 박시현 (Tech Lead) | 유재민 (Domain Dev & QA) | 김관우 (PM & Tech Writer) | 주차별 통합 목표 및 산출물 |
|:---:|:---:|:---|:---|:---|:---|
| **Phase 1** | **1주차** | SDN 기술 제약 조사 | 공격 특성 및 AI 기법 분석 | 일정 분석 & 관제탑 레퍼런스 | 3인 연구 주제 타당성 검토 |
| ^ | **2주차** | Mininet/OVS 호환성 분석 | 실시간 경량 추론 피처 도출 | 프로젝트 기획서 초안 설계 | 단일 주제 및 3인 R&R 확정 |
| ^ | **3주차** | Docker Ryu 및 계약 스키마 확정 | Python 3.10 가상환경 구축 | 개발 기획서 & 일정표 확정 | **Pydantic v2 SSOT 계약 동결** |
| **Phase 2**<br>(현재) | **4주차** | 다이아몬드 토폴로지 & Mock 하네스 | Scapy 정상 트래픽 생성기 | 4단계 자율 방어 시나리오 명세 | `diamond_topo.py`, `test_mock_ipc.py`, 정상 트래픽 |
| ^ | **5주차** | Ryu OF 1.3 스위칭 & Proxy ARP | Scapy 무작위 IP SYN Flood 공격기 | 주간 보고서 #2 & 관제탑 UI 베이스 | `controller.py`, `traffic_attack.py`, `pingall` 무유실 |
| ^ | **6주차** | **Ryu 2초 주기 포트 통계 발행** | **Redis 구독 & 5대 피처 계산기** | **주간 보고서 #3 & UI 차트 연동** | **[2-Tier 텔레메트리 파이프라인 관통]** |
| ^ | **7주차** | 포트 급증 시 세부 플로우 질의 | **Isolation Forest 모델 학습** | 주간 보고서 #4 & vis-network | AI 이상 탐지 모델 및 토폴로지 지도 |
| **Phase 3** | **8주차** | E2E 데이터 관통 E2E 점검 | 모델 추론 정량 성능 1차 검증 | **중간 진행 보고서 제출 (총괄)** | **[중간고사 & 1차 E2E 파이프라인 통합]** |
| **Phase 4** | **9주차** | In_port Priority 100 Drop 구현 | IP 스푸핑 방어 단일 룰 검증 | 주간 보고서 #5 & 적색 경보 UI | 화이트리스트 안전 가드레일 |
| ^ | **10주차** | Dijkstra 기반 다중 홉 우회 주입 | 정상 트래픽 무유실 우회 측정 | 주간 보고서 #6 & 우회 경로 하이라이트 | 선제적 OFPFC_ADD 우회 라우팅 |
| ^ | **11주차** | FSM 플래핑 방지 & 자가 복구 | 트래픽 정상화 판정 트리거 | 주간 보고서 #7 & 자가 치유 알림 | `flapping_fsm.py` 무개입 복구 |
| **Phase 5** | **12주차** | 통계/경보 직렬화 최적화 | E2E 지연시간 프로파일링(<100ms) | 주간 보고서 #8 & UI 60fps 튜닝 | 실시간 스트리밍 지연 100ms 미만 |
| ^ | **13주차** | 긴급 서킷 브레이커 & 수동 제어 | 정상 급증(Flash Crowd) 오탐 방지 | 주간 보고서 #9 & 수동 제어 모달 | F1-Score > 0.95, FPR < 1.0% |
| **Phase 6** | **14주차** | 4단계 E2E 풀코스 시연 하네스 | 정량 벤치마크 데이터셋 추출 | 주간 보고서 #10 & 타임라인 감수 | 전 과정 자동화 통과 및 손실 < 2% |
| ^ | **15주차** | 원클릭 데모 패키징 (`v1.0.0`) | 모의 공격 프로파일 프리셋 패키징 | **최종 발표 PPT (10장) & 대본** | 원클릭 데모 쉘 및 시연 리허설 3회 |
| ^ | **16주차** | 실시간 라이브 시연 기술 질의 대응 | 심사위원 질의응답 및 성능 시연 | **최종 발표 총괄 & A4 합본 제출** | **졸업작품 기말 최종 심사 및 평가** |


---

## 🗄️ 4. 이전 버전 가이드 아카이브

프로젝트 v1.0 기획 단계에서 작성되었던 초기 가이드 문서는 참고 목적으로 [`archive_v1/`](archive_v1/) 폴더에 보관되어 있습니다.  
구버전 문서에 포함된 `pip install`, 단일 스위치 수정(`OFPFC_MODIFY`) 등은 현재 아키텍처와 충돌하므로 참고용으로만 열람하십시오.
