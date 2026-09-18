# 📗 [Domain Dev & QA] Phase 4: IP 스푸핑 방어 검증 & 무유실 벤치마크 가이드
> **담당자:** 유재민 (22101498 / Domain Dev & QA)  
> **해당 기간:** 9주차 ~ 11주차 (2026.10.26 ~ 2026.11.15)  
> **핵심 산출물:** `tests/benchmarks/test_spoofing_defense.py`, `tests/benchmarks/test_lossless_reroute.py`  
> **선행 조건:** Phase 3 모델 검증 및 Phase 4 In_port 격리/우회 모듈 연동

---

## 1. Phase 4 개발 목표 및 완료 기준 (Definition of Done)

- [ ] **9주차 DoD:** Scapy 랜덤 IP 변조 공격 중 컨트롤러 플로우 테이블 개수 증가율 0% 검증 (In_port 단 1개 룰로 격리 성공 증명)
- [ ] **10주차 DoD:** 공격 차단 및 우회 라우팅 동작 중 정상 단말(`H_legit`)의 통신 패킷 손실률(Loss Rate) 0% 실측 검증
- [ ] **11주차 DoD:** 공격 중단 후 10초 내 트래픽 정상화 자동 판정 및 FSM 상태 복원 트리거 송출 확인

---

## 2. 벤치마크 측정 시나리오

1. **플로우 테이블 고갈 방어 실험:**
   - 기존 방식(Src IP 매칭): 초당 3,000개의 플로우가 컨트롤러로 유입되어 테이블 메모리 고갈 발생.
   - 제안 방식(`in_port=2` Drop): 단 1개의 Drop 룰 설치 후 신규 Flow-Mod 요청이 0건으로 수렴함을 증명.
2. **무유실 우회 지연시간(RTT) 측정:**
   - H_legit ➔ H_server 방향으로 100ms 간격의 ICMP 핑을 100회 발송하면서 공격 주입 및 우회 시 손실 패킷 수와 RTT 변화를 기록.
