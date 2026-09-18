# ⚙️ [공통] uv 패키지 매니저 및 통합 개발 환경 가이드
> **문서 대상:** 전 팀원 (박시현, 유재민, 김관우)  
> **기준 규칙:** `docs/planning/environment_rules.md`, `docs/planning/roadmap_v2.md`  
> **핵심 원칙:** `pip install` 및 `python -m venv` 절대 금지, `uv` 및 `./.venv` 단일 환경 표준 준수

---

## 1. uv 도입 배경 및 핵심 규칙

본 프로젝트는 SDN 컨트롤러, AI 머신러닝, 비동기 웹 관제 백엔드가 융합된 복합 시스템입니다. 이전의 개별 `venv-ai`, `venv-web` 가상환경 분리는 버전 불일치와 환경 오염 문제를 유발했으므로, **최신 Rust 기반 고속 패키지 관리자인 `uv`를 프로젝트 단일 표준으로 강제**합니다.

### 1.1 환경 골든 룰 (`environment_rules.md`)
1. **Python 패키지 관리자는 오직 `uv`만을 사용합니다.**
2. **`pip install` 또는 `python -m venv` 명령어를 터미널에서 직접 실행하지 마십시오.**
3. **가상환경은 프로젝트 루트의 `./.venv`에 단일 위치하며, `uv`가 자동으로 관리합니다.**
4. **패키지 추가 시:** `uv add <package>`
5. **스크립트, 서버, 테스트 실행 시:** 반드시 `uv run <command>` 사용

---

## 2. 골든 버전 런타임 이원화 구조

| 컴포넌트 계층 | 대상 모듈 | 실행 환경 | 의존성 관리 방식 |
|---|---|---|---|
| **AI / 웹 백엔드 / 테스트** | • `traffic/` (Scapy)<br>• `pipeline/` (피처 추출)<br>• `model/` (Isolation Forest)<br>• `harness/` (테스트 하네스/계약)<br>• `api/` (FastAPI / WebSocket) | **Host OS Python 3.10.12**<br>(프로젝트 루트 `./.venv`) | **`uv` 기반 패키지 관리**<br>`pyproject.toml` 및 `uv.lock`으로 100% 재현 |
| **SDN 제어 평면 (Ryu)** | • `ryu/app/controller.py`<br>• OpenFlow 1.3 스위칭/라우팅<br>• 포트 통계 수집기 | **Docker 컨테이너**<br>(`python:3.8-slim`, `--net=host`) | **Docker 격리 빌드**<br>Ryu 4.34 및 Eventlet 0.30.2 전용 격리 |

> [!WARNING]
> **Ryu를 호스트 Python 3.10 환경에 직접 `uv add ryu`로 설치하려고 시도하지 마십시오.**  
> Ryu는 Python 3.10+에서 `collections.abc` 및 `greenlet` C-확장 모듈 비호환성으로 인해 빌드가 영구 실패합니다. Ryu는 반드시 공식 제공되는 Docker 컨테이너 내부에서만 구동해야 합니다.

---

## 3. 일상 개발 워크플로우 치트시트

### 3.1 신규 패키지 추가
```bash
# 기본 라이브러리 추가
uv add scikit-learn==1.3.2 scapy==2.5.0 pandas==2.1.4 numpy==1.24.3
uv add fastapi==0.109.2 uvicorn==0.27.1 pydantic==2.6.1 redis==5.0.1

# 개발 및 테스트 전용 패키지 추가
uv add --dev pytest pytest-asyncio flake8 mypy
```

### 3.2 스크립트 및 테스트 실행
가상환경을 `source .venv/bin/activate`로 매번 켤 필요 없이, `uv run` 접두사로 즉시 일관된 환경에서 실행합니다.

```bash
# 단위 테스트 하네스 실행
uv run pytest tests/harness/test_mock_ipc.py -v

# Scapy 정상 트래픽 생성기 실행 (루트 권한 필요 시)
sudo uv run python traffic/traffic_normal.py

# AI 파이프라인 피처 추출기 실행
uv run python pipeline/feature_extractor.py

# FastAPI 웹소켓 서버 구동
uv run uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 4. 팀원별 환경 구성 검증 체크리스트

1. [ ] `which uv` 명령어로 `uv` 바이너리가 정상 인식되는지 확인 (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
2. [ ] 프로젝트 루트에서 `uv sync`를 실행했을 때 `./.venv`가 정상 구성되는지 확인
3. [ ] `uv run python --version` 출력 시 Python 3.10.x로 표시되는지 확인
4. [ ] AI 에이전트(Cursor / Antigravity) 프롬프트에 `uv run` 명령 형식을 지시하고 있는지 확인
