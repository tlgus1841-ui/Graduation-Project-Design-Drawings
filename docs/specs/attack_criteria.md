# 공격 · 정상 판단 기준 명세 (8주차 기준표의 구현)
> **작성:** 김관우 (PM & Tech Writer) with Claude Code
> **근거:** 8주차 발표 "공격 · 정상 판단 기준 세분화", 기준 문서 "공격 판단 기준 세분화"
> **구현:** [`model/criteria_engine.py`](../../model/criteria_engine.py) (판단), [`ryu/app/controller.py`](../../ryu/app/controller.py) (세는 규칙 · 속도 제한)
> **측정 도구:** [`harness/verification/criteria_measure.py`](../../harness/verification/criteria_measure.py)

---

## 1. 무엇을 세는가 (스위치 0번 테이블)

접속 호스트마다 스위치 0번 테이블에 세는 규칙 7개를 둔다. 컨트롤러가 2초마다 읽어 `sdn:stats:flowcount`로 발행한다.
패킷은 세기만 하고 1번(속도 제한) → 2번(전달 · 격리 · 우회) 테이블로 그대로 넘어간다. 그래서 격리 중에도 공격 패킷 수를 계속 셀 수 있다.

| 종류 | 일치 조건 | 쓰는 곳 |
|---|---|---|
| `syn` | in_port, TCP, SYN 있음 · ACK 없음 | SYN Flood (연결 요청만, 서버의 SYN-ACK 응답은 제외) |
| `fin` | in_port, TCP, FIN | SYN 짝 맞춤 |
| `rst` | in_port, TCP, RST | SYN 짝 맞춤 |
| `udp` | in_port, UDP | UDP Flood |
| `icmp` | in_port, ICMP | ICMP Flood |
| `rst_in` | 목적지 = 이 호스트, TCP, RST | 포트 스캔 (닫힌 TCP 포트의 거절) |
| `unreach_in` | 목적지 = 이 호스트, ICMP type 3 | 포트 스캔 (닫힌 UDP 포트의 도달 불가) |

파생 지표: `gap = syn − (fin + rst)` (짝이 안 맞는 연결 요청), `fail = rst_in + unreach_in` (받은 실패 응답).

## 2. 판단 기준

<!-- MEASURED -->

## 3. 위험도 단계와 대응

| 단계 | 조건 | 대응 (컨트롤러) |
|---|---|---|
| 정상 | 모든 지표가 기준선 이하 | 없음 |
| 주의 (WATCH) | 지표 하나라도 기준선 초과 | 기록만 (경보 없음) |
| 경고 (WARNING) | 공격 종류 확정 (2회 연속), 세기 < M | 그 포트의 **그 공격 종류 패킷만** 초당 100개로 제한 (UDP Flood면 UDP만, SYN Flood · 포트 스캔이면 SYN만). 마지막 경보 뒤 10초 동안 경보가 없으면 해제 |
| 위험 (DANGER) | 공격 종류 확정, 세기 ≥ M | 격리 + 우회 (기존 방식, FSM 쿨다운 5초 / 10초) |

세기 = 지표 값 / 판정선. 경고 중 위험 경보가 오면 속도 제한을 지우고 격리한다. 격리 중 경고 경보가 오면 격리를 유지한다.

## 4. 평소값

- **사전 학습:** 정상 트래픽만 흐르는 동안 평소값을 학습해 `model/criteria_baseline.json`에 저장한다.
  (`python -m model.inference_worker --learn 600` 또는 `criteria_measure --analyze <폴더> --baseline-out <파일>`)
- **시작:** 저장된 값으로 바로 방어한다. 파일이 없으면 최소값만으로 판단한다 (고정 기준).
- **갱신:** 2초마다 EWMA(α = 2/301, 최근 약 10분 기억). 그 포트가 5주기(10초) 연속 정상일 때만 갱신한다.
- **상하한:** 갱신된 평균 · 표준편차는 사전 학습값 ~ 2배 사이에서만 움직인다.

## 5. 아직 없는 것

- **Slow HTTP · 내부 확산:** 연결 단위 정보(연결 지속 시간, 접속한 서로 다른 주소 수)가 필요해 포트 카운터로는 볼 수 없다.
- **서비스 상태 신호:** 정상 사용자 손실 · 지연을 위험 단계 조건으로 쓰려면 입력이 필요하다.
- **특수 상황 관리자 승인 재학습:** 엔진에는 사전 학습값을 바꾸는 경로가 아직 없다 (`--learn`으로 다시 학습).
- **서로 다른 포트 수:** 카운터는 개수만 세므로, 포트 스캔은 실패 응답 개수와 실패 비율로 판단한다.
