# ⚙️ Environment & Runtime Rules (01_environment.md)

AI 에이전트는 코드 작성, 패키지 관리, 명령어 실행 시 아래 환경 규칙을 엄격히 준수해야 합니다.

---

## 1. 패키지 및 가상환경 관리 (`uv` 엄격 사용)
* **절대 금지:** `pip install`, `pip uninstall`, `python -m venv`, `virtualenv` 명령어를 직접 사용하지 마십시오.
* **패키지 추가:** 반드시 `uv add <package>` 명령어를 사용합니다. (개발 의존성은 `uv add --dev <package>`)
* **스크립트/테스트/서버 실행:** 반드시 `uv run <command>` 또는 `.venv/bin/<command>`를 사용합니다.
* **가상환경 경로:** 프로젝트 루트의 `./.venv` 단일 환경만 사용합니다.

---

## 2. 런타임 분리 (Golden Version Matrix)
* **SDN 컨트롤러 (Ryu 4.34):**
  - Python 3.8 공식 Docker 컨테이너(`python:3.8-slim`, `--net=host`)로 격리 구동합니다.
  - 호스트의 Python 3.10 환경에 Ryu를 직접 설치하거나 의존성을 주입하지 마십시오. (greenlet/eventlet 빌드 충돌 발생)
* **AI 모델 / 웹 백엔드 / 테스트 하네스:**
  - 호스트 OS의 **Python 3.10** 환경(`uv`)에서 구동합니다.
* **IPC 브로커 (Redis 7.2):**
  - Docker 컨테이너(`redis:7.2-alpine`, 포트 6379)를 사용하여 컴포넌트 간 비동기 통신을 담당합니다.
* **웹 프론트엔드 (React 18.2):**
  - Node.js 20 LTS 환경에서 `npm install` 및 `npm run dev`로 구동합니다.
