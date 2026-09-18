# 🛠️ [제8편] 개발 환경, Docker 네트워킹 & 실전 트러블슈팅 가이드

> ⬅️ [제7편: 웹 관제탑 프론트엔드 React](./07_Frontend_Visualization_React.md) | 🏠 [목차](./README.md)

본 문서는 본 프로젝트를 진행하며 팀원들이 가장 흔하게 겪는 **환경 설정 충돌, 도커 네트워크 원리, 그리고 7가지 치명적인 기술적 함정(Pitfalls)**과 그 명쾌한 해결책을 총정리한 실전 가이드입니다.

---

## 1. 프로젝트 환경 규칙 (Project Rules)

본 프로젝트는 의존성 지옥을 원천 차단하기 위해 작업 환경을 엄격히 규격화했습니다:

### 1.1 `uv` 패키지 매니저 사용 원칙
- 파이썬 환경 관리 시 전통적인 `pip install` 또는 `python -m venv` 대신, 초고속 Rust 기반 패키지 매니저인 **`uv`를 엄격히 사용**합니다.
- 패키지 추가: `uv add <package>` (예: `uv add scikit-learn`)
- 스크립트/서버 실행: `uv run <command>` (예: `uv run uvicorn ...`)
- 가상환경 위치: `./.venv`

### 1.2 Python 런타임 이원화 구조의 필연성
- **SDN 제어 평면 (Ryu):** `python:3.8-slim` Docker 컨테이너에서 격리 실행.
- **AI 추론 & 웹 백엔드 (FastAPI):** Host OS (Ubuntu 22.04 LTS) 네이티브의 Python 3.10 가상환경에서 실행.

---

## 2. Docker `--net=host` 모드의 핵심 원리

도커 컨테이너를 실행할 때 포트 포워딩(`-p 6653:6653`)을 쓰지 않고 왜 반드시 **`--net=host`** 모드를 써야 할까요?

### 2.1 도커 기본 브리지(`docker0`)의 한계
- 기본 브리지 모드에서 도커 컨테이너는 호스트와 격리된 별도의 가상 네트워크 네임스페이스와 사설 IP(예: `172.17.0.2`)를 부여받습니다.
- 호스트의 Mininet OVS 스위치들이 컨트롤러로 접속할 때 기본 대상 주소는 로컬 루프백(`127.0.0.1:6653`)입니다.
- 브리지 모드에서는 호스트의 `127.0.0.1`과 컨테이너 내부의 `127.0.0.1`이 완전히 다른 격리 공간이므로, **OVS 스위치와 Ryu 컨트롤러 간의 TCP 핸드셰이크가 100% 실패**합니다.

### 2.2 `--net=host` 모드의 해결책
- 컨테이너가 독자적인 네트워크 스택을 생성하지 않고, **호스트 머신의 네트워크 네임스페이스를 그대로 공유**합니다.
- 컨테이너 내부의 Ryu가 `0.0.0.0:6653`을 바인딩하면, 호스트 OS의 실제 네트워크 인터페이스 및 `127.0.0.1`에 즉시 직접 노출됩니다.
- OVS 스위치, Redis, Ryu 간의 통신 오버헤드가 제로가 되며 네임스페이스 격리로 인한 통신 불능 문제가 원천 해결됩니다.

---

## 3. 프로젝트 진행 중 마주치는 7대 치명적 함정과 해결책

개발 중 에러가 발생하면 가장 먼저 이 체크리스트를 확인하십시오.

---

### 🔥 [함정 1] Python 3.10+ 환경에서 Ryu 설치 시도 시 빌드 실패
* **증상:** `pip install ryu` 실행 시 `greenlet` C-확장 모듈 컴파일 실패, `collections.abc` 관련 `ImportError` 발생.
* **원인:** Ryu 프레임워크가 수년 전 Python 3.8 기준으로 개발이 동결되었기 때문.
* **해결책:** 호스트 파이썬에 Ryu를 설치하려 하지 말고, 미리 준비된 **Python 3.8 Docker 이미지**를 빌드하여 컨테이너로만 구동하십시오.

---

### 🔥 [함정 2] Ryu 내부에서 AI 추론 실행 시 OVS 스위치 연결 해제 (Switch Drop)
* **증상:** Scikit-learn 모델을 Ryu 스레드에서 돌리자마자 `Connection reset by peer`, `Echo Request timeout` 로그가 찍히며 스위치가 전부 떨어짐.
* **원인:** Ryu의 `eventlet` 그린 스레드가 CPU 집약적인 머신러닝 연산 동안 멈춰버려 스위치와의 생존 확인(Keepalive)을 실패함.
* **해결책:** AI 추론 엔진은 **별도의 독립 파이썬 프로세스(`ai_worker.py`)**로 실행하고, Ryu와는 **Redis Pub/Sub** 비동기 메시지로만 소통하십시오.

