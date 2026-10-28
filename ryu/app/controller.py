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


from harness.contracts.sdn_events import (
    MANUAL_RESTORE_HOLD_SEC,
    REDIS_CHANNEL_ANOMALY_ALERT,
    REDIS_CHANNEL_CONTROL_COMMAND,
    REDIS_CHANNEL_FLOW_COUNTS,
    REDIS_CHANNEL_TOPOLOGY_SYNC,
    WARNING_HOLD_SEC,
    WARNING_RATE_LIMIT_PPS,
    AnomalyAlertMessage,
    ControlCommandMessage,
    CountKind,
    DefenseAction,
    FlowCountItem,
    FlowCountMessage,
    RiskStage,
    ThreatType,
    TopologyLink,
    TopologyNode,
    TopologySyncMessage,
)
from harness.safety.circuit_breaker import CircuitBreaker
from harness.safety.flapping_fsm import DefenseState, FlappingFSM
from harness.safety.whitelist_guard import WhitelistGuard
try:
    from ryu.app.reroute import RerouteEngine
except ImportError:
    try:
        from reroute import RerouteEngine
    except ImportError:
        import sys
        from pathlib import Path
        sys.path.append(str(Path(__file__).resolve().parent))
        from reroute import RerouteEngine


# 3단 플로우 테이블: 0 = 종류별로 세기 → 1 = 경고 단계 속도 제한 → 2 = 전달(격리·우회·최단 경로).
# 세는 규칙이 맨 앞에 있어서 격리 중에도 공격 패킷 수를 계속 셀 수 있다 (공격이 멈췄는지 판단용).
TABLE_COUNT = 0
TABLE_POLICE = 1
TABLE_FORWARD = 2

# 세는 규칙의 cookie: 상위 16비트 태그 + dpid(24비트) + 포트(16비트) + 종류 번호(8비트)
COUNT_COOKIE_TAG = 0xC0DE << 48
COUNT_COOKIE_MASK = 0xFFFF << 48
COUNT_KINDS = [k.value for k in CountKind]

TCP_FIN, TCP_SYN, TCP_RST, TCP_ACK = 0x001, 0x002, 0x004, 0x010


def count_cookie(dpid: int, port: int, kind: str) -> int:
    return COUNT_COOKIE_TAG | (dpid << 24) | (port << 8) | COUNT_KINDS.index(kind)


def decode_count_cookie(cookie: int):
    """세는 규칙 cookie → (dpid, port, kind). 다른 규칙이면 None."""
    if cookie & COUNT_COOKIE_MASK != COUNT_COOKIE_TAG:
        return None
    index = cookie & 0xFF
    if index >= len(COUNT_KINDS):
        return None
    return (cookie >> 24) & 0xFFFFFF, (cookie >> 8) & 0xFFFF, COUNT_KINDS[index]


def police_matches(threat_type: str) -> list:
    """경고 단계에서 속도를 제한할 패킷 종류 (in_port 외의 매칭 조건). 모르는 종류면 포트 전체."""
    udp = {"eth_type": 0x0800, "ip_proto": 17}
    icmp = {"eth_type": 0x0800, "ip_proto": 1}
    syn = {"eth_type": 0x0800, "ip_proto": 6, "tcp_flags": (TCP_SYN, TCP_SYN | TCP_ACK)}
    return {ThreatType.UDP_FLOOD.value: [udp], ThreatType.ICMP_FLOOD.value: [icmp],
            ThreatType.SYN_FLOOD_SPOOFING.value: [syn],
            # 포트 스캔은 TCP(SYN)와 UDP 둘 다 쓰므로 둘 다 제한
            ThreatType.PORT_SCAN.value: [syn, udp]}.get(threat_type, [{}])


