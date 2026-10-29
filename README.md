# 🛡️ Self-Defending SDN Tower
> **SDN 기반 분산 트래픽 이상 탐지 및 자율 라우팅 관제 시스템**  
> *SDN-based Distributed Traffic Anomaly Detection and Autonomous Rerouting Web Monitoring System*

---

## 📌 1. 프로젝트 개요
본 프로젝트는 **Software-Defined Networking(SDN)**과 **경량 AI(Isolation Forest)**를 융합하여, 대규모 네트워크 공격(DDoS / IP Spoofing) 발생 시 제어 평면에서 공격 유입 진입 포트(`in_port`)를 실시간으로 격리하고 정상 트래픽을 무유실 우회(Rerouting)시키는 **자가 치유형 실시간 네트워크 관제탑** 구축을 목표로 합니다.

---

## 👥 2. 팀 역할 분담 (3인 협업 체계)

| 역할 | 담당자 (학번) | 주 업무 | 깃허브 / 산출물 기여 |
|:---:|:---:|:---|:---|
| **Tech Lead** | **박시현 (본인)**<br>(22101489) | • 가상 네트워크 및 테스트 하네스 아키텍처 설계<br>• 전체 파이프라인 통합 및 인터페이스 규격 정의<br>• 코어 SDN 컨트롤러(OpenFlow 차단 룰 주입 엔진) 연동 | 레포지토리 관리자, 코어 아키텍처 커밋 독점, 하네스 프레임워크 구축 |
| **Domain Dev & QA** | **유재민 (팀원 B)**<br>(22101498) | • 위협 탐지 알고리즘 구현<br>• Scapy 기반 공격 시나리오 패킷 생성<br>• 벤치마크 실행 및 정량 데이터(성능 지표) 추출 | 탐지/공격 모듈 커밋, 테스트 결과 보고서 및 그래프 데이터셋 |
| **PM & Tech Writer** | **김관우 (팀장)**<br>(22102237) | • 교수님 주간 보고 및 일정 관리<br>• 방어 정책/시나리오 기획서 작성<br>• 최종 논문(보고서) 작성 및 발표 PPT 제작 | 문서화(Docs), 시스템 흐름도 기획, 최종 발표 총괄 |

---

## 📂 3. 프로젝트 디렉토리 구조

```text
Self_Defending_SDN_Tower/
├── CHANGELOG.md                           # 🌟 팀원 & AI 에이전트 변경 이력 및 협업 인수인계 SSOT
├── .cursorrules                           # AI 에이전트 개발 규칙 및 자동 로깅 프로토콜
├── docker-compose.yml                     # Redis 7.2 브로커 및 Ryu 4.34 컨트롤러 컨테이너 오케스트레이션
├── pyproject.toml                         # Python 3.10 (uv) 의존성 및 린트/테스트 설정
│
├── docs/                                  # 프로젝트 기술 및 기획 문서 일원화
│   ├── thesis/                            # 🎓 학사 졸업논문 원고 (thesis_draft.md)
│   ├── manual/                            # 🖥️ 관제탑 운영자 매뉴얼 (operator_manual.md)
│   ├── specs/                             # 🔍 핵심 기술 명세 (공격 판단 기준, 방어 시나리오, IPC 통신 규격)
│   ├── verification/                      # ✅ 952k 극한 테스트 및 다중 공격 실측 검증 보고서 (data/)
│   ├── presentation/                      # 📊 최종 발표 슬라이드, 데모 시연 런북, PPT 프롬프트
│   └── planning/                          # 📐 종합 로드맵, 개발 계획서, 프로젝트 기획서 통합본
│
├── api/                                   # [김관우] FastAPI 관제탑 백엔드
│   ├── main.py                            # REST(/api/health, /api/topology, /api/control/manual) + WebSocket(/ws)
│   ├── manual_control.py                  # 운영자 비상 수동 격리/복원 검증 및 명령 생성
│   ├── websocket_hub.py                   # 연결 풀 및 Stale 세션 자동 정리
│   ├── mock_generator.py                  # 방어 시나리오 재생 더미 텔레메트리 송출기
│   ├── redis_bridge.py                    # Redis 4채널 구독 → 계약 검증 → WebSocket 중계 (live 모드)
│   └── redis_replay.py                    # Ryu 없이 더미 시나리오를 실제 Redis로 발행하는 검증 도구
├── ui/                                    # [김관우] React 18 + Vite + Tailwind 관제탑 (vis-network 토폴로지, ApexCharts 차트)
├── harness/                               # [박시현] 계약 스키마(contracts/), 안전 가드레일·FSM(safety/), 실증 도구(verification/)
├── ryu/                                   # [박시현] Ryu 4.34 OpenFlow 1.3 컨트롤러 (app/controller.py, app/reroute.py, Dockerfile.ryu)
├── topo/                                  # [박시현] Mininet 4-스위치 다이아몬드 토폴로지 (diamond_topo.py)
├── pipeline/                              # [유재민] 5대 파생 피처 실시간 추출기 및 CSV 로거 (feature_extractor.py, csv_logger.py)
├── model/                                 # [유재민] Isolation Forest 탐지 모델, 오탐 방지 가드, 추론 워커 (model.py, inference_worker.py)
├── traffic/                               # [유재민] Scapy 정상/공격 트래픽 생성기 (traffic_normal.py, traffic_attack.py, traffic_scan.py)
├── scripts/                               # [박시현] E2E 시나리오 데모 러너 및 환경 초기화 스크립트 (demo_scenario.sh, reset_env.sh)
└── tests/                                 # 단위/통합/벤치마크 테스트 스위트 (api, benchmarks, harness, model, pipeline, ryu, traffic)
```

