"""
SDN Topology Profile Loader.
Supports dual-mode execution: diamond_4sw (Default) and zone_8sw (Enterprise).
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import networkx as nx
import yaml


DEFAULT_PROFILE_NAME = "zone_8sw"


def find_profiles_yaml_path() -> Optional[Path]:
    """topology.yaml 또는 topology_profiles.yaml 파일 위치를 환경별로 자동 탐색"""
    candidates = [
        Path(os.environ.get("SDN_TOPOLOGY_PATH", "")),
        Path("/workspace/config/topology.yaml"),
        Path("/app/config/topology.yaml"),
        Path("config/topology.yaml"),
        Path(__file__).resolve().parents[2] / "config" / "topology.yaml",
        Path("/workspace/config/topology_profiles.yaml"),
        Path("/app/config/topology_profiles.yaml"),
        Path("config/topology_profiles.yaml"),
        Path(__file__).resolve().parents[2] / "config" / "topology_profiles.yaml",
    ]
    for p in candidates:
        if p and p.is_file():
            return p
    return None


def get_topology_profile(profile_name: Optional[str] = None) -> Dict[str, Any]:
    """
    엔터프라이즈 8-스위치 토폴로지 프로파일 로드 (SSOT).
    """
    p_path = find_profiles_yaml_path()

    profile = {}
    if p_path and p_path.exists():
        try:
            with open(p_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                if "topology" in data:
                    profile = data["topology"]
                elif "profiles" in data:
                    profiles = data["profiles"]
                    target = profile_name or "zone_8sw"
                    profile = profiles.get(target) or profiles.get("default") or {}
        except Exception:
            profile = {}

    if not profile or not profile.get("switches"):
        profile = _get_builtin_zone_8sw()

    # routing_table이 명시되어 있지 않은 경우 자동 계산
    if "routing_table" not in profile or not profile["routing_table"]:
        profile["routing_table"] = compute_routing_table(profile)

    return profile


def compute_routing_table(profile: Dict[str, Any]) -> Dict[int, Dict[str, int]]:
    """
    프로파일의 링크 및 호스트 정보를 바탕으로 Dijkstra 최단 경로 라우팅 테이블 자동 생성.
    결과: {dpid: {dst_ip: out_port}}
    """
    graph = nx.Graph()
    port_map: Dict[Tuple[int, int], int] = {}  # (u, v) -> u_out_port

    for link in profile.get("links", []):
        u, v, u_port, v_port = link[0], link[1], link[2], link[3]
        weight = float(link[4]) if len(link) > 4 else 1.0
        graph.add_edge(u, v, weight=weight)
        port_map[(u, v)] = u_port
        port_map[(v, u)] = v_port

    hosts = profile.get("hosts", {})
    switches = profile.get("switches", [])
    routing: Dict[int, Dict[str, int]] = {sw: {} for sw in switches}

    for dst_ip, host_info in hosts.items():
        host_dpid = host_info["dpid"]
        host_port = host_info["port"]

        for sw in switches:
            if sw == host_dpid:
                # 목적지 호스트가 직접 연결된 스위치
                routing[sw][dst_ip] = host_port
            else:
                # 스위치 간 최단 경로 탐색
                try:
                    path = nx.shortest_path(graph, source=sw, target=host_dpid, weight="weight")
                    if len(path) >= 2:
                        next_hop = path[1]
                        out_p = port_map.get((sw, next_hop))
                        if out_p is not None:
                            routing[sw][dst_ip] = out_p
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    continue

    return routing


def _get_builtin_zone_8sw() -> Dict[str, Any]:
    """엔터프라이즈 8-스위치 빌트인 표준 설정"""
    return {
        "name": "zone_8sw",
        "description": "Enterprise 8-Switch 5-Zone Topology (Builtin SSOT)",
        "switches": [1, 2, 3, 4, 5, 6, 7, 8],
        "hosts": {
            "10.0.0.1": {"mac": "00:00:00:00:00:01", "dpid": 3, "port": 1, "zone": "USER", "label": "h1"},
            "10.0.0.2": {"mac": "00:00:00:00:00:02", "dpid": 3, "port": 2, "zone": "USER", "label": "h2"},
            "10.0.0.3": {"mac": "00:00:00:00:00:03", "dpid": 4, "port": 1, "zone": "USER", "label": "h3"},
            "10.0.0.4": {"mac": "00:00:00:00:00:04", "dpid": 4, "port": 2, "zone": "USER", "label": "h4"},
            "10.0.0.11": {"mac": "00:00:00:00:00:11", "dpid": 5, "port": 1, "zone": "SERVER", "label": "h5"},
            "10.0.0.12": {"mac": "00:00:00:00:00:12", "dpid": 5, "port": 2, "zone": "SERVER", "label": "h6"},
            "10.0.0.21": {"mac": "00:00:00:00:00:21", "dpid": 6, "port": 1, "zone": "SERVER", "label": "h7"},
            "10.0.0.22": {"mac": "00:00:00:00:00:22", "dpid": 6, "port": 2, "zone": "SERVER", "label": "h8"},
            "10.0.0.254": {"mac": "00:00:00:00:00:fe", "dpid": 7, "port": 1, "zone": "ADMIN", "label": "h_admin"},
            "10.0.0.253": {"mac": "00:00:00:00:00:fd", "dpid": 7, "port": 2, "zone": "ADMIN", "label": "h_patch"},
            "10.0.0.250": {"mac": "00:00:00:00:00:fa", "dpid": 8, "port": 1, "zone": "QUARANTINE", "label": "h_sink"},
        },
        "links": [
            [1, 2, 1, 1, 1.0],
            [1, 3, 2, 99, 1.0],
            [1, 5, 3, 99, 1.0],
            [1, 7, 4, 98, 1.0],
            [1, 8, 5, 98, 1.0],
            [2, 4, 2, 99, 1.0],
            [2, 6, 3, 99, 1.0],
            [2, 7, 4, 99, 1.0],
            [2, 8, 5, 99, 1.0],
        ],
        "trunk_ports": {
            1: [1, 2, 3, 4, 5], 2: [1, 2, 3, 4, 5],
            3: [99], 4: [99], 5: [99], 6: [99],
            7: [98, 99], 8: [98, 99],
        },
        "access_ports": {
            1: [], 2: [],
            3: [1, 2], 4: [1, 2], 5: [1, 2], 6: [1, 2],
            7: [1, 2], 8: [1],
        },
        "protected_access_ports": {5: [1, 2], 6: [1, 2], 7: [1, 2]},
        "protected_ips": [
            "10.0.0.11", "10.0.0.12", "10.0.0.21", "10.0.0.22", "10.0.0.253", "10.0.0.254"
        ],
        "probe": {
            "dpid": 3,
            "ip": "10.0.0.250",
            "mac": "00:00:00:00:00:fa",
            "target_ip": "10.0.0.11",
        },
    }
