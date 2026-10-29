# 📝 Changelog Protocol (05_changelog.md)

AI 에이전트와 개발자는 작업 완료 즉시 [CHANGELOG.md](file:///home/tlgus/programming/Self_Defending_SDN_Tower/CHANGELOG.md)에 작업 내역을 기록해야 합니다.

---

## 1. 기록 시점 및 위치
1. **기록 시점:** 코드 작성/수정, 아키텍처/폴더 변경, 인터페이스 수정 작업 완료 직후.
2. **작성 위치:** `CHANGELOG.md`의 `## 📋 변경 이력 (Latest Changes)` 바로 아래 **최상단**에 새 블록을 추가합니다.

---

## 2. 필수 작성 양식 (Template)

```markdown
### [YYYY-MM-DD] <작업 유형>(<스코프>): <작업 요약 제목>
* **작업자:** <이름> (<역할>) with <AI 에이전트명>
* **작업 유형:** `Feat` | `Fix` | `Refactor` | `Docs` | `Test` | `Chore`
* **배경:** 왜 이 변경을 진행했는지에 대한 핵심 이유 및 배경 설명.
* **주요 변경 파일:**
  - `path/to/file.py`: 어떤 로직을 어떻게 수정/추가했는지 상세 기술
* **영향 범위 및 주의사항 (Breaking Changes):** 기존 기능에 미치는 영향 및 호환성 여부 (없으면 "없음")
* **검증:** 수행한 테스트 결과 명시 (`pytest` 통과 개수, `flake8` 결과 등)
* **다음 작업자 인수인계 메모:** 다음 작업자가 이어받아 진행해야 할 핵심 사항이나 주의점
```
