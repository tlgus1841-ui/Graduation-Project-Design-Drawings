"""
Unit tests for Multi-hop Dynamic Reroute Engine (Week 10).
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


def test_reroute_engine_initializes_diamond_topology():
    engine = RerouteEngine()
    # Nodes: 1, 2, 3, 4
    assert set(engine.graph.nodes) == {1, 2, 3, 4}
    # Primary shortest path between S1 and S4 is [1, 2, 4]
    path = engine.get_shortest_path(1, 4)
    assert path == [1, 2, 4]


def test_reroute_engine_computes_bypass_avoiding_congested_node():
    engine = RerouteEngine()
    # When S2 (intermediate) is congested or under attack, reroute through S3
    bypass_path = engine.compute_reroute_path(
        source_dpid=1, target_dpid=4, congested_intermediate_dpid=2
    )
    assert bypass_path == [1, 3, 4]


def test_reroute_engine_proactive_flow_specs_ordering():
    engine = RerouteEngine()
    bypass_path = [1, 3, 4]
    specs = engine.get_path_flow_specs(bypass_path, dst_ip="10.0.0.4")

    assert len(specs) == 2
    # Intermediate switch (S3) must come FIRST to prevent packet drop
    assert specs[0]["dpid"] == 3
    assert specs[0]["out_port"] == 2
    assert specs[0]["is_intermediate"] is True

    # Ingress switch (S1) comes SECOND (switches forwarding)
    assert specs[1]["dpid"] == 1
    assert specs[1]["out_port"] == 4
    assert specs[1]["is_intermediate"] is False


def test_reroute_engine_link_weight_update():
    engine = RerouteEngine()
    # Make primary path expensive
    engine.update_link_weight(1, 2, 10.0)
    engine.update_link_weight(2, 4, 10.0)

    # Dijkstra should now pick bypass [1, 3, 4] naturally
    path = engine.get_shortest_path(1, 4)
    assert path == [1, 3, 4]
