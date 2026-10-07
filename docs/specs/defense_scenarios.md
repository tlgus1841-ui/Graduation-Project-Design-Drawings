# 🛡️ 4단계 자율 방어 시나리오 명세서 (Defense Scenario Specification)
> **작성자:** 김관우 (22102237 / PM & Tech Writer, 팀장)
> **해당 주차:** 4주차 (2026.09.21 ~ 2026.09.27) — Phase 2 산출물
> **문서 상태:** v1.0 초안 (박시현·유재민 검토 후 확정)
> **상위 근거 문서:** [`roadmap_v2.md`](../planning/roadmap_v2.md), [`ai_harness_engineering_plan.md`](../planning/ai_harness_engineering_plan.md), [`contract_first_ipc_guide.md`](../guides/00_common/contract_first_ipc_guide.md), [`phase2_defense_scenario_web_spec.md`](../guides/dev_c_pm_writer/phase2_defense_scenario_web_spec.md)
> **계약 스키마(SSOT):** [`harness/contracts/sdn_events.py`](../../harness/contracts/sdn_events.py)

---

## 0. 문서 목적 및 적용 범위

본 문서는 Ryu 컨트롤러(박시현), AI Worker(유재민), FastAPI/웹 관제탑(김관우)이 **동일한 상태 정의·전이 조건·임계치**를 기준으로 개발하도록 하는 단일 기준 문서이다.

- 모든 수치는 **§6 파라미터 표**에 모아 관리한다. 코드에서 매직넘버로 쓰지 말고 이 표의 이름을 상수명으로 사용한다.
- `확정` 표기는 기존 기획 문서에 근거가 있는 값, `제안` 표기는 본 문서에서 처음 제시하는 값이며 담당자 검토 후 확정한다.
- 4주차 FastAPI 더미 송출기(`api/mock_generator.py`)는 본 명세의 상태 흐름을 그대로 재생한다.

---

## 1. 기준 토폴로지 (Diamond, `topo/diamond_topo.py`)

```
                          p1 ┌──────────────┐ p2
                  ┌──────────┤ S2 (Primary) ├──────────┐
                  │ p3       └──────────────┘       p2 │
 H_legit ──── p1 ┌┴───────────┐               ┌───────┴────┐ p1 ──── H_server
 (10.0.0.1)      │ S1 Ingress │               │ S4 Egress  │         (10.0.0.4)
 H_attacker ─ p2 └┬───────────┘               └───────┬────┘
 (10.0.0.2)       │ p4       ┌──────────────┐       p3 │
                  └──────────┤ S3 (Bypass)  ├──────────┘
                          p1 └──────────────┘ p2
```

| 구분 | 스위치:포트 | 연결 대상 | 역할 | 격리 가능 여부 |
|:---:|:---:|:---|:---|:---:|
| Access | S1:1 | H_legit | 정상 사용자 유입 | 가능 |
| Access | S1:2 | H_attacker | 공격자 유입 (시연 대상) | 가능 |
| Trunk | S1:3 ↔ S2:1 | S1-S2 | 기본 경로 | **불가 (화이트리스트)** |
| Trunk | S1:4 ↔ S3:1 | S1-S3 | 우회 경로 | **불가 (화이트리스트)** |
| Trunk | S2:2 ↔ S4:2 | S2-S4 | 기본 경로 | **불가 (화이트리스트)** |
| Trunk | S3:2 ↔ S4:3 | S3-S4 | 우회 경로 | **불가 (화이트리스트)** |
| Access | S4:1 | H_server | 보호 대상 서버 | 가능 (단, 자동 격리 대상 아님) |

- **기본 경로(Primary):** S1 → S2 → S4
- **우회 경로(Bypass):** S1 → S3 → S4

---

## 2. 상태 머신 (FSM) 개요

