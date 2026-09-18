# 🤖 [제5편] AI 기반 실시간 이상 탐지 (Isolation Forest & 5대 SDN 피처)

> ⬅️ [제4편: 네트워크 보안 & In_port 방어](./04_Network_Security_and_DDoS_Defense.md) | 🏠 [목차](./README.md) | ➡️ [제6편: 분산 IPC & FastAPI WebSocket](./06_Distributed_System_and_FastAPI.md)

본 문서는 왜 본 프로젝트에서 **비지도 학습(Unsupervised Learning)** 기반의 **Isolation Forest**를 채택했는지, OpenFlow의 원시 누적 카운터로부터 **5대 표준 파생 피처**를 엔지니어링하는 수학적 공식, 그리고 라우팅 플래핑(Flapping)을 방지하는 **FSM(유한 상태 머신)** 라이프사이클을 학습합니다.

---

## 1. 네트워크 침입 탐지에서의 머신러닝 패러다임

### 1.1 지도 학습(Supervised)의 한계와 데이터셋의 괴리
많은 연구가 CIC-DDoS2019와 같은 공개 데이터셋으로 지도 학습(Random Forest, XGBoost 등)을 시도하지만, 실제 SDN 실무 환경에서는 다음과 같은 치명적 문제가 발생합니다:
1. **DPI(심층 패킷 분석)의 불가능성:** CIC-DDoS2019의 80여 개 피처는 Wireshark로 pcap 전체를 덤프 떠서 TCP 윈도우 크기, 페이로드 플래그 비율, 양방향 패킷 지연 시간 등을 계산한 것입니다. 하지만 가상 스위치(OVS)와 SDN 컨트롤러는 회선 속도(Line-rate)를 유지하기 위해 패킷의 페이로드를 전수 검사할 수 없습니다.
2. **신종 공격(Zero-Day) 탐지 불가:** 공격자가 포트 번호나 패킷 전송 간격을 조금만 바꾸어도 지도학습 분류기는 이를 "정상"으로 오분류할 위험이 큽니다.

### 1.2 비지도 이상 탐지(Anomaly Detection)를 선택한 이유
- **"정상 상태(Normal Profile)"만 학습:** 평상시 정상 사용자(H_legit)의 트래픽 패턴(PPS, BPS, BPP)의 분포를 학습해 둡니다.
- **분포를 벗어나는 모든 이상 징후 감지:** 공격의 구체적인 유형(SYN Flood인지 UDP Flood인지)과 관계없이, 정상 경계를 급격히 벗어나는 트래픽을 즉각 "이상(Anomaly)"으로 스코어링합니다.

---

## 2. Isolation Forest (고립 산림) 알고리즘 심층 해부

Isolation Forest(아이솔레이션 포레스트)는 트리 기반의 대표적인 비지도 이상 탐지 알고리즘입니다.

### 2.1 핵심 직관: "이상치는 적고(Few), 다르다(Different)"
- **정상 데이터:** 데이터 공간 내에 빽빽하게 군집(Cluster)을 이루고 있습니다. 이를 한 점만 떼어내어 고립(Isolate)시키려면 수많은 무작위 분할선(Split)이 필요합니다 (트리의 깊이가 깊음).
- **이상치(공격) 데이터:** 정상 군집에서 멀리 떨어져 홀로 존재합니다. 무작위로 분할선을 몇 번만 그어도 아주 쉽게 다른 데이터들로부터 고립됩니다 (트리의 깊이가 매우 얕음).

```
[ 정상 데이터 (군집) ]                      [ 이상치 데이터 (공격) ]
      ●  ●●                                        ★ (초기 분할 1~2회 만에 고립됨!)
    ●● ●●● ●                                   ───────────── (Split 1)
     ●● ●●                                          
  (수십 번 잘라야 고립됨)
```

### 2.2 이상치 점수(Anomaly Score)의 수학적 정의
데이터 $x$가 $n$개의 데이터셋에서 $m$개의 iTree(Isolation Tree)를 통과할 때의 평균 탐색 경로 길이를 $E(h(x))$라고 할 때, 이상치 점수 $s(x, n)$은 다음과 같이 정의됩니다:

$$s(x, n) = 2^{-\frac{E(h(x))}{c(n)}}$$

*(여기서 $c(n)$은 $n$개의 노드를 가진 이진 탐색 트리에서의 평균 실패 경로 길이)*

- **$s \to 1$ (점수가 1에 수렴):** 경로 길이가 매우 짧음 $\to$ **명백한 이상치(공격 발생!)**
- **$s \to 0.5$ (점수가 0.5 부근):** 데이터 군집의 평균적인 깊이 $\to$ **정상 상태**
- **$s \to 0$ (점수가 0에 수렴):** 정상 군집의 가장 깊숙한 중심부

