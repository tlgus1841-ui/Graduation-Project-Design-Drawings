# ryu/app/controller.py
# flake8: noqa: E402
"""
OpenFlow 1.3 L2/L3 Switching & 2-Tier Telemetry Pipeline Controller.
Author: Sihyeon Park (22101489 / Tech Lead)
Phase 2 (Week 5 & Week 6) Milestone
"""

import json
import os
import time

import eventlet
eventlet.monkey_patch()

import redis
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import (
    CONFIG_DISPATCHER,
    DEAD_DISPATCHER,
    MAIN_DISPATCHER,
    set_ev_cls,
)
from ryu.lib import hub
from ryu.lib.packet import arp, ether_types, ethernet, ipv4, packet
from ryu.ofproto import ofproto_v1_3


class SelfDefendingSDNController(app_manager.RyuApp):
    """OpenFlow 1.3 L2/L3 스위칭 및 2-Tier 텔레메트리 수집 컨트롤러"""
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SelfDefendingSDNController, self).__init__(*args, **kwargs)
        # 호스트 정적 매핑 테이블
        self.arp_table = {
            "10.0.0.1": {"mac": "00:00:00:00:00:01", "dpid": 1, "port": 1},
            "10.0.0.2": {"mac": "00:00:00:00:00:02", "dpid": 1, "port": 2},
            "10.0.0.4": {"mac": "00:00:00:00:00:04", "dpid": 4, "port": 1},
        }
        # 기본 최단 경로 라우팅 맵: {dpid: {dst_ip: out_port}}
        self.routing_table = {
            # S1 -> S4: Port 3 (S2행)
            1: {"10.0.0.1": 1, "10.0.0.2": 2, "10.0.0.4": 3},
            # S2 -> S4: Port 2, -> S1: Port 1
            2: {"10.0.0.1": 1, "10.0.0.2": 1, "10.0.0.4": 2},
            # S3 (우회용)
            3: {"10.0.0.1": 1, "10.0.0.2": 1, "10.0.0.4": 2},
            # S4 -> S1: Port 2 (S2행), -> H_server: Port 1
            4: {"10.0.0.1": 2, "10.0.0.2": 2, "10.0.0.4": 1},
        }

        # 6주차: 활성 Datapath 맵 및 Redis 텔레메트리 파이프라인 초기화
        self.datapaths = {}
        self.redis_host = os.getenv("REDIS_HOST", "127.0.0.1")
        self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
        self.redis_client = None
        self._init_redis()

        # 2초 주기 비차단 포트 통계 폴링 그린스레드 가동
        self.monitor_thread = hub.spawn(self._monitor_loop)

        self.logger.info(">>> Self-Defending Controller Ready (OF1.3)! <<<")

    def _init_redis(self):
        """Redis 클라이언트 안전 초기화 (장애 격리)"""
        try:
            self.redis_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=0,
                decode_responses=True,
                socket_timeout=0.5,
            )
            self.redis_client.ping()
            self.logger.info(
                f"[Redis] Connected to {self.redis_host}:{self.redis_port}"
            )
        except Exception as e:
            self.logger.warning(
                f"[Redis] Connection failed: {e}. Will retry on next cycle."
            )
            self.redis_client = None

    @set_ev_cls(ofp_event.EventOFPStateChange,
                [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def state_change_handler(self, ev):
        """스위치 연결 및 단절 시 Datapath 맵 동적 관리"""
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            if datapath.id not in self.datapaths:
                self.datapaths[datapath.id] = datapath
                self.logger.info(f"[Topo] Registered switch: S{datapath.id}")
        elif ev.state == DEAD_DISPATCHER:
            if datapath.id in self.datapaths:
                del self.datapaths[datapath.id]
                self.logger.info(
                    f"[Topo] Unregistered switch: S{datapath.id}"
                )

    def _monitor_loop(self):
        """2초 주기로 활성 스위치 전체에 포트 통계 요청 발송"""
        while True:
            hub.sleep(2.0)
            for dp in list(self.datapaths.values()):
                self._request_stats(dp)

    def _request_stats(self, datapath):
        """OFPPortStatsRequest 메시지 발송"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        req = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def port_stats_reply_handler(self, ev):
        """OFPPortStatsReply 수신 및 Pydantic 규격 직렬화 후 Redis 발행"""
        body = ev.msg.body
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        dpid = datapath.id

        stats_items = []
        for stat in sorted(body, key=lambda p: p.port_no):
            # OFPP_LOCAL (0xfffffffe) 및 가상 더미 포트 필터링
            if stat.port_no > ofproto.OFPP_MAX:
                continue

            stats_items.append({
                "dpid": dpid,
                "port_no": stat.port_no,
                "rx_packets": stat.rx_packets,
                "tx_packets": stat.tx_packets,
                "rx_bytes": stat.rx_bytes,
                "tx_bytes": stat.tx_bytes,
                "rx_errors": getattr(stat, "rx_errors", 0),
                "duration_sec": getattr(stat, "duration_sec", 0),
            })

        payload = {
            "timestamp": time.time(),
            "dpid": dpid,
            "stats": stats_items,
        }

        self._publish_port_stats(payload)

    def _publish_port_stats(self, payload):
        """Redis sdn:stats:port 채널로 포트 통계 실시간 발행 (장애 격리)"""
        channel = "sdn:stats:port"
        message_json = json.dumps(payload)

        try:
            if not self.redis_client:
                self._init_redis()
            if self.redis_client:
                self.redis_client.publish(channel, message_json)
                self.logger.debug(
                    f"[Telemetry] Published {len(payload['stats'])} stats "
                    f"for S{payload['dpid']}"
                )
        except Exception as e:
            self.logger.warning(
                f"[Telemetry] Failed to publish stats to Redis: {e}"
            )
            self.redis_client = None

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Table-Miss Flow (Priority 0) 등록: 미매칭 패킷은 컨트롤러로 보고
        match = parser.OFPMatch()
        actions = [
            parser.OFPActionOutput(
                ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER
            )
        ]
        self.add_flow(datapath, priority=0, match=match, actions=actions)
        self.logger.info(
            f"Switch S{datapath.id} Connected. Table-Miss Installed."
        )

    def add_flow(
        self, datapath, priority, match, actions,
        idle_timeout=0, hard_timeout=0
    ):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [
            parser.OFPInstructionActions(
                ofproto.OFPIT_APPLY_ACTIONS, actions
            )
        ]
        mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=priority,
            match=match,
            instructions=inst,
            idle_timeout=idle_timeout,
            hard_timeout=hard_timeout,
            buffer_id=ofproto.OFP_NO_BUFFER,
        )
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        in_port = msg.match['in_port']
        pkt = packet.Packet(msg.data)

        # [방어 1] LLDP 및 IPv6 무시 (IndexError 방어)
        eth = pkt.get_protocol(ethernet.ethernet)
        if not eth or eth.ethertype in (ether_types.ETH_TYPE_LLDP, 0x86dd):
            return

        # [방어 2] ARP 브로드캐스트 스톰 방어 (Proxy ARP)
        arp_pkt = pkt.get_protocol(arp.arp)
        if arp_pkt:
            self.handle_arp(datapath, in_port, eth, arp_pkt)
            return

        # [방어 3] IPv4 패킷 유니캐스트 최단 경로 포워딩
        ip_pkt = pkt.get_protocol(ipv4.ipv4)
        if ip_pkt:
            self.handle_ipv4(datapath, in_port, eth, ip_pkt, msg.data)

    def handle_arp(self, datapath, in_port, eth, arp_pkt):
        if arp_pkt.opcode == arp.ARP_REQUEST:
            target_ip = arp_pkt.dst_ip
            if target_ip in self.arp_table:
                reply_mac = self.arp_table[target_ip]["mac"]
                self.send_arp_reply(
                    datapath, reply_mac, target_ip,
                    eth.src, arp_pkt.src_ip, in_port
                )
                self.logger.info(
                    f"[Proxy ARP] S{datapath.id}:P{in_port} Answered for "
                    f"{target_ip} (MAC: {reply_mac})"
                )
            else:
                self.logger.debug(
                    f"[Proxy ARP] S{datapath.id}: Unknown {target_ip} dropped"
                )

    def send_arp_reply(
        self, datapath, src_mac, src_ip, dst_mac, dst_ip, out_port
    ):
        pkt = packet.Packet()
        pkt.add_protocol(
            ethernet.ethernet(
                ethertype=ether_types.ETH_TYPE_ARP, dst=dst_mac, src=src_mac
            )
        )
        pkt.add_protocol(
            arp.arp(
                opcode=arp.ARP_REPLY,
                src_mac=src_mac,
                src_ip=src_ip,
                dst_mac=dst_mac,
                dst_ip=dst_ip,
            )
        )
        pkt.serialize()
        actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]
        out = datapath.ofproto_parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=datapath.ofproto.OFP_NO_BUFFER,
            in_port=datapath.ofproto.OFPP_CONTROLLER,
            actions=actions,
            data=pkt.data,
        )
        datapath.send_msg(out)

    def handle_ipv4(self, datapath, in_port, eth, ip_pkt, data):
        dpid = datapath.id
        dst_ip = ip_pkt.dst
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        if (
            dpid not in self.routing_table
            or dst_ip not in self.routing_table[dpid]
        ):
            self.logger.debug(
                f"[IPv4 Drop] S{dpid}: unknown destination {dst_ip}"
            )
            return

        out_port = self.routing_table[dpid][dst_ip]

        # [방어 4] 유입 포트 동일 루프백(Hairpinning) 방어
        if out_port == in_port:
            self.logger.warning(
                f"[Guard] S{dpid}: out_port == in_port ({in_port}), drop"
            )
            return

        actions = [parser.OFPActionOutput(out_port)]

        # [필수 조건] eth_type=0x0800 반드시 선언 (OpenFlow 1.3 표준 준수)
        match = parser.OFPMatch(eth_type=0x0800, ipv4_dst=dst_ip)
        self.add_flow(
            datapath, priority=10, match=match,
            actions=actions, idle_timeout=60
        )
        self.logger.info(
            f"[Flow Mod] S{dpid}: dst {dst_ip} -> OutPort {out_port}"
        )

        # 첫 패킷 무유실 포워딩
        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=ofproto.OFP_NO_BUFFER,
            in_port=in_port,
            actions=actions,
            data=data,
        )
        datapath.send_msg(out)
