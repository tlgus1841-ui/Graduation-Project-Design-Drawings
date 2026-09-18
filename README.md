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
.
├── README.md                              # 프로젝트 종합 안내서 (대문)
├── docs/                                  # 프로젝트 기술 및 기획 문서 일원화
│   ├── planning/                          # 로드맵, 공식 기획서, 환경 규칙, 일정 관리
│   │   ├── ai_harness_engineering_plan.md # [공식] AI 하네스 엔지니어링 개발 계획서
│   │   ├── project_proposal.md            # [공식] 졸업작품 개발 기획서 (제출/심사용)
│   │   ├── roadmap_v2.md                  # 3인 협업 설계서 및 골든 버전 매트릭스
│   │   ├── environment_rules.md           # Python uv 패키지 매니저 및 환경 규칙
│   │   └── schedule_and_milestones.md     # 주차별 일정 및 과제 관리표
│   ├── proposal/                          # 주제 선정 배경 및 발표 자료
│   │   ├── why_self_defending_sdn.md      # 주제 선정 당위성 보고서
│   │   └── ppt_slide_deck_outline.md      # 10장 발표용 AI 프롬프트/대본
│   ├── guides/                            # 3인 실전 바이브 코딩 가이드북 (Phase 1~6)
│   │   ├── README.md                      # 가이드 종합 인덱스 및 대문
│   │   ├── 00_common/                     # 공통 uv 규칙, 프롬프트 표준, 계약 스키마
│   │   ├── dev_a_tech_lead/               # [박시현] Tech Lead 가이드
│   │   ├── dev_b_domain_qa/               # [유재민] Domain Dev & QA 가이드
│   │   ├── dev_c_pm_writer/               # [김관우] PM & Tech Writer 가이드
│   │   └── archive_v1/                    # v1.0 초기 가이드 보관함
│   ├── study/                             # 네트워크/SDN/AI/웹 8대 기술 학습서
│   └── archive/                           # 이전 버전 기획서 보관함
```

---

## 📚 4. 주요 문서 바로가기

* 🛡️ **[공식] AI 하네스 엔지니어링 개발 계획서:** [`docs/planning/ai_harness_engineering_plan.md`](docs/planning/ai_harness_engineering_plan.md)
* 📑 **공식 졸업작품 개발 기획서:** [`docs/planning/project_proposal.md`](docs/planning/project_proposal.md)
* 📋 **종합 로드맵 및 기술 스택 규격:** [`docs/planning/roadmap_v2.md`](docs/planning/roadmap_v2.md)
* ⚙️ **개발 환경 및 패키지 룰:** [`docs/planning/environment_rules.md`](docs/planning/environment_rules.md)
* 📖 **8대 기술 스터디 종합 인덱스:** [`docs/study/README.md`](docs/study/README.md)
* 🎯 **주제 선정 배경 및 당위성:** [`docs/proposal/why_self_defending_sdn.md`](docs/proposal/why_self_defending_sdn.md)
