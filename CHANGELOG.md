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

### [2026-10-07] test(e2e) + docs: 김관우 14주차 E2E 통합 검증, 차단·우회 우선순위 충돌 발견
* **작업자:** 김관우 (PM & Tech Writer) with Claude Code
* **작업 유형:** `Test` / `Docs` / `Spec`
* **주요 변경 파일:**
  - `harness/verification/e2e_scenario.py`: ping 출력을 파일로 기록(호스트 pty 버퍼 포화로 ping이 멈추던 문제 수정), 응답 시각 기반 구간 손실, S1 우회 규칙 카운터 추가
  - `harness/verification/e2e_defense_standin.py`: `--drop-priority` 옵션, 비정상 카운터(ΔPPS > 1e7) 무시
  - `docs/writing/reports/verification/week14_e2e_verification.md`: (신규) E2E 보고서 + 원본 JSON·실데이터 관제탑 화면
  - `docs/specs/defense_scenarios.md`: v1.1, Q5 추가 (차단·우회 규칙 우선순위 충돌)
  - `docs/writing/thesis/thesis_draft.md`: 4.2 우선순위 서술, 5.4 결과 표(반응 78.4ms, 손실 0%), 5.5 E2E 절
* **상세 변경 내용 및 성과 (3회):**
  - 4단계 루프 완결, 정상 ping 손실 **0 / 4,312** (공격 구간 0 / 1,123), 격리 후 서버 도달 공격 0, 플래핑 0, 공격 종료 → 복구 평균 12.73초, 탐지 확정 → 규칙 설치 평균 78.4ms
  - 관제탑 live 모드에서 UNDER ATTACK → MITIGATED → NORMAL 전환과 S1:3 → S1:4 트래픽 이동이 실데이터로 확인됨
* **영향 범위 및 주의사항 (Breaking Changes):** 명세 변경 제안(Q5). 코드 인터페이스 변경 없음.
* **다음 작업자 인수인계 메모:**
  - **[박시현] 명세 Q5:** 차단과 우회가 둘 다 Priority 100이면 차단이 무력화됨(실측: 차단 적중 0, 공격 27,607패킷이 우회로로 서버 도달). ISOLATE drop을 200으로 올리거나 REROUTE 일치 조건에 `in_port=1` 추가 필요.
  - **[유재민]** Mininet 종료 시 포트 카운터 리셋으로 ΔPPS ≈ 9.2e18이 계산됨. `feature_extractor`에 비정상 값 무시 처리 권장.
  - 임시 구성요소(규칙 스코어, SpecFSM, ovs-ofctl)는 실제 AI·FSM·컨트롤러가 들어오면 같은 시나리오로 교체 측정.

### [2026-10-07] feat(api,ui) + docs: 김관우 13주차 비상 수동 제어, 관제 매뉴얼, 논문 구현 절
* **작업자:** 김관우 (PM & Tech Writer) with Claude Code
* **작업 유형:** `Feat` / `Test` / `Docs`
* **주요 변경 파일:**
  - `api/manual_control.py`: (신규) 수동 ISOLATE/RESTORE 요청 검증 → `ControlCommandMessage` 생성 (트렁크·존재하지 않는 포트 거부, 사유 필수, `[MANUAL] 운영자: 사유`)
  - `api/main.py`: `POST /api/control/manual` (선택적 `SDN_ADMIN_TOKEN` → `X-Admin-Token`), live 모드는 Redis `sdn:control:command`로 발행(구독 에코로 UI 반영), mock 모드는 WebSocket 직접 브로드캐스트, Redis 장애 시 503
  - `api/redis_bridge.py`: `publish()` 추가
  - `ui/src/components/ManualControl.jsx`: (신규) 헤더 "비상 수동 제어" 버튼 + 확인 대화상자 (동작·대상 포트·사유·운영자·토큰, 확인 체크 후 실행, 정상 호스트 격리 경고, Esc 닫기, 포커스 복귀). body 포털 렌더링
  - `ui/src/lib/api.js`: (신규) `sendManualControl`, `VITE_API_URL`
  - `ui/src/lib/towerState.js`, `EventFeed.jsx`: `[MANUAL]` 명령을 주황 `MANUAL` 이벤트로 표시
  - `tests/api/test_manual_control.py`: (신규) 14건
  - `docs/writing/manual/operator_manual.md`: (신규) 관제탑 사용자 매뉴얼
  - `docs/writing/thesis/thesis_draft.md`: 5.2 구성 요소별 구현 절 추가 (5.2→5.3, 5.3→5.4)
  - `README.md`: 매뉴얼·검증서 링크, 관리자 토큰·성능 측정 안내