`ai_harness_engineering_plan.md`의 FSM(`NORMAL → ATTACK_DETECTED → MITIGATED → COOLDOWN_VERIFY → NORMAL`)에 시스템 기동 직후의 보정 구간(`CALIBRATING`)을 더한 5개 상태로 정의한다. 4단계 시나리오와의 대응은 아래와 같다.

| 시나리오 단계 | FSM 상태 | 관제탑 상태 배지 |
|:---:|:---|:---|
| (기동) | `CALIBRATING` | `SYSTEM CALIBRATING` (황색) |
| 1단계: 정상 | `NORMAL` | `NORMAL` (녹색) |
| 2단계: 공격 탐지 | `ATTACK_DETECTED` | `UNDER ATTACK` (적색 점멸) |
| 3단계: 격리/우회 | `MITIGATED` | `MITIGATED` (청색) |
| 4단계: 복구 검증 | `COOLDOWN_VERIFY` | `RESTORING` (청록색) |

```
            (15초 경과)
 CALIBRATING ──────────▶ NORMAL ◀──────────────────────────────┐
                           │                                    │
                           │ T1: 이상 스코어 연속 초과          │ T5: 쿨다운 10초 동안
                           ▼                                    │     정상 판정 유지
                     ATTACK_DETECTED                            │     → RESTORE
                           │                                    │
                           │ T2: 화이트리스트 통과 → ISOLATE     │
                           │     + REROUTE 설치 완료            │
                           ▼                                    │
                       MITIGATED ──────── T3: 공격 소멸 ──▶ COOLDOWN_VERIFY
                           ▲                                    │
                           └──────── T4: 쿨다운 중 재공격 ───────┘
                                      (차단/우회 유지, 타이머 리셋)
```

> **플래핑 방지 핵심:** 차단·우회 플로우는 타임아웃으로 자동 만료시키지 않는다(`hard_timeout=0`, `idle_timeout=0`). 해제는 오직 T5(쿨다운 검증 통과) 후 명시적 `RESTORE` 명령으로만 수행한다.

---

## 3. 단계별 상세 명세

### 3.0 기동 보정 구간 — `CALIBRATING`
| 항목 | 내용 |
|:---|:---|
| 진입 조건 | 시스템(AI Worker) 기동 직후 |
| 지속 시간 | `CALIBRATION_SEC` = 15초 `확정` |
| 동작 | 포트 통계 수집만 수행, 이상 탐지 결과가 나와도 **차단 명령 발행 금지** |
| 관제탑 | 상단 배지 `SYSTEM CALIBRATING`, 토폴로지 전체 회색 톤 |
| 종료 조건 | 15초 경과 → `NORMAL` |

### 3.1 1단계: 정상 상태 — `NORMAL`
| 항목 | 내용 |
|:---|:---|
| 트래픽 | H_legit(10.0.0.1) → H_server(10.0.0.4) HTTP/Ping (`traffic_normal.py`, HTTP 70% / Bulk 20% / ICMP 10%) |
| 활성 경로 | S1 → S2 → S4, 기본 플로우 `Priority 10` |
| 정상 지표 범위 | PPS 10~100, BPP 약 500~1,400B |
| Ryu | 2초 주기 `OFPPortStatsRequest` → `sdn:stats:port` 발행 |
| AI Worker | 매 주기 스코어 계산, 경보 없음 |
| 관제탑 | 모든 노드·링크 녹색, 우회 링크(S1-S3, S3-S4)는 대기(점선) |

### 3.2 2단계: 공격 탐지 — `ATTACK_DETECTED`
| 항목 | 내용 |
|:---|:---|
| 트래픽 | H_attacker(10.0.0.2) → H_server, 무작위 출발지 IP SYN Flood (`traffic_attack.py`) |
| 공격 강도 | `ATTACK_PPS` 3,000 PPS (시험 범위 1,000~5,000) `확정`, 패킷 크기 54~74B `확정` |
| 탐지 지표 | S1:2 BPP ≤ `BPP_ATTACK_MAX`(80B) **그리고** Isolation Forest 스코어 < `SCORE_THRESHOLD`(-0.5) `확정` |
| 전이 조건 T1 | 위 조건이 `DETECT_CONSECUTIVE`(2) 주기 연속 충족 `제안` — 단일 스파이크 오탐(Flash Crowd) 방지 |
| 발행 메시지 | AI Worker → `sdn:anomaly:alert` (`AnomalyAlertMessage`, `threat_type=SYN_FLOOD_SPOOFING`) |
| 관제탑 | S1 노드·S1:2 링크 적색 점멸, 경보 피드에 팝업 1건 추가, 배지 `UNDER ATTACK` |

