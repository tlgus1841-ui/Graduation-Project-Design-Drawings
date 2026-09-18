# 📗 [Domain Dev & QA] Phase 5 & 6: E2E 레이턴시 프로파일링 & 최종 데이터셋 가이드
> **담당자:** 유재민 (22101498 / Domain Dev & QA)  
> **해당 기간:** 12주차 ~ 16주차 (2026.11.16 ~ 2026.12.20)  
> **핵심 산출물:** `tests/benchmarks/latency_profiler.py`, `dataset/final_benchmark_results.csv`, 논문용 정량 그래프 데이터  
> **선행 조건:** Phase 4 실증 벤치마크 완료

---

## 1. Phase 5 & 6 개발 목표 및 완료 기준 (Definition of Done)

- [ ] **12~13주차 DoD:** 전체 E2E 방어 반응 시간(피처 추출 <5ms + AI 추론 <10ms + OpenFlow 플로우 주입 <30ms) 100ms 미만 달성 검증
- [ ] **13주차 DoD:** 대용량 파일 다운로드 등 정상 트래픽 급증(Flash Crowd) 시 공격으로 오탐하지 않도록 Isolation Forest 임계치 튜닝 (FPR < 1.0%)
- [ ] **14~15주차 DoD:** 4단계 E2E 시나리오 풀코스에 대한 최종 벤치마크 데이터셋 추출 및 논문용 비교 차트(Loss Rate, RTT, Table Entry) 생성
- [ ] **16주차 DoD:** 심사위원 기술 질의 대비 머신러닝 모델의 수학적 근거 및 실시간성 방어 답변 준비

---

## 2. E2E 레이턴시 프로파일러 (`tests/benchmarks/latency_profiler.py`)

```python
# 전체 E2E 지연시간 분해 측정기
import time

def profile_defense_lifecycle():
    t0 = time.perf_counter()
    # 1. Feature Extraction (포트 통계 -> 5대 피처)
    t1 = time.perf_counter()
    # 2. AI Anomaly Inference (Isolation Forest)
    t2 = time.perf_counter()
    # 3. Redis Alert Publish & Ryu Handler Receive
    t3 = time.perf_counter()
    # 4. OpenFlow Flow-Mod (In_port Drop + Bypass Add)
    t4 = time.perf_counter()
    
    print(f"Feature Ext: {(t1-t0)*1000:.2f}ms")
    print(f"AI Inference: {(t2-t1)*1000:.2f}ms")
    print(f"IPC Transfer: {(t3-t2)*1000:.2f}ms")
    print(f"Flow Injection: {(t4-t3)*1000:.2f}ms")
    print(f"Total E2E: {(t4-t0)*1000:.2f}ms (Target: < 100ms)")
```
