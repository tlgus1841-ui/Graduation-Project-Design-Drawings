# 🐙 [공통] 3인 협업을 위한 실전 Git & GitHub 사용 가이드
> **문서 버전:** v1.0 (2026-09-18 작성)  
> **대상 저장소:** `https://github.com/tlgus1841-ui/Graduation-Project-Design-Drawings.git`  
> **적용 대상:** 박시현(Tech Lead), 유재민(Domain QA), 김관우(PM & Tech Writer)

---

## 1. 개요 및 목적

본 가이드는 **Self-Defending SDN Tower** 프로젝트에 참여하는 3인의 개발자가 단일 GitHub 저장소에서 코드 충돌(Conflict) 없이 안전하고 일관성 있게 협업하기 위한 실전 가이드입니다.

3인의 직무와 전담 디렉토리가 엄격히 분리되어 있으므로, 본 가이드의 기본 규칙(작업 전 `git pull`, 디렉토리 격리, 커밋 컨벤션)만 준수하면 충돌 없이 원활한 병렬 개발이 가능합니다.

---

## 2. 초기 셋업: 공동 작업자(Collaborator) 등록 및 인증

GitHub 정책상 계정 비밀번호로는 `git push`를 수행할 수 없으며, **Personal Access Token (PAT)** 인증이 필수입니다.

