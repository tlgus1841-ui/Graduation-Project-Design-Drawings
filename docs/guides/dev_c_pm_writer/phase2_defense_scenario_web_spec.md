# 📙 [PM & Tech Writer] Phase 2: 방어 시나리오 명세 & 관제 UI 기획/검수 가이드
> **담당자:** 김관우 (22102237 / PM & Tech Writer, 팀장)  
> **해당 기간:** 4주차 ~ 7주차 (2026.09.21 ~ 2026.10.18)  
> **핵심 산출물:** 방어 정책 명세서(`docs/specs/defense_scenarios.md`), 주간 진도 보고서 #2~#4, 관제탑 웹 UI/UX 기획서 및 스켈레톤 검수 리포트  
> **선행 조건:** Phase 1 마일스톤(팀 R&R 확정, 공식 개발 기획서 제출) 완료

---

## 1. Phase 2 관리 목표 및 주차별 상세 완료 기준 (Weekly DoD)

> **💡 Phase 2 PM/웹 미션:** 4주차부터 7주차까지 **방어 명세서 확정 ➔ 관제탑 UI 레이아웃 ➔ Redis-WS 라이브 중계 ➔ 토폴로지/시계열 차트 렌더링**으로 이어지는 관제 시스템을 구축하고 주간 진도 보고서(#2~#4)를 총괄 제출합니다.

| 주차 | 주차별 한 줄 핵심 미션 | 대상 파일 | 정량적 완료 기준 (DoD) | 팀원(A/B) 연계 포인트 |
|:---:|:---|:---|:---|:---|
| **4주차** | **4단계 자율 방어 시나리오 명세서 확정** | `docs/specs/defense_scenarios.md`<br>`api/websocket_hub.py` | • 4단계 상태 전이표 및 임계치(DoD) 동결<br>• FastAPI WebSocket Hub F5 10회 안정성 검증 | 박시현(토폴로지/하네스), 유재민(정상 트래픽) 연동 규격 제공 |
| **5주차** | **관제탑 웹 다크 테마 레이아웃 & 보고서 #2** | `ui/src/layouts/DashboardLayout.jsx`<br>`docs/writing/reports/weekly/week05_progress_report.md` | • Tailwind CSS 3.4 다크 테마 대시보드 스켈레톤<br>• WebSocket 연결 상태 배지 동작<br>• A4 주간 진도 보고서 #2 제출 | 박시현(스위칭 결과) + 유재민(공격기 데이터) 취합 보고 |
| **6주차** | **Redis Pub/Sub ➔ WebSocket 라이브 브리지** | `api/redis_bridge.py`<br>`docs/writing/reports/weekly/week06_progress_report.md` | • Redis 4채널 구독 ➔ 브라우저 실시간 중계<br>• fakeredis 기반 브리지 단위 테스트 통과<br>• A4 주간 진도 보고서 #3 제출 | 박시현(Ryu 포트 통계) 수신 ➔ ApexCharts 실시간 렌더링 |
| **7주차** | **토폴로지 지도 시각화 & 실시간 트래픽 차트** | `ui/src/components/TopologyMap.jsx`<br>`ui/src/components/TrafficCharts.jsx`<br>`docs/writing/reports/weekly/week07_progress_report.md` | • `vis-network` 다이아몬드(S1~S4) 동적 시각화<br>• `ApexCharts` 실시간 PPS·BPP 시계열 차트 스트리밍<br>• A4 주간 진도 보고서 #4 (중간점검 대비) 제출 | 유재민(AI 이상치 스코어) 연동 시 적색 경보 렌더링 준비 |

---

## 2. 주차별 작업 위치 및 산출물 매트릭스

| 주차 | 생성/검수 대상 파일 | 산출물 성격 | 연계 계획서/보고서 |
|:---:|:---|:---|:---|
| **4주차** | `docs/specs/defense_scenarios.md`<br>`api/websocket_hub.py` | 방어 시나리오 명세 / 백엔드 허브 | `docs/writing/reports/weekly/week04_traffic_normal_plan.md` |
| **5주차** | `ui/src/layouts/DashboardLayout.jsx`<br>`docs/writing/reports/weekly/week05_progress_report.md` | 관제탑 UI 스켈레톤 / 주간 보고서 | `docs/writing/reports/weekly/week05_progress_report.md` |
| **6주차** | `api/redis_bridge.py`<br>`docs/writing/reports/weekly/week06_progress_report.md` | 실시간 중계 브리지 / 주간 보고서 | `docs/writing/reports/weekly/week06_progress_report.md` |
| **7주차** | `ui/src/components/TopologyMap.jsx`<br>`ui/src/components/TrafficCharts.jsx`<br>`docs/writing/reports/weekly/week07_progress_report.md` | 토폴로지 지도 & 차트 / 주간 보고서 | `docs/writing/reports/weekly/week07_progress_report.md` |

---

## 3. 주차별 실전 기획 및 검수 워크플로우

### [4주차] 4단계 방어 시나리오 명세서 작성

팀장 김관우는 개발자 A(박시현)와 B(유재민)가 시스템을 연동할 수 있도록 명문화된 시나리오를 작성합니다.

```markdown
# [방어 시나리오 명세 가이드]
1. 1단계: 정상 상태 (Normal State)
   - 트래픽: H_legit(10.0.0.1) ➔ H_server(10.0.0.4) HTTP/Ping 통신
   - 활성 경로: S1 ➔ S2 ➔ S4 (최단 최적 경로)
   - 관제탑 표시: 모든 링크 및 노드 녹색(Green), PPS 안정(10~100)

2. 2단계: 공격 탐지 상태 (Under Attack)
   - 트래픽: H_attacker(10.0.0.2)에서 초당 3,000 PPS 무작위 IP SYN Flooding 발생
   - 탐지 지표: S1 Port 2의 BPP 급감 (64 바이트), Isolation Forest 이상치 스코어 < -0.5
   - 관제탑 표시: S1-Port 2 및 Ingress 링크 적색(Red Alert) 점멸, 이상 경보 피드 팝업

3. 3단계: 자율 차단 및 우회 상태 (Mitigated & Rerouted)
   - 제어 동작: S1 Port 2에 Priority 100 Drop 플로우 설치, Dijkstra 기반 S1 ➔ S3 ➔ S4 우회 경로 활성화
   - 관제탑 표시: 차단 포트 회색(Isolated), 우회 경로 청색(Blue Highlight), H_legit 무유실 유지

4. 4단계: 자가 치유 및 복구 (Restored State)
   - 트리거: 공격 트래픽 소멸 후 10초 쿨다운(FSM 상태 유지)
   - 복원 동작: S1 Port 2 차단 해제, 기본 경로(S1 ➔ S2 ➔ S4) 무중단 롤백
```

---

### [5주차 ~ 7주차] 웹 관제탑 시각화 검수 체크리스트

1. **Stale Connection 방어 검수:**
   - 브라우저에서 `F5`(새로고침)를 10회 연속 눌렀을 때, 백엔드 ASGI 서버(`uvicorn`)가 크래시되지 않고 웹소켓 세션을 자동 정리하는지 확인.
2. **다크 테마 SOC UI/UX 일관성:**
   - 배경 색상 (`bg-slate-900`), 텍스트 가독성, 카드 컨테이너의 높이(Height) 고정 여부 확인.
3. **토폴로지 물리 시뮬레이션 안정성:**
   - `vis-network` 노드가 마우스 드래그 후 멈추는지(Physics stabilization), 노드가 계속 진동하지 않는지 확인.

---

## 4. A4 주간 진행 보고서 작성 및 교수님 보고 주관

### A4 보고서 작성 원칙
- 매주 목요일 저녁까지 박시현(Tech Lead)과 유재민(Domain QA)의 커밋 로그 및 테스트 지표(Ping 손실률, 모델 추론 ms)를 전달받음.
- 정량적 수치(예: "100% 무유실", "추론 지연 4.2ms")를 강조하여 보고서의 신뢰도를 극대화.
- 지도교수님 대면 미팅 시 질의사항(SDN 플래핑 위험 해결 여부 등)을 기록하여 차주 일정표에 반영.

---

## 5. 팀원 인계 사항 및 협업 지침

- **박시현 (Tech Lead):** 관제탑 UI에서 스위치/호스트 클릭 시 상세 포트 통계를 모달로 띄울 수 있도록 REST API 엔드포인트 규격을 사전 조율하십시오.
- **유재민 (Domain QA):** 모델 평가 시 도출되는 ROC 커브 및 혼동행렬(Confusion Matrix) 이미지 파일을 보고서 첨부용으로 전달받으십시오.
