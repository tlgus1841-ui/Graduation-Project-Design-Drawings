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

### [2026-10-29] fix(ui): 관제탑 대시보드 가독성 개선 (한글 폰트 · 저대비 텍스트 · 작은 글자)
* **작업자:** 김관우 (PM & Tech Writer) with Claude Code
* **작업 유형:** `Fix`
* **배경:** "가독성이 좋지 않다"는 평가를 받음. 원인은 세 가지 — (1) 한글 전용 웹폰트 없이 Tailwind 기본 `ui-sans-serif/system-ui` 스택에 의존해 한글이 가늘고 빽빽하게 렌더링, (2) 실질 정보(이벤트 상세, 포트 통계, 패널 부제, 차트 축/툴팁 텍스트)에 저대비 회색(`text-slate-400`, 어두운 배경 대비 ~3.7:1로 WCAG AA 4.5:1 미달)을 과용, (3) 이벤트 피드·포트 텔레메트리 표 같은 핵심 데이터가 `text-xs`/`text-sm`으로 지나치게 작게 표시됨.
* **주요 변경 파일:**
  - `ui/index.html`, `ui/tailwind.config.js`: Pretendard Variable(CDN, jsdelivr) 추가해 `font-sans` 기본값으로 지정.
  - `ui/src/index.css`: 전역 `line-height: 1.5` · 폰트 안티앨리어싱 적용.
  - `ui/src/components/{Panel,EventFeed,PortStatsPanel,TopologyMap,TrafficCharts,ConnectionBadge,RecoveryNotice,ManualControl,RelearnControl}.jsx`, `ui/src/App.jsx`: 실질 정보 텍스트의 `text-slate-400`→`text-slate-300`(대비 개선), 핵심 콘텐츠(이벤트 상세, 포트 표, 패널 부제, 차트 범례)의 `text-xs`→`text-sm`, `text-sm`→`text-base` 승격. 차트 축/툴팁 색(`INK.secondary`)도 slate-400→slate-300로 교체.
* **영향 범위 및 주의사항 (Breaking Changes):** 없음. 순수 스타일 변경(색상·크기·폰트)만 적용, 레이아웃 구조·테스트 대상 로직(`data-testid` 등)은 그대로. 상태 색상(빨강/파랑/초록 등 FSM 의미 매핑)과 영문 모노스페이스 배지(라벨, command ID 등)는 의도적으로 유지.
* **검증:** `npx vitest run` 26 passed, `npm run build` 성공. Playwright로 `vite preview` 화면 스크린샷 확인 — 한글 렌더링 개선, 텍스트 대비·크기 증가 확인.
* **다음 작업자 인수인계 메모:** 실데이터(WS/Redis 연결)로 이벤트 피드 · 포트 텔레메트리 · 차트가 채워진 상태에서 추가로 가독성을 재평가해보는 것을 권장. `text-slate-400`이 여전히 남은 곳(IncidentStrip의 대기 상태 점 색 등)은 장식용 인디케이터라 의도적으로 보존함.

