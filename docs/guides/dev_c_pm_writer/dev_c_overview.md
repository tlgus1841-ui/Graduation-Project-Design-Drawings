# 📙 [PM & Tech Writer] 김관우 프로젝트 관리 및 산출물 총괄 개요
> **성명:** 김관우 (22102237)  
> **직책:** PM & Tech Writer (팀장)  
> **책임 영역:** 마일스톤 관리, 지도교수님 정기 보고, 방어 시나리오 기획, 웹 관제 UI/UX 기획 및 검수, 최종 졸업논문 및 10장 PPT 슬라이드 제작 총괄  
> **기준 문서:** `docs/planning/ai_harness_engineering_plan.md`, `docs/planning/schedule_and_milestones.md`

---

## 1. 역할 정의 및 관리 권한

PM & Tech Writer는 프로젝트의 전체 개발 진도를 조율하고, 기술적 성과를 학과 심사 기준 및 대외 발표 양식에 맞춰 완벽한 문서와 시연 시나리오로 변환하는 프로젝트 총괄자입니다.

### 1.1 담당 문서 및 기획/산출물 영역
- `docs/planning/`: 주차별 마일스톤 추적, 리스크 관리, 정기 계획 수정
- `docs/reports/`: 매주 학과에 제출하는 A4 주간 진행 보고서 작성 및 취합
- `docs/specs/`: 4단계 방어 시나리오(Normal ➔ Attack ➔ Mitigated ➔ Restored) 명세서
- `ui/`: 웹 관제탑 대시보드(React 18 + Tailwind) 사용자 인터페이스 레이아웃 기획 및 렌더링 검수
- `docs/thesis/`: 최종 졸업작품 논문(보고서) 본문 집필 및 초안 감수
- `docs/proposal/`: 최종 심사용 10장 PPT 슬라이드 대본 및 라이브 시연 대본(Script) 총괄

### 1.2 핵심 프로젝트 관리 책임
1. **주간 마일스톤 추적 및 A4 보고서 제출:** 매주 금요일 팀원들(박시현, 유재민)의 정량 검증 데이터를 취합하여 A4 규격 주간 보고서 작성 및 지도교수님 대면 보고 주관.
2. **방어 시나리오 정의:** 공격 유형 및 자가 치유 라이프사이클을 단계별 상태 전이도로 기획하여 Tech Lead와 AI 엔지니어에게 규격 제시.
3. **웹 관제탑 시각화 품질 검수:** 관리자 관점에서 네트워크 토폴로지 동적 변화(녹색 ➔ 적색 ➔ 청색)와 경보 타임라인이 직관적인지 감수.
4. **최종 발표 및 데모 리허설:** 15~16주차 라이브 시연을 위한 원클릭 시연 대본 작성 및 심사위원 예상 질의응답 대비.

---

## 2. 주차별 가이드 바로가기

* [Phase 1 (1~3주차): 기획서 확정 및 마일스톤 관리 (회고)](phase1_charter_milestones.md)
* [Phase 2 (4~7주차): 방어 시나리오 명세 및 관제 UI 기획/검수 (당면 과제)](phase2_defense_scenario_web_spec.md)
* [Phase 3 (8주차): A4 중간 보고서 작성 및 교수님 중간 평가](phase3_midterm_report_lead.md)
* [Phase 4 (9~11주차): 방어 시나리오 실증 검증서 및 UI 경보 감수](phase4_mitigation_verification.md)
* [Phase 5 & 6 (12~16주차): 사용자 매뉴얼, 최종 논문, 10장 PPT 슬라이드, 시연 총괄](phase5_6_thesis_ppt_demo.md)
