# 🤖 [공통] 바이브 코딩 프롬프트 5단계 표준 규격
> **문서 대상:** 전 팀원 (박시현, 유재민, 김관우)  
> **기준 규칙:** `docs/planning/ai_harness_engineering_plan.md`  
> **핵심 목적:** AI 코딩 어시스턴트(Antigravity, Cursor, Copilot) 활용 시 할루시네이션 및 아키텍처 위반을 방지하고 100% 동작 가능한 코드를 생성하기 위한 프롬프트 프레임워크

---

## 1. 바이브 코딩(Vibe Coding)의 정의와 위험성

바이브 코딩은 자연어 프롬프트를 통해 AI가 코드를 자율 생성하도록 하는 기법입니다. 그러나 SDN/보안 시스템과 같이 엄격한 하드웨어 제어 및 저지연 통신이 요구되는 환경에서는 AI가 다음과 같은 치명적인 실수를 저지르기 쉽습니다:
1. **Ryu 컨트롤러 내부 동기 연산:** `time.sleep()`이나 `model.predict()`를 컨트롤러 이벤트 루프에 작성하여 스위치 연결을 끊어버림.
2. **OpenFlow 스펙 위반:** 단일 스위치의 `OFPFC_MODIFY`로 다중 홉 우회가 된다고 착각하여 중간 스위치에서 패킷을 드롭시킴.
3. **가상환경 파편화:** 멋대로 `pip install`이나 별도 `venv`를 생성하라는 가이드를 출력함.

이를 방지하기 위해 모든 팀원은 아래의 **"원터치 개발자 신원 선언"** 및 **"5-Step 프롬프트 하네스(Prompt Harness)"** 구조를 준수하여 AI에 프롬프트를 입력해야 합니다.

---

## 2. 세션 시작 시 원터치 개발자 신원 선언 ("내가 [이름]이야")

팀원 각자의 컴퓨터에서 AI 어시스턴트(Cursor, Antigravity 등)와의 첫 대화를 시작할 때, 아래와 같이 한 마디만 입력하면 프로젝트 루트의 `.cursorrules`에 의해 AI가 즉시 개발자의 신원과 역할을 파악하고 최적화된 모드로 응답합니다.

```markdown
"내가 [이름]이야" (예: "내가 박시현이야", "내가 유재민이야", "내가 김관우야")
```

### 💡 AI의 자동 반응 및 전환 프로세스
1. **신원 및 환경 인식:** `"아, [직책] [이름] 개발자님 컴퓨터(환경)이군요! 반갑습니다."` 응답 출력.
2. **권한 및 작업 디렉토리 바인딩:**
   - **박시현 (Tech Lead):** `harness/`, `topo/`, `ryu/`, `tests/harness/` ➔ [Phase 2 가이드](../dev_a_tech_lead/phase2_core_mock_harness.md)
   - **유재민 (Domain QA):** `traffic/`, `pipeline/`, `model/`, `tests/benchmarks/` ➔ [Phase 2 가이드](../dev_b_domain_qa/phase2_traffic_features_model.md)
   - **김관우 (PM & Writer):** `docs/`, `ui/`, `reports/`, `docs/specs/` ➔ [Phase 2 가이드](../dev_c_pm_writer/phase2_defense_scenario_web_spec.md)
3. **가드레일 자동 활성화:** 해당 역할에 특화된 금지 수칙(Ryu 동기 블로킹 방지, Scapy Checksum 삭제 강제 등)을 AI 에이전트의 내부 작업 원칙으로 자동 설정.

---

## 3. 5-Step 프롬프트 하네스 구조

```text
┌────────────────────────────────────────────────────────────────────────┐
│ 1. [Role & Context]      : 역할, 골든 버전 매트릭스, 시스템 제약조건 명시    │
│ 2. [Contract & Schema]   : 참조할 Pydantic 스키마 및 인터페이스 정의         │
│ 3. [Implementation Goal] : 구현할 함수/클래스/스크립트의 명확한 입출력 명세  │
│ 4. [Safety Guardrails]   : 절대 하지 말아야 할 금지 수칙(Don'ts) 선언        │
│ 5. [Verification Runner] : 코드가 작성된 후 자체 검증할 `uv run pytest` 명령  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 4. 표준 프롬프트 템플릿 (복사하여 사용)

팀원들은 아래 템플릿의 괄호 부분을 채워 AI 코딩 어시스턴트에 전달합니다:

```markdown
당신은 "Self-Defending SDN Tower" 프로젝트의 [Tech Lead / Domain Dev / PM Writer] 전문 엔지니어입니다.

[1. 환경 및 버전 제약조건 (Golden Matrix)]
- 언어 및 런타임: Python 3.10.12 (Host OS)
- 패키지 관리자: uv strictly (`uv add`, `uv run`, ./.venv)
- 컨트롤러: Ryu 4.34 (Docker python:3.8-slim 격리)
- 메시징 버스: Redis 7.2 Pub/Sub
- 통신 규격: Pydantic v2 계약 준수

[2. 계약 및 스키마 참조]
- `harness/contracts/sdn_events.py`의 [해당 Pydantic 모델명] 모델을 준수하여 입출력 데이터를 직렬화/역직렬화하십시오.

[3. 구현 목표]
- 대상 파일: `[파일 경로]`
- 구현 기능: [구체적 함수명, 클래스명, 알고리즘 로직 명시]

[4. 절대 금지 수칙 (Critical Guardrails)]
- 절대 `pip install`이나 `python -m venv`를 사용하지 마십시오.
- 절대 Ryu 내부에서 동기 블로킹 연산(time.sleep, CPU-bound ML 추론)을 호출하지 마십시오.
- 단일 스위치 수정(OFPFC_MODIFY)에 의존하지 말고, 다중 홉 우회(OFPFC_ADD) 규칙을 고려하십시오.
- 포트 격리 시 Trunk 포트를 오차단하지 않도록 화이트리스트 체크를 포함하십시오.

[5. 자체 검증 테스트 코드]
- 코드 완성 후 `tests/harness/test_[모듈명].py`에 단위 테스트를 함께 작성하고,
- `uv run pytest tests/harness/test_[모듈명].py`로 검증할 수 있도록 하십시오.
```

---

## 5. 자가 치유 피드백 루프 (Self-Healing Prompt)

AI가 생성한 코드에서 Linter 오류나 Pytest 실패가 발생했을 때는 절대 코드를 손으로 고치지 말고, 에러 출력을 그대로 에이전트에 주입하여 자가 수정을 유도합니다:

```markdown
[에러 피드백]
방금 작성한 코드에서 `uv run pytest` 실행 시 아래 에러가 발생했습니다.
기존 아키텍처 규칙과 Pydantic 계약을 훼손하지 않는 선에서 원인을 분석하고 코드를 자가 수정(Self-Healing)해 주세요.

[Error Log]
<터미널 에러 내용 붙여넣기>
```