### [2026-10-29] merge: PR #10(공격 판단 기준 세분화)을 main에 통합하며 충돌 해소
* **작업자:** 유재민 (Domain Dev & QA) with Claude Code
* **작업 유형:** `Fix` / `Test`
* **배경:** `claude/quirky-cerf-h51gg3`(PR #10)과 main이 그사이 각자 `traffic/traffic_scan.py`를 독립적으로 만들어, 이름은 같지만 완전히 다른 두 생성기가 충돌했다. main 쪽 버전은 이번에 superseded된 구(舊) `model/attack_classifier.py`(PORT_SCAN/SLOW_DRIFT, PR #6) 검증용이었고, PR #10 쪽 버전은 새 `model/criteria_engine.py`의 실측 도구(`harness/verification/criteria_measure.py`)가 모듈 경로로 직접 호출하는 쪽이라 PR #10 버전을 남겼다.
* **주요 변경 파일:**
  - `traffic/traffic_scan.py`: PR #10 버전(`--kind tcp/udp`, `build_probe`/`run`) 유지. main 버전(`ScanProfile`/`dport_cycle` 기반)은 버림 — `model/attack_classifier.py`가 PR #10에서 그대로(PR #6에서 수정한 delta_pps 기준 유지, `--legacy` 경로로 공존) 들어왔으므로 기능 손실 없음.
  - `tests/traffic/test_traffic_scan.py`: 옛 API(`ScanProfile` 등) 기준 테스트를 PR #10 버전 API(`parse_ports`/`build_probe`/`run`) 기준으로 새로 작성 (4개).
  - `traffic/traffic_scan.py`, `traffic/traffic_flood.py`: 병합 후 재검사에서 드러난 scapy `Packet.__truediv__`(2단 체이닝) mypy 오탐 2건을 PR #5와 동일한 `# type: ignore[operator]` 관례로 처리.
  - `CHANGELOG.md`, `model/inference_worker.py`(모듈 docstring): 두 브랜치가 각자 추가한 안내문 병합(내용 중복 없음, 양쪽 다 유지).
* **영향 범위 및 주의사항 (Breaking Changes):** 없음. `model/attack_classifier.py`·`model/criteria_engine.py` 로직은 병합 중 변경하지 않음(파일명 충돌과 문서 텍스트 충돌만 해소).
* **검증:** 병합 후 `flake8` 0건, `mypy` 신규 에러 없음(기존 pydantic 버전 불일치 오탐 22건 제외), `pytest` 265 passed.
* **다음 작업자 인수인계 메모:**
  - **[공통]** `model/attack_classifier.py`(`SecondaryAttackClassifier`, `--legacy` 경로)와 `model/criteria_engine.py`(기본 경로)가 지금 둘 다 켜져 있습니다. 전자가 여전히 필요한지(이중 탐지 의도) 정리가 필요하면 논의해주세요.

### [2026-10-28] docs(specs): 공격 판단 기준에 실제 논문 출처 추가
* **작업자:** 유재민 (Domain Dev & QA) with Claude Code
* **작업 유형:** `Docs`
* **배경:** `docs/specs/attack_criteria.md`·`model/criteria_engine.py`에 있던 "Zeek", "Jung 2004" 같은 약식 언급을 검증된 정식 참고문헌으로 교체.
* **주요 변경 파일:**
  - `docs/specs/attack_criteria.md` §6 (신규): 서지 정보 7건 추가 — SYN Flood CUSUM(Wang·Zhang·Shin, INFOCOM 2002), 포트 스캔 실패 비율/TRW(Jung et al., IEEE S&P 2004), Zeek 스캔 임계치 원 논문(Paxson, Computer Networks 1999), 내부 확산 차단(Weaver et al., USENIX Security 2004), 평균+3σ EWMA 기준선(Ye·Borror·Zhang, QREI 2002), Slow HTTP 분류(Cambiaso et al., IJTMCC 2013), Flood 유형 분류(Mirkovic·Reiher, ACM SIGCOMM CCR 2004).
  - `docs/writing/thesis/thesis_draft.md`: 참고문헌 [1]~[3]에 이어 [4]~[10]으로 위 서지 추가.
  - `model/criteria_engine.py`: 모듈 docstring에 참고문헌 요약 포인터 추가.
* **영향 범위 및 주의사항 (Breaking Changes):** 없음. 로직·숫자 변경 없이 문서·주석만 수정.
* **검증:** 각 논문의 제목·저자·학회(지)·연도·DOI를 실제 검색으로 확인. 관련 테스트(`tests/model/test_criteria_engine.py` 26개) 통과, flake8 0건.

### [2026-10-28] perf(ryu,model): 종류별 개수를 1초마다 읽어 탐지 시간 단축
* **작업자:** 김관우 (PM & Tech Writer) with Claude Code
* **작업 유형:** `Performance` / `Test` / `Docs`
* **주요 변경 파일:**
  - `ryu/app/controller.py`, `harness/contracts/sdn_events.py`: 종류별 개수(`sdn:stats:flowcount`)는 1초마다(`FLOW_COUNT_INTERVAL_SEC`), 포트 통계 · 서비스 상태는 그대로 2초마다(`PORT_STATS_INTERVAL_SEC`). 관제탑 화면 갱신 주기는 그대로
  - `model/criteria_engine.py`: 시간 창을 보고 횟수가 아니라 초로 바꿈 (스캔 4초 · 5분, 주의 해제 4초, 학습 재개 10초, EWMA 10분 · 재학습 1분 기억). 보고 주기가 바뀌어도 뜻이 같다. "2회 연속 확인"은 그대로라 확정까지 걸리는 시간만 절반
  - `harness/verification/criteria_measure.py`: 공격 시작을 0~2초 무작위로 늦춰 보고 주기와 엇갈리게 함 (전에는 매번 보고 직후에 시작해 가장 늦은 경우만 쟀다)
  - `tests/`: 1초 보고에서도 같은 창 · 2초 만에 확정, 컨트롤러가 개수는 1초 · 포트 통계는 2초마다 요청하는지
* **영향 범위 및 주의사항 (Breaking Changes):** `sdn:stats:flowcount`가 1초마다 온다 (구독자는 추론 워커뿐). `CriteriaConfig`의 `scan_window` · `scan_long_window` · `watch_clear_intervals` · `learn_resume_intervals` · `ewma_alpha` · `relearn_alpha`가 초 단위 이름으로 바뀜
* **결과:** 1초 단위 정상 10분으로 숫자를 다시 확인(SYN 차이 최소값 20, 서비스 지연 12ms, SYN 누적 H 50, 평소값 다시 학습). 방어를 켠 공격 14종: 강한 Flood 1.8~2.5초, 약한 Flood 2.4~2.6초, 스캔 1.7~2.4초 (전에는 3.5~4.4초), 정상 5분 경보 0회. 명세 §2.7
* **다음 작업자 인수인계 메모:** 발표 자료의 "2초마다" · 탐지 지연 "약 4초"는 1초 · 약 2초로 바뀌었습니다


### [2026-10-28] feat(ryu,model,api,ui): 서비스 악화 조건 · Slow HTTP · 내부 확산 · 특수 상황 재학습 승인
* **작업자:** 김관우 (PM & Tech Writer) with Claude Code
* **작업 유형:** `Feature` / `Test` / `Docs`
* **주요 변경 파일:**
  - `ryu/app/controller.py`: **서비스 상태 확인** — 정상 사용자 자리(S1)에서 보호 서버로 0.2초마다 ICMP echo(가상 출발지 10.0.0.250, 컨트롤러가 ARP 대답)를 넣고, 2초마다 손실 · 왕복 시간을 `sdn:health:service`로 발행. **내부 확산** — Proxy ARP에서 접속 호스트가 물어본 없는 내부 주소를 세어 `arp_fail`로 함께 발행. 경고 단계 속도 제한에 Slow HTTP · 내부 확산(SYN) 추가
  - `pipeline/server_conn_agent.py` (신규): 서버의 열린 HTTP 연결을 `ss`로 2초마다 읽어 접속 PC별 느린 요청 수를 `sdn:stats:serverconn`으로 발행 (20초 넘게 요청이 안 끝나고 응답 전, 초당 500B 미만. Apache mod_reqtimeout과 같은 기준)
  - `model/criteria_engine.py`: 위험 = 공격 확정 + (판정선 5배 이상 **또는 서비스 악화 2회 연속**: 손실 25% · 평균 왕복 10ms, 정상 10분 최대의 2배). Slow HTTP(느린 요청 10개), 내부 확산(5분 25개, Zeek), 스캔 실패 응답은 보낸 연결 시도의 2배까지만 셈, 승인된 재학습(양만 · 위험 크기 제외 · 기간 뒤 복귀)
  - `model/inference_worker.py`: 서비스 상태 · 서버 연결 · RELEARN 명령 구독
  - `harness/contracts/sdn_events.py`: `ServiceHealthMessage`, `ServerConnMessage`, `ACCESS_HOST_PORTS`, `ThreatType.INTERNAL_SPREAD`, `CountKind.ARP_FAIL`, `DefenseAction.RELEARN`, `ControlCommandMessage.duration_sec`(선택)
  - `api/main.py`, `api/manual_control.py`: `POST /api/control/relearn` (기간 1~240분, 사유, 관리자 토큰)
  - `ui/src/components/RelearnControl.jsx` (신규), `ui/src/App.jsx`, `ui/src/lib/api.js`, `ui/src/lib/towerState.js`: 관제탑 "특수 상황 재학습" 승인 버튼 · 창
  - `traffic/traffic_slowhttp.py`, `traffic/traffic_spread.py` (신규): Slowloris 방식 Slow HTTP, 내부 확산(445 포트)
  - `harness/verification/criteria_measure.py`: 서비스 상태 · 서버 연결 기록, 시나리오 추가(중간 ICMP, 서버 장애 + 약한 UDP, Slow HTTP 30 · 150개, 내부 확산), 마지막 공격 뒤에도 쉬는 구간
  - `docs/specs/attack_criteria.md`: 새 기준과 숫자, 검증 결과, 한계
* **영향 범위 및 주의사항 (Breaking Changes):** 없음 (새 채널 · 필드는 추가만). 컨트롤러가 S1에 초당 5개의 확인 ping을 넣는다
* **다음 작업자 인수인계 메모:**
  - **[박시현]** 컨트롤러에 `_probe_loop`(서비스 상태 확인)와 `arp_fail_targets`(내부 확산)가 생겼습니다. 가상 주소 10.0.0.250은 실제 호스트에 쓰면 안 됩니다.
  - **[유재민]** Slow HTTP를 쓰려면 서버에서 `python -m pipeline.server_conn_agent`를 같이 띄워야 합니다 (테스트베드는 `criteria_measure`가 자동으로 띄움).

### [2026-10-28] feat(ryu,model): 8주차 공격 · 정상 판단 기준 구현, 기준 숫자 실측
* **작업자:** 김관우 (PM & Tech Writer) with Claude Code
* **작업 유형:** `Feature` / `Test` / `Docs`
* **주요 변경 파일:**
  - `ryu/app/controller.py`: 파이프라인을 3단 테이블로 변경 (0 = 종류별로 세는 규칙, 1 = 경고 단계 속도 제한, 2 = 기존 전달 · 격리 · 우회). 접속 호스트마다 SYN · FIN · RST · UDP · ICMP · 받은 RST · 받은 도달 불가를 세고 2초마다 `sdn:stats:flowcount`로 발행. 경고(WARNING) 경보는 그 포트의 그 공격 종류 패킷만 미터로 초당 50개 제한, 10초 동안 경보가 없으면 해제. 위험(DANGER)은 기존 격리 + 우회
  - `harness/contracts/sdn_events.py`: `FlowCountMessage`, `RiskStage`, `AnomalyAlertMessage.stage`(기본값 DANGER라 기존 송신자 호환), `DefenseAction.RATE_LIMIT/UNLIMIT`, `WARNING_RATE_LIMIT_PPS = 50`, `WARNING_HOLD_SEC = 10`
  - `model/criteria_engine.py` (신규): 기준표 판단 엔진. 기준선 = max(평균 + 3σ, 최소값), SYN Flood = SYN − (FIN+RST) 누적(CUSUM), UDP · ICMP Flood = 평소의 10배 + 초당 50개, 포트 스캔 = 받은 실패 응답(4초 15개 · 5분 30개 · 도달 불가 4개), 2회 연속 확정, 판정선의 5배 이상이면 위험. 평소값은 사전 학습 파일로 시작해 EWMA(약 10분)로 갱신, 사전 학습값 ~ 2배로 제한
  - `model/criteria_baseline.json` (신규): 정상 10분 실측으로 학습한 포트 · 지표별 평소값
  - `model/inference_worker.py`: 기준표 모드가 기본 (`--legacy`로 기존 AI 점수 판단). 경보에 단계 · 공격 종류 · 이유를 담고, AI 점수는 metadata에 참고로만 남김. `--learn 초`로 평소값 학습
  - `traffic/normal_user.py`, `traffic/traffic_flood.py`, `traffic/traffic_scan.py` (신규): 정상 사용자 시나리오 5종 + 닫힌 포트 실수, UDP · ICMP Flood, TCP · UDP 포트 스캔
  - `harness/verification/criteria_measure.py` (신규): 정상 10분 + 공격 9종 측정, 평소값 파일 생성, 방어를 켠 검증 리포트
  - `docs/specs/attack_criteria.md` (신규): 세는 규칙, 실측 평소값, 숫자를 정한 방법(정상 최대의 2배 여유), 단계별 대응, 검증 결과
  - `tests/ryu/test_count_and_warning.py`, `tests/model/test_criteria_engine.py`, `tests/harness/test_criteria_measure.py`, `tests/model/test_inference_worker.py`: 회귀 테스트
* **영향 범위 및 주의사항 (Breaking Changes):** 컨트롤러의 전달 · 격리 · 우회 규칙이 2번 테이블로 옮겨짐 (`add_flow` 기본 `table_id=2`). 기존 경보 송신자(`stage` 없음)는 그대로 위험 단계로 처리됨. 추론 워커 기본 동작이 기준표 판단으로 바뀜 (기존 방식은 `--legacy`)
* **다음 작업자 인수인계 메모:**
  - **[박시현]** 컨트롤러에 0 · 1번 테이블이 생겼습니다. 새 전달 규칙은 `add_flow`가 2번 테이블에 넣고, 세는 규칙은 쿠키(`0xC0DE…`)로 구분합니다.
  - **[유재민]** 판단 숫자는 `CriteriaConfig` 한 곳에 있고, 근거는 `docs/specs/attack_criteria.md` §2입니다. 평소값을 다시 학습하려면 `python -m model.inference_worker --learn 600`.
  - Slow HTTP · 내부 확산 · 서비스 상태 신호 · 특수 상황 재학습 승인은 바로 위 항목에서 추가했습니다.

### [2026-10-28] chore: 저장소 전체 mypy/flake8 정리 및 GitHub 브랜치 정리
* **작업자:** 유재민 (Domain Dev & QA) with Claude Code
* **작업 유형:** `Chore` / `Docs`
* **배경:** "깃허브에 있는 코드를 전체적으로 깔끔하게 정리해달라"는 요청으로 저장소 전체(팀원 파일 포함) 범위의 린트/타입/브랜치 정리를 수행.
* **주요 변경 파일:**
  - `traffic/traffic_normal.py`: scapy `Packet.__truediv__`가 `Self` 타입을 속성 할당(`__truediv__ = __div__`)으로 노출해 mypy가 `IP(...) / TCP(...) / bytes(...)` 2단 체이닝을 못 풀어내는 것을 최소 재현 스크립트로 확인 후, 기존 `# type: ignore[no-redef]` 관례와 동일하게 `# type: ignore[operator]`로 처리(런타임/테스트 영향 없음).
  - `ryu/app/controller.py`: `RerouteEngine` 3단 fallback import의 mypy no-redef 경고를 동일 관례로 처리.
  - `README.md`: 디렉터리 구조 설명에 누락됐던 `traffic/traffic_scan.py` 추가.
* **보고만 하고 수정하지 않은 것:** `ryu/app/controller.py`의 `TopologyNode`/`TopologyLink` 호출부 mypy call-arg 12건은 이 샌드박스의 pydantic==2.14.1(프로젝트 고정 2.6.1과 다름) 버전 불일치로 인한 오탐임을 최소 pydantic 모델로 재현해 확인. 실제 결함이 아니므로 손대지 않음 — 팀의 실제 핀 고정 환경(uv.lock)에서 CI 돌릴 때 재현되는지 확인 권장.
* **GitHub 브랜치 정리 (코드 아님, 커밋 손실 없음):**
  - main에 이미 merge된 9개 브랜치 삭제: `docs/reorganize-workspace`, `feat/week6-telemetry-pipeline`, `feature/multi-attack-type-defense`, `feature/yoo-jaemin-weeks-7-16`, `fix/harness-topo-lint-mypy`, `fix/topology-bypass-path-visibility`, `integration/week16-final`, `park16week`, `week4-integration`.
  - `fix/protected-host-isolation-guard`, `fix/yoo-jaemin-counter-overflow-guard`(유재민, 2026-10-12, merge 안 됨): 실제 diff를 떠보니 두 브랜치가 고치려던 내용이 2026-10-12 `fix(all)` 일괄 정렬 때 이미 main에 반영되어 있어(로직 동일, 공백/주석 차이만 있음) 삭제.
  - `claude/auto-blog-writer-1qwmon`: 이 프로젝트와 무관한 Naver 블로그 자동 작성 봇(Flask 대시보드)이 실수로 이 저장소에 커밋된 것으로 판단, 팀원 확인 후 삭제.
  - 남긴 것: `main`, `claude/quirky-cerf-h51gg3`(진행 중인 작업으로 보여 유지).
* **영향 범위 및 주의사항 (Breaking Changes):** 없음.
* **검증:** `flake8` 0건, `mypy` 신규 에러 없음(기존 pydantic 버전 불일치 오탐 12건 제외), `pytest` 207 passed.
* **다음 작업자 인수인계 메모:**
  - **[공통]** 브랜치 목록이 `main`/`claude/quirky-cerf-h51gg3`로 정리됐습니다. 이후 작업은 바로 main에서 새 브랜치를 따서 PR로 merge하는 흐름을 유지해주세요.

### [2026-10-28] fix(model): PORT_SCAN·SLOW_DRIFT 판정 신호를 실제 작동 가능한 신호로 교체
* **작업자:** 유재민 (Domain Dev & QA) with Claude Code
* **작업 유형:** `Fix` / `Test`
* **배경:** 2026-10-14 `feature/multi-attack-type-defense`에서 추가한 PORT_SCAN(`err_rate`=`rx_errors` 임계치)과 SLOW_DRIFT(`duration_sec` EWMA 추세)가 재검토 결과 실제 Mininet/OVS 트래픽에서는 작동할 수 없는 신호였음을 발견. `rx_errors`는 물리/링크 계층 수신 오류 카운터라 체크섬이 정상인 TCP RST(닫힌 포트 응답)에는 전혀 반응하지 않고, 이 프로젝트 공격 트래픽은 `checksum_utils.py`로 체크섬을 일부러 정상화해서 보내므로 코드베이스 안 어떤 트래픽도 `rx_errors`를 움직이지 못함. `duration_sec`은 포트 가동 시간(업타임)일 뿐 트래픽과 무관하게 항상 같은 속도로 흘러가 "공격 추세"를 전혀 반영하지 않음.
* **주요 변경 파일:**
  - `model/attack_classifier.py`: `SecondaryAttackClassifier`를 재작성 — 플러드 임계치(`MIN_ATTACK_PPS`=100 PPS) 미달이면서 BPP가 작은(`BPP_ATTACK_MAX` 이하) 트래픽이 `delta_pps`의 EWMA 기준선보다 **증가** 방향으로 벗어날 때만 의심으로 본다(둘 다 실제 OVS 포트 통계에서 관측 가능). 포트 통계만으로는 "포트 스캔"과 "Slow DDoS 전조"를 구조적으로 구분할 수 없으므로, 지속 시간(`SUSTAINED_TICKS_FOR_SLOW_DDOS`=10틱≈20초)으로 나눈다: 짧으면 PORT_SCAN, 오래 계속되면 SLOW_DRIFT로 승격.
  - `tests/model/test_attack_classifier.py`, `tests/model/test_inference_worker.py`: 새 신호 기준으로 전면 재작성 (err_rate 기반 `ErrorCounters` 테스트 제거, 소형 패킷 서브플러드 버스트/승격 테스트로 교체).
  - `traffic/traffic_scan.py` (신규), `tests/traffic/test_traffic_scan.py` (신규): 새 탐지 신호를 실제 Mininet 패킷(출발지 IP 스푸핑 없음, 플러드 임계치 미달 PPS로 목적지 포트 순환 SYN)으로 검증·시연할 생성기. `--duration`을 짧게/길게 주면 각각 포트 스캔/Slow DDoS 데모가 된다.
  - `model/inference_worker.py`: 문서만 보강 — `pipeline/feature_extractor.py`에 이미 Redis 실시간 캡처 CLI(`--label 0/1`)가 있다는 안내 추가(중복 기능 만들지 않음).
* **발견한 설계 결함 (자체 코드, 즉시 수정):** 위 배경 2건. 유닛 테스트에서만 통과하고 실제 환경에서는 영원히 발동하지 않는 신호였음 — 합성 피처 딕셔너리로만 테스트하면 이런 함정을 못 거른다는 교훈.
* **영향 범위 및 주의사항 (Breaking Changes):** 없음. `AttackCategory`/`ThreatType.PORT_SCAN`/`ThreatType.SLOW_DDOS` 등 외부 인터페이스는 그대로, 내부 판정 로직만 교체. `model/inference_worker.py`의 `SecondaryAttackClassifier` 생성 코드도 무변경(인터페이스 동일).
* **검증:** 신규/변경 테스트 전부 통과, `tests/` 전체(api·benchmarks 포함) 회귀 통과, flake8/mypy 0건.
* **다음 작업자 인수인계 메모:**
  - **[공통]** `docs/writing/reports/verification/multi_attack_type_defense_v2_fix_report.md`에 상세 재설계 배경과 재검증 결과 정리.
  - **[유재민]** 실데이터 F1 측정(2026-10-11 인수인계 메모)은 캡처 도구(`pipeline/feature_extractor.py --label`)가 이미 있으므로, GCP Mininet에서 정상/공격 구간을 캡처해 재학습·재측정하는 실행만 남음 (코드 작업 아님).

### [2026-10-14] fix(ui,control): 비상 수동 제어 입력 튐 · 공격 중 복원 무효 수정, BPP 그래프 가시성 개선
* **작업자:** 김관우 (PM & Tech Writer) with Claude Code
* **작업 유형:** `Fix` / `Test` / `Docs`
* **주요 변경 파일:**
  - `ui/src/components/ManualControl.jsx`: 모달의 초기 포커스 effect가 매 렌더마다 새로 만들어지는 `onClose`에 의존해, 2초 통계가 올 때마다 포커스를 '격리' 라디오로 되돌리던 버그 수정 (사유 입력이 끊기고, 띄어쓰기 한 번에 '격리'가 선택되고, 포트 목록이 닫히던 현상). effect는 열릴 때 한 번만 실행하고 컴포넌트를 `memo`로 감쌈. 복원 선택 시 보류 안내, 전송 알림에 보류 시간 표시
  - `ryu/app/controller.py`, `harness/contracts/sdn_events.py`: 수동 RESTORE 후 `MANUAL_RESTORE_HOLD_SEC`(60초) 동안 같은 포트의 AI 경보로 자동 재격리하지 않음 (기존에는 공격 중 복원해도 2초 안에 다음 경보가 다시 격리). 수동 ISOLATE 시 보류 해제, 보류 중 경보는 서킷 브레이커 집계 전에 거름
  - `api/main.py`: 수동 제어 응답에 `auto_isolation_hold_sec` (LIVE 모드 RESTORE = 60, 그 외 0)
  - `ui/src/components/TrafficCharts.jsx`: BPP 축을 0~1500B 고정에서 데이터 기준(최소 160B)으로 변경, 판정선 80B(점선)·판정 구간(음영)·'판정선 이하' 표시 추가. 실측 값(정상 ping 98B, SYN Flood 54B)이 바닥에 붙어 구분되지 않던 문제 해결
  - `tests/ryu/test_controller_logic.py`, `tests/api/test_manual_control.py`, `docs/writing/manual/operator_manual.md`: 보류 동작 회귀 테스트 3건, 응답 필드 검증, 매뉴얼 안내 추가
* **영향 범위 및 주의사항 (Breaking Changes):** 없음. 수동 복원 직후 60초 동안은 공격이 계속돼도 해당 포트가 자동으로 막히지 않음 (운영자가 의도한 동작). 다시 막으려면 수동 격리
* **다음 작업자 인수인계 메모:**
  - **[박시현]** 컨트롤러에 `manual_holds`와 `_manual_hold_active()`가 추가됐습니다. 보류 시간은 `harness/contracts/sdn_events.py`의 `MANUAL_RESTORE_HOLD_SEC` 하나로 관리합니다.

### [2026-10-12] fix(all): 코드·계약·관제탑·안전가드레일 및 전체 산출물 문서 정합성 일괄 정렬
* **작업자:** 박시현 · 유재민 · 김관우 with Antigravity AI Agent
* **작업 유형:** `Fix` / `Refactor` / `Docs` / `Test`
* **주요 변경 파일:**
  - `pipeline/feature_extractor.py`, `tests/pipeline/test_feature_extractor.py`: 유재민 `origin/fix/yoo-jaemin-counter-overflow-guard` 반영 — Mininet 종료 시 언사인드 64비트 래핑(`~9.22e18`) 거대 양수 델타를 원천 차단하는 `MAX_PLAUSIBLE_PACKET_DELTA = 10_000_000`, `MAX_PLAUSIBLE_BYTE_DELTA` 상한 가드 및 회귀 테스트 추가
  - `harness/safety/whitelist_guard.py`, `api/manual_control.py`, `ui/src/components/ManualControl.jsx`, `docs/writing/manual/operator_manual.md`, `tests/harness/test_whitelist_guard.py`, `tests/api/test_manual_control.py`: 유재민 `origin/fix/protected-host-isolation-guard` 반영 및 SSOT·UI·매뉴얼 정합성 통합 — `DEFAULT_PROTECTED_ACCESS_PORTS`(`S1:1` `H_legit`, `S4:1` `H_server`) 격리 차단 가드를 자율·수동 제어 경로와 UI 모달, 운영자 매뉴얼에 일관되게 적용
  - `harness/contracts/sdn_events.py`: `AnomalyAlertMessage.bps` 설명 단위를 `Bits per second rate (ΔBPS)`로 교정, `TopologySyncMessage`에 컨트롤러 방어 단계 전달용 선택적 필드 `phase: Optional[str]` 추가
  - `ryu/app/controller.py`: `_publish_topology_sync` 발행 시 현재 FSM 단계(`phase`) 포함, 자율 방어 감사 이벤트 발행 시 `REROUTE` 우선순위를 실제 OpenFlow 규칙과 동일한 `priority=20`으로 통일
  - `api/redis_bridge.py`, `tests/api/test_redis_bridge.py`: `LivePhaseTracker`가 `TopologySyncMessage.phase`(`COOLDOWN_VERIFY` 등)를 반영하도록 개선하여 실데이터 모드(`SDN_MOCK=0`)에서도 관제 UI 복구 검증 배지·카운트다운·복구 모달이 동작하도록 수정 및 단위 테스트 보강
  - `api/mock_generator.py`: `SCORE_THRESHOLD = 0.0`, `PRIORITY_REROUTE = 20`으로 실제 파이프라인 상수와 일치시키고, 모의 경보 `bps` 계산식에 `× 8`(bits/sec) 적용
  - `scripts/demo_scenario.sh`, `scripts/reset_env.sh`: 시연 안내 문구(`Score < 0.0`, `Priority 100 / Priority 20`), `model.inference_worker` 기동 안내 추가 및 모듈(`-m`) 실행 프로세스 종료 패턴 보완
  - `README.md`, `docs/specs/defense_scenarios.md`, `docs/writing/thesis/thesis_draft.md`, `docs/writing/presentations/final_demo_runbook.md`, `docs/writing/reports/verification/week16_real_components_e2e.md`, `docs/writing/reports/weekly/semester_weekly_report_compilation.md`, `docs/writing/reports/final_review_feedback.md`: 16주차 실제 구성(`IsolationForest` + 컨트롤러 내장 FSM/Reroute + `Priority 100 / 20` + 반응시간 `1.4~2.5ms`) 기준으로 수치·상태·오픈 이슈 전면 갱신
  - `docs/guides/**`, `docs/writing/reports/weekly/week05_*.md`, `week06_*.md`: 디렉토리 구조(`pipeline/`, `tests/model/`, `docs/writing/`), CLI 인자(`--label 0`), 깨진 상대 경로 링크(`../archive/v1_guides/`, `phase2_core_mock_harness.md`) 일괄 수정
* **영향 범위 및 주의사항 (Breaking Changes):** 없음 (`TopologySyncMessage.phase`는 `Optional[str] = None` 기본값을 사용하여 기존 메시지 하위 호환성 100% 유지. 보호 호스트 `S1:1`, `S4:1`은 격리 `ISOLATE`만 차단되며 복원 `RESTORE`는 기존대로 허용).
* **다음 작업자 인수인계 메모:**
  - **[공통]** 유재민 님의 원격 브랜치 2건(`fix/yoo-jaemin-counter-overflow-guard`, `fix/protected-host-isolation-guard`)을 포함한 전 모듈 코드와 공식 문서 간 상수·우선순위·단위·경로 불일치가 모두 해소되었습니다.

### [2026-10-11] feat(model): 김관우 AI 추론 워커 추가 및 실제 구성 E2E 검증
* **작업자:** 김관우 (PM & Tech Writer) with Claude Code
* **작업 유형:** `Feat` / `Test` / `Docs`
* **주요 변경 파일:**
  - `model/inference_worker.py`: (신규) `sdn:stats:port` → FeatureExtractor → AnomalyModel → DetectionGuard → `sdn:anomaly:alert`. 감시 대상은 보호 호스트가 없는 접속 포트(S1:2), 초당 100패킷 미만은 연속 기록을 끊음, 확정 중 매 주기 경보(컨트롤러 FSM 하트비트). 모델 파일이 없으면 `--train-csv` 또는 합성 데이터로 학습 후 저장
  - `tests/model/test_inference_worker.py`: (신규) 2주기 확정, 트렁크 포트 무경보, 단발 스파이크·저속 소형 패킷 무경보
  - `harness/verification/e2e_scenario.py`: 컨트롤러 우회 규칙(Priority 20) 카운터 포함, 실행 시간 필드가 없는 이벤트 로그도 분석
  - `docs/writing/reports/verification/week16_real_components_e2e.md`: (신규) 실제 구성 E2E 3회 보고서 + `data/week16_real_e2e.json`
* **상세 성과 (3회, 임시 구성 없음):** 공격 시작 → 차단 평균 3.35초, 경보 → 컨트롤러 차단·우회 명령 1.4ms, 정상 ping 손실 0 / 4,337, 서버 도달 공격 0, 플래핑 0, 오탐 0, 공격 종료 → 자동 복구 10.87초
* **영향 범위 및 주의사항 (Breaking Changes):** 없음. 기존 인터페이스 그대로 사용.
* **다음 작업자 인수인계 메모:**
  - **[박시현]** MITIGATED 중 반복 경보마다 ISOLATE·REROUTE 기록이 다시 발행됨(공격 20초에 10쌍). 상태 유지 시 기록 생략 검토. 복구 때 우회 규칙(Priority 20)도 같이 지우는 것 검토.
  - **[유재민]** 모델이 합성 데이터로 학습됨. Mininet 정상 트래픽 CSV로 `--train-csv` 학습 후 실데이터 F1 측정 필요.

### [2026-10-10] feat(core): 박시현(Tech Lead) 7~16주차 전담 파트 일괄 개발 완료 (자율 방어/우회/FSM/서킷브레이커/E2E 데모)
* **작업자:** 박시현 (Tech Lead) with Antigravity AI Agent
* **작업 유형:** `Feat` / `Refactor` / `Test` / `Scripts`
* **주요 변경 및 신규 파일:**
  - `harness/safety/whitelist_guard.py`: S1~S4 트렁크 포트 오차단 방지 및 엑세스 포트만 선별 격리하는 안전 가드레일 (9주차)
  - `ryu/app/reroute.py`: NetworkX Dijkstra 기반 다중 홉 최단/우회 경로 계산 및 선제적 `OFPFC_ADD` 프로비저닝 엔진 (10주차)
  - `harness/safety/flapping_fsm.py`: 5단계 상태 전이(Normal ➔ Attack ➔ Mitigated ➔ Cooldown ➔ Normal) 플래핑 방지 및 자가 치유 FSM (11주차)
  - `harness/safety/circuit_breaker.py`: 명령 폭주 및 AI 오작동 시 제어권 차단 긴급 서킷 브레이커 (13주차)
  - `ryu/app/controller.py`: In_port Drop(Priority 100), 다중 홉 우회 주입, FSM 자가 복구, Redis `sdn:control:command` 및 `sdn:anomaly:alert` 비동기 구독 제어 통합
  - `scripts/demo_scenario.sh`, `scripts/reset_env.sh`: 4단계 시나리오 원클릭 실행 데모 러너 및 시스템 초기화 툴 (15~16주차)
  - `tests/harness/test_whitelist_guard.py`, `tests/ryu/test_reroute.py`, `tests/harness/test_flapping_fsm.py`, `tests/harness/test_circuit_breaker.py`, `tests/harness/test_e2e_pipeline.py`, `tests/harness/test_full_scenario.py`: 신규 테스트 20종 추가
* **상세 성과 및 검증 결과:**
  - 전체 단위/통합 테스트: **77 / 77 tests passed (100% Pass, 1.25s)**
  - flake8 (120자 준수) 0건, mypy 타입 체크 0건 완벽 통과
  - 트렁크 포트 오차단율 0%, 우회 시 패킷 드롭 0%, 공격 소멸 후 10초 쿨다운 무개입 자가 치유 라이프사이클 완성.
  - **3인 모듈 통합 정합성 강화 (승인 반영 완료):**
    1. FSM 상태 열거형 호환성: `DefenseState.COOLDOWN_VERIFY` 별칭 추가로 관제탑 UI 배지 연동 100% 호환
    2. 실시간 토폴로지 동기화: 자율 격리(`MITIGATED`), 우회(`REROUTED`), 복구(`NORMAL`) 발생 시 `sdn:topology:sync` 자동 발행 탑재
    3. 감사 명령 로깅: 자율 방어 조치 내역을 `sdn:control:command`로 자동 발행하여 웹 대시보드 이벤트 타임라인에 실시간 카드 기록
    4. Eventlet 루프 최적화: Redis 리스너 루프 폴링 주기를 `timeout=0.1`, `hub.sleep(0.05)`로 미세 튜닝하여 비차단 코루틴 협력적 스케줄링 보장
* **다음 작업자 인수인계 메모:**
  - **유재민 (Domain Dev & QA):** Ryu 컨트롤러가 Redis `sdn:anomaly:alert`를 수신하여 자율 차단 및 우회를 완벽히 수행하므로, 7주차 Isolation Forest 모델 훈련 및 `inference_worker.py`와의 연동 파이프라인 개발에 집중 가능.
  - **김관우 (PM & Tech Writer):** 4단계 방어 및 자가 복구 라이프사이클과 실시간 토폴로지 동기화(`sdn:topology:sync`), 감사 이벤트 피드 연동이 완성되었으므로 웹 UI 데모 연동 및 최종 논문/발표 보고서 작성에 즉시 활용 가능.

### [2026-10-07] docs: 김관우 16주차 주간 보고서 합본, 논문 결론 장, 심사 피드백 정리서
* **작업자:** 김관우 (PM & Tech Writer) with Claude Code
* **작업 유형:** `Docs`
* **주요 변경 파일:**
  - `docs/writing/reports/weekly/semester_weekly_report_compilation.md`: (신규) 1~16주차 합본 — 학기 요약, 주차별 한눈표, 주차별 팀원 보고, 산출물 목록
  - `docs/writing/reports/final_review_feedback.md`: (신규) 심사 당일 기록 · 질의응답 · 피드백 양식, 방학 개선 과제 9건 사전 도출
  - `docs/writing/thesis/thesis_draft.md`: 지도교수 기입, 초록 복구 방식(타임아웃 → 10초 쿨다운 검증)과 실측 수치 반영, 6장 결론 · 한계 · 향후 과제 작성
  - `docs/writing/presentations/final_demo_runbook.md`: §8 심사 당일 진행 · 역할 분담
* **영향 범위 및 주의사항 (Breaking Changes):** 없음.
* **다음 작업자 인수인계 메모:**
  - **[박시현 · 유재민]** 합본의 7~15주차 `진행중` 항목은 저장소 기준. 각자 결과가 반영되면 합본 해당 칸과 결과 수치를 갱신해 주세요.
  - **[박시현]** 논문 초록 · 4.3절은 "Dijkstra 기반 우회"라고 쓰지만 현재 검증은 고정 우회 경로(S1→S3→S4) 기준. 경로 계산 엔진이 들어오면 그대로, 아니면 문구 조정 필요.
  - **[유재민]** 논문 5.4 표의 F1 · 추론 지연 `[ ]` 칸.

### [2026-10-07] docs: 김관우 15주차 최종 발표 10장 덱, 시연 진행표 · 리허설 기록지
* **작업자:** 김관우 (PM & Tech Writer) with Claude Code
* **작업 유형:** `Docs`
* **주요 변경 파일:**
  - `docs/writing/presentations/final_demo_runbook.md`: (신규) 발표 시간 배분, 시연 전 준비 9항목, 4단계 시연 조작 · 대사, 장애 대응, 백업 영상 녹화 기준, 리허설 3회 기록표, 예상 질문 7개
  - 최종 발표 10장 슬라이드 (팀 슬라이드 링크로 공유): 9~14주차 실측 수치(규칙 증가 0, 전환 손실 0 / 4,000, 플래핑 7 → 0, 60fps, 78.4ms, 손실 0%) 반영
* **영향 범위 및 주의사항 (Breaking Changes):** 없음.
* **다음 작업자 인수인계 메모:**
  - **[유재민]** 백업 시연 영상 녹화 (진행표 §5 기준). 실제 AI 모델이 연동되면 성능 슬라이드 수치를 재측정값으로 교체.
  - **[박시현]** 시연 실행 순서(진행표 §2)가 컨트롤러 실행 방식과 맞는지 확인. 명세 Q5 결정되면 5번 슬라이드 "검토중" 문구 갱신.
  - 표지의 지도교수명 · 발표일은 비워 둠.

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
