"""
Self-Defending SDN Tower: Whitelist Safety Guardrail.
Author: Sihyeon Park (22101489 / Tech Lead)
Phase 4 (Week 9) Milestone

Ensures trunk links between switches are never blocked by automated defense or manual errors.
Only Access ports connecting end-hosts (e.g. H_attacker on S1:P2) can be isolated.
"""

from typing import Dict, List, Optional, Set


# Enterprise 8-Switch 5-Zone Trunk Port Mapping: {dpid: [trunk_ports]}
# S1 (Core 1): P1(to S2), P2(to S3), P3(to S5), P4(to S7), P5(to S8)
# S2 (Core 2): P1(to S1), P2(to S4), P3(to S6), P4(to S7), P5(to S8)
# S3: P99(to S1), S4: P99(to S2), S5: P99(to S1), S6: P99(to S2)
# S7: P98(to S1), P99(to S2), S8: P98(to S1), P99(to S2)
DEFAULT_TRUNK_PORTS: Dict[int, List[int]] = {
    1: [1, 2, 3, 4, 5],
    2: [1, 2, 3, 4, 5],
    3: [99],
    4: [99],
    5: [99],
    6: [99],
    7: [98, 99],
    8: [98, 99],
}

# Dedicated Access ports for 8-Switch Topology: {dpid: [access_ports]}
DEFAULT_ACCESS_PORTS: Dict[int, List[int]] = {
    1: [],
    2: [],
    3: [1, 2],  # h1, h2
    4: [1, 2],  # h3, h4
    5: [1, 2],  # h5, h6
    6: [1, 2],  # h7, h8
    7: [1, 2],  # h_admin, h_patch
    8: [1],     # h_sink
}

# Protected end-host ports that must never be isolated (Servers, Admin, Patch)
DEFAULT_PROTECTED_ACCESS_PORTS: Dict[int, List[int]] = {
    5: [1, 2],
    6: [1, 2],
    7: [1, 2],
}

DEFAULT_PROTECTED_IPS: Set[str] = {
    "10.0.0.11",
    "10.0.0.12",
    "10.0.0.21",
    "10.0.0.22",
    "10.0.0.253",
    "10.0.0.254",
}


class WhitelistGuard:
    """Trunk 포트 오차단을 원천 차단하고 인프라 가용성을 보장하는 안전 가드레일"""

    def __init__(
        self,
        trunk_ports: Optional[Dict[int, List[int]]] = None,
        access_ports: Optional[Dict[int, List[int]]] = None,
        protected_ips: Optional[Set[str]] = None,
        protected_access_ports: Optional[Dict[int, List[int]]] = None,
    ):
        self.trunk_ports = trunk_ports if trunk_ports is not None else DEFAULT_TRUNK_PORTS
        self.access_ports = access_ports if access_ports is not None else DEFAULT_ACCESS_PORTS
        self.protected_ips = protected_ips if protected_ips is not None else DEFAULT_PROTECTED_IPS
        self.protected_access_ports = (
            protected_access_ports if protected_access_ports is not None else DEFAULT_PROTECTED_ACCESS_PORTS
        )

    def is_trunk_port(self, dpid: int, port_no: int) -> bool:
        """포트가 스위치 간 트렁크 포트인지 확인"""
        return port_no in self.trunk_ports.get(dpid, [])

    def is_access_port(self, dpid: int, port_no: int) -> bool:
        """포트가 엔드 호스트가 연결된 엑세스 포트인지 확인"""
        return port_no in self.access_ports.get(dpid, [])

    def is_protected_access_port(self, dpid: int, port_no: int) -> bool:
        """H_legit/H_server 등 보호 대상 호스트가 연결된 포트인지 확인"""
        return port_no in self.protected_access_ports.get(dpid, [])

    def validate_isolation_target(self, dpid: int, port_no: int) -> bool:
        """
        포트 격리 대상 유효성 검증.
        트렁크 포트 또는 보호 호스트 포트 차단 시도 시 ValueError 발생.
        """
        if self.is_trunk_port(dpid, port_no):
            raise ValueError(
                f"치명적 오류: DPID {dpid}의 Port {port_no}는 Trunk 포트이므로 차단할 수 없습니다."
            )
        if self.is_protected_access_port(dpid, port_no):
            raise ValueError(
                f"치명적 오류: DPID {dpid}의 Port {port_no}는 보호 호스트 포트이므로 차단할 수 없습니다."
            )
        return True

    def can_isolate(self, dpid: int, port_no: int) -> bool:
        """차단 가능 여부를 boolean으로 반환 (예외 대신 가드 체크용).

        트렁크 포트뿐 아니라 보호 호스트(H_legit, H_server) 포트도 격리 불가.
        """
        if self.is_protected_access_port(dpid, port_no):
            return False
        return not self.is_trunk_port(dpid, port_no)

    def is_ip_protected(self, ip_addr: str) -> bool:
        """보호 대상 호스트 IP 여부 확인"""
        return ip_addr in self.protected_ips
