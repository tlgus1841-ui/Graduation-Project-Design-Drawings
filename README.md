# 🛡️ Self-Defending SDN Tower
> **SDN 기반 분산 트래픽 이상 탐지 및 자율 라우팅 관제 시스템**  
> *SDN-based Distributed Traffic Anomaly Detection and Autonomous Rerouting Web Monitoring System*

---

## 📌 1. 프로젝트 개요
본 프로젝트는 **Software-Defined Networking(SDN)**과 **경량 AI(Isolation Forest)**를 융합하여, 대규모 네트워크 공격(DDoS / IP Spoofing) 발생 시 제어 평면에서 공격 유입 진입 포트(`in_port`)를 실시간으로 격리하고 정상 트래픽을 무유실 우회(Rerouting)시키는 **자가 치유형 실시간 네트워크 관제탑** 구축을 목표로 합니다.

---

## 👥 2. 팀 역할 분담 (3인 협업 체계)

| 역할 | 담당자 (학번) | 주 업무 | 깃허브 / 산출물 기여 | 바로가기 가이드 |
|:---:|:---:|:---|:---|:---:|
| **Tech Lead** | **박시현 (본인)**<br>(22101489) | • 가상 네트워크(Mininet) 및 테스트 하네스 아키텍처 설계<br>• 전체 파이프라인 통합 및 인터페이스 규격 정의<br>• 코어 SDN 컨트롤러(OpenFlow 차단 룰 주입 엔진) 연동 | 레포지토리 관리자, 코어 아키텍처 커밋 독점, 하네스 프레임워크 구축 | [Tech Lead 가이드](docs/guides/dev_a_tech_lead/dev_a_overview.md) |
| **Domain Dev & QA** | **유재민 (팀원 B)**<br>(22101498) | • 위협 탐지 알고리즘 구현<br>• Scapy 기반 공격 시나리오 패킷 생성<br>• 벤치마크 실행 및 정량 데이터(성능 지표) 추출 | 탐지/공격 모듈 커밋, 테스트 결과 보고서 및 그래프 데이터셋 | [Domain QA 가이드](docs/guides/dev_b_domain_qa/dev_b_overview.md) |
| **PM & Tech Writer** | **김관우 (팀장)**<br>(22102237) | • 교수님 주간 보고 및 일정 관리<br>• 방어 정책/시나리오 기획서 작성<br>• 최종 논문(보고서) 작성 및 발표 PPT 제작 | 문서화(Docs), 시스템 흐름도 기획, 최종 발표 총괄 | [PM & Writer 가이드](docs/guides/dev_c_pm_writer/dev_c_overview.md) |

---

## 📂 3. 프로젝트 디렉토리 구조

```text
Self_Defending_SDN_Tower/
├── CHANGELOG.md                           # 🌟 팀원 & AI 에이전트 변경 이력 및 협업 인수인계 SSOT
├── .cursorrules                           # AI 에이전트 개발 규칙 및 자동 로깅 프로토콜
│
├── docs/                                  # 프로젝트 기술 및 기획 문서 일원화
│   ├── writing/                           # ✍️ [집필 전용] 제출/발표 공식 산출물
│   │   ├── proposal/                      # 공식 졸업작품 개발 기획서 (선정 당위성 통합)
│   │   │   └── project_proposal.md
│   │   ├── reports/                       # 주간 및 중간 진행 보고서
│   │   │   └── weekly/week04_traffic_normal_plan.md
│   │   ├── thesis/                        # 최종 학술 논문 초안 및 챕터 원고
│   │   │   └── thesis_draft.md
│   │   └── presentations/                 # 발표 PPT 슬라이드 덱 아웃라인 및 대본
│   │       └── ppt_slide_deck_outline.md
│   │
│   ├── planning/                          # 📐 [설계/일정] 아키텍처 로드맵, 일정, 하네스 계획
│   │   ├── roadmap_v2.md                  # 3인 협업 설계서 및 골든 버전 매트릭스
│   │   ├── schedule_and_milestones.md     # 16주차 일정 및 주차별 마일스톤 (DoD)
│   │   ├── ai_harness_engineering_plan.md # AI 하네스 엔지니어링 개발 계획서
│   │   └── environment_rules.md           # Python uv 패키지 매니저 및 환경 규칙
│   │
│   ├── specs/                             # 🔍 [기술 명세]
│   │   └── defense_scenarios.md           # 4단계 자율 방어 시나리오 명세서
│   │
│   ├── guides/                            # 🛠️ [3인 가이드] 실전 개발 가이드북 (Phase 1~6)
│   │   ├── 00_common/                     # 공통 uv 규칙, 프롬프트 표준, 계약 스키마
│   │   ├── dev_a_tech_lead/               # [박시현] Tech Lead 가이드
│   │   ├── dev_b_domain_qa/               # [유재민] Domain Dev & QA 가이드
│   │   └── dev_c_pm_writer/               # [김관우] PM & Tech Writer 가이드
│   │
│   ├── study/                             # 📚 [이론 스터디] 네트워크/SDN/AI/웹 8대 기술 학습서
│   │   ├── 01_Network_and_SDN_Fundamentals.md ~ 08_Environment_and_Troubleshooting.md
│   │   └── README.md
│   │
│   └── archive/                           # 🗄️ [통합 아카이브] 구버전 v1 파일 격리 보관소
│       ├── v1_proposal/                   # v1 제안서 및 병합 원본 파일
│       └── v1_guides/                     # v1 초기 가이드 보관함
│
├── api/                                   # [김관우] FastAPI 관제탑 백엔드
│   ├── main.py                            # REST(/api/health, /api/topology) + WebSocket(/ws)
│   ├── websocket_hub.py                   # 연결 풀 및 Stale 세션 자동 정리
│   └── mock_generator.py                  # 방어 시나리오 재생 더미 텔레메트리 송출기
├── harness/                               # [박시현] Pydantic v2 계약 스키마 (sdn_events.py)
├── ryu/                                   # [박시현] Ryu 4.34 OpenFlow 1.3 컨트롤러 (Docker)
├── topo/                                  # [박시현] Mininet 다이아몬드 토폴로지 (diamond_topo.py)
├── traffic/                               # [유재민] Scapy 트래픽 생성기 (traffic_normal.py)
└── tests/                                 # 30개 단위/통합 테스트 (100% Pass)
```

