# Phase 6-C-4: 8-스위치 표준 운영 안정화 및 도구 정합성 확보 상세 구현 계획서

## 1. 개요 및 배경 (Executive Summary)

본 문서는 **종합 로드맵([ROADMAP.md](file:///home/tlgus/programming/Self_Defending_SDN_Tower/docs/planning/ROADMAP.md))의 Phase 6-C-4**에 명시된 **"8-스위치 표준 운영 안정화 및 도구 정합성 확보"**의 상세 엔지니어링 구현 계획서입니다.

### 1.1 현재 상황 재인지 및 방향성 정립
1. **4-스위치 다이아몬드 토폴로지 완전 퇴역**:
   * 구형 4-스위치는 이미 아카이브(`archive/`)되었으며, 현재 프로덕션 및 실운영 인프라는 **오직 8-스위치 5-Zone 엔터프라이즈 토폴로지 단 하나로만 동작**합니다.
   * 불필요한 4-스위치 하위 호환성이나 중복 분기를 제거하고, 모든 도구를 **현재 8-스위치 단일 표준에 맞추어 깔끔하게 정규화**합니다.
2. **경량 런타임 격리 배포 체계 가동 중**:
   * Phase 6-C-3를 통해 문서(`docs/`), 테스트(`tests/`), 개발 설정(`rules/`), Git 메타데이터(`.git/`)가 100% 격리된 초경량(877 KB) 런타임 디렉토리(`/home/tlgus1841/sdn-tower-runtime`)가 VM에 배포되었습니다.
3. **Phase 6-C-4의 유일한 목표**:
   * 현재 가동 중인 8-스위치 런타임 환경에서 **오류가 발생하는 레거시 도구 3종(`native_attack.sh`, `demo_scenario.sh`, `vm_demo_controller.sh`)과 AI 기준선 데이터 1건(`criteria_baseline.json`)을 정규화하여 시스템 안정성을 100% 확보**하는 것입니다.
   * (※ 6종 공격 정밀 측정 및 학술 지표 리포트 작성은 차기 단계인 **Phase 6-C-6**에서 전담 수행하므로 본 계획에서 과감히 분리 배제합니다.)

---

## 2. 4대 안정화 대상 및 정합성 매트릭스

| 대상 파일 | 현재 문제점 (오류 원인) | 8-스위치 표준 정규화 방안 |
| :--- | :--- | :--- |
| **`scripts/native_attack.sh`** | • 미존재 네임스페이스 `ns_attacker` 호출로 즉시 실패<br>• 목적지가 구형 `10.0.0.4`로 고정 | • 기본 발신지: `ns_h2` (User Zone A PC 2)<br>• 기본 목적지: `10.0.0.11` (Server Zone A Nginx Web)<br>• 인자 지원: `--src <NS>`, `--dst <IP>`, `--type <TYPE>`<br>• 6종 공격(SYN, UDP, ICMP, Scan, SlowHTTP, Spread) 즉각 발동 |
| **`scripts/demo_scenario.sh`** | • 과거 4-스위치 다이아몬드 ASCII 및 레거시 IP 출력 | • 8-스위치 5-Zone 구조 및 S1-S2 듀얼 코어 백본 안내 최신화 |
| **`scripts/vm_demo_controller.sh`** | • 구 디렉토리 `~/sdn-tower`를 SSH로 접근<br>• 구 핑 로그 `/tmp/h_legit_ping.log` 조회 | • 신규 격리 런타임 `~/sdn-tower-runtime` 기준 실행<br>• 신규 정상 핑 로그 `/tmp/h1_ping.log` 자동 연동<br>• Docker Compose 프로젝트명 `-p sdn-tower` 적용 |
| **`model/criteria_baseline.json`** | • 구형 포트(`1:1`, `1:2`, `4:1`) 3개만 존재<br>• 8-스위치 포트 인입 시 미등록 fallback 처리 | • 8-스위치 10개 핵심 액세스 포트(`3:1`, `3:2`, `4:1`, `4:2`, `5:1`, `5:2`, `6:1`, `6:2`, `7:1`, `7:2`) 통계치 정식 등록 |

---

## 3. 4단계 세부 구현 마일스톤 (Milestones M1 ~ M4)

### 📌 Milestone M1: 트래픽 주입 도구(`scripts/native_attack.sh`) 8-스위치 표준화
- **작업 내용**:
  - `ns_attacker` 참조를 제거하고, 현재 표준 공격 발신지인 `ns_h2`(또는 `ns_h4`)를 기본값으로 지정.
  - 기본 공격 대상을 현재 표준 웹서버인 `10.0.0.11`(`ns_h5`)로 표준화.
  - 6종 공격 스크립트(`traffic/traffic_attack.py`, `traffic_scan.py`, `traffic_flood.py`, `traffic_slowhttp.py`, `traffic_spread.py`)가 8-스위치 파라미터로 즉각 실행되도록 검증.

---

### 📌 Milestone M2: 데모 시나리오(`demo_scenario.sh`) 및 원격 컨트롤러(`vm_demo_controller.sh`) 최신화
- **작업 내용**:
  - `scripts/demo_scenario.sh`의 아키텍처 다이어그램을 8-스위치 5-Zone 엔터프라이즈 구조로 전면 갱신.
  - `scripts/vm_demo_controller.sh` 내의 모든 작업 디렉토리를 `/home/tlgus1841/sdn-tower-runtime`으로 일원화.
  - `ping-status` 조회 대상을 `/tmp/h1_ping.log`로 갱신하여 현재 실시간 정상 사용자 통신 상태가 즉각 출력되도록 개선.

---

### 📌 Milestone M3: AI 이상치 탐지 기준선(`model/criteria_baseline.json`) 10개 포트 동기화
- **작업 내용**:
  - 8-스위치 5-Zone의 10개 핵심 액세스 포트(`3:1`, `3:2`, `4:1`, `4:2`, `5:1`, `5:2`, `6:1`, `6:2`, `7:1`, `7:2`)에 대한 통계 평균(mean) 및 표준편차(std)를 사전에 정밀 계산하여 등록.
  - AI Criteria Engine이 8-스위치 전 구역의 트래픽을 감시할 때 누락이나 오탐 없이 기준치를 비교할 수 있도록 SSOT 완성.

---

### 📌 Milestone M4: 단위 테스트 작성, 로컬 회귀 검증 및 원격 런타임 배포
- **작업 내용**:
  - `tests/scripts/test_script_stabilization.py`를 신설하여 스크립트 표준화 및 문법 무결성 검증.
  - 로컬 pytest 전체 스위트(294개 이상) 100% 통과 유지.
  - `./scripts/deploy_remote.sh`를 실행하여 VM의 `~/sdn-tower-runtime`으로 즉각 배포 및 실환경 공격 주입 동작 검증.

---

## 4. 검증 기준 및 완료 정의 (Definition of Done)

| 번호 | 검증 항목 | 검증 방법 및 합격 기준 |
| :---: | :--- | :--- |
| **DoD-1** | **공격 도구 오류 해소** | `sudo ./scripts/native_attack.sh syn 5 200` 실행 시 `ns_attacker` 오류 없이 `ns_h2` ➔ `ns_h5`로 공격 패킷이 정상 전송되어야 함 |
| **DoD-2** | **원격 데모 제어 무결성** | `./scripts/vm_demo_controller.sh attack syn` 실행 시 VM `~/sdn-tower-runtime` 상에서 원격 공격이 에러 없이 즉시 발동되어야 함 |
| **DoD-3** | **AI 포트 기준선 완비** | `model/criteria_baseline.json` 내 8-스위치 10개 핵심 포트(`3:1`~`8:1`)가 정의되어 있어야 함 |
| **DoD-4** | **회귀 테스트 100% 통과** | 신규 작성된 안정화 테스트를 포함하여 전체 pytest 스위트가 에러 없이 All-Pass 되어야 함 |

---

## 5. 단계별 실행 일정 (Timeline)

| 마일스톤 | 작업 내용 | 예상 소요 시간 | 상태 |
| :--- | :--- | :---: | :---: |
| **M1** | 트래픽 주입 도구(`scripts/native_attack.sh`) 8-스위치 표준화 | 0.5시간 | **완료 (Verified)** |
| **M2** | 데모 시나리오 및 원격 컨트롤러(`vm_demo_controller.sh`) 최신화 | 0.5시간 | **완료 (Verified)** |
| **M3** | AI 이상치 탐지 기준선(`model/criteria_baseline.json`) 10개 포트 동기화 | 0.5시간 | **완료 (Verified)** |
| **M4** | 단위 테스트 작성, 전체 회귀 검증 및 원격 배포 실증 | 0.5시간 | **완료 (Verified)** |
| **합계** | **Phase 6-C-4 전체 완료** | **약 2.0시간** | **완료 (Verified)** |
