# 🛡️ Self-Defending SDN Tower
> **SDN 기반 분산 트래픽 이상 탐지 및 자율 라우팅 관제 시스템**  
> *SDN-based Distributed Traffic Anomaly Detection and Autonomous Rerouting Web Monitoring System*

---

## 📌 1. 프로젝트 개요
본 프로젝트는 **Software-Defined Networking(SDN)**과 **경량 AI(Isolation Forest)**를 융합하여, 대규모 네트워크 공격(DDoS / IP Spoofing) 발생 시 제어 평면에서 공격 유입 진입 포트(`in_port`)를 실시간으로 격리하고 정상 트래픽을 무유실 우회(Rerouting)시키는 **자가 치유형 실시간 네트워크 관제탑** 구축을 목표로 합니다.

---

## 👥 2. 팀 역할 분담 (3인 협업)

| 역할 | 개발자 | 핵심 담당 영역 | 주요 기술 스택 | 바로가기 가이드 |
|:---:|:---:|:---|:---|:---:|
| **Dev A** | 개발자 A | **SDN 인프라 & 제어 평면** | Mininet 2.3+, Ryu 4.34 (Docker), OpenFlow 1.3, NetworkX | [가이드북](docs/guides/dev_a_sdn_infra/week1_vibe_guide.md) |
| **Dev B** | 개발자 B | **AI 이상 탐지 & 보안 파이프라인** | Scapy, Python 3.10 (`venv-ai`), Scikit-learn, Redis IPC | [가이드북](docs/guides/dev_b_ai_security/week1_vibe_guide.md) |
| **Dev C** | 개발자 C | **웹 관제탑 (Full-Stack)** | FastAPI, Asyncio WebSocket, React 18, Vite, vis-network | [가이드북](docs/guides/dev_c_web_control/week1_vibe_guide.md) |

---

## 📂 3. 프로젝트 디렉토리 구조

```text
.
├── README.md                              # 프로젝트 종합 안내서 (대문)
├── docs/                                  # 프로젝트 기술 및 기획 문서 일원화
│   ├── planning/                          # 로드맵, 공식 기획서, 환경 규칙, 일정 관리
│   │   ├── project_proposal.md            # [공식] 졸업작품 개발 기획서 (제출/심사용)
│   │   ├── roadmap_v2.md                  # 3인 협업 설계서 및 골든 버전 매트릭스
│   │   ├── environment_rules.md           # Python uv 패키지 매니저 및 환경 규칙
│   │   └── schedule_and_milestones.md     # 주차별 일정 및 과제 관리표
│   ├── proposal/                          # 주제 선정 배경 및 발표 자료
│   │   ├── why_self_defending_sdn.md      # 주제 선정 당위성 보고서
│   │   └── ppt_slide_deck_outline.md      # 10장 발표용 AI 프롬프트/대본
│   ├── guides/                            # 개발자별 주차별 실전 바이브 코딩 가이드
│   │   ├── dev_a_sdn_infra/
│   │   ├── dev_b_ai_security/
│   │   └── dev_c_web_control/
│   ├── study/                             # 네트워크/SDN/AI/웹 8대 기술 학습서
│   └── archive/                           # 이전 버전 기획서 보관함
```

---

## 📚 4. 주요 문서 바로가기

* 📑 **공식 졸업작품 개발 기획서:** [`docs/planning/project_proposal.md`](docs/planning/project_proposal.md)
* 📋 **종합 로드맵 및 기술 스택 규격:** [`docs/planning/roadmap_v2.md`](docs/planning/roadmap_v2.md)
* ⚙️ **개발 환경 및 패키지 룰:** [`docs/planning/environment_rules.md`](docs/planning/environment_rules.md)
* 📖 **8대 기술 스터디 종합 인덱스:** [`docs/study/README.md`](docs/study/README.md)
* 🎯 **주제 선정 배경 및 당위성:** [`docs/proposal/why_self_defending_sdn.md`](docs/proposal/why_self_defending_sdn.md)
