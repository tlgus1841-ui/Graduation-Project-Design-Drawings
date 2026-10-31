"""
SDN Topology Profile Loader.
Supports dual-mode execution: diamond_4sw (Default) and zone_8sw (Enterprise).
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import networkx as nx
import yaml


DEFAULT_PROFILE_NAME = "diamond_4sw"


def find_profiles_yaml_path() -> Optional[Path]:
    """topology_profiles.yaml 파일 위치를 환경별로 자동 탐색"""
    candidates = [
        Path(os.environ.get("SDN_PROFILES_PATH", "")),
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
    지정된 또는 환경 변수(SDN_TOPOLOGY_PROFILE)에 따른 토폴로지 프로파일 로드.
    미설정 시 기본값 'diamond_4sw'로 안전 폴백.
    """
    target = profile_name or os.environ.get("SDN_TOPOLOGY_PROFILE") or DEFAULT_PROFILE_NAME
    p_path = find_profiles_yaml_path()

    loaded_profiles = {}
    if p_path and p_path.exists():
        try:
            with open(p_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                loaded_profiles = data.get("profiles", {})
        except Exception:
            loaded_profiles = {}

    profile = loaded_profiles.get(target)
    if not profile:
        # Fallback to diamond_4sw hardcoded defaults if YAML loading fails
        profile = _get_builtin_diamond_4sw()

    # routing_table이 명시되어 있지 않은 경우 자동 계산 (예: zone_8sw)
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


def _get_builtin_diamond_4sw() -> Dict[str, Any]:
    """기본 diamond_4sw 빌트인 설정"""
    return {
        "name": "diamond_4sw",
        "description": "Builtin diamond 4-switch fallback profile",
        "switches": [1, 2, 3, 4],
        "hosts": {
            "10.0.0.1": {"mac": "00:00:00:00:00:01", "dpid": 1, "port": 1, "zone": "USER", "label": "h_legit"},
            "10.0.0.2": {"mac": "00:00:00:00:00:02", "dpid": 1, "port": 2, "zone": "USER", "label": "h_attacker"},
            "10.0.0.4": {"mac": "00:00:00:00:00:04", "dpid": 4, "port": 1, "zone": "SERVER", "label": "h_server"},
        },
        "routing_table": {
            1: {"10.0.0.1": 1, "10.0.0.2": 2, "10.0.0.4": 3, "10.0.0.254": 3},
            2: {"10.0.0.1": 1, "10.0.0.2": 1, "10.0.0.4": 2, "10.0.0.254": 2},
            3: {"10.0.0.1": 1, "10.0.0.2": 1, "10.0.0.4": 2, "10.0.0.254": 2},
            4: {"10.0.0.1": 2, "10.0.0.2": 2, "10.0.0.4": 1, "10.0.0.254": 2},
        },
        "links": [
            [1, 2, 3, 1, 1.0],
            [1, 3, 4, 1, 2.0],
            [2, 4, 2, 2, 1.0],
            [3, 4, 2, 3, 2.0],
        ],
        "trunk_ports": {1: [3, 4], 2: [1, 2], 3: [1, 2], 4: [2, 3]},
        "access_ports": {1: [1, 2], 2: [], 3: [], 4: [1, 2]},
        "protected_access_ports": {1: [1], 4: [1, 2]},
        "protected_ips": ["10.0.0.1", "10.0.0.4", "10.0.0.254"],
        "probe": {
            "dpid": 1,
            "ip": "10.0.0.250",
            "mac": "00:00:00:00:00:fa",
            "target_ip": "10.0.0.4",
        },
    }
