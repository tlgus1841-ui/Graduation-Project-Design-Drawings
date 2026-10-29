# PORT_SCAN·SLOW_DRIFT 판정 신호 재설계 보고서 (v2 수정)

- **작성일**: 2026-10-28
- **작성자**: 유재민 (Domain Dev & QA)
- **대상 브랜치**: [`fix/secondary-attack-classifier-real-signals`](https://github.com/tlgus1841-ui/Graduation-Project-Design-Drawings/pull/new/fix/secondary-attack-classifier-real-signals) (`main` 최신 동기화 후 분기)
- **전편**: [`multi_attack_type_defense_report.md`](multi_attack_type_defense_report.md) (2026-10-14, 이번 보고서가 그 설계를 교체함)

---

## 1. 무엇이 왜 잘못됐는가

2026-10-14에 추가한 PORT_SCAN/SLOW_DRIFT 탐지를 팀 동료들의 이후 작업과 맞춰 재검토하던 중, **둘 다 실제 Mininet/OVS 환경에서는 작동할 수 없는 신호**였다는 걸 발견했습니다. 유닛 테스트는 전부 통과했지만, 테스트가 신호를 합성 피처 딕셔너리로 수동 주입했기 때문에 "실제로 그 값이 바뀌는가"를 검증하지 못했습니다.

| 유형 | v1 신호 | 왜 실제로는 안 움직이는가 |
| :--- | :--- | :--- |
| **PORT_SCAN** | `err_rate` (OpenFlow `rx_errors`) | `rx_errors`는 스위치의 **물리/링크 계층** 수신 오류(CRC·프레임 오류 등) 카운터입니다. 닫힌 포트로 보낸 TCP SYN에 대한 RST 응답은 스위치 입장에서 완전히 정상적인 프레임이라 전혀 반응하지 않습니다. 게다가 이 프로젝트의 공격 트래픽은 [`traffic/checksum_utils.py`](../../traffic/checksum_utils.py)로 체크섬을 일부러 정상화해서 보내므로, 코드베이스 안 **어떤 트래픽 생성기도 `rx_errors`를 움직이지 못합니다**. |
| **SLOW_DRIFT** | `duration_sec` (포트 가동 시간) EWMA 추세 | `duration_sec`은 "그 포트가 켜져 있던 시간"(업타임)입니다. 공격이든 아니든 2초 주기마다 항상 똑같이 2씩 늘어나므로, 이걸 EWMA로 추적해도 "공격 추세"가 아니라 "시간이 흐른다"는 사실만 감지하게 됩니다. |

## 2. 재설계

두 유형 모두 **실제로 관측 가능한 신호 하나**에서 출발하도록 바꿨습니다: `DetectionGuard`(플러드)가 걸러낸 `MIN_ATTACK_PPS`(100 PPS) 미달 구간에서, BPP는 작은데(`BPP_ATTACK_MAX` 이하) `delta_pps`가 EWMA 기준선보다 **증가** 방향으로 벗어나는 것.

포트 통계만으로는 "포트 스캔"과 "Slow DDoS 전조"를 구조적으로 구분할 근거가 없습니다(둘 다 "플러드에는 못 미치는 소형 패킷 트래픽의 비정상적 증가"로 똑같이 보입니다). 그래서 **지속 시간**으로 나눕니다: 짧게(10틱≈20초 미달) 튀면 탐색성 버스트(PORT_SCAN), 그 이상 계속되면 저속·장기 자원 고갈(SLOW_DRIFT)로 승격합니다.

```
EWMA(delta_pps) 기준선보다 증가
  AND delta_pps < MIN_ATTACK_PPS(100)   # 플러드 임계치 미달 (DetectionGuard 영역이 아님)
  AND bpp <= BPP_ATTACK_MAX(80)         # 소형 패킷(페이로드 없는 SYN류)
  2틱 연속 확정
    -> 10틱 미달: PORT_SCAN
    -> 10틱 이상 계속: SLOW_DRIFT
```

이 신호는 [`model/detection_guard.py`](../../model/detection_guard.py)가 플러드 판정에 쓰는 것과 같은 `BPP_ATTACK_MAX=80` 관례를 그대로 재사용하고, `delta_pps`는 Ryu `OFPPortStatsReply`에서 직접 나오는 값이라 실제 OVS 환경에서 의미 있게 움직입니다.

EWMA는 기준선 대비 증가·감소 양방향 이탈을 모두 "이상"으로 보는 범용 SPC 설계([`model/ewma_detector.py`](../../model/ewma_detector.py), 변경 없음)라서, "증가만" 의심하도록 걸러주는 조건을 분류기 쪽에 추가했습니다 — 그렇지 않으면 버스트 직후 기준선 복귀도 반대 방향의 큰 편차로 잡혀, 바로 다음 재급등을 "연속 2틱"으로 오인하는 문제가 테스트로 발견됐습니다(아래 4절).

## 3. 변경 파일

| 파일 | 상태 | 내용 |
| :--- | :--- | :--- |
| [`model/attack_classifier.py`](../../model/attack_classifier.py) | 재작성 | `SecondaryAttackClassifier`를 새 신호로 교체. `AttackCategory`/`CATEGORY_TO_THREAT_TYPE`/`StreakGuard` 인터페이스는 그대로 (스트릭 길이를 읽는 `streak` 속성만 추가) |
| [`tests/model/test_attack_classifier.py`](../../tests/model/test_attack_classifier.py) | 재작성 | err_rate 기반 테스트 제거, 소형 패킷 서브플러드 버스트·PORT_SCAN→SLOW_DRIFT 승격 테스트로 교체 |
| [`tests/model/test_inference_worker.py`](../../tests/model/test_inference_worker.py) | 수정 | `ErrorCounters` 제거, 같은 새 신호로 통합 테스트 재작성 |
| [`traffic/traffic_scan.py`](../../traffic/traffic_scan.py) | 신규 | 새 탐지 신호를 실제 Mininet 패킷으로 검증·시연하는 생성기 (아래 5절) |
| [`tests/traffic/test_traffic_scan.py`](../../tests/traffic/test_traffic_scan.py) | 신규 | 패킷 생성·포트 순환·PPS 루프 단위 테스트 |
| [`model/inference_worker.py`](../../model/inference_worker.py) | 문서만 | `pipeline/feature_extractor.py`에 이미 실데이터 캡처 CLI가 있다는 안내만 추가 (아래 6절) |

`AttackCategory`, `ThreatType.PORT_SCAN`/`SLOW_DDOS`, `CATEGORY_TO_THREAT_TYPE` 등 외부에 노출된 인터페이스는 전부 그대로이며, `model/inference_worker.py`가 `SecondaryAttackClassifier`를 생성·호출하는 코드도 무변경입니다. 내부 판정 로직만 바뀐 비파괴적 교체입니다.

## 4. 재설계 중 발견하고 즉시 고친 설계 결함 1건

첫 구현에서 "급등 → 기준선 복귀 → 재급등"을 "첫 급등 1회 + 두 번째 급등 1회(연속 아님, 오탐 아님)"로 기대한 테스트가 실패했습니다. 원인: EWMA는 방향에 상관없이 `|편차| > k·표준편차`면 이상으로 보는데, 급등 직후 평균이 급등 값 쪽으로 따라붙은 상태에서 기준선으로 복귀하면 그 자체가 반대 방향의 큰 편차가 되어 "이상"으로 또 잡혀버립니다 — 스트릭이 끊기지 않고 계속 이어져 2번째 급등에서 바로 확정되는 문제였습니다.

수정: "의심" 조건에 `delta_pps > 직전 EWMA 평균` (증가 방향만)을 추가했습니다. 복귀 틱은 평균보다 낮으므로 더 이상 스트릭을 잇지 않습니다.

## 5. 실제 패킷으로 검증·시연하는 생성기 추가 (`traffic/traffic_scan.py`)

기존 `traffic/`에는 SYN Flood(`traffic_attack.py`)와 정상(`traffic_normal.py`)만 있어 새 탐지기를 실제 패킷으로 확인할 방법이 없었습니다. `traffic_scan.py`는:
- 출발지 IP를 스푸핑하지 않습니다 (실제 포트 스캐너는 응답을 받아야 하므로).
- 목적지 포트(기본 1~1024)를 순환하며, 플러드 임계치(100 PPS) 미달(기본 20~60 PPS)로 SYN을 보냅니다.
- `--duration`을 짧게(12초) 주면 포트 스캔 데모, 길게(30초 이상) 주면 Slow DDoS 데모가 됩니다 — 탐지기가 지속 시간으로만 두 유형을 나누는 것과 1:1로 대응합니다.

```bash
sudo uv run python traffic/traffic_scan.py --dst 10.0.0.4 --duration 12   # 포트 스캔 데모
sudo uv run python traffic/traffic_scan.py --dst 10.0.0.4 --duration 30   # Slow DDoS 데모
```

**주의**: 이 Windows 샌드박스에는 Mininet/Npcap 실행 환경이 없어, 이번 검증은 유닛 테스트(패킷 생성·포트 순환·PPS 루프, send() 모킹)까지만 확인했습니다. 실제 GCP Mininet에서 한 번 돌려 `model/attack_classifier.py`가 실제로 PORT_SCAN/SLOW_DRIFT를 확정하는지 재현하는 것을 다음 단계로 권장합니다.

## 6. 바로잡습니다: "실데이터 F1 캡처 도구가 없다"는 이전 보고는 제 조사 실수였습니다

지난 리뷰에서 "실데이터로 재학습·F1 측정할 캡처 도구가 없다"고 말씀드렸는데, 다시 확인해보니 **[`pipeline/feature_extractor.py`](../../pipeline/feature_extractor.py)에 이미 완전히 구현되고 테스트까지 된 캡처 CLI가 있었습니다**:

```bash
uv run python pipeline/feature_extractor.py --label 0 --out dataset/real_normal.csv   # 정상 구간
uv run python pipeline/feature_extractor.py --label 1 --out dataset/real_attack.csv   # 공격 구간
```

Redis `sdn:stats:port`를 직접 구독해 레이블이 붙은 CSV를 기록하며, `tests/pipeline/test_feature_extractor.py`의 `test_run_consumes_fakeredis_messages_and_logs_csv` 등으로 이미 검증돼 있습니다. 그래서 `model/inference_worker.py`에 중복으로 캡처 기능을 추가하지 않고, 문서 한 줄로 이 도구를 가리키는 것만 추가했습니다.

**즉, 2026-10-11 인수인계 메모("실데이터 F1 측정 필요")에 남은 건 코드 작업이 아니라 실행 작업입니다**: GCP Mininet에서 위 두 명령으로 정상/공격 구간을 캡처 → CSV 합치기 → `AnomalyModel().fit()`으로 재학습 → `model/benchmark_report.py`와 같은 방식(단, `synthetic_samples` 대신 이 실데이터)으로 F1 재측정. 이 세션(Windows, Mininet 없음)에서는 실행할 수 없어 다음 GCP 접속 시 직접 진행을 권장합니다.

## 7. 테스트 결과

| 항목 | 결과 |
| :--- | :--- |
| `tests/model/test_ewma_detector.py` | ✅ 5/5 (무변경) |
| `tests/model/test_attack_classifier.py` (재작성) | ✅ 11/11 |
| `tests/model/test_inference_worker.py` (수정) | ✅ 7/7 |
| `tests/traffic/test_traffic_scan.py` (신규) | ✅ 6/6 |
| 전체 회귀 (`tests/` 전체, api·benchmarks 포함) | ✅ 전부 통과 |
| `flake8` (변경/신규 파일) | 0 issues |
| `mypy` (변경/신규 파일) | 0 issues |

## 8. 다음 단계

- `fix/secondary-attack-classifier-real-signals` 브랜치 리뷰·머지 부탁드립니다.
- GCP Mininet 접속 시: (1) `traffic_scan.py`로 실제 포트 스캔/Slow 패킷을 쏴서 탐지 확정 여부 재현, (2) `pipeline/feature_extractor.py`로 실데이터 캡처 후 재학습·F1 재측정.
- `docs/verification/v2_breaking_points_fix_backlog.md`의 BP-01(서킷 브레이커 조기 복구)은 여전히 미해결입니다. 이번에 PORT_SCAN/SLOW_DRIFT 경보가 늘어난 만큼 같은 경로를 타는 경보 종류도 늘었으니, 박시현님 쪽에서 우선순위를 다시 봐주시면 좋겠습니다.
