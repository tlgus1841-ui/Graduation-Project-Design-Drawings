# 📗 [Domain Dev & QA] Phase 1: uv 환경 구축 & 피처 스펙 확립 (회고)
> **담당자:** 유재민 (22101498 / Domain Dev & QA)  
> **해당 기간:** 1주차 ~ 3주차 (2026.08.31 ~ 2026.09.20)  
> **상태:** **완료 (Completed & Frozen)**

---

## 1. Phase 1 완료 핵심 산출물 요약

1. **Host Python 3.10 `uv` 단일 가상환경 구축:**
   - `uv`를 통해 Scapy 2.5, Scikit-learn 1.3.2, Pandas 2.1.4, NumPy 1.24.3, Redis 5.0.1 고정 의존성 설치 완료.
2. **실시간 5대 SDN 파생 피처 스펙 확정:**
   - 무거운 L7 CIC-DDoS2019 공개 피처의 한계를 인식하고, Ryu 포트 카운터 기반 실시간 계산 가능한 $\Delta \text{PPS}$, $\Delta \text{BPS}$, $\text{BPP}$, $\text{ERR\_Rate}$, $\text{Duration}$ 5대 지표 선정.
3. **Scapy 패킷 엔진 환경 검증:**
   - Ubuntu 22.04 LTS에서 Scapy Raw Socket 송수신 권한 및 Linux 커널 Checksum Offload 제약 분석 완료.