### 3.3 3단계: 자율 차단 및 우회 — `MITIGATED`
| 항목 | 내용 |
|:---|:---|
| 선행 검증 | **화이트리스트 가드:** `target_port`가 §1의 Trunk 포트이면 명령 폐기 + 경고 로그 |
| 차단 동작 | `ISOLATE`: S1에 `match(in_port=2) → drop`, `Priority 100` `확정` ⚠ 14주차 E2E에서 우회 규칙과 우선순위가 같아 차단이 무력화됨 → Q5 |
| 우회 동작 | `REROUTE`: H_legit ↔ H_server 플로우를 S1 → S3 → S4로 선제 `OFPFC_ADD`, `Priority 100` `확정` |
| 설치 순서 | ① 우회 경로 하류부터 설치(S4 → S3 → S1) ② 차단 룰 설치 — 정상 트래픽 무유실 보장 |
| 발행 메시지 | `sdn:control:command` (`ControlCommandMessage`) 2건: `ISOLATE`, `REROUTE` / `sdn:topology:sync` 1건 |
| 전이 조건 T2 | 두 명령의 FlowMod 설치 완료 → `MITIGATED` |
| 관제탑 | S1:2 링크 회색(`BLOCKED`), S1-S3-S4 링크 청색 강조(`REROUTED`), S1-S2-S4는 대기, H_legit 통신 그래프 유지 |

### 3.4 4단계: 자가 복구 — `COOLDOWN_VERIFY` → `NORMAL`
| 항목 | 내용 |
|:---|:---|
| 전이 조건 T3 | S1:2 PPS < `ATTACK_CEASE_PPS`(100) 및 스코어 ≥ -0.5 → `COOLDOWN_VERIFY` 진입 `제안` |
| 쿨다운 | `COOLDOWN_SEC` = 10초 `확정`, 이 기간 동안 차단·우회 **유지** |
| 재공격 T4 | 쿨다운 중 T1 조건 재충족 → 즉시 `MITIGATED` 복귀, 타이머 리셋 (플래핑 방지) |
| 복구 T5 | 10초 동안 정상 판정 유지 → `RESTORE` 명령 발행 |
| 복구 동작 | ① S1:2 Drop 룰 `OFPFC_DELETE_STRICT` ② 우회 플로우(S1, S3, S4) `OFPFC_DELETE_STRICT` → 기본 경로(`Priority 10`)로 자동 복귀 |
| 주의 | 우회 플로우를 삭제하지 않으면 `Priority 100`이 남아 기본 경로로 돌아가지 않음 (`roadmap_v2.md` §15) |
| 관제탑 | 배지 `RESTORING` 후 `NORMAL`, 모든 링크 녹색 복귀, 이벤트 타임라인에 복구 시각 기록 |

---

## 4. 채널별 메시지 흐름 요약

| 단계 | `sdn:stats:port` | `sdn:anomaly:alert` | `sdn:control:command` | `sdn:topology:sync` |
|:---|:---:|:---:|:---:|:---:|
| CALIBRATING | 2초 주기 | - | - (발행 금지) | 기동 시 1회 |
| NORMAL | 2초 주기 | - | - | - |
| ATTACK_DETECTED | 2초 주기 | 매 주기 | - | S1 `ATTACKED` |
| MITIGATED | 2초 주기 | 선택(공격 지속 시) | `ISOLATE`, `REROUTE` | S1 `MITIGATED`, 링크 `BLOCKED`/`REROUTED` |
| COOLDOWN_VERIFY | 2초 주기 | - | - | - |
| → NORMAL | 2초 주기 | - | `RESTORE` | 전체 `NORMAL`/`ACTIVE` |

