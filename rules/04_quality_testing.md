# 🧪 Quality & Testing Rules (04_quality_testing.md)

AI 에이전트는 코드 작성 및 수정 후 반드시 품질 검증과 회귀 테스트를 수행해야 합니다.

---

## 1. 단위 및 통합 테스트 100% 통과 원칙
* **전수 통과 필수:** 모든 코드 변경 후에는 `pytest`를 실행하여 기존 265개 테스트가 단 1건도 실패하지 않아야 합니다.
  ```bash
  uv run pytest
  # 또는 ./.venv/bin/pytest
  ```
* 신규 기능 추가 시 반드시 상응하는 단위 테스트(`tests/`)를 함께 작성해야 합니다.

---

## 2. 코드 스타일 및 린트 검사 준수
* **Flake8 스타일 가이드:**
  - 본 프로젝트는 **120자 최대 줄 길이(`--max-line-length=120`)** 규칙을 따릅니다.
  - 가상환경 및 UI는 제외하고 검사합니다:
    ```bash
    uv run flake8 --max-line-length=120 --exclude=.venv,ui
    ```
  - flake8 위반 에러가 0건이어야 합니다.
* **Mypy 타입 체크:**
  - Python 타입 힌트를 적극 유지하며, 타입 에러를 발생시키지 않도록 주의합니다.
  ```bash
  uv run mypy api model harness pipeline ryu traffic tests
  ```
