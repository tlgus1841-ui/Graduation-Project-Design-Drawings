"""
Unit tests for Multi-hop Dynamic Reroute Engine (8-Switch 5-Zone Topology).
Author: Sihyeon Park (22101489 / Tech Lead)
"""

import importlib.util
from pathlib import Path

# Load reroute directly from ryu/app/reroute.py
_reroute_path = Path(__file__).resolve().parent.parent.parent / "ryu" / "app" / "reroute.py"
_spec = importlib.util.spec_from_file_location("reroute_mod", _reroute_path)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
RerouteEngine = _mod.RerouteEngine


def test_reroute_engine_initializes_8sw_topology():
    engine = RerouteEngine()
    # 8 Switches: S1 ~ S8
    assert set(engine.graph.nodes) == {1, 2, 3, 4, 5, 6, 7, 8}
    # Shortest path between User A (S3) and Server A (S5) is [3, 1, 5]
    path = engine.get_shortest_path(3, 5)
    assert path == [3, 1, 5]


def test_reroute_engine_computes_bypass_avoiding_congested_node():
    engine = RerouteEngine()
    # Path from S1 to S7 (Admin): direct link is S1:P4 <-> S7:P98 (weight 1.0)
    # If S1 is avoided from S2, S2 reaches S7 directly via [2, 7]
    path_s2_to_s7 = engine.get_shortest_path(source_dpid=2, target_dpid=7)
    assert path_s2_to_s7 == [2, 7]

    # User A (S3) to Server B (S6): [3, 1, 2, 6]
    path_s3_to_s6 = engine.get_shortest_path(3, 6)
    assert path_s3_to_s6 == [3, 1, 2, 6]


def test_reroute_engine_proactive_flow_specs_ordering():
    engine = RerouteEngine()
    path = [3, 1, 5]  # S3 -> S1 -> S5
    specs = engine.get_path_flow_specs(path, dst_ip="10.0.0.11")

    assert len(specs) == 2
    # Intermediate switch (S1) must come FIRST to prevent packet drop
    assert specs[0]["dpid"] == 1
    assert specs[0]["out_port"] == 3  # S1 to S5 is port 3
    assert specs[0]["is_intermediate"] is True

    # Ingress switch (S3) comes SECOND (switches forwarding)
    assert specs[1]["dpid"] == 3
    assert specs[1]["out_port"] == 99  # S3 to S1 is port 99
    assert specs[1]["is_intermediate"] is False


def test_reroute_engine_link_weight_update():
    engine = RerouteEngine()
    # S1 to S7: default is [1, 7] (weight 1.0)
    # Make direct S1-S7 link very expensive (weight 10.0)
    engine.update_link_weight(1, 7, 10.0)

    # Dijkstra should now prefer [1, 2, 7] (weights 1.0 + 1.0 = 2.0 < 10.0)
    path = engine.get_shortest_path(1, 7)
    assert path == [1, 2, 7]
