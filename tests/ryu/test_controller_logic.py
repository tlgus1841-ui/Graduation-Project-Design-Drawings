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
    mock_handler.DEAD_DISPATCHER = "dead"
    mock_handler.set_ev_cls = lambda *a, **k: lambda fn: fn
    mock_controller.handler = mock_handler
    mock_controller.ofp_event = MagicMock()

    mock_ofproto = types.ModuleType("ryu.ofproto")
    mock_ofproto_v1_3 = types.ModuleType("ryu.ofproto.ofproto_v1_3")
    mock_ofproto_v1_3.OFP_VERSION = 0x04
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
    sys.modules["ryu.lib.packet.icmp"] = MagicMock()

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


def test_arp_table_and_topo_consistency():
    """Verify ARP table mappings match 8-Switch 5-Zone hardware definitions."""
    controller = SelfDefendingSDNController()

    # Verify IP and MAC mappings for key hosts in User & Server zones
    assert controller.arp_table["10.0.0.1"]["mac"] == "00:00:00:00:00:01"
    assert controller.arp_table["10.0.0.1"]["dpid"] == 3
    assert controller.arp_table["10.0.0.1"]["port"] == 1

    assert controller.arp_table["10.0.0.2"]["mac"] == "00:00:00:00:00:02"
    assert controller.arp_table["10.0.0.2"]["dpid"] == 3
    assert controller.arp_table["10.0.0.2"]["port"] == 2

    assert controller.arp_table["10.0.0.11"]["mac"] == "00:00:00:00:00:11"
    assert controller.arp_table["10.0.0.11"]["dpid"] == 10
    assert controller.arp_table["10.0.0.11"]["port"] == 1

    # Total 13 enterprise hosts (including DMZ, External & Legacy Sinkhole)
    assert len(controller.arp_table) == 13


def test_routing_table_shortest_path_continuity():
    """Verify end-to-end shortest path forwarding (S3 <-> S1 <-> S10)."""
    controller = SelfDefendingSDNController()

    # Forward direction: h1 (10.0.0.1) -> web1 (10.0.0.11)
    # S3 forwards 10.0.0.11 out port 98 (to S1)
    assert controller.routing_table[3]["10.0.0.11"] == 98
    # S1 forwards 10.0.0.11 out port 7 (to S10)
    assert controller.routing_table[1]["10.0.0.11"] == 7
    # S10 forwards 10.0.0.11 out port 1 (to local host web1)
    assert controller.routing_table[10]["10.0.0.11"] == 1

    # Reverse direction: web1 (10.0.0.11) -> h1 (10.0.0.1)
    # S10 forwards 10.0.0.1 out port 98 (to S1)
    assert controller.routing_table[10]["10.0.0.1"] == 98
    # S1 forwards 10.0.0.1 out port 2 (to S3)
    assert controller.routing_table[1]["10.0.0.1"] == 2
    # S3 forwards 10.0.0.1 out port 1 (to local host h1)
    assert controller.routing_table[3]["10.0.0.1"] == 1


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
    datapath.id = 3  # User edge S3
    datapath.ofproto_parser = MagicMock()
    datapath.ofproto = MagicMock()

    eth = MagicMock()
    ip_pkt = MagicMock()
    ip_pkt.dst = "10.0.0.11"  # h5 Web server

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
        ipv4_dst="10.0.0.11",
    )

    # Verify PacketOut sent for first packet zero-loss
    datapath.ofproto_parser.OFPPacketOut.assert_called_once()
    datapath.send_msg.assert_called_once()


def test_ipv4_loopback_guard():
    """Verify packet with out_port == in_port is dropped to prevent loop."""
    controller = SelfDefendingSDNController()
    controller.add_flow = MagicMock()

    datapath = MagicMock()
    datapath.id = 3

    eth = MagicMock()
    ip_pkt = MagicMock()
    # Routing table maps 10.0.0.1 -> out_port 1 on S3
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
    datapath.id = 3

    eth = MagicMock()
    ip_pkt = MagicMock()
    ip_pkt.dst = "172.16.0.50"  # Not in routing_table[3]

    raw_data = b"\x00" * 64

    controller.handle_ipv4(
        datapath, in_port=1, eth=eth, ip_pkt=ip_pkt, data=raw_data
    )

    controller.add_flow.assert_not_called()
    datapath.send_msg.assert_not_called()


# ---------------------------------------------------------------------
# Manual RESTORE hold: an operator's restore is not undone by the next alert
# ---------------------------------------------------------------------
from harness.contracts.sdn_events import (  # noqa: E402
    MANUAL_RESTORE_HOLD_SEC,
    REDIS_CHANNEL_ANOMALY_ALERT,
    REDIS_CHANNEL_CONTROL_COMMAND,
    AnomalyAlertMessage,
    ControlCommandMessage,
)


def _defense_controller():
    controller = SelfDefendingSDNController()
    for name in ("isolate_port", "restore_port", "reroute_traffic", "restore_reroute_traffic",
                 "_publish_control_command", "_publish_topology_sync"):
        setattr(controller, name, MagicMock())
    return controller


def _attack_alert():
    return AnomalyAlertMessage(dpid=3, in_port=2, score=-0.3, pps=1500.0, bps=650000.0, bpp=54.0).model_dump_json()


def _command(command_id, action):
    return ControlCommandMessage(command_id=command_id, action=action, target_dpid=3, target_port=2,
                                 reason="[MANUAL] admin: AI 오탐 의심").model_dump_json()


def test_manual_restore_holds_auto_isolation_while_attack_continues():
    """공격 중 수동 복원 → 다음 경보가 와도 보류 시간 동안은 다시 격리하지 않는다."""
    controller = _defense_controller()
    controller._handle_redis_message(REDIS_CHANNEL_ANOMALY_ALERT, _attack_alert())
    assert controller.isolate_port.call_count == 1

    controller._handle_redis_message(REDIS_CHANNEL_CONTROL_COMMAND, _command("manual-restore-1", "RESTORE"))
    controller.restore_port.assert_called_once()
    assert "3:2" in controller.manual_holds

    controller._handle_redis_message(REDIS_CHANNEL_ANOMALY_ALERT, _attack_alert())
    assert controller.isolate_port.call_count == 1  # not re-isolated during the hold


def test_auto_isolation_resumes_after_manual_hold_expires():
    controller = _defense_controller()
    controller._handle_redis_message(REDIS_CHANNEL_CONTROL_COMMAND, _command("manual-restore-1", "RESTORE"))
    controller.manual_holds["3:2"] -= MANUAL_RESTORE_HOLD_SEC + 1  # hold already over

    controller._handle_redis_message(REDIS_CHANNEL_ANOMALY_ALERT, _attack_alert())
    controller.isolate_port.assert_called_once()
    assert "3:2" not in controller.manual_holds


def test_manual_isolate_ends_the_hold_and_auto_restore_sets_none():
    controller = _defense_controller()
    controller._handle_redis_message(REDIS_CHANNEL_CONTROL_COMMAND, _command("manual-restore-1", "RESTORE"))
    controller._handle_redis_message(REDIS_CHANNEL_CONTROL_COMMAND, _command("manual-isolate-2", "ISOLATE"))
    assert "3:2" not in controller.manual_holds

    # Only operator commands create a hold.
    controller._handle_redis_message(REDIS_CHANNEL_CONTROL_COMMAND, _command("standin-restore-3", "RESTORE"))
    assert controller.manual_holds == {}
