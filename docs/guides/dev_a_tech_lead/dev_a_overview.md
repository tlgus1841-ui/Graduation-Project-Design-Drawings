# 📘 [Tech Lead] 박시현 엔지니어링 개요 및 아키텍처 책임 매트릭스
> **성명:** 박시현 (22101489)  
> **직책:** Tech Lead & 시스템 아키텍트  
> **책임 영역:** 코어 아키텍처 설계, 가상 인프라, SDN 컨트롤러, 듀얼 하네스 프레임워크, 레포지토리 관리  
> **기준 문서:** `docs/planning/ai_harness_engineering_plan.md`, `docs/planning/roadmap_v2.md`

---

## 1. 역할 정의 및 레포지토리 관리 권한

Tech Lead는 전체 시스템의 안정성, 프로토콜 정합성, 그리고 AI 코딩 에이전트의 품질을 통제하는 시스템 아키텍트입니다.

### 1.1 독점 관리 소스코드 영역
- `harness/`: Pydantic 계약 스키마(SSOT), 안전 가드레일, FSM 상태 머신
- `topo/`: Mininet 다중 경로 토폴로지 에뮬레이션 스크립트 (`diamond_topo.py`)
- `ryu/`: OpenFlow 1.3 제어 평면 컨트롤러 (`ryu/app/controller.py`), Dockerfile
- `tests/harness/`: Mock IPC 버스, Headless 토폴로지 시뮬레이터, 회귀 테스트 러너
- `scripts/`: 원클릭 실행(`run_system.sh`), 초기화 스크립트(`reset_env.sh`)

### 1.2 핵심 개발 책임
1. **아키텍처 격리 수호:** Ryu 컨트롤러가 Docker Python 3.8 환경에서 격리 실행되도록 통제하고, 컨트롤러 내부에서 블로킹 연산이 일어나지 않도록 보호.
2. **계약 기반 통신 통제:** Redis 4대 채널의 Pydantic 스키마 무결성 유지.
3. **OpenFlow 1.3 제어:** ARP Broadcast Storm 차단, 최단 경로 스위칭, In_port 차단, Dijkstra 기반 다중 홉 우회 라우팅 선제 주입.
4. **자가 복구 FSM 설계:** 라우팅 플래핑(Flapping)을 방지하는 4단계 상태 전이 엔진 구현.

---

## 2. 주차별 가이드 바로가기

* [Phase 1 (1~3주차): 하네스 기반 확립 및 환경 격리 (회고)](phase1_harness_setup.md)
* [Phase 2 (4~7주차): 코어 모듈 구현 및 Mock 하네스 (당면 과제)](phase2_core_mock_harness.md)
* [Phase 3 (8주차): 중간고사 대비 1차 E2E 파이프라인 관통](phase3_midterm_pipeline.md)
* [Phase 4 (9~11주차): In_port 격리, Dijkstra 우회, FSM 플래핑 방지](phase4_safety_rerouting.md)
* [Phase 5 & 6 (12~16주차): 관제탑 연동, 긴급 서킷브레이커, 최종 라이브 시연](phase5_6_dashboard_e2e.md)