### 4.1 예시 페이로드 (계약 스키마 준수)
```json
// sdn:anomaly:alert
{"timestamp": 1790000000.0, "dpid": 1, "in_port": 2, "threat_type": "SYN_FLOOD_SPOOFING",
 "score": -0.78, "pps": 3000.0, "bps": 192000.0, "bpp": 64.0,
 "metadata": {"model": "IsolationForest-v1", "threshold": "-0.50"}}

// sdn:control:command (ISOLATE)
{"timestamp": 1790000002.0, "command_id": "cmd-isolate-0001", "action": "ISOLATE",
 "target_dpid": 1, "target_port": 2, "reason": "SYN_FLOOD_SPOOFING on S1:2", "priority": 100}
```

---

## 5. 관제탑 표시 규칙 (UI 매핑)

| 계약 필드 값 | 색상 (Tailwind) | 표현 |
|:---|:---|:---|
| `TopologyNode.status = NORMAL` | `emerald-500` | 실선 테두리 |
| `TopologyNode.status = ATTACKED` | `red-500` | 1초 주기 점멸 |
| `TopologyNode.status = MITIGATED` | `sky-500` | 방패 아이콘 |
| `TopologyNode.status = OFFLINE` | `slate-500` | 반투명 |
| `TopologyLink.status = ACTIVE` | `emerald-500` | 실선 |
| `TopologyLink.status = BLOCKED` | `slate-500` | 점선 + X 표시 |
| `TopologyLink.status = REROUTED` | `blue-500` | 굵은 실선 + 흐름 애니메이션 |

- 배경 `bg-slate-900`, 카드 `bg-slate-800` (다크 SOC 테마)
- WebSocket 연결 상태 배지: `CONNECTED`(녹색) / `RECONNECTING`(황색) / `DISCONNECTED`(적색)

### 5.1 WebSocket 전송 형식 (FastAPI → 브라우저)
FastAPI는 Redis 채널 메시지를 아래 봉투(envelope)로 감싸 브로드캐스트한다. `data`는 계약 스키마의 JSON 그대로이다.
```json
{"type": "sdn:stats:port", "data": { ...PortStatsMessage... }}
{"type": "system:status",  "data": {"phase": "MITIGATED", "mode": "mock", "timestamp": 1790000004.0}}
```
| `type` | `data` 스키마 |
|:---|:---|
| `sdn:stats:port` | `PortStatsMessage` |
| `sdn:anomaly:alert` | `AnomalyAlertMessage` |
| `sdn:control:command` | `ControlCommandMessage` |
| `sdn:topology:sync` | `TopologySyncMessage` |
| `system:status` | `{phase, mode, timestamp}` — `phase`는 §2의 FSM 상태명 |

---

## 6. 파라미터 표 (상수 단일 관리)

