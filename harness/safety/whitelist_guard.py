"""
Self-Defending SDN Tower: Whitelist Safety Guardrail.
Author: Sihyeon Park (22101489 / Tech Lead)
Phase 4 (Week 9) Milestone

Ensures trunk links between switches are never blocked by automated defense or manual errors.
Only Access ports connecting end-hosts (e.g. H_attacker on S1:P2) can be isolated.
"""

from typing import Dict, List, Optional, Set


# Diamond Topology Trunk Port Mapping: {dpid: [trunk_ports]}
# S1: P3 (to S2), P4 (to S3)
# S2: P1 (to S1), P2 (to S4)
# S3: P1 (to S1), P2 (to S4)
# S4: P2 (to S2), P3 (to S3)
DEFAULT_TRUNK_PORTS: Dict[int, List[int]] = {
    1: [3, 4],
    2: [1, 2],
    3: [1, 2],
    4: [2, 3],
}

# Dedicated Access ports for Diamond Topology: {dpid: [access_ports]}
# S1: P1 (H_legit), P2 (H_attacker)
# S4: P1 (H_server)
DEFAULT_ACCESS_PORTS: Dict[int, List[int]] = {
    1: [1, 2],
    2: [],
    3: [],
    4: [1],
}


class WhitelistGuard:
    """Trunk 포트 오차단을 원천 차단하고 인프라 가용성을 보장하는 안전 가드레일"""

    def __init__(
        self,
        trunk_ports: Optional[Dict[int, List[int]]] = None,
        access_ports: Optional[Dict[int, List[int]]] = None,
        protected_ips: Optional[Set[str]] = None,
    ):
        self.trunk_ports = trunk_ports if trunk_ports is not None else DEFAULT_TRUNK_PORTS
        self.access_ports = access_ports if access_ports is not None else DEFAULT_ACCESS_PORTS
        # H_legit (10.0.0.1), H_server (10.0.0.4) 등 주요 호스트 보호 IP 목록
        self.protected_ips = protected_ips if protected_ips is not None else {"10.0.0.1", "10.0.0.4"}

    def is_trunk_port(self, dpid: int, port_no: int) -> bool:
        """포트가 스위치 간 트렁크 포트인지 확인"""
        return port_no in self.trunk_ports.get(dpid, [])

    def is_access_port(self, dpid: int, port_no: int) -> bool:
        """포트가 엔드 호스트가 연결된 엑세스 포트인지 확인"""
        return port_no in self.access_ports.get(dpid, [])

    def validate_isolation_target(self, dpid: int, port_no: int) -> bool:
        """
        포트 격리 대상 유효성 검증.
        트렁크 포트 차단 시도 시 ValueError 발생.
        """
        if self.is_trunk_port(dpid, port_no):
            raise ValueError(
                f"치명적 오류: DPID {dpid}의 Port {port_no}는 Trunk 포트이므로 차단할 수 없습니다."
            )
        return True

    def can_isolate(self, dpid: int, port_no: int) -> bool:
        """차단 가능 여부를 boolean으로 반환 (예외 대신 가드 체크용)"""
        return not self.is_trunk_port(dpid, port_no)

    def is_ip_protected(self, ip_addr: str) -> bool:
        """보호 대상 호스트 IP 여부 확인"""
        return ip_addr in self.protected_ips
