# 9주차 실증 검증서: IP 스푸핑 공격 시 플로우 테이블 폭발 방어

| 항목 | 내용 |
|:---|:---|
| 작성 | 김관우 (PM & Tech Writer) |
| 측정일 | 2026.10.07 |
| 대상 | `ryu/app/controller.py` (main `e1ba60e`), `traffic/traffic_attack.py` |
| 측정 도구 | `harness/verification/flow_table_check.py` |
| 원본 데이터 | [`data/week09_flow_table_check.json`](data/week09_flow_table_check.json) |

## 1. 검증 목적

공격기는 패킷마다 출발지 IP를 무작위로 바꾼다. 컨트롤러가 출발지 IP나 5-튜플(출발지·목적지 IP와 포트, 프로토콜)을 기준으로 규칙을 만들면, 공격 패킷 하나마다 새 규칙이 생겨 스위치 플로우 테이블이 가득 찬다. 그러면 정상 트래픽용 규칙도 설치할 수 없게 된다. 이것이 **플로우 테이블 폭발**이다.

이 검증서는 공격이 진행되는 동안 스위치의 규칙 개수가 늘어나지 않는지를 실제 Mininet에서 측정한다.

## 2. 측정 방법

1. 다이아몬드 토폴로지(`topo/diamond_topo.py`)와 Ryu 컨트롤러, Redis를 실행한다.
2. `pingall`로 기본 통신을 확인한다. 이때 기본 경로 규칙이 설치된다.
3. H_attacker에서 공격기를 10초 실행한다.
4. 공격 전과 공격 중 1초마다 S1~S4의 플로우 개수를 기록한다(`ovs-ofctl dump-flows`).
5. S1:2(공격자 포트)의 수신 카운터 차이로 실제 주입량을 계산한다.

```bash
sudo python3 -m harness.verification.flow_table_check --duration 10 --out flow_check.json
# OVS 커널 모듈이 없는 환경(WSL 등): --userspace 추가
```

환경: Mininet 2.3, Open vSwitch(유저스페이스 데이터패스), Ryu 4.34 (Python 3.8, `ryu/Dockerfile.ryu`와 같은 버전), Redis 7.

## 3. 측정 결과

| 항목 | 결과 |
|:---|:---:|
| `pingall` 손실률 | **0%** |
| S1:2로 들어온 공격 패킷 | **18,103개** (11.5초) |
| 실제 주입 속도 | 약 1,571 PPS |
| 서로 다른 출발지 IP | 패킷마다 무작위 (공격기 설계) |

### 스위치별 플로우 개수

| 스위치 | 공격 전 | 공격 중 최대 | 증가 |
|:---:|:---:|:---:|:---:|
| S1 | 4 | 4 | **0** |
| S2 | 4 | 4 | **0** |
| S3 | 1 | 1 | **0** |
| S4 | 4 | 4 | **0** |

S1에서 1초 간격으로 기록한 개수는 13번 모두 4로 같았다.

### 공격 직후 S1 플로우 테이블

```
priority=10,ip,nw_dst=10.0.0.1 actions=output:"s1-eth1"   n_packets=3
priority=10,ip,nw_dst=10.0.0.2 actions=output:"s1-eth2"   n_packets=3
priority=10,ip,nw_dst=10.0.0.4 actions=output:"s1-eth3"   n_packets=18105
priority=0 actions=CONTROLLER:65535                        n_packets=8
```

공격 패킷 18,103개가 모두 **목적지 10.0.0.4 규칙 하나**에 걸렸다. 출발지 IP가 매번 달라도 새 규칙은 생기지 않았다.

## 4. 해석

- 컨트롤러는 **목적지 IP(`ipv4_dst`)만으로** 규칙을 만든다. 출발지가 몇 개든 서버로 가는 규칙은 하나다.
- 그래서 IP 스푸핑 공격으로는 규칙 수를 늘릴 수 없고, 플로우 테이블 폭발은 일어나지 않는다.
- Table-Miss로 컨트롤러에 올라간 패킷은 8개뿐이다. 공격 트래픽이 컨트롤러에 부담을 주지 않는다.

**판정: 통과.** IP 스푸핑 SYN Flood 동안 플로우 테이블 증가 0.

## 5. 한계와 후속 검증

- 현재 컨트롤러는 공격 패킷도 서버로 그대로 전달한다. 공격을 막는 **In_port 차단 규칙(Priority 100)**은 9주차 Tech Lead 작업이다.
- 차단 규칙이 들어오면 같은 스크립트로 다음을 추가 확인한다.

| 확인 항목 | 기대 결과 |
|:---|:---|
| S1 플로우 개수 | 공격 전 대비 **+1** (차단 규칙 1개만 추가) |
| 차단 규칙 `n_packets` | 공격 패킷 수만큼 증가 |
| 서버행 규칙 `n_packets` | 공격 중 더 이상 늘지 않음 |
| 정상 호스트 ping | 계속 성공 |

- 측정은 유저스페이스 OVS에서 했다. 규칙 개수는 데이터패스 종류와 무관하지만, 주입 속도(PPS)는 커널 데이터패스에서 더 높게 나올 수 있다.
