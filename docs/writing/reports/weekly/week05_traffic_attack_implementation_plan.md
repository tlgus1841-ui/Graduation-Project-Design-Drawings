# 📗 [Domain Dev & QA] 5주차 구현 계획서 — 랜덤 IP 스푸핑 SYN Flood 공격기 (`traffic/traffic_attack.py`)
> **담당자:** 유재민 (22101498 / Domain Dev & QA)
> **해당 기간:** 5주차 (2026.09.28 ~ 2026.10.04)
> **상위 근거 문서:** [`schedule_and_milestones.md`](../../../planning/schedule_and_milestones.md), [`phase2_traffic_features_model.md`](../../../guides/dev_b_domain_qa/phase2_traffic_features_model.md), [`week04_traffic_normal_plan.md`](week04_traffic_normal_plan.md) §6(체크섬 유틸 중복 리스크)

---

## 1. 목적 및 배경

4주차에 만든 정상 트래픽(`traffic_normal.py`)이 AI 탐지 모델의 "정상 기준선"이라면, 5주차 공격기는 "이상치 라벨" 데이터를 만든다. 두 트래픽 모두 같은 체크섬 무결성 규약을 지켜야 6주차 `feature_extractor.py`가 뽑는 피처(특히 BPP)가 라벨과 무관하게 왜곡되지 않는다.

- **대상 파일:** `traffic/traffic_attack.py`
- **실행 위치:** Mininet 호스트 `H_attacker` (10.0.0.2)
- **목적지:** `H_server` (10.0.0.4:80)
- **후속 연계:** 6주차 `feature_extractor.py`가 BPP 급감(정상 700~1200B → 공격 64B 근방)을 탐지 신호로 사용

## 2. 요구사항 정리 (DoD 기준)

| # | 요구사항 | 출처 |
|:---:|:---|:---|
| R1 | 출발지 IP 무작위 변조 (1.0.0.0~223.255.255.255, 사설/예약 대역 제외) | phase2 가이드 5주차 |
| R2 | 출발지 포트 무작위 (1024~65535) | phase2 가이드 5주차 |
| R3 | TCP SYN 플래그 고정, 페이로드 없음 (54~74B 극소형 패킷) | phase2 가이드 5주차 |
| R4 | 초당 1,000~5,000 PPS 가변 주입 | schedule_and_milestones.md 5주차 |
| R5 | 전송 직전 IP/TCP 체크섬 삭제 → 커널 재계산 강제 | `.cursorrules`, 4주차 계획서 공통 리스크 |
| R6 | 4주차에 남긴 리스크 해소: 체크섬 유틸을 `traffic_normal.py`와 공유 | 4주차 계획서 §6 |

## 3. 설계 개요

### 3.1 체크섬 유틸 공유 (R6 해소)
`finalize_checksum()`을 `traffic/checksum_utils.py`로 분리하고, `traffic_normal.py`와 `traffic_attack.py`가 공통으로 import한다. (4주차 계획서에서 "5주차 착수 시 재검토"로 남겨둔 항목)

### 3.2 모듈 구조
```
traffic/
├── checksum_utils.py     # (신규, 공용) finalize_checksum()
├── traffic_normal.py     # (수정) 자체 finalize_checksum 제거, 공용 유틸 사용
└── traffic_attack.py     # (신규)
    ├── AttackProfile (dataclass)   # dst, dport
    ├── _random_public_ip()         # 사설/예약 대역 제외 랜덤 공인 IP
    ├── build_syn_packet()          # 무페이로드 SYN 패킷 생성
    ├── flood_second()              # 1초 분량 패킷 리스트 생성 후 일괄 send()
    ├── run()                       # duration 동안 초당 랜덤 PPS(1000~5000)로 flood_second 반복
    └── main()                      # CLI(--dst --dport --duration --min-pps --max-pps)
```

### 3.3 패킷 스펙
| 필드 | 값 |
|:---|:---|
| 목적지 | H_server 10.0.0.4:80 (TCP) |
| 출발지 IP | 매 패킷마다 무작위 공인 IP (10/8, 172.16/12, 192.168/16, 127/8, 169.254/16 제외) |
| 출발지 포트 | 1024~65535 무작위 |
| TCP 플래그 | `S` (SYN) 고정 |
| 페이로드 | 없음 → Ethernet(14B) + IP(20B) + TCP(20B) = 54B (옵션 있을 경우 최대 74B 내) |
| 전송 방식 | 초당 1,000~5,000개 중 무작위 목표치를 정해 `send(list, verbose=False)`로 일괄 전송 |

## 4. 일자별 실행 계획 (5주차, 09.28~10.04)

| 일자 | 작업 | 체크포인트 |
|:---:|:---|:---|
| Day 1 (09.28) | `checksum_utils.py` 분리, `traffic_normal.py` 리팩토링 및 회귀 확인 | 기존 6종 테스트 그대로 통과 |
| Day 2 (09.29) | `_random_public_ip()` + 사설대역 제외 로직, `build_syn_packet()` | 패킷 스펙 단위 테스트 |
| Day 3 (09.30) | `flood_second()` / `run()` PPS 가변 주입 루프 | 1초당 목표 PPS 대로 패킷 수 생성 확인 |
| Day 4 (10.01) | CLI/`main()` 및 로그 출력 | `--help` 정상 출력 |
| Day 5 (10.02) | Mininet에서 `H_attacker → H_server` 실제 주입, 컨트롤러(5주차 박시현 산출물) 플로우 테이블 폭증 여부 관찰 | 리눅스 환경 검증 (별도 확인 필요) |
| Day 6~7 (10.03~10.04) | 회귀(`pytest`, `flake8`, `mypy`) 및 주간 보고서 정리 | DoD 전항목 충족 |

## 5. 테스트 및 검증 계획
1. **단위 검증:** SYN 패킷의 목적지/포트/플래그/페이로드 없음/체크섬 삭제 여부, 사설 IP 미생성(다수 샘플)
2. **속도 검증:** `run()`을 짧은 duration으로 돌려 초당 목표 PPS와 실제 생성 패킷 수 일치 확인 (`send()`는 모킹)
3. **회귀 검증:** `traffic_normal.py` 리팩토링 후 기존 4주차 테스트 6종 그대로 통과

## 6. 리스크 및 대응
| 리스크 | 대응 |
|:---|:---|
| 사설 IP가 우연히 생성되어 실제 내부망으로 라우팅될 위험 | `_random_public_ip()`에서 10/8, 172.16/12, 192.168/16, 127/8, 169.254/16 명시적 차단 |
| 컨트롤러 플로우 테이블 폭증(9주차 이전이라 아직 방어 로직 없음) | 5주차는 격리 로직 이전이므로 Mininet에서 **짧은 duration**으로만 실측, 장시간 방치 금지 |
| root 권한 필요 | `sudo uv run python traffic/traffic_attack.py` |

## 7. 완료 기준 체크리스트 (DoD)
- [ ] `traffic/checksum_utils.py` 분리 및 `traffic_normal.py` 회귀 통과
- [ ] `traffic/traffic_attack.py` 구현 (사설 IP 제외, SYN 고정, 54~74B, PPS 1000~5000)
- [ ] 전송 직전 체크섬 삭제 적용
- [ ] 단위 테스트 통과, 기존 4주차 테스트 회귀 없음