---

## 📚 4. 주요 문서 바로가기

* 🎓 **최종 학술 논문 초안:** [`docs/thesis/thesis_draft.md`](docs/thesis/thesis_draft.md)
* 🖥️ **관제탑 사용자 매뉴얼:** [`docs/manual/operator_manual.md`](docs/manual/operator_manual.md)
* 🔍 **6종 공격 판단 기준 및 방어 시나리오:** [`docs/specs/attack_criteria.md`](docs/specs/attack_criteria.md), [`docs/specs/defense_scenarios.md`](docs/specs/defense_scenarios.md)
* 📡 **컴포넌트 간 IPC 통신 계약 규격:** [`docs/specs/contract_first_ipc_guide.md`](docs/specs/contract_first_ipc_guide.md)
* ✅ **실증 검증 보고서 및 데이터셋:** [`docs/verification/`](docs/verification/)
* 📊 **발표 슬라이드 아웃라인 & 시연 런북:** [`docs/presentation/ppt_slide_deck_outline.md`](docs/presentation/ppt_slide_deck_outline.md), [`docs/presentation/final_demo_runbook.md`](docs/presentation/final_demo_runbook.md)
* 📑 **공식 졸업작품 개발 기획서 (통합본):** [`docs/planning/project_proposal.md`](docs/planning/project_proposal.md)
* 📋 **종합 로드맵 및 기술 스택 규격:** [`docs/planning/roadmap_v2.md`](docs/planning/roadmap_v2.md)
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

# 5-1. 실제 Redis 연동(live) 모드: Redis 4채널을 구독해 브라우저로 중계
SDN_MOCK=0 REDIS_URL=redis://localhost:6379/0 uv run uvicorn api.main:app --port 8000
uv run python -m api.redis_replay --speed 4   # Ryu 대신 더미 시나리오를 Redis로 발행 (검증용)

# 6. 관제탑 대시보드 실행 (Node 20+, 백엔드를 먼저 켜 두세요)
cd ui && npm install && npm run dev      # → http://localhost:5173
#    → WebSocket 주소 변경: ui/.env.example을 ui/.env로 복사 후 VITE_WS_URL 수정
#    → 비상 수동 제어 보호: 백엔드 실행 전 export SDN_ADMIN_TOKEN=<비밀값>
#    → 화면 성능 측정: cd ui && npm run build && npm run perf
```