### 2.3 왜 SDN 실시간 탐지에 최적인가?
1. **$O(t \cdot \log n)$의 초고속 추론 시간:** 신경망(Deep Learning)과 달리 복잡한 행렬 곱셈이 없어 수 밀리초($\text{ms}$) 내에 스코어링이 완료됩니다.
2. **극도로 가벼운 메모리 사용량:** 경량 트리 구조체이므로 임베디드 장비나 소형 VM에서도 부담 없이 동작합니다.

---

## 3. SDN 5대 표준 파생 피처(Derived Features) 엔지니어링

Ryu의 `OFPPortStatsReply`는 단순히 스위치가 켜진 이후부터 지금까지 지나간 **누적 카운터(`rx_packets`, `rx_bytes`, `duration_sec`)**만 알려줍니다.  
이를 그대로 ML 모델에 넣으면 시간이 지남에 따라 숫자가 무한히 커지므로, **단위 시간당 변화율($\Delta$)**을 계산하는 피처 엔지니어링이 필수적입니다.

### 3.1 5대 피처 계산 공식

$$\Delta t = t_{\text{current}} - t_{\text{previous}}$$

1. **$\Delta \text{PPS}$ (Packets Per Second, 초당 패킷 수):**
   $$\Delta \text{PPS} = \frac{\text{rx\_packets}_t - \text{rx\_packets}_{t-1}}{\Delta t}$$
   - *의미:* 트래픽의 빈도. SYN Flooding 시 평소 10~50 PPS에서 수천 PPS로 급증.
2. **$\Delta \text{BPS}$ (Bytes Per Second, 초당 비트 전송률):**
   $$\Delta \text{BPS} = \frac{(\text{rx\_bytes}_t - \text{rx\_bytes}_{t-1}) \times 8}{\Delta t}$$
   - *의미:* 회선 대역폭 소모량.
3. **$\text{BPP}$ (Bytes Per Packet, 패킷당 평균 크기) ⭐ 가장 강력한 판별자:**
   $$\text{BPP} = \frac{\text{rx\_bytes}_t - \text{rx\_bytes}_{t-1}}{\text{rx\_packets}_t - \text{rx\_packets}_{t-1}}$$
   - *의미:* 정상 트래픽은 데이터 페이로드가 있어 500~1400 바이트인 반면, SYN Flood 공격 패킷은 페이로드 없이 헤더만 존재하므로 54~74 바이트로 급감!
4. **$\text{Packet Ratio}$ (송수신 패킷 비율):**
   $$\text{Ratio} = \frac{\Delta \text{rx\_packets}}{\Delta \text{tx\_packets} + 1}$$
   - *의미:* 일방적으로 쏟아붓기만 하는 비대칭 공격 트래픽 감지.
5. **$\text{Port Utilization}$ (포트 사용률 변화율):**
   $$\text{Util} = \frac{\Delta \text{BPS}}{\text{Link Max Bandwidth}} \times 100\ (\%)$$

---

## 4. 라우팅 플래핑 방지를 위한 FSM (유한 상태 머신)

단순히 타임아웃(예: 10초)으로만 롤백을 처리하면, 공격이 아직 안 끝났는데 10초 만에 원래 경로로 돌아갔다가 다시 공격을 감지하고 튕겨 나가는 **라우팅 플래핑(Route Flapping)**이 발생합니다. 이를 막기 위해 명시적 FSM을 적용합니다.

```
       [ NORMAL ] (정상 경로 S1-S2-S4)
           │
           │ Anomaly Score >= 0.70 감지
           ▼
     [ UNDER_ATTACK ] (공격 진입 포트 식별)
           │
           │ In_port Drop (Priority 100) 주입 & S3 우회 플로우 활성화
           ▼
       [ MITIGATED ] (방어 성공 & 정상 트래픽 우회 유지)
           │
           │ 3회 연속 Anomaly Score < 0.30 & PPS 정상화 (Heartbeat 검증)
           ▼
       [ RESTORING ] (공격 소멸 확인)
           │
           │ Drop 규칙 제거 & 최단 경로 S1-S2-S4 안전 롤백
           ▼
       [ NORMAL ]
```

- **능동형 하트비트 연장:** `MITIGATED` 상태에서 해당 포트에 여전히 대량의 공격 패킷이 유입되고 있다면 Drop 규칙의 수명을 연장합니다.
- **쿨다운(Cooldown) 검증:** 공격 트래픽이 완전히 멈춘 뒤 일정 주기(예: 6초) 이상 정상 상태가 유지될 때만 안전하게 기본 경로로 복귀합니다.

---

> ⬅️ [제4편: 네트워크 보안 & In_port 방어](./04_Network_Security_and_DDoS_Defense.md) | 🏠 [목차](./README.md) | ➡️ [제6편: 분산 IPC & FastAPI WebSocket](./06_Distributed_System_and_FastAPI.md)