* **상세 변경 내용 및 성과:**
  - 브라우저 검수: 대화상자 열림·포커스, 확인 전 실행 비활성, 정상 호스트 경고, 전송 후 알림·MANUAL 이벤트, Esc 닫기, 모바일 넘침 없음, 오류 0. 트렁크 포트 API 직접 요청 409.
* **영향 범위 및 주의사항 (Breaking Changes):** 없음. 새 엔드포인트 추가.
* **다음 작업자 인수인계 메모:**
  - Tech Lead 컨트롤러가 `sdn:control:command`를 구독해 ISOLATE(Priority 100 in_port drop)/RESTORE를 실행하면 수동 제어가 실제 스위치에 반영됨. 서킷 브레이커(`harness/safety/circuit_breaker.py`)가 수동 모드로 전환할 때도 이 API를 그대로 사용 가능.

### [2026-10-07] perf(ui) + docs(thesis): 김관우 12주차 관제탑 60fps 성능 검수 및 논문 본문 집필 착수
* **작업자:** 김관우 (PM & Tech Writer) with Claude Code
* **작업 유형:** `Perf` / `Test` / `Docs`
* **주요 변경 파일:**
  - `ui/src/hooks/useControlTowerSocket.js`, `ui/src/lib/towerState.js`: 한 애니메이션 프레임에 들어온 WebSocket 메시지를 모아 `batch`로 한 번에 반영 (주기당 리렌더 6회 → 1회)
  - `ui/src/components/TrafficCharts.jsx`: 차트 옵션 고정, 점별 dataLabels 제거(빈 라벨 240개 생성·측정 비용 제거) → 차트 위 최신값 행(`LatestValues`)으로 대체
  - `ui/src/components/TopologyMap.jsx`, `EventFeed.jsx`: `memo` 적용
  - `ui/scripts/fps-check.mjs` + `npm run perf`: (신규) 한 사이클 FPS·p95/p99·끊김 비율·Long Task 측정, CPU 1배/4배 조건. `playwright` devDependency 추가
  - `docs/writing/reports/verification/week12_ui_performance_verification.md`: (신규) 개선 전후 검수서 + 원본 JSON
  - `docs/writing/thesis/thesis_draft.md`: 1장(서론), 2장(2.1·2.2), 3장(아키텍처), 5장(환경·시나리오·결과 표) 초안
* **상세 변경 내용 및 성과:**
  - 일반 CPU: 평균 58.6 → **60.0fps**, p99 33.4 → **16.8ms**, 끊김 1.0 → **0%**
  - CPU 4배 감속: 47.4 → **56.6fps**, p99 233 → **16.8ms**, Long Task 79 → 40회
* **영향 범위 및 주의사항 (Breaking Changes):** 없음. 차트 범례가 ApexCharts 내장 범례에서 최신값 행으로 바뀜 (같은 색·이름).
* **다음 작업자 인수인계 메모:**
  - 논문 5.3 표의 [ ] (F1, 추론 지연, 반응 시간, 종합 손실률)는 AI 모델·E2E 측정 후 채움. 2.3 선행 연구 비교는 문헌 조사 필요.

### [2026-10-07] feat(ui,verification,docs): 김관우 11주차 자가 복구 알림 UI, 플래핑 수용 시험, 논문 4장 초안
* **작업자:** 김관우 (PM & Tech Writer) with Claude Code
* **작업 유형:** `Feat` / `Test` / `Docs`
* **주요 변경 파일:**
  - `ui/src/components/IncidentStrip.jsx`: COOLDOWN_VERIFY 청록색 스트립 + 10초 카운트다운·진행 막대
  - `ui/src/components/RecoveryNotice.jsx`: (신규) 자가 복구 완료 알림 (탐지·우회·격리·복구 확인·복구 완료 ms 타임라인, 총 소요 시간, 확인 버튼/15초 자동 닫힘)
  - `ui/src/lib/towerState.js`: `incident.cooldownAt`(재진입 시 리셋), `recovery` 보고서, `COOLDOWN_SEC`
  - `harness/verification/fsm_acceptance.py`: (신규) 명세 FSM 참조 구현(`SpecFSM`) + 5개 시나리오 수용 시험, 비교용 타임아웃식 FSM
  - `tests/harness/test_fsm_acceptance.py`: (신규) 9건
  - `docs/writing/reports/verification/week11_self_healing_verification.md`: (신규) 11주차 검증서 + 원본 JSON
  - `docs/writing/thesis/thesis_draft.md`: 제4장(4.1~4.4) 본문 초안 v0.1
* **상세 변경 내용 및 성과:**
  - 명세 FSM: 5개 시나리오 모두 플래핑 0회 (V5 충족), 지속 공격 종료 후 12초 내 복구. 타임아웃식 FSM은 맥동 공격에서 플래핑 7회로 실패 → 시험 도구의 검출력 확인.
  - 브라우저 검수: 카운트다운 9.9→6.9초 감소, 복구 확인 시작→완료 10.0초, 알림 표시·닫힘, 모바일 넘침 없음, 오류 0.