### 2.1 저장소 소유자(박시현) 작업
1. GitHub 저장소 페이지 접속: [`https://github.com/tlgus1841-ui/Graduation-Project-Design-Drawings`](https://github.com/tlgus1841-ui/Graduation-Project-Design-Drawings)
2. 상단 메뉴 **Settings** ➔ 좌측 **Access > Collaborators** 클릭
3. 초록색 **Add people** 버튼 클릭
4. 팀원(유재민, 김관우)의 GitHub 아이디 또는 이메일 검색 후 초대장 발송

### 2.2 팀원(유재민, 김관우) 초대 수락 (필수!)
1. 본인 GitHub 가입 이메일 또는 GitHub 우측 상단 알림(종 모양) 확인
2. **View invitation** 클릭 후 **Accept invitation (초대 수락)** 버튼 클릭

### 2.3 팀원 컴퓨터에서 GitHub 인증 토큰(PAT) 발급
1. GitHub 우측 상단 프로필 사진 ➔ **Settings** 클릭
2. 좌측 최하단 **Developer settings** 클릭
3. **Personal access tokens** ➔ **Tokens (classic)** ➔ **Generate new token (classic)** 클릭
4. **Note:** `SDN-Tower-Token` 입력
5. **Expiration:** `90 days` 또는 `No expiration` 권장
6. **Select scopes:** 맨 위 **`repo` (모든 하위 항목 포함)** 체크
7. 맨 아래 **Generate token** 클릭 ➔ 생성된 토큰(`ghp_...`)을 즉시 복사하여 메모장에 보관

### 2.4 토큰 영구 저장 설정 (매번 입력 안 하는 법)
터미널에서 아래 명령어를 한 번만 실행하면 최초 푸시 시 1회만 토큰을 입력하고 영구 저장됩니다:
```bash
git config --global credential.helper store
```

### 2.5 저장소 복제 (팀원 최초 1회)
```bash
git clone https://github.com/tlgus1841-ui/Graduation-Project-Design-Drawings.git
cd Graduation-Project-Design-Drawings
```

---

## 3. 일상적인 5단계 Git 작업 워크플로우

매일 작업을 시작하고 끝낼 때 다음 5단계를 기본 루틴으로 실행합니다.

```text
[ 1. 최신 코드 받기 ] git pull origin main
         ▼
[ 2. 본인 전담 디렉토리 작업 ]
         ▼
[ 3. 변경 상태 확인 ] git status
         ▼
[ 4. 스테이징 & 커밋 ] git add <파일> ➔ git commit -m "feat: ..."
         ▼
[ 5. 원격 푸시 ] git push origin main
```

### Step 1. 작업 시작 전 항상 최신 코드 동기화
다른 팀원이 올린 최신 코드를 먼저 내려받고 작업을 시작합니다:
```bash
git pull origin main
```

### Step 2. 코드 작업 및 로컬 검증
- `.cursorrules`에 명시된 본인의 전담 디렉토리 내에서 코드를 수정/생성합니다.
- `uv run pytest` 등을 통해 코드가 정상 작동하는지 확인합니다.

### Step 3. 변경 상태 확인
어떤 파일이 수정되었거나 새로 생겼는지 확인합니다:
```bash
git status
```

### Step 4. 스테이징 및 커밋
- 특정 파일만 추가할 때: `git add <경로/파일명>`
- 수정한 모든 파일을 추가할 때: `git add .`
- 커밋 메시지 작성:
```bash
git commit -m "feat(traffic): add Scapy Poisson normal traffic generator"
```

### Step 5. 원격 저장소로 푸시
```bash
git push origin main
```
*(최초 1회에는 GitHub Username과 발급받은 PAT 토큰을 입력합니다)*

---

## 4. 3인 팀원별 전담 작업 디렉토리 규칙

우리 프로젝트는 역할별로 작업 공간이 완전히 분리되어 있습니다. 본인 영역 외의 파일을 수정해야 할 경우, 해당 담당자와 사전 상의 후 수정합니다.

| 담당자 | 역할 | 전담 디렉토리 | 절대 수정 금지 영역 (타 담당자 영역) |
|:---|:---|:---|:---|
| **박시현**<br>(Tech Lead) | 시스템 아키텍트 & 코어 | `harness/`<br>`topo/`<br>`ryu/`<br>`tests/harness/` | `traffic/`, `model/`, `ui/` |
| **유재민**<br>(Domain QA) | AI/보안 엔지니어 & QA | `traffic/`<br>`pipeline/`<br>`model/`<br>`tests/benchmarks/`<br>`dataset/` | `topo/`, `ryu/`, `harness/` |
| **김관우**<br>(PM/Writer) | PM & 웹 대시보드 기획 | `docs/`<br>`reports/`<br>`ui/` | `ryu/`, `traffic/`, `model/` |

> **공통 파일 주의:**  
> `README.md`, `.gitignore`, `pyproject.toml` 등 루트 공통 설정 파일을 수정할 때는 팀 채팅방에 사전 공유 후 커밋합니다.

---

## 5. 커밋 메시지 표준 컨벤션 (Conventional Commits)

깃 로그의 가독성과 주간 보고서 정리를 위해 아래 커밋 접두사를 표준으로 사용합니다:

| 타입 | 의미 | 예시 |
|:---:|:---|:---|
| `feat` | 새로운 기능 추가 | `feat(topo): add 4-switch diamond topology script` |
| `fix` | 버그 수정 | `fix(controller): resolve ARP storm infinite loop in S1` |
| `docs` | 문서 추가 및 수정 | `docs(planning): update week 4 milestone report` |
| `refactor` | 기능 변경 없는 코드 리팩토링 | `refactor(pipeline): optimize feature extraction loop` |
| `test` | 테스트 코드 추가/수정 | `test(harness): add mock IPC serialization test case` |
| `chore` | 환경 설정, 의존성 패키지 관리 | `chore(env): add scikit-learn dependency via uv` |

---

## 6. 자주 발생하는 문제 해결 (Troubleshooting & FAQ)

### Q1. `git push`를 했는데 `rejected - non-fast-forward (fetch first)` 오류가 납니다.
* **원인:** 다른 팀원이 먼저 `origin/main`에 푸시하여 원격 저장소가 내 컴퓨터보다 앞서 있기 때문입니다.
* **해결법:**
  ```bash
  # 원격의 최신 커밋을 받아서 내 커밋과 합침
  git pull --rebase origin main
  # 다시 푸시
  git push origin main
  ```

### Q2. `git push` 시 `Authentication failed` 오류가 발생합니다.
* **원인:** GitHub 계정 비밀번호를 입력했거나, PAT 토큰 권한(`repo`)이 만료/부족하기 때문입니다.
* **해결법:**
  1. 본인 GitHub에서 새 PAT 토큰(Classic, `repo` 체크)을 다시 발급받습니다.
  2. 터미널에서 `git push origin main` 실행 후 비밀번호 자리에 복사한 새 토큰을 붙여넣습니다.

### Q3. 실수로 충돌(Merge Conflict)이 발생했을 때 어떻게 하나요?
* **원인:** 두 명의 개발자가 같은 파일의 같은 라인을 동시에 수정했을 때 발생합니다.
* **해결법:**
  1. `git status`를 치면 `both modified: <파일명>`으로 표시됩니다.
  2. 해당 파일을 열면 아래와 같은 충돌 표시가 있습니다:
     ```text
     <<<<<<< HEAD
     내 컴퓨터에서 수정한 코드
     =======
     원격에서 받아온 팀원의 코드
     >>>>>>> origin/main
     ```
  3. 팀원과 상의하여 올바른 코드만 남기고 `<<<<<<<`, `=======`, `>>>>>>>` 줄을 깨끗이 지웁니다.
  4. 파일 저장 후:
     ```bash
     git add <충돌해결한파일명>
     git commit -m "fix(conflict): resolve merge conflict in <파일명>"
     git push origin main
     ```

### Q4. 작업 중인 코드가 있는데 잠시 `git pull`을 받아야 할 때
* 작업 중인 코드를 임시 서랍에 보관하고 최신 코드를 내려받은 뒤 꺼냅니다:
  ```bash
  git stash        # 작업 중인 변경 사항 임시 저장
  git pull origin main  # 최신 코드 받기
  git stash pop    # 임시 저장했던 작업 내용 다시 복원
  ```

### Q5. `.venv`나 임시 파일이 자꾸 `git status`에 뜹니다.
* 가상환경이나 캐시 파일은 깃에 올리면 안 됩니다. `.gitignore`에 해당 경로가 들어있는지 확인하고, 실수로 추적된 경우 아래 명령으로 깃 인덱스에서만 제거합니다:
  ```bash
  git rm -r --cached .venv
  git commit -m "chore: remove .venv from git tracking"
  ```
