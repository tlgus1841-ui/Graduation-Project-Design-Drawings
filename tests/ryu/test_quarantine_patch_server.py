"""
Unit tests for Phase 6-C-1 Milestone M4:
Quarantine L4 Patch Server (10.0.0.253:80) Flow Enforcement & Multi-Switch Policy Consistency.
"""

from unittest.mock import MagicMock
import os

from tests.ryu.test_controller_logic import SelfDefendingSDNController

_globals = SelfDefendingSDNController.__init__.__globals__
TABLE_COUNT = _globals["TABLE_COUNT"]
TABLE_POLICY = _globals["TABLE_POLICY"]
TABLE_POLICE = _globals["TABLE_POLICE"]
TABLE_FORWARD = _globals["TABLE_FORWARD"]


def _make_large_controller_with_all_dps():
    """8-스위치 zone_8sw 프로파일이 적용된 컨트롤러 및 모의 Datapath 생성"""
    old_env = os.environ.get("SDN_TOPOLOGY_PROFILE")
    os.environ["SDN_TOPOLOGY_PROFILE"] = "zone_8sw"
    try:
        controller = SelfDefendingSDNController()
    finally:
        if old_env is not None:
            os.environ["SDN_TOPOLOGY_PROFILE"] = old_env
        else:
            os.environ.pop("SDN_TOPOLOGY_PROFILE", None)

    for dpid in range(1, 9):
        dp = MagicMock()
        dp.id = dpid
        dp.ofproto.OFPP_ANY = 0xFFFFFFFF
        dp.ofproto.OFPG_ANY = 0xFFFFFFFF
        dp.ofproto.OFP_NO_BUFFER = 0xFFFFFFFF
        dp.ofproto.OFPP_CONTROLLER = 0xFFFFFFFD
        dp.ofproto.OFPCML_NO_BUFFER = 0xFFFF
        dp.ofproto_parser = MagicMock()
        controller.datapaths[dpid] = dp

    return controller


def test_zone_8sw_switch_features_installs_policies():
    controller = _make_large_controller_with_all_dps()
    controller.add_flow = MagicMock()

    # S3 (User A switch, DPID 3, hosts: h1(10.0.0.1:P1), h2(10.0.0.2:P2))
    dp3 = controller.datapaths[3]
    ev = MagicMock()
    ev.msg.datapath = dp3

    controller.switch_features_handler(ev)

    policy_calls = [
        c.kwargs for c in controller.add_flow.call_args_list
        if c.kwargs.get("table_id") == TABLE_POLICY
    ]
    assert len(policy_calls) > 0

    priorities = [c["priority"] for c in policy_calls]
    # Trunk bypass to S1 (Port 99)
    assert 65535 in priorities
    # ARP pass
    assert 500 in priorities
    # Probe pass
    assert 400 in priorities
    # USER -> SERVER allow rules for h1 and h2
    assert 200 in priorities
    # ZONE_DENY miss per access port
    assert 0 in priorities


def test_patch_server_hard_whitelist_protection():
    controller = _make_large_controller_with_all_dps()

    # Patch server (10.0.0.253) and Admin (10.0.0.254) cannot be quarantined
    assert controller.quarantine_host("10.0.0.253") is False
    assert controller.quarantine_host("10.0.0.254") is False
    # Server hosts (10.0.0.11 ~ 10.0.0.22) cannot be quarantined
    assert controller.quarantine_host("10.0.0.11") is False
    assert controller.quarantine_host("10.0.0.21") is False

    assert len(controller.quarantined_hosts) == 0


def test_quarantine_enforces_patch_server_http_safe_channel():
    controller = _make_large_controller_with_all_dps()
    dp3 = controller.datapaths[3]
    controller.delete_flow = MagicMock()
    controller.add_flow = MagicMock()

    # 1. Quarantine h1 (10.0.0.1 on S3:Port 1)
    ok = controller.quarantine_host("10.0.0.1")
    assert ok is True
    assert "10.0.0.1" in controller.quarantined_hosts

    # Verify normal Pri 200 rules deleted
    deleted = [
        c.kwargs for c in controller.delete_flow.call_args_list
        if c.kwargs.get("table_id") == TABLE_POLICY and c.kwargs.get("priority") == 200
    ]
    assert len(deleted) >= 4  # Server rules deleted

    # Verify Pri 300 safe channels added:
    # Must include Admin HTTPS 443, DNS 53, AND Patch Server HTTP 80 (10.0.0.253:80)
    added_quarantine = [
        c.kwargs for c in controller.add_flow.call_args_list
        if c.kwargs.get("table_id") == TABLE_POLICY and c.kwargs.get("priority") == 300
    ]
    assert len(added_quarantine) == 3  # HTTPS, DNS, and HTTP PATCH

    match_calls = [c.kwargs for c in dp3.ofproto_parser.OFPMatch.call_args_list]
    patch_matches = [
        m for m in match_calls
        if m.get("ipv4_dst") == "10.0.0.253" and m.get("tcp_dst") == 80
    ]
    assert len(patch_matches) >= 1, "Must install HTTP 80 safe channel to 10.0.0.253"

    # 2. Release h1 after remediation
    controller.delete_flow.reset_mock()
    controller.add_flow.reset_mock()

    ok_rel = controller.release_host("10.0.0.1")
    assert ok_rel is True
    assert "10.0.0.1" not in controller.quarantined_hosts

    # Verify Pri 300 safe channels deleted
    deleted_q = [
        c.kwargs for c in controller.delete_flow.call_args_list
        if c.kwargs.get("table_id") == TABLE_POLICY and c.kwargs.get("priority") == 300
    ]
    assert len(deleted_q) == 3

    # Verify Pri 200 normal rules restored
    restored = [
        c.kwargs for c in controller.add_flow.call_args_list
        if c.kwargs.get("table_id") == TABLE_POLICY and c.kwargs.get("priority") == 200
    ]
    assert len(restored) >= 4