* **영향 범위 및 주의사항 (Breaking Changes):** 없음.
* **다음 작업자 인수인계 메모:**
  - Tech Lead `flapping_fsm.py` 구현 시 `step(sample) -> [명령]` 형태로 감싸 `fsm_acceptance.run_all()`에 넣으면 같은 기준으로 판정됨.
  - 논문 초록의 "FSM 타임아웃을 통해 자가 복구" 표현은 명세(타임아웃 없이 쿨다운 후 명시적 RESTORE)와 다름. 초록 작성자 확인 필요.

### [2026-10-07] feat(ui,verification): 김관우 10주차 청색 우회 경로 UI 및 무유실 경로 전환 실증
* **작업자:** 김관우 (PM & Tech Writer) with Claude Code
* **작업 유형:** `Feat` / `Test` / `Docs`
* **주요 변경 파일:**
  - `ui/src/components/IncidentStrip.jsx`: MITIGATED 단계 청색 스트립 (격리 포트, 우회 경로, 탐지→격리·우회 ms, 격리 시각)
  - `ui/src/lib/towerState.js`: ISOLATE·REROUTE 명령 시각을 `incident`에 기록 (첫 명령만)
  - `ui/src/lib/format.js`: `elapsedMs` 추가
  - `ui/src/components/TopologyMap.jsx`: REROUTED 링크 청색 발광 효과
  - `harness/verification/reroute_loss_check.py`: (신규) ping 도중 우회 규칙을 S3→S4→S1 순서로 주입하고 손실률·우회 규칙 카운터 측정
  - `tests/harness/test_reroute_loss_check.py`, `ui/src/lib/*.test.js`: 테스트 추가
  - `docs/writing/reports/verification/week10_reroute_loss_verification.md`: (신규) 10주차 실증 검증서 + 원본 데이터 4회분
* **상세 변경 내용 및 성과:**
  - 실측: 경로 전환 중 정상 ping **4,000 / 4,000 수신 (손실 0%)**, 회당 약 800개가 우회 규칙 통과.
  - 브라우저 검수: MITIGATED 청색 스트립, 우회 링크 발광, NORMAL 복귀 시 해제, 콘솔 오류 0.
* **영향 범위 및 주의사항 (Breaking Changes):** 없음.
* **다음 작업자 인수인계 메모:**
  - 컨트롤러 REROUTE 구현 시 `BYPASS_FLOWS`와 같은 규칙·순서(S1을 마지막에)로 설치하면 무유실이 유지됨. 같은 스크립트로 재검증 가능.

### [2026-10-07] feat(ui,verification): 김관우 9주차 적색 경보 UI 및 플로우 테이블 폭발 방어 실증
* **작업자:** 김관우 (PM & Tech Writer) with Claude Code
* **작업 유형:** `Feat` / `Test` / `Docs`
* **주요 변경 파일:**
  - `ui/src/components/IncidentStrip.jsx`: (신규) 헤더 아래 상태 스트립. `ATTACK_DETECTED` 동안 적색 경보 점멸(유입 포트, 위협 유형, score·PPS·BPP, 탐지 시각 ms), 평상시에는 단계별 안내 문구. 레이아웃 흔들림 방지를 위해 항상 같은 자리에 표시
  - `ui/src/lib/towerState.js`: `incident` 상태 추가 (첫 알림에서 열리고 NORMAL·CALIBRATING에서 닫힘)
  - `ui/src/lib/format.js`: (신규) `clockMs`(HH:MM:SS.mmm), `PORT_NAMES`, `fmt` 공용화
  - `ui/src/components/EventFeed.jsx`: 보안 이벤트 시각을 밀리초 단위로 표시
  - `ui/src/components/PortStatsPanel.jsx`: 공격 유입 포트 행 적색 점멸
  - `ui/tailwind.config.js`: `animate-alert-blink` 키프레임 추가 (`motion-reduce` 시 정지)
  - `harness/verification/flow_table_check.py`: (신규) Mininet에서 공격 중 스위치별 플로우 개수를 1초마다 측정하는 실증 스크립트
  - `tests/harness/test_flow_table_check.py`, `ui/src/lib/format.test.js`, `ui/src/lib/towerState.test.js`: 테스트 추가
  - `docs/writing/reports/verification/week09_flow_table_verification.md`: (신규) 9주차 실증 검증서 + 원본 데이터 JSON
