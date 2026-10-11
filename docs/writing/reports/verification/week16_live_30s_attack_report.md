# 16주차 30초 Live DDoS 공격 실측 성적표 (GCP VM 통합 검증)

| 항목 | 내용 |
|:---|:---|
| **측정 일시** | 2026.10.11 |
| **측정 환경** | GCP Compute Engine `e2-standard-4` (`34.64.74.172`, Ubuntu 22.04 LTS) |
| **기준 브랜치 / 커밋** | `integration/week16-final` (`2fc0f65` — 중복 조치 기록 방지 & 복구 시 우회 규칙 즉시 삭제 반영본) |
| **구동 구성요소** | Mininet 4-Switch Diamond Topo + Ryu 4.34 Controller (`sdn-ryu`) + Redis 7.2 (`sdn-redis`) + Isolation Forest 추론 워커 (`model.inference_worker`) + FastAPI/React 관제탑 (`SDN_MOCK=0` Live Mode) |
| **원본 측정 데이터** | [`data/week16_live_30s_attack.json`](data/week16_live_30s_attack.json) |

---

## 1. 30초 Live 공격 실측 종합 성적표

| 평가 지표 | 실측 결과 | 의미 및 해석 |
|:---|:---:|:---|
| **총 공격 지속 시간 (`attack_seconds`)** | **30.9 초** | `H_attacker` (`10.0.0.2`)가 30초간 연속 SYN Flood 폭격 수행 |
| **총 발사 공격 패킷 수 (`attack_packets`)** | **47,288 개** | 초당 약 1,530 PPS의 랜덤 Source IP 변조 공격 |
| **공격 시작 ➔ AI 탐지 및 차단 (`detect_after_attack_s`)** | **3.20 초** | 2초 통계 주기 2회 연속(`DetectionGuard`) 확인 후 즉시 공격 확정 |
| **경보 수신 ➔ 컨트롤러 차단 반응 (`first_alert_to_isolate_ms`)** | **2.5 ms** | Redis 경보 수신 후 OpenFlow FlowMod 주입까지 **0.0025초** 소요 |
| **격리 중 S1에서 차단(Drop)된 공격 패킷** | **40,163 개** | Priority 100 `in_port=2` Drop 규칙이 스위치 하드웨어 레벨에서 원천 소각 |
| **격리 중 서버(`H_server`)로 유출된 공격 패킷** | **0 개** | **방어율 100% (격리 이후 서버 도달 공격 패킷 0)** |
| **격리 중 S3 우회 경로를 통과한 정상 패킷** | **510 개** | Priority 20 `S1 -> S3 -> S4` 우회 라우팅 정상 작동 |
| **격리 명령 발행 횟수 (`isolate_count`)** | **1 회** | 30초간 15회 경보 수신 중 **중복 발행 없이 딱 1회만 발행** (FSM 수명만 연장) |
| **복구 명령 발행 횟수 (`restore_count`)** | **1 회** | 라우팅 플래핑(Flapping) **0회**, 단일 복구 완료 |
| **공격 종료 ➔ 자율 복구 시간 (`recovery_after_attack_s`)** | **10.36 초** | 마지막 경보 이후 10초 쿨다운 직후 차단(Priority 100) 및 우회(Priority 20) 규칙 동시 삭제 |

---

## 2. 구간별 정상 사용자(`H_legit` ➔ `H_server`) 통신 손실률 (`normal_loss`)

50ms 간격 연속 Ping 측정을 통해 공격 전·중·후 모든 구간에서 **무유실(0.0% Loss)** 통신을 입증했습니다.

| 측정 구간 | 전송 패킷 (`sent`) | 유실 패킷 (`lost`) | 손실률 (`loss_percent`) |
|:---|:---:|:---:|:---:|
| **전체 시나리오 구간 (`whole_run`)** | 1,098 개 | **0 개** | **0.0 %** |
| **1단계: 공격 전 평시 (`before_attack`)** | 118 개 | **0 개** | **0.0 %** |
| **2단계: 공격 발생 ~ 격리 전 (`attack_until_isolated`)** | 63 개 | **0 개** | **0.0 %** |
| **3단계: 공격 격리 및 S3 우회 중 (`attack_while_isolated`)** | 543 개 | **0 개** | **0.0 %** |
| **4단계: 공격 종료 및 자가 복구 후 (`after_attack`)** | 374 개 | **0 개** | **0.0 %** |

---

## 3. 분석 JSON 원본 (`e2e_scenario --analyze`)

