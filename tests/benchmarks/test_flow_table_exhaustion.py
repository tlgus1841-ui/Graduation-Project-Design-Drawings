"""9주차 검증: 랜덤 IP 스푸핑 공격 시 플로우 테이블 고갈 방어 (week09 계획서).

박시현의 in_port 기반 Priority 100 Drop 로직(whitelist_guard.py)이 아직
이 저장소에 없어, 실제 컨트롤러 대신 두 가지 차단 전략을 모의 플로우
테이블로 시뮬레이션해 비교한다:
  A) 순진한 방법: 공격 패킷의 (스푸핑된) 출발지 IP마다 Drop 룰 추가
  B) 설계된 방법: 공격이 들어오는 in_port 하나에만 Drop 룰 추가
"""

from dataclasses import dataclass, field
from typing import Set, Tuple

from scapy.layers.inet import IP

import traffic.traffic_attack as attack_module
from traffic.traffic_attack import AttackProfile, build_syn_packet, flood_second

ATTACKER_IN_PORT = 2  # S1:2 (H_attacker), docs/specs/defense_scenarios.md §1


@dataclass
class MockFlowTable:
    """OpenFlow 스위치의 플로우 테이블을 단순화해 설치된 매치 키 집합만 추적한다."""

    entries: Set[Tuple[str, object]] = field(default_factory=set)

    def install(self, match_key: Tuple[str, object]) -> None:
        self.entries.add(match_key)

    @property
    def size(self) -> int:
        return len(self.entries)


def block_by_source_ip(table: MockFlowTable, src_ip: str) -> None:
    """전략 A (순진한 방법): 스푸핑된 출발지 IP마다 Drop 룰을 설치한다."""
    table.install(("drop_src_ip", src_ip))


def block_by_ingress_port(table: MockFlowTable, in_port: int) -> None:
    """전략 B (설계된 방법): 공격 유입 포트 하나에만 Drop 룰을 설치한다 (멱등)."""
    table.install(("drop_in_port", in_port))


def test_per_source_ip_blocking_grows_with_attack_volume():
    """IP 기반 차단은 스푸핑 공격 1,000건이면 엔트리도 거의 1,000개로 늘어 테이블이 고갈된다."""
    table = MockFlowTable()
    profile = AttackProfile(dst="10.0.0.4", dport=80)

    for _ in range(1000):
        pkt = build_syn_packet(profile)
        block_by_source_ip(table, pkt[IP].src)

    # 출발지 IP가 매번 랜덤이라 중복이 거의 없어 엔트리 수가 공격량에 거의 비례한다.
    assert table.size > 900


def test_ingress_port_blocking_stays_at_one_entry_regardless_of_attack_volume():
    """같은 공격을 in_port 기준으로 막으면 스푸핑된 IP가 몇 개든 룰은 1개로 유지된다."""
    table = MockFlowTable()
    profile = AttackProfile(dst="10.0.0.4", dport=80)

    for _ in range(5000):
        build_syn_packet(profile)  # 스푸핑된 IP는 매번 다르지만
        block_by_ingress_port(table, ATTACKER_IN_PORT)  # 포트는 고정이라 룰 1개로 충분

    assert table.size == 1


def test_ingress_port_blocking_handles_max_pps_with_one_rule(monkeypatch):
    """ATTACK_PPS 상한(5,000 PPS, 1초 분량)을 실제로 생성해도 룰 1개로 전부 막을 수 있다."""
    sent = []
    monkeypatch.setattr(attack_module, "send", lambda pkts, verbose=False: sent.extend(pkts))

    profile = AttackProfile(dst="10.0.0.4", dport=80)
    flood_second(profile, pps=5000)

    table = MockFlowTable()
    for _ in sent:
        block_by_ingress_port(table, ATTACKER_IN_PORT)

    assert len(sent) == 5000
    assert table.size == 1