* **상세 변경 내용 및 성과:**
  - 실측: IP 스푸핑 SYN Flood 18,103패킷 동안 S1~S4 플로우 증가 **0** (S1 4개 유지, 공격 패킷 전부 `nw_dst=10.0.0.4` 규칙 1개에 매칭). pingall 0%.
  - 브라우저 검수: 공격 단계에서 적색 경보 점멸, S1:2 행 강조, 이벤트 시각 ms 표시, 격리 후 경보 해제, 모바일 가로 넘침 없음, 콘솔 오류 0.
  - Python 69 / 웹 10 테스트 통과, flake8(120자)·mypy 통과.
* **영향 범위 및 주의사항 (Breaking Changes):** 없음. 백엔드·계약 스키마 변경 없음.
* **다음 작업자 인수인계 메모:**
  - Tech Lead의 In_port 차단 규칙(Priority 100)이 들어오면 같은 스크립트로 "플로우 +1, 차단 규칙 n_packets 증가"를 재검증 (검증서 §5).
  - live 모드의 적색 경보는 AI 워커가 `sdn:anomaly:alert`를 발행해야 표시됨 (7주차 이후).

### [2026-10-06] fix & sync: 유재민 팀원 트래픽 버그픽스 통합 및 main 브랜치 최신화
* **작업자:** 박시현 (Tech Lead) with Antigravity AI Agent
* **작업 유형:** `Fix` / `Merge` / `Chore`
* **주요 변경 및 병합 내역:**
  - `traffic/traffic_attack.py`, `traffic/traffic_normal.py`: CLI 직접 실행 시 패키지 컨텍스트 부재로 인한 `ModuleNotFoundError` 수정 (유재민 커밋 `be5c35b` 병합)
  - `main` 브랜치: 5~6주차 Ryu 컨트롤러, 텔레메트리 파이프라인, 관제탑 백엔드/UI 전체 작업물 로컬 `main`으로 Fast-forward 통합 완료
  - 전체 회귀 테스트 통과: **55 / 55 tests passed (100% Pass, 0.69s)**, flake8 (120자 준수) 0건, mypy 0건 통과
* **다음 작업자 인수인계 메모:**
  - `git push origin main` 완료 시 유재민, 김관우 팀원도 본 `CHANGELOG.md` 및 최신 6주차 완성본 코드를 즉시 공유받을 수 있음.


### [2026-10-03] feat(ryu): 박시현(Tech Lead) 6주차 2-Tier 텔레메트리 파이프라인 및 Redis 포트 통계 발행 구현 완료
* **작업자:** 박시현 (Tech Lead) with Antigravity AI Agent
* **작업 유형:** `Feat` / `Test`
* **주요 변경 파일:**
  - `ryu/app/controller.py`: Eventlet 2초 주기 비차단 모니터 루프(`_monitor_loop`), `OFPPortStatsRequest` 발송 및 `OFPPortStatsReply` 파서 탑재, `OFPP_LOCAL` 필터링, Pydantic SSOT(`PortStatsMessage`) 직렬화 후 Redis `sdn:stats:port` 채널 실시간 발행, Redis 장애 격리 가드레일(`try-except` 및 비차단 복원) 완성
  - `tests/ryu/test_telemetry.py`: (신규 생성) 6주차 텔레메트리 단위 테스트 4종 추가 (Datapath 등록/해제 FSM, 통계 요청 발송, 계약 모델 엄격 검증, Redis 장애 격리)
  - `tests/ryu/test_controller_logic.py`: `DEAD_DISPATCHER` 및 `hub` 모킹 보강
* **상세 변경 내용 및 성과:**
  - Ryu Greenlet 코루틴 루프를 일체 블로킹하지 않고 2.0초 주기로 4개 스위치(S1~S4)의 포트 통계를 수집하여 Redis로 실시간 브로드캐스팅하는 2-Tier 수집 파이프라인 완성.
  - 김관우 팀원의 `api/redis_bridge.py` 및 관제탑 웹(`towerState.js`) 실시간 차트 수신 규격과 100% 일치 확인.
  - 전체 회귀 테스트 통과: **53 / 53 tests passed (100% Pass, 0.70s)**.
  - flake8 (79자 준수) 및 mypy 0건 통과 (`Success: no issues found in 4 source files`).
* **영향 범위 및 주의사항 (Breaking Changes):**
  - 기존 5주차 L2/L3 스위칭 및 Proxy ARP 방어 로직에 영향 없음. 호환성 100% 유지.
* **다음 작업자 인수인계 메모:**
  - **유재민 (Domain Dev & QA):** Ryu가 2초마다 Redis `sdn:stats:port`로 `PortStatsMessage`를 발행하므로, 6주차 과제인 **5대 파생 피처 계산기 (`feature_extractor.py` — $\Delta$PPS, $\Delta$BPS, BPP)** 구현에 바로 착수 가능.
  - **김관우 (PM & Tech Writer):** 6주차 텔레메트리 관통 성과를 바탕으로 주간 진도 보고서 #3 최종 마감 가능.

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
