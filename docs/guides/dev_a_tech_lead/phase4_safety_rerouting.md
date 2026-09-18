# 📘 [Tech Lead] Phase 4: In_port 격리 & 다중 홉 우회 & FSM 플래핑 방지 가이드
> **담당자:** 박시현 (22101489 / Tech Lead)  
> **해당 기간:** 9주차 ~ 11주차 (2026.10.26 ~ 2026.11.15)  
> **핵심 산출물:** `harness/safety/whitelist_guard.py`, `ryu/app/reroute.py`, `harness/safety/flapping_fsm.py`  
> **선행 조건:** Phase 3 E2E 파이프라인 관통 완료

---

## 1. Phase 4 개발 목표 및 완료 기준 (Definition of Done)

- [ ] **9주차 DoD:** AI 경보 수신 즉시 공격 유입 포트(`in_port`) 기반 `Priority 100 Drop` 플로우 주입 핸들러 및 화이트리스트(Trunk 포트 오차단 방지) 가드레일 구현
- [ ] **10주차 DoD:** NetworkX 기반 다익스트라 경로 계산 및 대체 경로 중간 스위치들에 선제적 `OFPFC_ADD` 규칙 주입을 통한 다중 홉 무유실 우회 라우팅 완성
- [ ] **11주차 DoD:** 명시적 FSM(Normal ➔ Attack ➔ Mitigated ➔ Cooldown ➔ Normal) 엔진 탑재로 라우팅 플래핑(Flapping) 방지 및 공격 소멸 시 무개입 자동 롤백 실현

---

## 2. 핵심 알고리즘 구현 명세

### 2.1 화이트리스트 안전 가드레일 (`harness/safety/whitelist_guard.py`)
```python
# Trunk 포트(스위치 간 연결선) 오차단을 원천 차단하는 가드레일
TRUNK_PORTS = {
    1: [3, 4],  # S1의 Port 3, 4는 Trunk
    2: [1, 2],  # S2의 Port 1, 2는 Trunk
    3: [1, 2],  # S3의 Port 1, 2는 Trunk
    4: [2, 3]   # S4의 Port 2, 3은 Trunk
}

def validate_isolation_target(dpid: int, port_no: int) -> bool:
    if port_no in TRUNK_PORTS.get(dpid, []):
        raise ValueError(f"치명적 오류: DPID {dpid}의 Port {port_no}는 Trunk 포트이므로 차단할 수 없습니다.")
    return True
```

### 2.2 다중 홉 선제적 플로우 주입 (`OFPFC_ADD`)
출발 스위치(S1)만 수정하면 중간 스위치(S3)에서 패킷이 드롭되므로, 우회 경로 `[S1, S3, S4]`상의 모든 스위치에 우회 플로우를 먼저 `OFPFC_ADD`로 설치한 후 S1의 출력 포트를 4번(S3 방향)으로 전환합니다.