---

## 📚 4. 주요 문서 바로가기

* 📑 **공식 졸업작품 개발 기획서 (통합본):** [`docs/writing/proposal/project_proposal.md`](docs/writing/proposal/project_proposal.md)
* 📋 **종합 로드맵 및 기술 스택 규격:** [`docs/planning/roadmap_v2.md`](docs/planning/roadmap_v2.md)
* 📅 **16주차 상세 일정 및 마일스톤:** [`docs/planning/schedule_and_milestones.md`](docs/planning/schedule_and_milestones.md)
* 🛡️ **[공식] AI 하네스 엔지니어링 개발 계획서:** [`docs/planning/ai_harness_engineering_plan.md`](docs/planning/ai_harness_engineering_plan.md)
* 🔍 **4단계 자율 방어 시나리오 명세서:** [`docs/specs/defense_scenarios.md`](docs/specs/defense_scenarios.md)
* 🎓 **최종 학술 논문 초안 (작성용):** [`docs/writing/thesis/thesis_draft.md`](docs/writing/thesis/thesis_draft.md)
* 📊 **발표 슬라이드 덱 아웃라인:** [`docs/writing/presentations/ppt_slide_deck_outline.md`](docs/writing/presentations/ppt_slide_deck_outline.md)
* 🐙 **실전 Git & GitHub 3인 협업 가이드:** [`docs/guides/00_common/git_collaboration_guide.md`](docs/guides/00_common/git_collaboration_guide.md)
* 📖 **8대 기술 스터디 종합 인덱스:** [`docs/study/README.md`](docs/study/README.md)
* 📝 **팀원 & AI 에이전트 협업 로그:** [`CHANGELOG.md`](CHANGELOG.md)

---

## 🚀 5. 빠른 시작 (Getting Started)

다음 개발자가 저장소를 클론한 후 바로 테스트하고 개발을 시작할 수 있는 방법입니다.

```bash
# 1. 저장소 클론 및 이동
git clone https://github.com/tlgus1841-ui/Graduation-Project-Design-Drawings.git
cd Graduation-Project-Design-Drawings

# 2. uv 패키지 환경 동기화 (Python 3.10 및 모든 의존성 자동 설치)
uv sync

# 3. Mock IPC 하네스 단위 테스트 실행 (0.1초 소요, 100% 통과 확인)
uv run pytest tests/harness/test_mock_ipc.py -v

# 4. 토폴로지 구조 검증
uv run python -c "from topo.diamond_topo import DiamondTopo; topo = DiamondTopo(); print('Diamond Topo Loaded!')"

# 5. 관제탑 백엔드 실행 (Mock 모드: 4단계 방어 시나리오 더미 텔레메트리 송출)
uv run uvicorn api.main:app --reload --port 8000
#    → http://localhost:8000/api/health , ws://localhost:8000/ws
#    → 더미 송출 없이 허브만 띄우려면: SDN_MOCK=0 uv run uvicorn api.main:app --port 8000
```