---

### 🔥 [함정 3] Mininet 비정상 종료 후 재실행 시 "Device or resource busy" 에러
* **증상:** `Cannot create interface`, `Port s1-eth1 already exists` 에러와 함께 토폴로지 생성이 중단됨.
* **원인:** 이전 Mininet 프로세스가 강제 종료(Ctrl+C)되면서 리눅스 커널에 가상 인터페이스(`veth`)와 OVS 브리지가 남아있음.
* **해결책:** Mininet 실행 전 반드시 정리 명령어를 실행하십시오:
  ```bash
  sudo mn -c
  ```

---

### 🔥 [함정 4] OVS 인터페이스 이름과 OpenFlow 포트 번호 불일치
* **증상:** Mininet 스크립트에서는 1번 링크에 연결했는데, Ryu에서는 `in_port`가 2번이나 3번으로 찍혀 엉뚱한 포트가 차단됨.
* **원인:** OVS가 인터페이스를 바인딩할 때 리눅스 커널 인터페이스 인덱스와 OpenFlow 프로토콜의 `ofport` 번호가 다르게 매핑될 수 있음.
* **해결책:** 
  1. Mininet 스크립트 작성 시 `self.addLink(h1, s1, port2=1)`처럼 포트를 명시적으로 고정하십시오.
  2. Ryu 핸드셰이크 시 `OFPPortDescStatsReply`를 파싱하여 스위치 포트 매핑 딕셔너리를 관리하십시오.

---

### 🔥 [함정 5] Scapy 모의 패킷이 수신측에서 증발 (Checksum Offload 오류)
* **증상:** 공격 호스트에서 Scapy로 SYN Flood를 쐈는데, OVS 스위치나 서버의 통계 카운터가 전혀 올라가지 않음.
* **원인:** 가상 인터페이스 환경에서 Scapy가 계산하지 않은 빈 체크섬을 리눅스 커널이 불량 패킷으로 간주하여 드랍함.
* **해결책:** Scapy 패킷 전송 직전 반드시 체크섬 재계산을 강제하십시오:
  ```python
  del pkt[IP].chksum
  del pkt[TCP].chksum
  ```

---

### 🔥 [함정 6] 커널 역방향 경로 필터링(`rp_filter`)으로 인한 스푸핑 패킷 차단
* **증상:** 공격자 호스트에서 출발지 IP를 변조(`IP(src="1.2.3.4")`)하여 쐈는데 패킷이 가상 랜선 밖으로 나가지 못함.
* **원인:** 우분투 커널의 `rp_filter` 보안 기능이 비정상 발신지 IP 패킷을 커널 레벨에서 폐기함.
* **해결책:** 호스트 OS에서 다음 명령으로 필터를 완화하십시오:
  ```bash
  sudo sysctl -w net.ipv4.conf.all.rp_filter=0
  sudo sysctl -w net.ipv4.conf.default.rp_filter=0
  ```

---

### 🔥 [함정 7] 시작 스위치만 `OFPFC_MODIFY` 하여 우회 경로 패킷 유실
* **증상:** S1 스위치의 출력 포트를 S3(우회 스위치)로 바꿨는데 패킷이 S4 목적지 서버에 도달하지 못하고 끊김.
* **원인:** S3 스위치 내부에는 해당 패킷을 S4로 보내라는 플로우 규칙이 아직 설치되지 않았기 때문.
* **해결책:** 우회 경로 전환 시, **중간 경유 스위치(S3)에 먼저 `OFPFC_ADD`로 포워딩 규칙을 심은 뒤**, 시작 스위치(S1)의 출력을 전환하십시오.

---

## 4. 1분 스모크 테스트 (Smoke Test) 명령어

개발 환경이 정상적으로 갖추어졌는지 1분 만에 점검하는 검증 명령어들입니다:

```bash
# 1. Mininet 기본 에뮬레이션 정상 동작 확인
sudo mn --test pingall

# 2. Redis 브로커 컨테이너 동작 확인
docker compose exec redis redis-cli ping
# 기대 출력: PONG

# 3. Python 핵심 라이브러리 임포트 검증
uv run python -c "import scapy, sklearn, fastapi, uvicorn, pydantic, redis; print(' All Core Modules OK!')"

# 4. OVS 데몬 정상 동작 확인
sudo ovs-vsctl show
```

---

> ⬅️ [제7편: 웹 관제탑 프론트엔드 React](./07_Frontend_Visualization_React.md) | 🏠 [목차](./README.md)
