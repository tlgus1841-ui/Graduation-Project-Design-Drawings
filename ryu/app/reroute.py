"""
Self-Defending SDN Tower: Multi-hop Dynamic Rerouting Engine.
Author: Sihyeon Park (22101489 / Tech Lead)
Phase 4 (Week 10) Milestone

NetworkX Dijkstra-based alternative path computation and proactive multi-hop
flow rule provisioning (OFPFC_ADD) across intermediate switches to guarantee
zero packet loss during mitigation.
"""

from typing import Any, Dict, List, Optional, Tuple
import networkx as nx


class RerouteEngine:
    """
    OpenFlow 1.3 다중 홉 우회 경로 계산 및 플로우 프로비저닝 엔진.
    다이아몬드 토폴로지(S1, S2, S3, S4) 및 일반 메쉬 토폴로지 지원.
    """

    def __init__(self):
        self.graph = nx.Graph()
        self.port_map: Dict[Tuple[int, int], Tuple[int, int]] = {}
        # (u, v) -> (u_out_port, v_in_port)
        self._build_diamond_topology()

    def _build_diamond_topology(self):
        """다이아몬드 기본 토폴로지 링크 및 포트 매핑 초기화"""
        # S1: P3 <-> S2: P1
        # S1: P4 <-> S3: P1
        # S2: P2 <-> S4: P2
        # S3: P2 <-> S4: P3
        links = [
            (1, 2, 3, 1, 1.0),  # (u, v, u_port, v_port, weight)
            (1, 3, 4, 1, 2.0),  # Backup route has slightly higher initial weight
            (2, 4, 2, 2, 1.0),
            (3, 4, 2, 3, 2.0),
        ]
        for u, v, u_p, v_p, w in links:
            self.graph.add_edge(u, v, weight=w)
            self.port_map[(u, v)] = (u_p, v_p)
            self.port_map[(v, u)] = (v_p, u_p)

    def update_link_weight(self, u: int, v: int, weight: float):
        """혼잡이나 공격 발생 시 특정 링크 가중치 동적 조정"""
        if self.graph.has_edge(u, v):
            self.graph[u][v]["weight"] = weight

    def get_shortest_path(
        self, source_dpid: int, target_dpid: int, avoid_dpids: Optional[List[int]] = None
    ) -> List[int]:
        """
        Dijkstra 알고리즘으로 최적 경로 산출.
        avoid_dpids에 지정된 스위치는 경로 탐색에서 제외.
        """
        working_graph = self.graph.copy()
        if avoid_dpids:
            for node in avoid_dpids:
                if node in working_graph and node not in (source_dpid, target_dpid):
                    working_graph.remove_node(node)

        try:
            return nx.shortest_path(
                working_graph, source=source_dpid, target=target_dpid, weight="weight"
            )
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []

    def compute_reroute_path(
        self,
        source_dpid: int = 1,
        target_dpid: int = 4,
        congested_intermediate_dpid: int = 2,
    ) -> List[int]:
        """
        주 경로(예: S1-S2-S4) 장애/공격 시 대체 우회 경로(예: S1-S3-S4) 산출.
        """
        return self.get_shortest_path(
            source_dpid, target_dpid, avoid_dpids=[congested_intermediate_dpid]
        )

    def get_path_flow_specs(
        self, path: List[int], dst_ip: str
    ) -> List[Dict[str, Any]]:
        """
        우회 경로 [S1, ..., Sn] 상의 각 스위치별 선제적 OFPFC_ADD 설치 명세 생성.
        중간 스위치(Intermediate)부터 Egress, Ingress 순으로 설치할 수 있도록 반환.
        반환 예시:
        [
          {"dpid": 3, "out_port": 2, "dst_ip": "10.0.0.4", "is_intermediate": True},
          {"dpid": 1, "out_port": 4, "dst_ip": "10.0.0.4", "is_intermediate": False}
        ]
        """
        if len(path) < 2:
            return []

        specs = []
        for i in range(len(path) - 1):
            curr_dpid = path[i]
            next_dpid = path[i + 1]
            out_port, _ = self.port_map.get((curr_dpid, next_dpid), (None, None))
            if out_port is None:
                continue

            specs.append({
                "dpid": curr_dpid,
                "out_port": out_port,
                "dst_ip": dst_ip,
                "is_intermediate": (i > 0),
                "step_index": i,
            })

        # 중간 경유 스위치들을 먼저 프로비저닝한 뒤 출발지(Ingress)를 변경하는 안전 순서 정렬
        # (중간 스위치 우선 설치 -> 마지막에 Ingress 스위치 스위칭)
        specs.sort(key=lambda s: 0 if s["is_intermediate"] else 1)
        return specs
