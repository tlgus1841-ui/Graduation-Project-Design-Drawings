# 📗 [Domain Dev & QA] 4주차 구현 계획서 — Scapy 정상 트래픽 생성기 (`traffic/traffic_normal.py`)
> **담당자:** 유재민 (22101498 / Domain Dev & QA)
> **해당 기간:** 4주차 (2026.09.21 ~ 2026.09.27)
> **개발 단계:** Phase 2 (코어 모듈 구현 & Mock 하네스 기반 병렬 개발) 착수 주차
> **상위 근거 문서:** [`schedule_and_milestones.md`](../../../planning/schedule_and_milestones.md), [`phase2_traffic_features_model.md`](../../../guides/dev_b_domain_qa/phase2_traffic_features_model.md)

---

## 1. 목적 및 배경

Self-Defending SDN Tower는 정상 트래픽 대비 공격 트래픽의 통계적 괴리(BPP 급감 등)를 실시간 5대 피처로 탐지한다. 이 탐지 모델의 **기준선(baseline)** 이 되는 것이 4주차에 구현할 정상 트래픽 생성기이며, 5주차 공격기(`traffic_attack.py`)와 반드시 동일한 패킷 무결성 규약(Checksum 재계산)을 공유해야 Isolation Forest 학습 데이터가 왜곡되지 않는다.

- **대상 파일:** `traffic/traffic_normal.py`
- **실행 위치:** Mininet 호스트 `H_legit` (10.0.0.1) — Ryu 다이아몬드 토폴로지(S1 Ingress ~ S4 Egress) 경유
- **목적지:** `H_server` (10.0.0.4), 포트 80/443
- **후속 연계:** 6주차 `feature_extractor.py`가 본 트래픽의 Ryu 포트 통계를 소비하여 5대 파생 피처를 계산

---

## 2. 요구사항 정리 (Definition of Done 기준)

| # | 요구사항 | 출처 |
|:---:|:---|:---|
| R1 | 트래픽 패턴 3종 혼합 비율로 전송 (A:HTTP GET 70%, B:대용량 전송 20%, C:ICMP Ping 10%) | `schedule_and_milestones.md` 4주차 |
| R2 | 발송 간격은 지수 분포(Poisson process) 기반 무작위 딜레이 | `schedule_and_milestones.md` 4주차 |
| R3 | 전송 직전 `del pkt[IP].chksum`, `del pkt[TCP].chksum`으로 커널 재계산 강제 | `.cursorrules`, Phase2 가이드 §4 |
| R4 | Wireshark 캡처 기준 TCP/IP Checksum 무결성 100% 검증 | Phase2 가이드 DoD |
| R5 | Mock IPC 테스트 하네스(`test_mock_ipc.py`) 통과율 100% 유지 (회귀 없음) | 4주차 공통 마일스톤 |

---

## 3. 설계 개요

### 3.1 모듈 구조

```
traffic/
└── traffic_normal.py
    ├── PacketProfile (dataclass)       # 패턴별 비율·크기·포트 설정값 보관
    ├── build_http_packet()             # 패턴 A: HTTP GET 모사 (페이로드 500~1000B)
    ├── build_bulk_packet()             # 패턴 B: 대용량 전송 모사 (1400B 풀사이즈)
    ├── build_icmp_ping()               # 패턴 C: ICMP Echo Request (64B)
    ├── finalize_checksum(pkt)          # 공용: del chksum 후 반환 (공격기와 로직 공유 예정)
    ├── weighted_pattern_choice()       # 70/20/10 비율 샘플링
    ├── poisson_interval(lambda_rate)   # 지수 분포 발송 간격 계산
    └── main(loop)                      # CLI 인자 파싱 → 무한 루프 전송
```

### 3.2 트래픽 패턴 스펙

| 패턴 | 비율 | 목적지 포트 | 페이로드 크기 | 비고 |
|:---:|:---:|:---:|:---:|:---|
| A. 웹 서핑(HTTP GET) | 70% | 80 | 500~1,000B (균등 랜덤) | `Raw(load=...)` 텍스트성 더미 페이로드 |
| B. 대용량 전송 | 20% | 443 | 1,400B 고정 (MTU 근접 풀사이즈) | 연속 3~5개 패킷 버스트 전송 |
| C. ICMP Ping | 10% | - | 64B | `IP()/ICMP()`, TTL 기본값 |

- **발송 간격:** `random.expovariate(1 / mean_interval)` — 기본 평균 간격 0.2초(0.05~0.5초 범위에 대략 부합하도록 `mean_interval` 파라미터화)
- **체크섬 처리 공통 함수:** 패턴 A/B/C 모두 `finalize_checksum()`을 거치며, 이 함수는 5주차 `traffic_attack.py`에서도 재사용 가능하도록 별도 유틸(`traffic/checksum_utils.py`)로 분리할지 이번 주 내 결정 필요 (→ §6 리스크 참조)

### 3.3 CLI 인터페이스 (예정)

```bash
sudo uv run python traffic/traffic_normal.py \
  --src 10.0.0.1 --dst 10.0.0.4 \
  --mean-interval 0.2 --duration 60
```

---

## 4. 일자별 실행 계획 (4주차, 09.21~09.27)