```json
{
  "attack_seconds": 30.9,
  "attack_packets": 47288,
  "detect_after_attack_s": 3.2,
  "first_alert_to_isolate_ms": 2.5,
  "decision_to_isolated_ms": null,
  "flow_install_ms": {
    "REROUTE": null,
    "ISOLATE": null
  },
  "isolate_count": 1,
  "restore_count": 1,
  "recovery_after_attack_s": 10.36,
  "dropped_at_s1_while_isolated": 40163,
  "leaked_to_server_while_isolated": 0,
  "s1_bypass_hits_while_isolated": 510,
  "normal_loss": {
    "whole_run": {
      "sent": 1098,
      "lost": 0,
      "loss_percent": 0.0
    },
    "before_attack": {
      "sent": 118,
      "lost": 0,
      "loss_percent": 0.0
    },
    "attack_until_isolated": {
      "sent": 63,
      "lost": 0,
      "loss_percent": 0.0
    },
    "attack_while_isolated": {
      "sent": 543,
      "lost": 0,
      "loss_percent": 0.0
    },
    "after_attack": {
      "sent": 374,
      "lost": 0,
      "loss_percent": 0.0
    }
  }
}
```

---

## 4. 실제 경보(`alert`) 및 제어 명령(`command`) 타임라인 로그

30초 공격 동안 AI 추론 워커가 2초마다 총 15회의 경보(`alert`)를 발행했으나, 컨트롤러는 최초 1회만 `ISOLATE` + `REROUTE`를 실행·기록하고 이후 14회는 FSM 쿨다운 타이머만 연장했습니다. 공격 종료 후 마지막 경보(`1791719591.918`)로부터 정확히 **10.06초 뒤(`1791719601.982`)**에 자율 복구(`RESTORE`)가 실행되었습니다.

```json
{"t": 1791719563.90752,   "kind": "alert",   "stats_ts": 1791719563.9034238, "port": "S1:2", "score": -0.1035}
{"t": 1791719563.9100633, "kind": "command", "action": "ISOLATE", "target": "S1:2", "command_id": "auto-isolate-1791719563909"}
{"t": 1791719563.9111185, "kind": "command", "action": "REROUTE", "target": "S1:4", "command_id": "auto-reroute-1791719563910"}
{"t": 1791719565.9079325, "kind": "alert",   "stats_ts": 1791719565.9044194, "port": "S1:2", "score": -0.1031}
{"t": 1791719567.9087288, "kind": "alert",   "stats_ts": 1791719567.9059663, "port": "S1:2", "score": -0.1045}
{"t": 1791719569.9094698, "kind": "alert",   "stats_ts": 1791719569.9064896, "port": "S1:2", "score": -0.099}
{"t": 1791719571.9106145, "kind": "alert",   "stats_ts": 1791719571.9068568, "port": "S1:2", "score": -0.1014}
{"t": 1791719573.9109986, "kind": "alert",   "stats_ts": 1791719573.9080305, "port": "S1:2", "score": -0.0968}
{"t": 1791719575.911716,  "kind": "alert",   "stats_ts": 1791719575.9089031, "port": "S1:2", "score": -0.1017}
{"t": 1791719577.9129755, "kind": "alert",   "stats_ts": 1791719577.9098613, "port": "S1:2", "score": -0.1007}
{"t": 1791719579.9130812, "kind": "alert",   "stats_ts": 1791719579.9102495, "port": "S1:2", "score": -0.103}
{"t": 1791719581.9139605, "kind": "alert",   "stats_ts": 1791719581.9111562, "port": "S1:2", "score": -0.1017}
{"t": 1791719583.9163706, "kind": "alert",   "stats_ts": 1791719583.912304,  "port": "S1:2", "score": -0.0952}
{"t": 1791719585.9158568, "kind": "alert",   "stats_ts": 1791719585.913052,  "port": "S1:2", "score": -0.1039}
{"t": 1791719587.917309,  "kind": "alert",   "stats_ts": 1791719587.9142284, "port": "S1:2", "score": -0.0983}
{"t": 1791719589.917072,  "kind": "alert",   "stats_ts": 1791719589.914022,  "port": "S1:2", "score": -0.0999}
{"t": 1791719591.9181147, "kind": "alert",   "stats_ts": 1791719591.9153397, "port": "S1:2", "score": -0.0975}
{"t": 1791719601.982589,  "kind": "command", "action": "RESTORE", "target": "S1:2", "command_id": "auto-restore-1791719601982"}
```
