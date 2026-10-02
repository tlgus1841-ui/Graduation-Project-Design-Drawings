"""
Unit tests for Ryu 2-Tier Telemetry Pipeline (Week 6 Milestone).
Validates:
1. Datapath registration and deregistration on StateChange events
2. Periodic OFPPortStatsRequest dispatch
3. OFPPortStatsReply parsing and PortStatsMessage contract conformance
4. Filtering of OFPP_LOCAL (0xfffffffe) and dummy ports
5. Fault tolerance when Redis is unreachable (no crash of switching plane)
"""

import importlib.util
from pathlib import Path
import sys
import types
from unittest.mock import MagicMock

from harness.contracts.sdn_events import (
    REDIS_CHANNEL_PORT_STATS,
    PortStatsMessage,
)


def _setup_and_load_controller_for_telemetry():
    """Mock ryu dependencies and dynamically load
    SelfDefendingSDNController."""
    mock_eventlet = MagicMock()
    sys.modules["eventlet"] = mock_eventlet

    mock_ryu = types.ModuleType("ryu")
    mock_ryu.__path__ = []

    mock_base = types.ModuleType("ryu.base")
    mock_app_manager = types.ModuleType("ryu.base.app_manager")

    class FakeRyuApp(object):
        def __init__(self, *args, **kwargs):
            self.logger = MagicMock()

    mock_app_manager.RyuApp = FakeRyuApp
    mock_base.app_manager = mock_app_manager

    mock_controller = types.ModuleType("ryu.controller")
    mock_handler = types.ModuleType("ryu.controller.handler")
    mock_handler.CONFIG_DISPATCHER = "config"
    mock_handler.MAIN_DISPATCHER = "main"
    mock_handler.DEAD_DISPATCHER = "dead"
    mock_handler.set_ev_cls = lambda *a, **k: lambda fn: fn
    mock_controller.handler = mock_handler
    mock_controller.ofp_event = MagicMock()

    mock_ofproto = types.ModuleType("ryu.ofproto")
    mock_ofproto_v1_3 = types.ModuleType("ryu.ofproto.ofproto_v1_3")
    mock_ofproto_v1_3.OFP_VERSION = 0x04
    mock_ofproto_v1_3.OFPP_ANY = 0xFFFFFFFF
    mock_ofproto_v1_3.OFPP_MAX = 0xFFFFFF00
    mock_ofproto_v1_3.OFPP_LOCAL = 0xFFFFFFFE
    mock_ofproto.ofproto_v1_3 = mock_ofproto_v1_3

    mock_lib = types.ModuleType("ryu.lib")
    mock_hub = types.ModuleType("ryu.lib.hub")
    mock_hub.spawn = MagicMock(return_value=MagicMock())
    mock_hub.sleep = MagicMock()
    mock_lib.hub = mock_hub

    mock_packet = types.ModuleType("ryu.lib.packet")
    mock_ether_types = types.ModuleType("ryu.lib.packet.ether_types")
    mock_ether_types.ETH_TYPE_ARP = 0x0806
    mock_ether_types.ETH_TYPE_IP = 0x0800
    mock_ether_types.ETH_TYPE_LLDP = 0x88cc

    mock_arp = types.ModuleType("ryu.lib.packet.arp")
    mock_arp.ARP_REQUEST = 1
    mock_arp.ARP_REPLY = 2

    sys.modules["ryu"] = mock_ryu
    sys.modules["ryu.base"] = mock_base
    sys.modules["ryu.base.app_manager"] = mock_app_manager
    sys.modules["ryu.controller"] = mock_controller
    sys.modules["ryu.controller.handler"] = mock_handler
    sys.modules["ryu.controller.ofp_event"] = mock_controller.ofp_event
    sys.modules["ryu.ofproto"] = mock_ofproto
    sys.modules["ryu.ofproto.ofproto_v1_3"] = mock_ofproto_v1_3
    sys.modules["ryu.lib"] = mock_lib
    sys.modules["ryu.lib.hub"] = mock_hub
    sys.modules["ryu.lib.packet"] = mock_packet
    sys.modules["ryu.lib.packet.ether_types"] = mock_ether_types
    sys.modules["ryu.lib.packet.packet"] = MagicMock()
    sys.modules["ryu.lib.packet.ethernet"] = MagicMock()
    sys.modules["ryu.lib.packet.arp"] = mock_arp
    sys.modules["ryu.lib.packet.ipv4"] = MagicMock()

    root_dir = Path(__file__).resolve().parent.parent.parent
    controller_path = root_dir / "ryu" / "app" / "controller.py"
    spec = importlib.util.spec_from_file_location(
        "controller_module_telemetry", controller_path
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.SelfDefendingSDNController


SelfDefendingSDNController = _setup_and_load_controller_for_telemetry()


def test_datapath_registration_and_deregistration():
    """Verify datapaths are dynamically tracked on StateChange events."""
    controller = SelfDefendingSDNController()

    dp1 = MagicMock()
    dp1.id = 1
    ev_connect = MagicMock()
    ev_connect.datapath = dp1
    ev_connect.state = "main"

    controller.state_change_handler(ev_connect)
    assert 1 in controller.datapaths
    assert controller.datapaths[1] == dp1

    # Disconnect
    ev_disconnect = MagicMock()
    ev_disconnect.datapath = dp1
    ev_disconnect.state = "dead"

    controller.state_change_handler(ev_disconnect)
    assert 1 not in controller.datapaths


def test_request_stats_sends_ofpportstatsrequest():
    """Verify _request_stats sends OFPPortStatsRequest with OFPP_ANY."""
    controller = SelfDefendingSDNController()

    datapath = MagicMock()
    datapath.id = 1
    datapath.ofproto.OFPP_ANY = 0xFFFFFFFF
    datapath.ofproto_parser = MagicMock()

    controller._request_stats(datapath)

    datapath.ofproto_parser.OFPPortStatsRequest.assert_called_once_with(
        datapath, 0, 0xFFFFFFFF
    )
    datapath.send_msg.assert_called_once()


def test_port_stats_reply_filtering_and_contract_validation():
    """Verify port stats reply parses ports, ignores OFPP_LOCAL,
    and validates."""
    controller = SelfDefendingSDNController()
    controller.redis_client = MagicMock()

    datapath = MagicMock()
    datapath.id = 1
    datapath.ofproto.OFPP_MAX = 0xFFFFFF00

    # Build dummy port stats list: port 1, port 2, and OFPP_LOCAL (0xfffffffe)
    p1 = MagicMock(
        port_no=1, rx_packets=100, tx_packets=80,
        rx_bytes=10000, tx_bytes=8000, rx_errors=0, duration_sec=10
    )
    p2 = MagicMock(
        port_no=2, rx_packets=5000, tx_packets=20,
        rx_bytes=320000, tx_bytes=1280, rx_errors=0, duration_sec=10
    )
    p_local = MagicMock(
        port_no=0xFFFFFFFE, rx_packets=5, tx_packets=5,
        rx_bytes=500, tx_bytes=500, rx_errors=0, duration_sec=10
    )

    ev = MagicMock()
    ev.msg.datapath = datapath
    ev.msg.body = [p1, p2, p_local]

    controller.port_stats_reply_handler(ev)

    # Verify Redis publish was called
    controller.redis_client.publish.assert_called_once()
    channel, published_json = controller.redis_client.publish.call_args[0]
    assert channel == REDIS_CHANNEL_PORT_STATS

    # Verify JSON strictly conforms to Pydantic SSOT contract model
    parsed_model = PortStatsMessage.model_validate_json(published_json)
    assert parsed_model.dpid == 1
    assert len(parsed_model.stats) == 2  # OFPP_LOCAL must be filtered out!

    stat1 = parsed_model.stats[0]
    assert stat1.port_no == 1
    assert stat1.rx_packets == 100
    assert stat1.rx_bytes == 10000

    stat2 = parsed_model.stats[1]
    assert stat2.port_no == 2
    assert stat2.rx_packets == 5000
    assert stat2.rx_bytes == 320000


def test_redis_failure_fault_tolerance():
    """Verify Redis publishing failure does not crash the controller."""
    controller = SelfDefendingSDNController()
    controller.redis_client = MagicMock()
    controller.redis_client.publish.side_effect = RuntimeError("Redis down")

    payload = {"timestamp": 12345.0, "dpid": 1, "stats": []}

    # Should not raise exception
    controller._publish_port_stats(payload)
    assert controller.redis_client is None  # Resets for next cycle retry


def test_state_change_updates_datapath_on_reconnect():
    """Verify datapath instance is refreshed upon switch reconnection."""
    controller = SelfDefendingSDNController()

    old_dp = MagicMock(id=1, name="old_dp")
    ev1 = MagicMock(datapath=old_dp, state="main")
    controller.state_change_handler(ev1)
    assert controller.datapaths[1] is old_dp

    # Reconnection event with fresh datapath socket
    new_dp = MagicMock(id=1, name="new_dp")
    ev2 = MagicMock(datapath=new_dp, state="main")
    controller.state_change_handler(ev2)
    assert controller.datapaths[1] is new_dp


def test_port_stats_reply_with_empty_body():
    """Verify empty stats body still publishes valid contract message."""
    controller = SelfDefendingSDNController()
    controller.redis_client = MagicMock()

    datapath = MagicMock(id=3)
    ev = MagicMock()
    ev.msg.datapath = datapath
    ev.msg.body = []

    controller.port_stats_reply_handler(ev)
    controller.redis_client.publish.assert_called_once()
    _, published_json = controller.redis_client.publish.call_args[0]
    parsed = PortStatsMessage.model_validate_json(published_json)
    assert parsed.dpid == 3
    assert parsed.stats == []
