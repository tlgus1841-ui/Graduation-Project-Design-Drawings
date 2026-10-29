# 🏛️ Core Architecture & SDN Rules (02_architecture.md)

AI 에이전트는 컨트롤러, 네트워크 토폴로지, 탐지 엔진 수정 시 아래 원칙을 엄격히 준수해야 합니다.

---

## 1. Ryu 컨트롤러 동기 블로킹 절대 금지 (Non-Blocking Event Loop)
* Ryu는 파이썬의 `eventlet` 코루틴 기반으로 동작합니다.
* Scikit-learn 추론, 무거운 CPU 계산, 동기 파일 I/O, 블로킹 소켓 호출을 Ryu 내부 스레드에서 직접 실행하지 마십시오.
* 위반 시 Ryu의 이벤트 루프가 멈춰 스위치와의 OpenFlow Keepalive(Echo)가 실패하여 스위치 연결이 끊어집니다.
* **해결 원칙:** 통계는 Redis로 비동기 송출하고, AI 추론은 독립 프로세스(`model/inference_worker.py`)에서 수행한 뒤 제어 명령만 Redis로 수신합니다.

---

## 2. Ingress 물리 포트(`in_port`) 단일 격리 원칙
* 공격자는 Scapy 등으로 출발지 IP를 무작위 변조(IP Spoofing)하여 공격합니다.
* 출발지 IP마다 Drop 규칙을 주입하면 스위치 플로우 테이블이 고갈(Flow Table Exhaustion)됩니다.
* **해결 원칙:** 출발지 IP가 아닌, 공격 패킷이 유입된 **스위치 물리 포트(`in_port`)에 단일 차단 규칙(`Priority 100 Drop`)을 주입**하여 플로우 테이블 폭발을 방지합니다.

---

## 3. 선제적 다중 홉 우회 라우팅 (Autonomous Rerouting)
* 단일 스위치에서 `OFPFC_MODIFY`만 실행하면 중간 경유 스위치에 룰이 없어 패킷이 드랍됩니다.
* **해결 원칙:** Dijkstra 알고리즘으로 계산된 대체 우회 경로(S1-S3-S4) 상의 모든 경유 스위치에 **선제적으로 플로우 규칙을 주입(`OFPFC_ADD`)**한 뒤 진입 스위치 경로를 전환하여 **정상 트래픽 손실 0.0%**를 유지합니다.

---

## 4. FSM 기반 라우팅 플래핑 방지
* 단순 시간 초과(Timeout)에만 의존해 복원하면 공격 지속 중 플래핑(Route Flapping)이 발생합니다.
* **해결 원칙:** 명시적 FSM 상태 머신(`Normal` → `Under Attack` → `Mitigated` → `Restoring`)을 통해 공격 소멸 여부를 검증한 후 안전하게 기본 경로로 복귀시킵니다.
