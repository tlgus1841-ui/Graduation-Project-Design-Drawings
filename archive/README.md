# 📦 Archive (레거시 자산 보관소)

본 디렉토리는 Phase 6-A 이전(Mininet 에뮬레이터 의존 환경)에 사용되었던 레거시 코드 및 토폴로지 구성 요소를 보관하는 아카이브 영역입니다.

## 아카이브 목록
* **`topo/diamond_topo.py`**:
  - 과거 Phase 1~5에서 Mininet 파이썬 API(`mininet.topo.Topo`, `mininet.net.Mininet`)를 통해 가상 4-스위치 다이아몬드 토폴로지를 생성하던 에뮬레이션 스크립트.
  - **현재 대체 구현**: Phase 6-A 이후 순수 리눅스 커널 OVS 및 `ip netns` 기반 프로덕션 스크립트(`scripts/setup_native_ovs.sh`, `scripts/prod_stack.sh`)로 100% 완전 대체됨.