def count_rule_specs(arp_table):
    """접속 호스트마다 0번 테이블에 깔 세는 규칙 (dpid, port, kind, priority, match 인자).

    한 패킷은 한 테이블에서 규칙 하나에만 걸리므로 우선순위로 겹침을 정리한다: 호스트가 '보내는'
    패킷(in_port 기준)이 먼저, 호스트로 '들어오는' 실패 응답(ipv4_dst 기준)이 그다음이다.
    """
    specs = []
    for ip, host in arp_table.items():
        dpid, port = host["dpid"], host["port"]
        out = {"in_port": port, "eth_type": 0x0800}
        specs += [
            (dpid, port, CountKind.SYN.value, 204, {**out, "ip_proto": 6, "tcp_flags": (TCP_SYN, TCP_SYN | TCP_ACK)}),
            (dpid, port, CountKind.RST.value, 203, {**out, "ip_proto": 6, "tcp_flags": (TCP_RST, TCP_RST)}),
            (dpid, port, CountKind.FIN.value, 202, {**out, "ip_proto": 6, "tcp_flags": (TCP_FIN, TCP_FIN)}),
            (dpid, port, CountKind.UDP.value, 201, {**out, "ip_proto": 17}),
            (dpid, port, CountKind.ICMP.value, 200, {**out, "ip_proto": 1}),
            (dpid, port, CountKind.RST_IN.value, 150,
             {"eth_type": 0x0800, "ipv4_dst": ip, "ip_proto": 6, "tcp_flags": (TCP_RST, TCP_RST)}),
            (dpid, port, CountKind.UNREACH_IN.value, 150,
             {"eth_type": 0x0800, "ipv4_dst": ip, "ip_proto": 1, "icmpv4_type": 3}),
        ]
    return specs