| 일자 | 작업 내용 | 산출물/체크포인트 |
|:---:|:---|:---|
| Day 1 (09.21, 일) | Scapy 2.5 Raw Socket 권한 재확인, CLI 인자 구조 설계, `PacketProfile` 스키마 정의 | 파일 스켈레톤 커밋 |
| Day 2 (09.22, 월) | 패턴 A `build_http_packet()` 구현 및 단독 전송 테스트 | H_legit→H_server 80포트 패킷 확인 |
| Day 3 (09.23, 화) | 패턴 B `build_bulk_packet()` 구현 (443포트, 버스트 전송) | tcpdump로 1,400B 패킷 확인 |
| Day 4 (09.24, 수) | 패턴 C `build_icmp_ping()` + `weighted_pattern_choice()`(70/20/10) 통합 | 3패턴 혼합 루프 동작 확인 |
| Day 5 (09.25, 목) | `poisson_interval()` 적용, 발송 간격 분포 검증(평균/분산 로그 출력) | 간격 히스토그램 육안 검증 |
| Day 6 (09.26, 금) | `finalize_checksum()` 전 패턴 적용, Wireshark로 IP/TCP Checksum 100% 정상 캡처 검증 | 캡처 스크린샷/pcap 저장 |
| Day 7 (09.27, 토) | `uv run pytest tests/harness/test_mock_ipc.py -v` 회귀 확인, 주간 보고서 초안 작성 | DoD 체크리스트 전항목 충족 |

---

## 5. 테스트 및 검증 계획

1. **단위 검증:** 각 `build_*_packet()` 함수가 반환한 패킷의 길이·플래그·목적지 포트가 스펙과 일치하는지 `assert` 기반 스모크 테스트 작성 (`tests/traffic/test_traffic_normal.py`, 선택 사항이나 권장).
2. **체크섬 무결성 검증:** Mininet `H_legit` → `H_server` 구간에서 `tcpdump -w capture.pcap` 후 Wireshark로 IP/TCP Checksum 필드가 `unverified`가 아닌 정상 재계산 값으로 표시되는지 확인 (오프로드 환경에서는 Wireshark의 "Checksum Offloading" 옵션 확인 필요).
3. **통계적 검증:** 60초간 실행 후 패턴 비율이 70/20/10 ±5%p 이내인지, 발송 간격 평균이 목표값(예: 0.2초) ±10% 이내인지 로그로 확인.
4. **회귀 검증:** `uv run pytest tests/harness/test_mock_ipc.py -v` 100% 통과 유지 (본 작업이 IPC 계약에 영향 없음을 재확인).

---

## 6. 리스크 및 대응 (Gotchas)

| 리스크 | 영향 | 대응 방안 |
|:---|:---:|:---|
| Checksum 필드 미삭제 시 OVS/커널 스택에서 패킷 조용히 폐기 | 높음 | `finalize_checksum()`을 모든 전송 경로의 마지막 단계로 강제, 유닛 테스트로 체크섬 필드가 `None`인지 확인 |
| Scapy Raw Socket 실행에 root 권한 필요 (`sudo uv run ...`) | 중간 | 실행 스크립트에 권한 안내 주석 명시, CI/자동화 스크립트에서도 동일하게 `sudo` 처리 |
| Poisson 분포 평균 간격이 너무 짧아 컨트롤러 부하 유발 가능 | 낮음 | `mean_interval`을 CLI 파라미터화하여 6주차 피처 튜닝 시 조정 가능하도록 설계 |
| `traffic_attack.py`(5주차)와 체크섬 유틸 중복 구현 위험 | 낮음 | 공용 유틸 분리 여부를 5주차 착수 전 박시현/유재민 간 짧게 합의 (본 계획서는 4주차 범위 내 `traffic_normal.py` 내부 함수로 우선 구현, 분리는 5주차 착수 시 재검토) |

---

## 7. 완료 기준 체크리스트 (DoD)

- [ ] `traffic/traffic_normal.py` 구현 완료 (패턴 A/B/C 전 함수)
- [ ] Poisson 기반 발송 간격 적용 및 분포 검증
- [ ] 전 패턴에 `del pkt[IP].chksum` / `del pkt[TCP].chksum` 적용
- [ ] Wireshark 캡처 기준 Checksum 무결성 100% 확인
- [ ] `test_mock_ipc.py` 회귀 테스트 100% 통과
- [ ] 5주차 `traffic_attack.py` 착수를 위한 인터페이스(CLI 인자 패턴, 체크섬 유틸 분리 여부) 정리

---

## 8. 팀원 인계 사항

- **박시현 (Tech Lead):** 본 트래픽은 S1(Ingress) → S2(기본 경로) → S4(Egress) 경로를 사용하므로, `pingall` 무유실 검증이 선행되어야 정상 트래픽 손실이 탐지 피처 왜곡으로 오인되지 않습니다.
- **김관우 (PM & Tech Writer):** 정상 트래픽 BPP(패킷당 평균 바이트) 예상 범위는 700~1,200B이며, 이는 주간 보고서의 "정상 vs 공격 BPP 대비" 그래프의 기준값으로 사용될 예정입니다.
