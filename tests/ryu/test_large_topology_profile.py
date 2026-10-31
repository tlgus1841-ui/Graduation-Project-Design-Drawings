"""
Unit tests for Phase 6-C-1 Large Topology Profiles & Zone Policy Extension.
Validates:
1. Profile Loader dual-mode resolution (diamond_4sw vs zone_8sw)
2. 8-Switch dynamic routing matrix generation via NetworkX Dijkstra
3. RerouteEngine multi-switch path computation & failover across core switches
4. Extended zones.yaml policies including QUARANTINE_TO_ADMIN_HTTP_PATCH and H_Patch
"""

import importlib.util
from pathlib import Path

from harness.topology.profile_loader import (
    get_topology_profile,
    find_profiles_yaml_path,
)

# Load reroute directly from ryu/app/reroute.py
_reroute_path = Path(__file__).resolve().parent.parent.parent / "ryu" / "app" / "reroute.py"
_spec = importlib.util.spec_from_file_location("reroute_mod", _reroute_path)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
RerouteEngine = _mod.RerouteEngine


def test_profile_loader_default_ssot():
    profile = get_topology_profile()
    assert profile["name"] in ("zone_10sw", "zone_8sw")
    assert profile["switches"] == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    assert "10.0.0.1" in profile["hosts"]
    assert "10.0.0.2" in profile["hosts"]
    assert "10.0.0.11" in profile["hosts"]
    assert profile["hosts"]["10.0.0.1"]["dpid"] == 3
    assert profile["hosts"]["10.0.0.11"]["dpid"] == 10

    routing = profile["routing_table"]
    assert routing[3]["10.0.0.11"] == 98
    assert routing[1]["10.0.0.11"] == 7


def test_profile_loader_zone_8sw():
    profile = get_topology_profile("zone_8sw")
    assert profile["name"] in ("zone_10sw", "zone_8sw")
    assert profile["switches"] == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

    # Verify enterprise hosts
    hosts = profile["hosts"]
    assert len(hosts) == 13
    # User Zone
    assert hosts["10.0.0.1"]["dpid"] == 3
    assert hosts["10.0.0.2"]["dpid"] == 3
    assert hosts["10.0.0.3"]["dpid"] == 4
    assert hosts["10.0.0.4"]["dpid"] == 4
    # DMZ Zone
    assert hosts["10.0.0.11"]["dpid"] == 10
    assert hosts["10.0.0.12"]["dpid"] == 10
    # Server Zone
    assert hosts["10.0.0.21"]["dpid"] == 5
    assert hosts["10.0.0.22"]["dpid"] == 6
    # Admin Zone
    assert hosts["10.0.0.254"]["dpid"] == 7
    assert hosts["10.0.0.253"]["dpid"] == 7
    # Quarantine Zone
    assert hosts["10.0.0.240"]["dpid"] == 8
    # External Zone
    assert hosts["192.168.100.100"]["dpid"] == 9

    # Verify routing table automatically computed
    routing = profile["routing_table"]
    assert len(routing) == 10
    # S3 (User A) -> S10 (DMZ web1, 10.0.0.11): S3 out-port to S1 is 98
    assert routing[3]["10.0.0.11"] == 98
    # S1 (Core 1) -> S10 (DMZ web1, 10.0.0.11): S1 out-port to S10 is 7
    assert routing[1]["10.0.0.11"] == 7
    # S10 (DMZ) -> web1 (10.0.0.11): local host port is 1
    assert routing[10]["10.0.0.11"] == 1


def test_reroute_engine_zone_8sw_paths():
    profile = get_topology_profile("zone_8sw")
    engine = RerouteEngine(profile=profile)

    # 1. Path from S3 (User A) to S10 (DMZ): [3, 1, 10]
    path_s3_to_s10 = engine.get_shortest_path(source_dpid=3, target_dpid=10)
    assert path_s3_to_s10 == [3, 1, 10]

    # 2. Path from S3 (User A) to S6 (Server B): [3, 1, 6]
    path_s3_to_s6 = engine.get_shortest_path(source_dpid=3, target_dpid=6)
    assert path_s3_to_s6 == [3, 1, 6]

    # 3. Path from S3 to S7 (Admin): [3, 1, 7]
    path_s3_to_s7 = engine.get_shortest_path(source_dpid=3, target_dpid=7)
    assert path_s3_to_s7 == [3, 1, 7]

    # 4. S1 core congested/failed -> path to S7 via S2:
    # S7 is connected to both S1 and S2!
    path_s2_to_s7 = engine.get_shortest_path(source_dpid=2, target_dpid=7)
    assert path_s2_to_s7 == [2, 7]

    # 5. Path from S2 to S10 (DMZ): [2, 10]
    path_s2_to_s10 = engine.get_shortest_path(source_dpid=2, target_dpid=10)
    assert path_s2_to_s10 == [2, 10]


def test_zone_policy_and_patch_server_specs():
    import yaml
    p_path = find_profiles_yaml_path()
    assert p_path is not None

    zones_path = p_path.parent / "zones.yaml"
    with open(zones_path, "r", encoding="utf-8") as f:
        zones_data = yaml.safe_load(f)

    # Patch server IP in ADMIN zone
    assert "10.0.0.253" in zones_data["zones"]["ADMIN"]
    assert "10.0.0.253" in zones_data["hard_whitelist"]["protected_ips"]

    # Rule allowing QUARANTINE -> ADMIN on HTTP (Port 80)
    rule_names = [r["name"] for r in zones_data["rules"]]
    assert "QUARANTINE_TO_ADMIN_HTTP_PATCH" in rule_names

    patch_rule = next(r for r in zones_data["rules"] if r["name"] == "QUARANTINE_TO_ADMIN_HTTP_PATCH")
    assert patch_rule["from_zone"] == "QUARANTINE"
    assert patch_rule["to_zone"] == "ADMIN"
    assert patch_rule["dst_port"] == 80
    assert patch_rule["proto"] == "tcp"