| 상수명 | 값 | 단위 | 상태 | 담당 | 근거 |
|:---|:---:|:---:|:---:|:---:|:---|
| `STATS_POLL_INTERVAL_SEC` | 2 | 초 | 확정 | 박시현 | `sdn_events.py` |
| `CALIBRATION_SEC` | 15 | 초 | 확정 | 유재민 | `roadmap_v2.md` §17 |
| `NORMAL_PPS_RANGE` | 10~100 | PPS | 확정 | 유재민 | Phase2 가이드 |
| `ATTACK_PPS` | 3,000 (1,000~5,000) | PPS | 확정 | 유재민 | `schedule_and_milestones.md` 5주차 |
| `ATTACK_PKT_SIZE` | 54~74 | Byte | 확정 | 유재민 | `roadmap_v2.md` Sprint 4 |
| `BPP_ATTACK_MAX` | 80 | Byte | 제안 | 유재민 | 공격 패킷 최대 74B + 여유 |
| `SCORE_THRESHOLD` | -0.5 | - | 확정 | 유재민 | Phase2 가이드 |
| `DETECT_CONSECUTIVE` | 2 | 주기 | 제안 | 유재민 | Flash Crowd 오탐 방지 |
| `ATTACK_CEASE_PPS` | 100 | PPS | 제안 | 유재민 | 정상 PPS 상한 |
| `COOLDOWN_SEC` | 10 | 초 | 확정 | 박시현·유재민 | `roadmap_v2.md` Sprint 4 |
| `PRIORITY_DROP` | 100 | - | 확정 | 박시현 | `project_proposal.md` |
| `PRIORITY_REROUTE` | 100 | - | 확정 | 박시현 | `roadmap_v2.md` |
| `PRIORITY_DEFAULT` | 10 | - | 확정 | 박시현 | `roadmap_v2.md` |

---

## 7. 합격 기준 (시연 검증 체크리스트)

| # | 검증 항목 | 목표 | 측정 담당 |
|:---:|:---|:---|:---:|
| V1 | 공격 개시 → `ISOLATE` 설치까지 E2E 반응 시간 | ≤ 100ms (탐지 주기 제외) | 유재민 |
| V2 | 우회 전환 중 H_legit 패킷 유실률 | ≤ 2.0% | 유재민 |
| V3 | 탐지 모델 F1-Score | ≥ 0.95 | 유재민 |
| V4 | Trunk 포트 대상 `ISOLATE` 명령 | 100% 거부 | 박시현 |
| V5 | 쿨다운 중 재공격 시 차단 해제 발생 | 0회 (플래핑 없음) | 박시현 |
| V6 | 복구 후 트래픽 경로 | S1-S2-S4로 복귀 (`ovs-ofctl dump-flows`로 확인) | 박시현 |
| V7 | 관제탑 상태 표시 지연 | 이벤트 발생 후 ≤ 1초 | 김관우 |
| V8 | 브라우저 F5 10회 연속 | 백엔드 크래시 0회, 연결 수 정상 복귀 | 김관우 |

---

## 8. 미결 사항 (검토 요청)

| # | 내용 | 검토자 |
|:---:|:---|:---:|
| Q1 | `DETECT_CONSECUTIVE`=2 적용 시 탐지 지연이 최대 4초 증가 — V1 측정 구간 정의 확인 필요 | 유재민 |
| Q2 | 쿨다운 중 공격 소멸 판정을 AI Worker가 할지, Ryu FSM이 할지 주체 확정 (`flapping_fsm.py` 위치) | 박시현 |
| Q3 | `system:status`(FSM 상태)를 Redis 채널로 계약에 추가할지, FastAPI가 경보/명령으로 추론할지 결정 | 박시현 |
| Q4 | H_server 포트(S4:1) 공격 시(서버 역방향 공격) 시나리오 범위 포함 여부 | 전원 |
| Q5 | 차단(`in_port=2 → drop`)과 우회(`nw_dst=10.0.0.4 → S3`)가 모두 Priority 100이면 공격 패킷이 두 규칙에 동시에 해당해 어느 쪽이 적용될지 정해지지 않는다. 14주차 E2E 실측에서 차단 규칙 적중 0, 공격 27,607패킷이 우회로로 서버 도달. **제안:** 차단 Priority를 200으로 올리거나, 우회 규칙에 `in_port=1` 조건 추가 (`docs/writing/reports/verification/week14_e2e_verification.md` §4.2) | 박시현 |

---

## 변경 이력
| 버전 | 일자 | 작성자 | 내용 |
|:---:|:---:|:---:|:---|
| v1.0 | 2026.09.29 | 김관우 | 최초 작성 (4주차 산출물) |
| v1.1 | 2026.10.07 | 김관우 | Q5 추가: 차단·우회 규칙 우선순위 충돌 (14주차 E2E 실측) |