class SelfDefendingSDNController(app_manager.RyuApp):
    """OpenFlow 1.3 L2/L3 스위칭, 텔레메트리 및 자율 방어 컨트롤러"""
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

        # 7~13주차 핵심 엔진 인스턴스화
        self.whitelist_guard = WhitelistGuard()
        self.reroute_engine = RerouteEngine()
        self.circuit_breaker = CircuitBreaker()
        self.fsm = FlappingFSM(
            cooldown_sec=10.0,
            on_state_change=self._on_fsm_state_change,
        )
        # 수동 RESTORE 보류: {"dpid:port": 보류 만료 시각}. 이 시각 전까지는 AI 경보로 다시 격리하지 않음
        self.manual_holds = {}
        # 경고 단계 속도 제한 중인 포트: {"dpid:port": 마지막 WARNING 경보 시각}
        self.rate_limits = {}
        # 세는 규칙이 있는 스위치 (접속 호스트가 붙은 스위치만 카운트를 요청한다)
        self.count_dpids = {host["dpid"] for host in self.arp_table.values()}

        # 2초 주기 비차단 포트 통계 폴링 그린스레드 가동
        self.monitor_thread = hub.spawn(self._monitor_loop)
        # Redis 제어/경보 비동기 구독 수신 그린스레드 가동
        self.command_subscriber_thread = hub.spawn(self._command_listener_loop)

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
                socket_connect_timeout=0.5,
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
                try:
                    self._request_stats(dp)
                    if dp.id in self.count_dpids:
                        self._request_count_stats(dp)
                except Exception as e:
                    self.logger.warning(
                        f"[Telemetry] Stats request failed for S{dp.id}: {e}"
                    )

    def _request_stats(self, datapath):
        """OFPPortStatsRequest 메시지 발송"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        req = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY)
        datapath.send_msg(req)

    def _request_count_stats(self, datapath):
        """0번 테이블의 세는 규칙(cookie 태그)만 골라 플로우 통계 요청"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        req = parser.OFPFlowStatsRequest(
            datapath, 0, TABLE_COUNT, ofproto.OFPP_ANY, ofproto.OFPG_ANY,
            COUNT_COOKIE_TAG, COUNT_COOKIE_MASK, parser.OFPMatch(),
        )
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def flow_stats_reply_handler(self, ev):
        """세는 규칙의 누적 패킷 수를 sdn:stats:flowcount 채널로 발행"""
        counts = []
        for stat in ev.msg.body:
            decoded = decode_count_cookie(stat.cookie)
            if decoded is None:
                continue
            _, port, kind = decoded
            counts.append(FlowCountItem(port_no=port, kind=kind, packets=stat.packet_count))
        if not counts:
            return
        msg = FlowCountMessage(timestamp=time.time(), dpid=ev.msg.datapath.id, counts=counts)
        try:
            if not self.redis_client:
                self._init_redis()
            if self.redis_client:
                self.redis_client.publish(REDIS_CHANNEL_FLOW_COUNTS, msg.model_dump_json())
        except Exception as e:
            self.logger.warning(f"[Telemetry] Failed to publish flow counts: {e}")
            self.redis_client = None

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

        # 0번(세기)·1번(속도 제한) 테이블: 걸리지 않은 패킷은 다음 테이블로
        for table_id in (TABLE_COUNT, TABLE_POLICE):
            self.add_flow(datapath, priority=0, match=parser.OFPMatch(), actions=[], table_id=table_id,
                          instructions=[parser.OFPInstructionGotoTable(table_id + 1)])
        # 0번 테이블: 이 스위치에 붙은 호스트의 종류별 세는 규칙
        for dpid, port, kind, priority, match_kwargs in count_rule_specs(self.arp_table):
            if dpid != datapath.id:
                continue
            self.add_flow(datapath, priority=priority, match=parser.OFPMatch(**match_kwargs), actions=[],
                          table_id=TABLE_COUNT, cookie=count_cookie(dpid, port, kind),
                          instructions=[parser.OFPInstructionGotoTable(TABLE_POLICE)])

        # 전달 테이블 Table-Miss Flow (Priority 0) 등록: 미매칭 패킷은 컨트롤러로 보고
        match = parser.OFPMatch()
        actions = [
            parser.OFPActionOutput(
                ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER
            )
        ]
        self.add_flow(datapath, priority=0, match=match, actions=actions)
        self.logger.info(
            f"Switch S{datapath.id} Connected. Count/Police/Forward tables and Table-Miss Installed."
        )

    def add_flow(
        self, datapath, priority, match, actions,
        idle_timeout=0, hard_timeout=0, table_id=TABLE_FORWARD, cookie=0, instructions=None
    ):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = instructions if instructions is not None else [
            parser.OFPInstructionActions(
                ofproto.OFPIT_APPLY_ACTIONS, actions
            )
        ]
        mod = parser.OFPFlowMod(
            datapath=datapath,
            table_id=table_id,
            cookie=cookie,
            priority=priority,
            match=match,
            instructions=inst,
            idle_timeout=idle_timeout,
            hard_timeout=hard_timeout,
            buffer_id=ofproto.OFP_NO_BUFFER,
        )
        datapath.send_msg(mod)

    def delete_flow(self, datapath, priority, match, table_id=TABLE_FORWARD):
        """특정 우선순위 및 매칭 규칙의 플로우 엔트리 명시적 삭제 (OFPFC_DELETE)"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        mod = parser.OFPFlowMod(
            datapath=datapath,
            table_id=table_id,
            command=ofproto.OFPFC_DELETE,
            out_port=ofproto.OFPP_ANY,
            out_group=ofproto.OFPG_ANY,
            priority=priority,
            match=match,
            buffer_id=ofproto.OFP_NO_BUFFER,
        )
        datapath.send_msg(mod)

    def rate_limit_port(self, dpid: int, in_port: int, threat_type: str = "", pps: int = WARNING_RATE_LIMIT_PPS):
        """경고 단계: 해당 포트에서 그 공격 종류의 패킷만 초당 pps개로 제한 (미터 + 1번 테이블 규칙).

        UDP Flood면 UDP만, SYN Flood면 SYN만, 포트 스캔이면 SYN과 UDP만 제한해서 같은 포트의 다른 정상
        트래픽(웹 응답 ACK, 다운로드 등)은 그대로 지나가게 한다. 모르는 종류면 포트 전체를 제한한다.
        규칙이 여러 개여도 미터 하나를 같이 쓴다.
        """
        self.whitelist_guard.validate_isolation_target(dpid, in_port)
        datapath = self.datapaths.get(dpid)
        if not datapath:
            return False
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        # 포트 번호를 미터 번호로 쓴다 (스위치마다 따로라 겹치지 않음). 다시 설치하면 덮어쓴다.
        for command in (ofproto.OFPMC_DELETE, ofproto.OFPMC_ADD):
            datapath.send_msg(parser.OFPMeterMod(
                datapath, command=command, flags=ofproto.OFPMF_PKTPS | ofproto.OFPMF_BURST, meter_id=in_port,
                bands=[parser.OFPMeterBandDrop(rate=pps, burst_size=pps)] if command == ofproto.OFPMC_ADD else []))
        self.delete_flow(datapath, priority=100, match=parser.OFPMatch(in_port=in_port), table_id=TABLE_POLICE)
        for extra in police_matches(threat_type):
            self.add_flow(datapath, priority=100, match=parser.OFPMatch(in_port=in_port, **extra),
                          actions=[], table_id=TABLE_POLICE,
                          instructions=[parser.OFPInstructionMeter(in_port),
                                        parser.OFPInstructionGotoTable(TABLE_FORWARD)])
        self.logger.info(f"[Defense] S{dpid}: In_port {in_port} {threat_type or 'all'} RATE LIMITED to {pps} pps")
        return True

    def unrate_limit_port(self, dpid: int, in_port: int):
        """경고 단계 해제: 속도 제한 규칙과 미터 삭제."""
        datapath = self.datapaths.get(dpid)
        if not datapath:
            return False
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        self.delete_flow(datapath, priority=100, match=parser.OFPMatch(in_port=in_port), table_id=TABLE_POLICE)
        datapath.send_msg(parser.OFPMeterMod(datapath, command=ofproto.OFPMC_DELETE, flags=0,
                                             meter_id=in_port, bands=[]))
        self.logger.info(f"[Defense] S{dpid}: In_port {in_port} rate limit lifted")
        return True

    def isolate_port(self, dpid: int, in_port: int, priority: int = 100):
        """
        9주차: 유입 포트 기반 Priority 100 Drop 규칙 주입 (컨트롤러 고갈 원천 방어)
        화이트리스트 가드레일로 Trunk 포트 오차단을 원천 차단함.
        """
        # 1. 화이트리스트 안전 검증
        self.whitelist_guard.validate_isolation_target(dpid, in_port)

        datapath = self.datapaths.get(dpid)
        if not datapath:
            self.logger.warning(
                f"[Defense] Cannot isolate S{dpid}:P{in_port}: switch not connected"
            )
            return False

        parser = datapath.ofproto_parser
        # in_port 매칭, actions=[] (Drop)
        match = parser.OFPMatch(in_port=in_port)
        self.add_flow(datapath, priority=priority, match=match, actions=[])
        self.logger.info(
            f"[Defense] S{dpid}: In_port {in_port} ISOLATED (Priority {priority} Drop Installed)"
        )
        return True

    def restore_port(self, dpid: int, in_port: int, priority: int = 100):
        """11주차: 차단된 In_port Drop 규칙 삭제 및 통신 복원"""
        datapath = self.datapaths.get(dpid)
        if not datapath:
            return False

        parser = datapath.ofproto_parser
        match = parser.OFPMatch(in_port=in_port)
        self.delete_flow(datapath, priority=priority, match=match)
        self.logger.info(
            f"[Defense] S{dpid}: In_port {in_port} RESTORED (Drop Flow Deleted)"
        )
        return True

    def reroute_traffic(self, source_dpid: int = 1, target_dpid: int = 4, dst_ip: str = "10.0.0.4"):
        """
        10주차: NetworkX Dijkstra 기반 다중 홉 선제적 OFPFC_ADD 우회 라우팅 주입.
        중간 스위치(예: S3)에 먼저 규칙을 설치한 후 Ingress 스위치(S1)를 전환하여 무유실 보장.
        """
        path = self.reroute_engine.compute_reroute_path(source_dpid, target_dpid, congested_intermediate_dpid=2)
        if not path:
            self.logger.warning(f"[Reroute] No path found between S{source_dpid} and S{target_dpid}")
            return False

        specs = self.reroute_engine.get_path_flow_specs(path, dst_ip)
        for spec in specs:
            dp = self.datapaths.get(spec["dpid"])
            if not dp:
                continue
            parser = dp.ofproto_parser
            actions = [parser.OFPActionOutput(spec["out_port"])]
            # 우회 경로는 기본 경로(priority 10)보다 높은 priority 20으로 주입 (복구 시 명시적 삭제)
            match = parser.OFPMatch(eth_type=0x0800, ipv4_dst=dst_ip)
            self.add_flow(dp, priority=20, match=match, actions=actions, idle_timeout=0)
            self.logger.info(
                f"[Reroute] S{spec['dpid']}: Injected priority 20 flow -> Port {spec['out_port']} for {dst_ip}"
            )

        self.logger.info(f"[Reroute] Successfully activated bypass route: {path} for {dst_ip}")
        return True

    def restore_reroute_traffic(
        self,
        source_dpid: int = 1,
        target_dpid: int = 4,
        dst_ip: str = "10.0.0.4",
        priority: int = 20,
    ):
        """
        11주차: 복구 시 우회 경로(Priority 20) 플로우 규칙 명시적 삭제.
        Ingress 스위치(S1)부터 역순으로 우회 규칙을 제거하여 즉시 주 경로(S1-S2-S4)로 복귀.
        """
        path = self.reroute_engine.compute_reroute_path(
            source_dpid, target_dpid, congested_intermediate_dpid=2
        )
        if not path:
            return False

        specs = self.reroute_engine.get_path_flow_specs(path, dst_ip)
        for spec in reversed(specs):
            dp = self.datapaths.get(spec["dpid"])
            if not dp:
                continue
            parser = dp.ofproto_parser
            match = parser.OFPMatch(eth_type=0x0800, ipv4_dst=dst_ip)
            self.delete_flow(dp, priority=priority, match=match)
            self.logger.info(
                f"[Reroute] S{spec['dpid']}: Deleted priority {priority} bypass flow for {dst_ip}"
            )

        self.logger.info(f"[Reroute] Restored primary route from bypass: {path} for {dst_ip}")
        return True

    def _publish_topology_sync(self, phase_name: str = "NORMAL"):
        """Redis sdn:topology:sync 채널로 실시간 토폴로지 링크/노드 상태 브로드캐스트"""
        attacked = (phase_name == "ATTACK_DETECTED")
        mitigated = (phase_name in ("MITIGATED", "COOLDOWN_VERIFY", "COOLDOWN"))
        s1_status = "ATTACKED" if attacked else "MITIGATED" if mitigated else "NORMAL"

        nodes = [
            TopologyNode(id="s1", label="S1 (Ingress)", node_type="switch", dpid=1, status=s1_status),
            TopologyNode(id="s2", label="S2 (Primary)", node_type="switch", dpid=2),
            TopologyNode(id="s3", label="S3 (Bypass)", node_type="switch", dpid=3),
            TopologyNode(id="s4", label="S4 (Egress)", node_type="switch", dpid=4),
            TopologyNode(id="h_legit", label="H_legit", node_type="host", ip="10.0.0.1", mac="00:00:00:00:00:01"),
            TopologyNode(
                id="h_attacker", label="H_attacker", node_type="host",
                ip="10.0.0.2", mac="00:00:00:00:00:02", status=s1_status
            ),
            TopologyNode(id="h_server", label="H_server", node_type="host", ip="10.0.0.4", mac="00:00:00:00:00:04"),
        ]

        bypass_status = "REROUTED" if mitigated else "ACTIVE"
        links = [
            TopologyLink(source="s1", target="h_legit", src_port=1, dst_port=1),
            TopologyLink(
                source="s1", target="h_attacker", src_port=2, dst_port=1,
                status="BLOCKED" if mitigated else "ACTIVE"
            ),
            TopologyLink(source="s1", target="s2", src_port=3, dst_port=1, is_trunk=True),
            TopologyLink(source="s1", target="s3", src_port=4, dst_port=1, is_trunk=True, status=bypass_status),
            TopologyLink(source="s2", target="s4", src_port=2, dst_port=2, is_trunk=True),
            TopologyLink(source="s3", target="s4", src_port=2, dst_port=3, is_trunk=True, status=bypass_status),
            TopologyLink(source="s4", target="h_server", src_port=1, dst_port=1),
        ]

        sync_msg = TopologySyncMessage(
            timestamp=time.time(), phase=phase_name, nodes=nodes, links=links
        )
        try:
            if not self.redis_client:
                self._init_redis()
            if self.redis_client:
                self.redis_client.publish(REDIS_CHANNEL_TOPOLOGY_SYNC, sync_msg.model_dump_json())
                self.logger.debug(f"[TopologySync] Broadcasted {phase_name} topology to Redis")
        except Exception as e:
            self.logger.warning(f"[TopologySync] Failed to publish topology sync: {e}")

    def _publish_control_command(self, action: str, dpid: int, port: int, reason: str, priority: int = 100):
        """자율 방어 조치 내역을 sdn:control:command 채널에 발행하여 웹 대시보드 이벤트 타임라인에 기록"""
        cmd = ControlCommandMessage(
            command_id=f"auto-{action.lower()}-{int(time.time()*1000)}",
            action=action,
            target_dpid=dpid,
            target_port=port,
            reason=reason,
            priority=priority,
            timestamp=time.time(),
        )
        try:
            if not self.redis_client:
                self._init_redis()
            if self.redis_client:
                self.redis_client.publish(REDIS_CHANNEL_CONTROL_COMMAND, cmd.model_dump_json())
        except Exception as e:
            self.logger.warning(f"[Audit Command] Failed to publish control command: {e}")

    def _on_fsm_state_change(self, prev_state, next_state, meta):
        """11주차: FSM 상태 전이 이벤트 핸들러"""
        self.logger.info(
            f"[FSM] Transition: {prev_state.value} -> {next_state.value} (meta: {meta})"
        )
        if next_state == DefenseState.NORMAL:
            # 정상 상태 롤백: 등록된 격리 타깃들 복원 및 우회 경로(Priority 20) 삭제
            cleared = meta.get("cleared_targets", {})
            restored_sources = set()
            for key, info in cleared.items():
                self.restore_port(info["dpid"], info["in_port"])
                if info["dpid"] not in restored_sources:
                    self.restore_reroute_traffic(
                        source_dpid=info["dpid"], target_dpid=4, dst_ip="10.0.0.4"
                    )
                    restored_sources.add(info["dpid"])
                self._publish_control_command(
                    action=DefenseAction.RESTORE.value,
                    dpid=info["dpid"],
                    port=info["in_port"],
                    reason="Attack ceased: 10s cooldown passed, autonomous rollback",
                )
            self._publish_topology_sync("NORMAL")
            self.logger.info("[FSM] All defense flows rolled back to NORMAL baseline.")
        elif next_state in (DefenseState.COOLDOWN, DefenseState.COOLDOWN_VERIFY):
            self._publish_topology_sync("COOLDOWN_VERIFY")

    def _command_listener_loop(self):
        """
        13주차: Redis sdn:control:command 및 sdn:anomaly:alert 비동기 구독 루프
        AI 이상 감지 경보 수신 시 FSM 트리거 및 차단/우회 실행,
        수동 관리자 명령 및 긴급 서킷 브레이커 안전 가드 연동.
        """
        while True:
            try:
                if not self.redis_client:
                    self._init_redis()
                if not self.redis_client:
                    hub.sleep(2.0)
                    continue

                pubsub = self.redis_client.pubsub()
                pubsub.subscribe(REDIS_CHANNEL_ANOMALY_ALERT, REDIS_CHANNEL_CONTROL_COMMAND)
                self.logger.info(
                    f"[Redis Sub] Subscribed to {REDIS_CHANNEL_ANOMALY_ALERT} and {REDIS_CHANNEL_CONTROL_COMMAND}"
                )

                while True:
                    # timeout=0.1로 짧게 대기하여 Eventlet 코루틴 협력적 스케줄링 양보 보장
                    msg = pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
                    # 주기적 FSM 쿨다운 하트비트 평가 + 경고 단계 속도 제한 만료 처리
                    self.fsm.evaluate_heartbeat()
                    self._expire_rate_limits()

                    if not msg:
                        hub.sleep(0.05)
                        continue

                    channel = msg.get("channel")
                    data_str = msg.get("data")
                    if not data_str or not isinstance(data_str, str):
                        hub.sleep(0.01)
                        continue

                    self._handle_redis_message(channel, data_str)
                    hub.sleep(0.01)

            except Exception as e:
                self.logger.warning(f"[Redis Sub] Listener exception: {e}. Reconnecting in 2s...")
                hub.sleep(2.0)

    def _manual_hold_active(self, dpid: int, port: int) -> bool:
        """수동 RESTORE 보류 시간 안이면 True. 만료된 보류는 지운다."""
        key = f"{dpid}:{port}"
        until = self.manual_holds.get(key)
        if until is None:
            return False
        remaining = until - time.time()
        if remaining > 0:
            self.logger.info(f"[Manual Hold] S{dpid}:P{port} 수동 복원 보류 중 → 자동 격리 생략 (남은 {remaining:.0f}s)")
            return True
        del self.manual_holds[key]
        return False

    def _expire_rate_limits(self, now=None):
        """마지막 WARNING 경보 뒤 WARNING_HOLD_SEC 동안 경보가 없으면 속도 제한을 푼다."""
        now = now if now is not None else time.time()
        for key, last in list(self.rate_limits.items()):
            if now - last < WARNING_HOLD_SEC:
                continue
            dpid, port = (int(x) for x in key.split(":"))
            del self.rate_limits[key]
            self.unrate_limit_port(dpid, port)
            self._publish_control_command(
                action=DefenseAction.UNLIMIT.value, dpid=dpid, port=port,
                reason=f"Warning ceased: {WARNING_HOLD_SEC:.0f}s without alerts, rate limit lifted", priority=100)
            if self.fsm.get_state() == DefenseState.NORMAL and not self.rate_limits:
                self._publish_topology_sync("NORMAL")

    def _handle_warning_alert(self, alert):
        """경고(WARNING) 경보: 격리하지 않고 그 포트만 속도 제한. 이미 격리된 포트면 격리 유지(하트비트)."""
        target_key = f"{alert.dpid}:{alert.in_port}"
        if self.fsm.get_state() != DefenseState.NORMAL and target_key in self.fsm.mitigated_targets:
            # 위험 단계에서 격리 중인데 공격이 약해진 경우: 공격이 이어지는 동안 격리를 유지한다.
            self.fsm.trigger_anomaly(alert.dpid, alert.in_port, threat_info=alert.model_dump())
            return
        first = target_key not in self.rate_limits
        self.rate_limits[target_key] = time.time()
        if first and self.rate_limit_port(alert.dpid, alert.in_port, alert.threat_type):
            self._publish_control_command(
                action=DefenseAction.RATE_LIMIT.value, dpid=alert.dpid, port=alert.in_port,
                reason=f"Warning: {alert.threat_type} confirmed, limit those packets to {WARNING_RATE_LIMIT_PPS} pps",
                priority=100)
            self._publish_topology_sync("ATTACK_DETECTED")

    def _handle_redis_message(self, channel: str, data_str: str):
        """수신된 Redis 채널 메시지 파싱 및 제어 디스패치"""
        try:
            if channel == REDIS_CHANNEL_ANOMALY_ALERT:
                alert = AnomalyAlertMessage.model_validate_json(data_str)
                # 운영자가 수동 복원한 포트는 보류 시간 동안 자동 재격리 생략 (명령이 아니므로 서킷 브레이커 집계 전)
                if self._manual_hold_active(alert.dpid, alert.in_port):
                    return
                # 서킷 브레이커 가드 검사
                if not self.circuit_breaker.record_command():
                    self.logger.error(
                        f"[CircuitBreaker] Alert rejected! Status: {self.circuit_breaker.get_status()}"
                    )
                    return

                self.logger.info(
                    f"[Alert Ingested] Anomaly on S{alert.dpid}:P{alert.in_port} "
                    f"(threat: {alert.threat_type}, stage: {alert.stage}, score: {alert.score})"
                )
                if alert.stage == RiskStage.WARNING.value:
                    if self.whitelist_guard.can_isolate(alert.dpid, alert.in_port):
                        self._handle_warning_alert(alert)
                    return
                # 위험(DANGER): In_port 차단 (트렁크는 화이트리스트가 방어)
                if self.whitelist_guard.can_isolate(alert.dpid, alert.in_port):
                    target_key = f"{alert.dpid}:{alert.in_port}"
                    if target_key in self.rate_limits:
                        # 경고에서 위험으로 올라감: 속도 제한 대신 격리
                        del self.rate_limits[target_key]
                        self.unrate_limit_port(alert.dpid, alert.in_port)
                    already_mitigated = (
                        self.fsm.get_state() != DefenseState.NORMAL
                        and target_key in self.fsm.mitigated_targets
                    )
                    if not already_mitigated:
                        self.isolate_port(alert.dpid, alert.in_port, priority=100)
                        self._publish_control_command(
                            action=DefenseAction.ISOLATE.value,
                            dpid=alert.dpid,
                            port=alert.in_port,
                            reason=f"Autonomous In_port Drop: {alert.threat_type} (score {alert.score:.2f})",
                            priority=100,
                        )
                        # 2. 다중 홉 우회 라우팅 선제 설치
                        self.reroute_traffic(source_dpid=alert.dpid, target_dpid=4, dst_ip="10.0.0.4")
                        self._publish_control_command(
                            action=DefenseAction.REROUTE.value,
                            dpid=alert.dpid,
                            port=4,
                            reason="Autonomous Bypass: Proactive S1-S3-S4 Rerouting",
                            priority=20,
                        )
                        # 3. FSM 상태 전이
                        self.fsm.trigger_anomaly(alert.dpid, alert.in_port, threat_info=alert.model_dump())
                        # 4. 실시간 토폴로지 동기화 발행
                        self._publish_topology_sync("MITIGATED")
                    else:
                        # 이미 격리된 타깃: FSM 하트비트(쿨다운 타이머)만 연장하고 중복 명령 기록 발행 생략
                        prev_state = self.fsm.get_state()
                        self.fsm.trigger_anomaly(alert.dpid, alert.in_port, threat_info=alert.model_dump())
                        if prev_state != DefenseState.MITIGATED:
                            self._publish_topology_sync("MITIGATED")

            elif channel == REDIS_CHANNEL_CONTROL_COMMAND:
                cmd = ControlCommandMessage.model_validate_json(data_str)
                # 자신이 발행한 auto 커맨드는 중복 실행 방지
                if cmd.command_id.startswith("auto-"):
                    return

                self.logger.info(
                    f"[Control Cmd] Action: {cmd.action} on S{cmd.target_dpid}:P{cmd.target_port} (reason: {cmd.reason})"
                )
                is_manual = cmd.command_id.startswith("manual-")
                target_key = f"{cmd.target_dpid}:{cmd.target_port}"
                if cmd.action == "ISOLATE":
                    if is_manual:
                        # 운영자가 다시 격리하면 보류도 끝
                        self.manual_holds.pop(target_key, None)
                    self.isolate_port(cmd.target_dpid, cmd.target_port, priority=cmd.priority)
                    self._publish_topology_sync("MITIGATED")
                elif cmd.action == "RESTORE":
                    if self.rate_limits.pop(target_key, None) is not None:
                        self.unrate_limit_port(cmd.target_dpid, cmd.target_port)
                    self.restore_port(cmd.target_dpid, cmd.target_port, priority=cmd.priority)
                    self.restore_reroute_traffic(
                        source_dpid=cmd.target_dpid, target_dpid=4, dst_ip="10.0.0.4"
                    )
                    self.fsm.force_restore()
                    if is_manual:
                        # 공격이 이어져도 다음 경보(2초 이내)가 바로 다시 막지 않도록 자동 재격리 보류
                        self.manual_holds[target_key] = time.time() + MANUAL_RESTORE_HOLD_SEC
                    self._publish_topology_sync("NORMAL")
                elif cmd.action == "REROUTE":
                    self.reroute_traffic(source_dpid=cmd.target_dpid, target_dpid=4)
                    self._publish_topology_sync("MITIGATED")
        except Exception as e:
            self.logger.warning(f"[Control Dispatcher] Error processing message on {channel}: {e}")

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
