"""
Unit tests for Ryu OpenFlow 1.3 Controller Logic.
Validates:
1. Diamond Topology port & ARP table consistency
2. Primary shortest-path routing table continuity (S1-S2-S4)
3. Proxy ARP reply generation and storm suppression
4. IPv4 flow mod installation (OFPMatch eth_type=0x0800) and PacketOut
5. Loopback hairpinning guard
"""

import importlib.util
from pathlib import Path
import sys
import types
from unittest.mock import MagicMock


def _setup_and_load_controller():
    """Mock ryu dependencies and dynamically load
    SelfDefendingSDNController."""
    mock_eventlet = MagicMock()
    sys.modules["eventlet"] = mock_eventlet

    # Create root and subpackages
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
    mock_handler.set_ev_cls = lambda *a, **k: lambda fn: fn
    mock_controller.handler = mock_handler
    mock_controller.ofp_event = MagicMock()

    mock_ofproto = types.ModuleType("ryu.ofproto")
    mock_ofproto_v1_3 = types.ModuleType("ryu.ofproto.ofproto_v1_3")
    mock_ofproto_v1_3.OFP_VERSION = 0x04
    mock_ofproto.ofproto_v1_3 = mock_ofproto_v1_3

    mock_lib = types.ModuleType("ryu.lib")
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
    sys.modules["ryu.lib.packet"] = mock_packet
    sys.modules["ryu.lib.packet.ether_types"] = mock_ether_types
    sys.modules["ryu.lib.packet.packet"] = MagicMock()
    sys.modules["ryu.lib.packet.ethernet"] = MagicMock()
    sys.modules["ryu.lib.packet.arp"] = mock_arp
    sys.modules["ryu.lib.packet.ipv4"] = MagicMock()

    # Load controller module
    root_dir = Path(__file__).resolve().parent.parent.parent
    controller_path = root_dir / "ryu" / "app" / "controller.py"
    spec = importlib.util.spec_from_file_location(
        "controller_module", controller_path
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.SelfDefendingSDNController


SelfDefendingSDNController = _setup_and_load_controller()
from topo.diamond_topo import DiamondTopo  # noqa: E402


def test_arp_table_and_topo_consistency():
    """Verify ARP table mappings match the DiamondTopo hardware
    definitions."""
    controller = SelfDefendingSDNController()
    topo = DiamondTopo()

    # Verify IP and MAC mappings for all 3 key hosts
    assert controller.arp_table["10.0.0.1"]["mac"] == "00:00:00:00:00:01"
    assert controller.arp_table["10.0.0.1"]["dpid"] == 1
    assert controller.arp_table["10.0.0.1"]["port"] == 1

    assert controller.arp_table["10.0.0.2"]["mac"] == "00:00:00:00:00:02"
    assert controller.arp_table["10.0.0.2"]["dpid"] == 1
    assert controller.arp_table["10.0.0.2"]["port"] == 2

    assert controller.arp_table["10.0.0.4"]["mac"] == "00:00:00:00:00:04"
    assert controller.arp_table["10.0.0.4"]["dpid"] == 4
    assert controller.arp_table["10.0.0.4"]["port"] == 1

    # Verify switch count in topology
    assert len(topo.switches()) == 4
    assert len(topo.hosts()) == 3


def test_routing_table_shortest_path_continuity():
    """Verify end-to-end shortest path forwarding (S1 <-> S2 <-> S4)."""
    controller = SelfDefendingSDNController()

    # Forward direction: H_legit (10.0.0.1) -> H_server (10.0.0.4)
    # S1 forwards 10.0.0.4 out port 3 (to S2)
    assert controller.routing_table[1]["10.0.0.4"] == 3
    # S2 forwards 10.0.0.4 out port 2 (to S4)
    assert controller.routing_table[2]["10.0.0.4"] == 2
    # S4 forwards 10.0.0.4 out port 1 (to H_server)
    assert controller.routing_table[4]["10.0.0.4"] == 1

    # Reverse direction: H_server (10.0.0.4) -> H_legit (10.0.0.1)
    # S4 forwards 10.0.0.1 out port 2 (to S2)
    assert controller.routing_table[4]["10.0.0.1"] == 2
    # S2 forwards 10.0.0.1 out port 1 (to S1)
    assert controller.routing_table[2]["10.0.0.1"] == 1
    # S1 forwards 10.0.0.1 out port 1 (to H_legit)
    assert controller.routing_table[1]["10.0.0.1"] == 1


def test_proxy_arp_known_host():
    """Verify Controller intercepts ARP request for known host and replies."""
    controller = SelfDefendingSDNController()
    controller.send_arp_reply = MagicMock()

    datapath = MagicMock()
    datapath.id = 1

    eth = MagicMock()
    eth.src = "00:00:00:00:00:01"

    arp_pkt = MagicMock()
    arp_pkt.opcode = 1  # ARP_REQUEST
    arp_pkt.dst_ip = "10.0.0.4"
    arp_pkt.src_ip = "10.0.0.1"

    controller.handle_arp(datapath, in_port=1, eth=eth, arp_pkt=arp_pkt)

    # Controller should respond with H_server's MAC directly to in_port 1
    controller.send_arp_reply.assert_called_once_with(
        datapath,
        "00:00:00:00:00:04",  # reply_mac
        "10.0.0.4",            # target_ip
        "00:00:00:00:00:01",  # dst_mac
        "10.0.0.1",            # dst_ip
        1,                     # out_port (in_port)
    )


def test_proxy_arp_unknown_host_suppressed():
    """Verify Controller suppresses ARP requests for unregistered IPs."""
    controller = SelfDefendingSDNController()
    controller.send_arp_reply = MagicMock()

    datapath = MagicMock()
    datapath.id = 1

    eth = MagicMock()
    eth.src = "00:00:00:00:00:01"

    arp_pkt = MagicMock()
    arp_pkt.opcode = 1
    arp_pkt.dst_ip = "192.168.99.99"  # Unknown IP
    arp_pkt.src_ip = "10.0.0.1"

    controller.handle_arp(datapath, in_port=1, eth=eth, arp_pkt=arp_pkt)

    # Must NOT call send_arp_reply and must NOT flood
    controller.send_arp_reply.assert_not_called()


def test_ipv4_forwarding_installs_flow_and_packet_out():
    """Verify IPv4 packet installs flow mod and sends packet-out."""
    controller = SelfDefendingSDNController()
    controller.add_flow = MagicMock()

    datapath = MagicMock()
    datapath.id = 1
    datapath.ofproto_parser = MagicMock()
    datapath.ofproto = MagicMock()

    eth = MagicMock()
    ip_pkt = MagicMock()
    ip_pkt.dst = "10.0.0.4"

    raw_data = b"\x00" * 64

    controller.handle_ipv4(
        datapath, in_port=1, eth=eth, ip_pkt=ip_pkt, data=raw_data
    )

    # Check Flow Mod installation
    controller.add_flow.assert_called_once()
    _, kwargs = controller.add_flow.call_args
    assert kwargs["priority"] == 10
    assert kwargs["idle_timeout"] == 60

    # Verify parser.OFPMatch called with eth_type=0x0800
    datapath.ofproto_parser.OFPMatch.assert_called_once_with(
        eth_type=0x0800,
        ipv4_dst="10.0.0.4",
    )

    # Verify PacketOut sent for first packet zero-loss
    datapath.ofproto_parser.OFPPacketOut.assert_called_once()
    datapath.send_msg.assert_called_once()


def test_ipv4_loopback_guard():
    """Verify packet with out_port == in_port is dropped to prevent loop."""
    controller = SelfDefendingSDNController()
    controller.add_flow = MagicMock()

    datapath = MagicMock()
    datapath.id = 1

    eth = MagicMock()
    ip_pkt = MagicMock()
    # Routing table maps 10.0.0.1 -> out_port 1 on S1
    ip_pkt.dst = "10.0.0.1"

    raw_data = b"\x00" * 64

    # Simulate packet arriving ON port 1 with destination 10.0.0.1
    controller.handle_ipv4(
        datapath, in_port=1, eth=eth, ip_pkt=ip_pkt, data=raw_data
    )

    # Should be dropped by loopback guard
    controller.add_flow.assert_not_called()
    datapath.send_msg.assert_not_called()


def test_ipv4_unknown_destination_dropped():
    """Verify packet destined for unknown subnet is dropped cleanly."""
    controller = SelfDefendingSDNController()
    controller.add_flow = MagicMock()

    datapath = MagicMock()
    datapath.id = 1

    eth = MagicMock()
    ip_pkt = MagicMock()
    ip_pkt.dst = "172.16.0.50"  # Not in routing_table[1]

    raw_data = b"\x00" * 64

    controller.handle_ipv4(
        datapath, in_port=1, eth=eth, ip_pkt=ip_pkt, data=raw_data
    )

    controller.add_flow.assert_not_called()
    datapath.send_msg.assert_not_called()
