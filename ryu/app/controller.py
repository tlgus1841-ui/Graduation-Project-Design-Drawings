# ryu/app/controller.py
# flake8: noqa: E402
"""
OpenFlow 1.3 L2/L3 Switching & 2-Tier Telemetry Pipeline Controller.
Author: Sihyeon Park (22101489 / Tech Lead)
Phase 2 (Week 5 & Week 6) Milestone
"""

import json
import os
from pathlib import Path
import time
from typing import Dict, List, Optional, Set

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
from ryu.lib.packet import arp, ether_types, ethernet, icmp, ipv4, packet
from ryu.ofproto import ofproto_v1_3


from harness.contracts.sdn_events import (
    MANUAL_RESTORE_HOLD_SEC,
    REDIS_CHANNEL_ANOMALY_ALERT,
    REDIS_CHANNEL_CONTROL_COMMAND,
    FLOW_COUNT_INTERVAL_SEC,
    PORT_STATS_INTERVAL_SEC,
    REDIS_CHANNEL_FLOW_COUNTS,
    REDIS_CHANNEL_SERVICE_HEALTH,
    REDIS_CHANNEL_TOPOLOGY_SYNC,
    SERVICE_PROBE_DPID,
    SERVICE_PROBE_INTERVAL_SEC,
    SERVICE_PROBE_IP,
    SERVICE_PROBE_MAC,
    SERVICE_PROBE_TARGET_IP,
    SERVICE_PROBE_TIMEOUT_SEC,
    WARNING_HOLD_SEC,
    WARNING_RATE_LIMIT_PPS,
    AnomalyAlertMessage,
    ControlCommandMessage,
    CountKind,
    DefenseAction,
    FlowCountItem,
    FlowCountMessage,
    RiskStage,
    ServiceHealthMessage,
    ThreatType,
    TopologyLink,
    TopologyNode,
    TopologySyncMessage,
)
from harness.safety.circuit_breaker import CircuitBreaker
from harness.safety.flapping_fsm import DefenseState, FlappingFSM
from harness.safety.whitelist_guard import WhitelistGuard
try:
    from harness.topology.profile_loader import get_topology_profile
except ImportError:
    try:
        from profile_loader import get_topology_profile  # type: ignore[no-redef]
    except ImportError:
        import sys
        from pathlib import Path
        sys.path.append(str(Path(__file__).resolve().parents[2]))
        from harness.topology.profile_loader import get_topology_profile  # type: ignore[no-redef]
try:
    from ryu.app.reroute import RerouteEngine
except ImportError:
    try:
        from reroute import RerouteEngine  # type: ignore[no-redef]
    except ImportError:
        import sys
        from pathlib import Path
        sys.path.append(str(Path(__file__).resolve().parent))
        from reroute import RerouteEngine  # type: ignore[no-redef]


# 4단 플로우 테이블:
# 0 = 종류별로 세기 (Count)
# 1 = 망 정책 및 접근 제어 (Zone Policy & Source Guard)
# 2 = 경고 단계 속도 제한 (Meter & Police)
# 3 = 전달 (Forward: Dijkstra 최단 경로 / 우회).
# 세는 규칙이 맨 앞에 있어서 격리 중에도 공격 패킷 수를 계속 셀 수 있다 (공격이 멈췄는지 판단용).
TABLE_COUNT = 0
TABLE_POLICY = 1
TABLE_POLICE = 2
TABLE_METER = 2
TABLE_FORWARD = 3

# 세는 규칙의 cookie: 상위 16비트 태그 + dpid(24비트) + 포트(16비트) + 종류 번호(8비트)
COUNT_COOKIE_TAG = 0xC0DE << 48
COUNT_COOKIE_MASK = 0xFFFF << 48
COUNT_KINDS = [k.value for k in CountKind]

TCP_FIN, TCP_SYN, TCP_RST, TCP_ACK = 0x001, 0x002, 0x004, 0x010
# 서비스 상태 확인 ping의 ICMP id (다른 ping과 구분)
PROBE_ICMP_ID = 0x5D7E
ICMP_ECHO_REPLY, ICMP_ECHO_REQUEST = 0, 8


class ProbeTracker:
    """서비스 상태 확인 ping의 보낸 시각과 왕복 시간을 기록해 2초마다 손실·지연으로 요약한다.

    응답 대기 시간(timeout)이 지난 ping만 요약에 넣으므로, 한 번의 요약은 대략 1~3초 전에 보낸 ping을 다룬다.
    """

    def __init__(self, timeout=SERVICE_PROBE_TIMEOUT_SEC):
        self.timeout = timeout
        self.seq = 0
        self.sent = {}  # seq → 보낸 시각
        self.rtt_ms = {}  # seq → 왕복 시간(ms), 대기 시간 안에 온 응답만

    def next_seq(self, now):
        self.seq = self.seq % 0xFFFF + 1
        self.sent[self.seq] = now
        return self.seq

    def reply(self, seq, now):
        sent_at = self.sent.get(seq)
        if sent_at is not None and seq not in self.rtt_ms and now - sent_at <= self.timeout:
            self.rtt_ms[seq] = (now - sent_at) * 1000.0

    def summary(self, now, target_ip=SERVICE_PROBE_TARGET_IP):
        settled = [seq for seq, sent_at in self.sent.items() if now - sent_at >= self.timeout]
        if not settled:
            return None
        rtts = [self.rtt_ms[seq] for seq in settled if seq in self.rtt_ms]
        for seq in settled:
            self.sent.pop(seq)
            self.rtt_ms.pop(seq, None)
        return ServiceHealthMessage(
            timestamp=now, target_ip=target_ip, sent=len(settled), received=len(rtts),
            loss_percent=round(100.0 * (len(settled) - len(rtts)) / len(settled), 1),
            rtt_avg_ms=round(sum(rtts) / len(rtts), 2) if rtts else None,
            rtt_max_ms=round(max(rtts), 2) if rtts else None)


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


def police_matches(threat_type: str) -> List[Dict[str, object]]:
    """경고 단계에서 속도를 제한할 패킷 종류 (in_port 외의 매칭 조건). 모르는 종류면 포트 전체."""
    udp: Dict[str, object] = {"eth_type": 0x0800, "ip_proto": 17}
    icmp: Dict[str, object] = {"eth_type": 0x0800, "ip_proto": 1}
    syn: Dict[str, object] = {"eth_type": 0x0800, "ip_proto": 6, "tcp_flags": (TCP_SYN, TCP_SYN | TCP_ACK)}
    return {ThreatType.UDP_FLOOD.value: [udp], ThreatType.ICMP_FLOOD.value: [icmp],
            ThreatType.SYN_FLOOD_SPOOFING.value: [syn],
            # Slow HTTP: 새 연결(SYN)만 제한해 연결을 더 늘리지 못하게 한다
            ThreatType.SLOW_DDOS.value: [syn],
            # 포트 스캔은 TCP(SYN)와 UDP 둘 다 쓰므로 둘 다 제한
            ThreatType.PORT_SCAN.value: [syn, udp],
            # 내부 확산: 다른 PC로의 새 연결(SYN, 445 · 3389 등)을 제한
            ThreatType.INTERNAL_SPREAD.value: [syn]}.get(threat_type, [{}])


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
        # 8-스위치 5-Zone 엔터프라이즈 토폴로지 프로파일 로드 (SSOT)
        self.profile = get_topology_profile()
        self.profile_name = self.profile.get("name", "zone_8sw")

        # 호스트 정적 매핑 테이블 (11개 호스트)
        self.arp_table = self.profile.get("hosts", {})
        # 기본 최단 경로 라우팅 맵: {dpid: {dst_ip: out_port}}
        self.routing_table = self.profile.get("routing_table", {})

        # 6주차: 활성 Datapath 맵 및 Redis 텔레메트리 파이프라인 초기화
        self.datapaths = {}
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            from urllib.parse import urlparse
            parsed = urlparse(redis_url)
            self.redis_host = parsed.hostname or "127.0.0.1"
            self.redis_port = parsed.port or 6379
        else:
            self.redis_host = os.getenv("REDIS_HOST", "127.0.0.1")
            self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
        self.redis_client = None
        self._init_redis()

        # 7~13주차 핵심 엔진 인스턴스화
        self.whitelist_guard = WhitelistGuard(
            trunk_ports=self.profile.get("trunk_ports"),
            access_ports=self.profile.get("access_ports"),
            protected_ips=set(self.profile.get("protected_ips", ["10.0.0.1", "10.0.0.4"])),
            protected_access_ports=self.profile.get("protected_access_ports"),
        )
        self.reroute_engine = RerouteEngine(profile=self.profile)
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
        # 내부 확산: 접속 포트마다 ARP로 물어본 '없는 내부 주소' (서로 다른 주소, 누적)
        self.arp_fail_targets = {(host["dpid"], host["port"]): set() for host in self.arp_table.values()}

        # 서비스 상태 확인: 정상 사용자 자리(S1 또는 프로파일 프로브 DPID)에서 보호 서버로 보내는 ping의 손실·지연
        self.probe = ProbeTracker()
        probe_cfg = self.profile.get("probe", {})
        probe_target_dpid = probe_cfg.get("dpid", SERVICE_PROBE_DPID)
        # 응답을 송신 스위치까지 돌려보낼 때 쓸 경로 = 해당 스위치에 붙은 호스트로 가는 경로
        matching_ips = [ip for ip, host in sorted(self.arp_table.items()) if host["dpid"] == probe_target_dpid]
        self.probe_route_ip = matching_ips[0] if matching_ips else "10.0.0.1"

        # 2초 주기 비차단 포트 통계 폴링 그린스레드 가동
        self.monitor_thread = hub.spawn(self._monitor_loop)
        self.probe_thread = hub.spawn(self._probe_loop)
        # Redis 제어/경보 비동기 구독 수신 그린스레드 가동
        self.command_subscriber_thread = hub.spawn(self._command_listener_loop)

        # 동적 망 분리(Segmentation) 설정 및 격리 호스트 집합
        self.zones_config = self._load_zones_config()
        self.quarantined_hosts = set()

        self.logger.info(">>> Self-Defending Controller Ready (OF1.3)! <<<")

    def _load_zones_config(self):
        """zones.yaml 설정 안전 로드 (로컬 개발 환경 및 컨테이너 환경 호환)"""
        default_cfg = {
            "silent_drop_udp_ports": [137, 138, 139, 1900, 5353, 5355],
            "hard_whitelist": {"probe_ip": "10.0.0.240", "protected_ips": ["10.0.0.4", "10.0.0.254"]},
        }
        try:
            import yaml
            candidate_paths = [
                Path("/workspace/config/zones.yaml"),
                Path("/app/config/zones.yaml"),
                Path("config/zones.yaml"),
            ]
            cur = Path(__file__).resolve()
            if len(cur.parents) >= 3:
                candidate_paths.insert(0, cur.parents[2] / "config" / "zones.yaml")

            for p in candidate_paths:
                try:
                    if p.exists():
                        with open(p, "r", encoding="utf-8") as f:
                            cfg = yaml.safe_load(f) or {}
                            self.logger.info(f"[Segmentation] Successfully loaded zones.yaml from {p}")
                            return cfg
                except Exception:
                    continue
        except Exception as e:
            self.logger.warning(f"[Segmentation] Failed to load zones.yaml: {e}")
        return default_cfg

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
        """종류별 개수는 1초마다, 포트 통계·서비스 상태는 2초마다 요청·발행"""
        port_every = max(1, round(PORT_STATS_INTERVAL_SEC / FLOW_COUNT_INTERVAL_SEC))
        tick = 0
        while True:
            hub.sleep(FLOW_COUNT_INTERVAL_SEC)
            tick += 1
            port_round = tick % port_every == 0
            for dp in list(self.datapaths.values()):
                try:
                    if port_round:
                        self._request_stats(dp)
                    if dp.id in self.count_dpids:
                        self._request_count_stats(dp)
                except Exception as e:
                    self.logger.warning(
                        f"[Telemetry] Stats request failed for S{dp.id}: {e}"
                    )
            if port_round:
                self._publish_service_health()

    def _probe_loop(self):
        """서비스 상태 확인 ping을 0.2초마다 보낸다 (S1이 연결돼 있을 때만)"""
        while True:
            hub.sleep(SERVICE_PROBE_INTERVAL_SEC)
            datapath = self.datapaths.get(SERVICE_PROBE_DPID)
            if datapath is None:
                continue
            try:
                self._send_probe(datapath)
            except Exception as e:
                self.logger.warning(f"[Health] Probe send failed: {e}")

    def _send_probe(self, datapath):
        """가상 출발지(SERVICE_PROBE_IP)의 ICMP echo를 S1의 테이블에 넣는다.

        OFPP_TABLE로 내보내서 사용자 패킷과 같은 전달 규칙(격리·우회 포함)을 탄다. in_port가 컨트롤러라
        0번 테이블의 세는 규칙(호스트 포트 기준)에는 걸리지 않는다.
        """
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        seq = self.probe.next_seq(time.time())
        pkt = packet.Packet()
        pkt.add_protocol(ethernet.ethernet(ethertype=ether_types.ETH_TYPE_IP, src=SERVICE_PROBE_MAC,
                                           dst=self.arp_table[SERVICE_PROBE_TARGET_IP]["mac"]))
        pkt.add_protocol(ipv4.ipv4(src=SERVICE_PROBE_IP, dst=SERVICE_PROBE_TARGET_IP, proto=1))
        pkt.add_protocol(icmp.icmp(type_=ICMP_ECHO_REQUEST, code=0, csum=0,
                                   data=icmp.echo(id_=PROBE_ICMP_ID, seq=seq, data=b"sdn-health-probe")))
        pkt.serialize()
        datapath.send_msg(parser.OFPPacketOut(
            datapath=datapath, buffer_id=ofproto.OFP_NO_BUFFER, in_port=ofproto.OFPP_CONTROLLER,
            actions=[parser.OFPActionOutput(ofproto.OFPP_TABLE)], data=pkt.data))

    def _handle_probe_reply(self, datapath, in_port, pkt, data):
        """서비스 상태 확인 ping의 응답: S1에 도착하면 기록하고, 다른 스위치에서는 S1 쪽으로 보낸다."""
        if datapath.id == SERVICE_PROBE_DPID:
            icmp_pkt = pkt.get_protocol(icmp.icmp)
            if (icmp_pkt is not None and icmp_pkt.type == ICMP_ECHO_REPLY
                    and getattr(icmp_pkt.data, "id", None) == PROBE_ICMP_ID):
                self.probe.reply(icmp_pkt.data.seq, time.time())
            return
        out_port = self.routing_table.get(datapath.id, {}).get(self.probe_route_ip)
        if out_port is None or out_port == in_port:
            return
        parser = datapath.ofproto_parser
        actions = [parser.OFPActionOutput(out_port)]
        self.add_flow(datapath, priority=10, match=parser.OFPMatch(eth_type=0x0800, ipv4_dst=SERVICE_PROBE_IP),
                      actions=actions, idle_timeout=60)
        datapath.send_msg(parser.OFPPacketOut(datapath=datapath, buffer_id=datapath.ofproto.OFP_NO_BUFFER,
                                              in_port=in_port, actions=actions, data=data))

    def _publish_service_health(self, now=None):
        """응답 대기 시간이 지난 ping의 손실·지연을 sdn:health:service로 발행"""
        msg = self.probe.summary(time.time() if now is None else now)
        if msg is None:
            return
        try:
            if not self.redis_client:
                self._init_redis()
            if self.redis_client:
                self.redis_client.publish(REDIS_CHANNEL_SERVICE_HEALTH, msg.model_dump_json())
        except Exception as e:
            self.logger.warning(f"[Health] Failed to publish service health: {e}")
            self.redis_client = None

    def _request_stats(self, datapath):
        """OFPPortStatsRequest 메시지 발송"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        req = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY)
        datapath.send_msg(req)

    def _request_count_stats(self, datapath):
        """0번(카운팅) 및 1번(망 정책 ZONE_DENY) 테이블의 세는 규칙(cookie 태그) 플로우 통계 요청"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        table_all = getattr(ofproto, "OFPTT_ALL", 0xFF)
        req = parser.OFPFlowStatsRequest(
            datapath, 0, table_all, ofproto.OFPP_ANY, ofproto.OFPG_ANY,
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
        dpid = ev.msg.datapath.id
        counts += [FlowCountItem(port_no=port, kind=CountKind.ARP_FAIL.value, packets=len(targets))
                   for (d, port), targets in sorted(self.arp_fail_targets.items()) if d == dpid]
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

        # 0번(세기) -> 1번(망 정책) 기본 전달 규칙
        self.add_flow(datapath, priority=0, match=parser.OFPMatch(), actions=[], table_id=TABLE_COUNT,
                      instructions=[parser.OFPInstructionGotoTable(TABLE_POLICY)])
        # 2번(속도 제한) -> 3번(전달) 기본 전달 규칙
        self.add_flow(datapath, priority=0, match=parser.OFPMatch(), actions=[], table_id=TABLE_POLICE,
                      instructions=[parser.OFPInstructionGotoTable(TABLE_FORWARD)])

        # 0번 테이블: 이 스위치에 붙은 호스트의 종류별 세는 규칙 (Goto Table 1)
        for dpid, port, kind, priority, match_kwargs in count_rule_specs(self.arp_table):
            if dpid != datapath.id:
                continue
            self.add_flow(datapath, priority=priority, match=parser.OFPMatch(**match_kwargs), actions=[],
                          table_id=TABLE_COUNT, cookie=count_cookie(dpid, port, kind),
                          instructions=[parser.OFPInstructionGotoTable(TABLE_POLICY)])

        # 1번 테이블: 망 정책(Zone Policy & Source Guard) 설치
        self._install_policy_table(datapath)

        # 3번(전달) 테이블 Table-Miss Flow (Priority 0) 등록: 미매칭 패킷은 컨트롤러로 보고
        match = parser.OFPMatch()
        actions = [
            parser.OFPActionOutput(
                ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER
            )
        ]
        self.add_flow(datapath, priority=0, match=match, actions=actions, table_id=TABLE_FORWARD)
        self.logger.info(
            f"Switch S{datapath.id} Connected. Count/Policy/Police/Forward tables and Table-Miss Installed."
        )

    def _install_policy_table(self, datapath):
        """Table 1 망 정책(Zone Policy) 기본 플로우 주입"""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        dpid = datapath.id

        # 1. Pri 65535: 스위치 간 트렁크(Trunk) 포트 절대 바이패스 -> Table 2 (TABLE_POLICE)
        trunk_ports = self.whitelist_guard.trunk_ports.get(dpid, [])
        for t_port in trunk_ports:
            self.add_flow(
                datapath, priority=65535, match=parser.OFPMatch(in_port=t_port),
                actions=[], table_id=TABLE_POLICY,
                instructions=[parser.OFPInstructionGotoTable(TABLE_POLICE)],
            )

        # 2. Pri 500: ARP (0x0806) -> Table 2 -> Table 3 (Proxy ARP 처리를 위해 필수 통과)
        self.add_flow(
            datapath, priority=500, match=parser.OFPMatch(eth_type=0x0806),
            actions=[], table_id=TABLE_POLICY,
            instructions=[parser.OFPInstructionGotoTable(TABLE_POLICE)],
        )

        # 3. Pri 400: 컨트롤러 상태체크 핑 (10.0.0.240) 양방향 무조건 허용
        self.add_flow(
            datapath, priority=400,
            match=parser.OFPMatch(eth_type=0x0800, ipv4_src=SERVICE_PROBE_IP),
            actions=[], table_id=TABLE_POLICY,
            instructions=[parser.OFPInstructionGotoTable(TABLE_POLICE)],
        )
        self.add_flow(
            datapath, priority=400,
            match=parser.OFPMatch(eth_type=0x0800, ipv4_dst=SERVICE_PROBE_IP),
            actions=[], table_id=TABLE_POLICY,
            instructions=[parser.OFPInstructionGotoTable(TABLE_POLICE)],
        )

        # 4. Pri 350: OS 백그라운드 노이즈 Silent Drop (NetBIOS, mDNS, LLMNR, SSDP)
        silent_ports = self.zones_config.get("silent_drop_udp_ports", [137, 138, 139, 1900, 5353, 5355])
        for u_port in silent_ports:
            self.add_flow(
                datapath, priority=350,
                match=parser.OFPMatch(eth_type=0x0800, ip_proto=17, udp_dst=u_port),
                actions=[], table_id=TABLE_POLICY,
            )

        # 5. 접속 호스트별 망 정책 설치
        for ip, host_info in self.arp_table.items():
            if host_info["dpid"] != dpid:
                continue
            h_port = host_info["port"]
            h_mac = host_info["mac"]
            h_zone = host_info.get("zone", "SERVER" if ip == "10.0.0.4" else "USER")

            if h_zone == "SERVER" or ip in ("10.0.0.4", "10.0.0.11", "10.0.0.12", "10.0.0.21", "10.0.0.22"):
                # SERVER 호스트: 역방향 응답 허용 (Pri 100)
                # Web reply (TCP src 80)
                self.add_flow(
                    datapath, priority=100,
                    match=parser.OFPMatch(in_port=h_port, eth_type=0x0800, ip_proto=6, tcp_src=80),
                    actions=[], table_id=TABLE_POLICY,
                    instructions=[parser.OFPInstructionGotoTable(TABLE_POLICE)],
                )
                # API reply (TCP src 8080)
                self.add_flow(
                    datapath, priority=100,
                    match=parser.OFPMatch(in_port=h_port, eth_type=0x0800, ip_proto=6, tcp_src=8080),
                    actions=[], table_id=TABLE_POLICY,
                    instructions=[parser.OFPInstructionGotoTable(TABLE_POLICE)],
                )
                # DB reply (TCP src 3306)
                self.add_flow(
                    datapath, priority=100,
                    match=parser.OFPMatch(in_port=h_port, eth_type=0x0800, ip_proto=6, tcp_src=3306),
                    actions=[], table_id=TABLE_POLICY,
                    instructions=[parser.OFPInstructionGotoTable(TABLE_POLICE)],
                )
                # DNS reply (UDP src 53)
                self.add_flow(
                    datapath, priority=100,
                    match=parser.OFPMatch(in_port=h_port, eth_type=0x0800, ip_proto=17, udp_src=53),
                    actions=[], table_id=TABLE_POLICY,
                    instructions=[parser.OFPInstructionGotoTable(TABLE_POLICE)],
                )
                # ICMP reply (Echo Reply type 0)
                self.add_flow(
                    datapath, priority=100,
                    match=parser.OFPMatch(in_port=h_port, eth_type=0x0800, ip_proto=1, icmpv4_type=0),
                    actions=[], table_id=TABLE_POLICY,
                    instructions=[parser.OFPInstructionGotoTable(TABLE_POLICE)],
                )
            elif h_zone == "ADMIN":
                # ADMIN 호스트 (H_Admin / H_Patch): 관리 서비스 응답 허용
                self.add_flow(
                    datapath, priority=100,
                    match=parser.OFPMatch(in_port=h_port, eth_type=0x0800, ip_proto=6, tcp_src=443),
                    actions=[], table_id=TABLE_POLICY,
                    instructions=[parser.OFPInstructionGotoTable(TABLE_POLICE)],
                )
                self.add_flow(
                    datapath, priority=100,
                    match=parser.OFPMatch(in_port=h_port, eth_type=0x0800, ip_proto=6, tcp_src=80),
                    actions=[], table_id=TABLE_POLICY,
                    instructions=[parser.OFPInstructionGotoTable(TABLE_POLICE)],
                )
                self.add_flow(
                    datapath, priority=100,
                    match=parser.OFPMatch(in_port=h_port, eth_type=0x0800, ip_proto=17, udp_src=53),
                    actions=[], table_id=TABLE_POLICY,
                    instructions=[parser.OFPInstructionGotoTable(TABLE_POLICE)],
                )
            elif h_zone == "QUARANTINE":
                # QUARANTINE 호스트 (h_sink 및 정적 격리망):
                # Pri 300: 관리 포털 (10.0.0.254:443, 53) 및 보안 패치 서버 (10.0.0.253:80) 허용
                self.add_flow(
                    datapath, priority=300,
                    match=parser.OFPMatch(in_port=h_port, eth_type=0x0800, ipv4_dst="10.0.0.254", ip_proto=6, tcp_dst=443),
                    actions=[], table_id=TABLE_POLICY,
                    instructions=[parser.OFPInstructionGotoTable(TABLE_POLICE)],
                )
                self.add_flow(
                    datapath, priority=300,
                    match=parser.OFPMatch(in_port=h_port, eth_type=0x0800, ipv4_dst="10.0.0.254", ip_proto=17, udp_dst=53),
                    actions=[], table_id=TABLE_POLICY,
                    instructions=[parser.OFPInstructionGotoTable(TABLE_POLICE)],
                )
                if "10.0.0.253" in self.arp_table:
                    self.add_flow(
                        datapath, priority=300,
                        match=parser.OFPMatch(in_port=h_port, eth_type=0x0800, ipv4_dst="10.0.0.253", ip_proto=6, tcp_dst=80),
                        actions=[], table_id=TABLE_POLICY,
                        instructions=[parser.OFPInstructionGotoTable(TABLE_POLICE)],
                    )
            else:
                # USER 호스트: SERVER 향 허용 규칙 (Pri 200)
                target_servers = ["10.0.0.11", "10.0.0.12", "10.0.0.21", "10.0.0.22"]
                for s_ip in target_servers:
                    # Web request (TCP dst 80)
                    self.add_flow(
                        datapath, priority=200,
                        match=parser.OFPMatch(in_port=h_port, eth_type=0x0800, ipv4_dst=s_ip, ip_proto=6, tcp_dst=80),
                        actions=[], table_id=TABLE_POLICY,
                        instructions=[parser.OFPInstructionGotoTable(TABLE_POLICE)],
                    )
                    # DNS request (UDP dst 53)
                    self.add_flow(
                        datapath, priority=200,
                        match=parser.OFPMatch(in_port=h_port, eth_type=0x0800, ipv4_dst=s_ip, ip_proto=17, udp_dst=53),
                        actions=[], table_id=TABLE_POLICY,
                        instructions=[parser.OFPInstructionGotoTable(TABLE_POLICE)],
                    )
                    # ICMP request (Echo Request type 8)
                    self.add_flow(
                        datapath, priority=200,
                        match=parser.OFPMatch(in_port=h_port, eth_type=0x0800, ipv4_dst=s_ip, ip_proto=1, icmpv4_type=8),
                        actions=[], table_id=TABLE_POLICY,
                        instructions=[parser.OFPInstructionGotoTable(TABLE_POLICE)],
                    )
                    # ICMP reply (Echo Reply type 0)
                    self.add_flow(
                        datapath, priority=200,
                        match=parser.OFPMatch(in_port=h_port, eth_type=0x0800, ipv4_dst=s_ip, ip_proto=1, icmpv4_type=0),
                        actions=[], table_id=TABLE_POLICY,
                        instructions=[parser.OFPInstructionGotoTable(TABLE_POLICE)],
                    )

            # 6. Pri 0: Table-Miss per Access Port -> DROP & Count ZONE_DENY
            self.add_flow(
                datapath, priority=0,
                match=parser.OFPMatch(in_port=h_port),
                actions=[], table_id=TABLE_POLICY,
                cookie=count_cookie(dpid, h_port, CountKind.ZONE_DENY.value),
            )

    def quarantine_host(
        self,
        target_ip: str,
        target_mac: Optional[str] = None,
        dpid: Optional[int] = None,
        port: Optional[int] = None,
    ) -> bool:
        """침해 호스트를 동적 격리망(QUARANTINE)으로 강등"""
        if not target_ip:
            return False

        # 하드 화이트리스트 보호 (서버 및 프로브 핑, 관리 서버는 절대 격리 불가)
        protected = {"10.0.0.4", "10.0.0.250", "10.0.0.254", "10.0.0.253", "10.0.0.11", "10.0.0.12", "10.0.0.21", "10.0.0.22"} | set(self.whitelist_guard.protected_ips)
        if target_ip in protected:
            self.logger.error(f"[Quarantine] Refusing to quarantine protected target: {target_ip}")
            return False

        host_info = self.arp_table.get(target_ip)
        if host_info:
            target_mac = target_mac or host_info["mac"]
            dpid = dpid or host_info["dpid"]
            port = port or host_info["port"]

        if not dpid or not port:
            self.logger.warning(f"[Quarantine] Unknown target: {target_ip}")
            return False

        datapath = self.datapaths.get(dpid)
        if not datapath:
            self.logger.warning(f"[Quarantine] Datapath S{dpid} not connected")
            self.quarantined_hosts.add(target_ip)
            return True

        parser = datapath.ofproto_parser

        # 1. 기존 Pri 200 정상 USER 허용 규칙 삭제
        target_servers = ["10.0.0.11", "10.0.0.12", "10.0.0.21", "10.0.0.22"]
        for s_ip in target_servers:
            self.delete_flow(
                datapath, priority=200,
                match=parser.OFPMatch(in_port=port, eth_type=0x0800, ipv4_dst=s_ip, ip_proto=6, tcp_dst=80),
                table_id=TABLE_POLICY,
            )
            self.delete_flow(
                datapath, priority=200,
                match=parser.OFPMatch(in_port=port, eth_type=0x0800, ipv4_dst=s_ip, ip_proto=17, udp_dst=53),
                table_id=TABLE_POLICY,
            )
            for icmp_type in (8, 0):
                self.delete_flow(
                    datapath, priority=200,
                    match=parser.OFPMatch(in_port=port, eth_type=0x0800, ipv4_dst=s_ip, ip_proto=1, icmpv4_type=icmp_type),
                    table_id=TABLE_POLICY,
                )

        # 2. Pri 300 격리 규칙 설치 (관리망 10.0.0.254:443 및 DNS 53만 허용)
        self.add_flow(
            datapath, priority=300,
            match=parser.OFPMatch(in_port=port, eth_type=0x0800, ipv4_dst="10.0.0.254", ip_proto=6, tcp_dst=443),
            actions=[], table_id=TABLE_POLICY,
            instructions=[parser.OFPInstructionGotoTable(TABLE_POLICE)],
        )
        self.add_flow(
            datapath, priority=300,
            match=parser.OFPMatch(in_port=port, eth_type=0x0800, ipv4_dst="10.0.0.254", ip_proto=17, udp_dst=53),
            actions=[], table_id=TABLE_POLICY,
            instructions=[parser.OFPInstructionGotoTable(TABLE_POLICE)],
        )
        # 패치 서버(10.0.0.253)가 활성화된 경우: HTTP 80 패치 다운로드 허용
        if "10.0.0.253" in self.arp_table:
            self.add_flow(
                datapath, priority=300,
                match=parser.OFPMatch(in_port=port, eth_type=0x0800, ipv4_dst="10.0.0.253", ip_proto=6, tcp_dst=80),
                actions=[], table_id=TABLE_POLICY,
                instructions=[parser.OFPInstructionGotoTable(TABLE_POLICE)],
            )

        self.quarantined_hosts.add(target_ip)
        self.logger.info(f"[Quarantine] Host {target_ip} (MAC: {target_mac}) QUARANTINED on S{dpid}:P{port}")
        return True

    def release_host(
        self,
        target_ip: str,
        target_mac: Optional[str] = None,
        dpid: Optional[int] = None,
        port: Optional[int] = None,
    ) -> bool:
        """관리자 승인에 의한 격리 해제 및 USER 망 원상 복구"""
        if not target_ip:
            return False

        host_info = self.arp_table.get(target_ip)
        if host_info:
            target_mac = target_mac or host_info["mac"]
            dpid = dpid or host_info["dpid"]
            port = port or host_info["port"]

        if not dpid or not port:
            return False

        datapath = self.datapaths.get(dpid)
        if not datapath:
            self.quarantined_hosts.discard(target_ip)
            return True

        parser = datapath.ofproto_parser

        # 1. Pri 300 격리 규칙 삭제
        self.delete_flow(
            datapath, priority=300,
            match=parser.OFPMatch(in_port=port, eth_type=0x0800, ipv4_dst="10.0.0.254", ip_proto=6, tcp_dst=443),
            table_id=TABLE_POLICY,
        )
        self.delete_flow(
            datapath, priority=300,
            match=parser.OFPMatch(in_port=port, eth_type=0x0800, ipv4_dst="10.0.0.254", ip_proto=17, udp_dst=53),
            table_id=TABLE_POLICY,
        )
        if "10.0.0.253" in self.arp_table:
            self.delete_flow(
                datapath, priority=300,
                match=parser.OFPMatch(in_port=port, eth_type=0x0800, ipv4_dst="10.0.0.253", ip_proto=6, tcp_dst=80),
                table_id=TABLE_POLICY,
            )

        # 2. Pri 200 정상 USER 규칙 복원
        target_servers = ["10.0.0.11", "10.0.0.12", "10.0.0.21", "10.0.0.22"]
        for s_ip in target_servers:
            self.add_flow(
                datapath, priority=200,
                match=parser.OFPMatch(in_port=port, eth_type=0x0800, ipv4_dst=s_ip, ip_proto=6, tcp_dst=80),
                actions=[], table_id=TABLE_POLICY,
                instructions=[parser.OFPInstructionGotoTable(TABLE_POLICE)],
            )
            self.add_flow(
                datapath, priority=200,
                match=parser.OFPMatch(in_port=port, eth_type=0x0800, ipv4_dst=s_ip, ip_proto=17, udp_dst=53),
                actions=[], table_id=TABLE_POLICY,
                instructions=[parser.OFPInstructionGotoTable(TABLE_POLICE)],
            )
            self.add_flow(
                datapath, priority=200,
                match=parser.OFPMatch(in_port=port, eth_type=0x0800, ipv4_dst=s_ip, ip_proto=1, icmpv4_type=8),
                actions=[], table_id=TABLE_POLICY,
                instructions=[parser.OFPInstructionGotoTable(TABLE_POLICE)],
            )
            self.add_flow(
                datapath, priority=200,
                match=parser.OFPMatch(in_port=port, eth_type=0x0800, ipv4_dst=s_ip, ip_proto=1, icmpv4_type=0),
                actions=[], table_id=TABLE_POLICY,
                instructions=[parser.OFPInstructionGotoTable(TABLE_POLICE)],
            )

        self.quarantined_hosts.discard(target_ip)
        self.logger.info(f"[Release] Host {target_ip} (MAC: {target_mac}) RELEASED on S{dpid}:P{port}")
        return True

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

    def reroute_traffic(self, source_dpid: int = 3, target_dpid: int = 5, dst_ip: str = "10.0.0.11"):
        """
        10주차: NetworkX Dijkstra 기반 다중 홉 선제적 OFPFC_ADD 우회 라우팅 주입.
        중간 스위치에 먼저 규칙을 설치한 후 Ingress 스위치를 전환하여 무유실 보장.
        """
        path = self.reroute_engine.compute_reroute_path(source_dpid, target_dpid, congested_intermediate_dpid=1)
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
        source_dpid: int = 3,
        target_dpid: int = 5,
        dst_ip: str = "10.0.0.11",
        priority: int = 20,
    ):
        """
        11주차: 복구 시 우회 경로(Priority 20) 플로우 규칙 명시적 삭제.
        Ingress 스위치부터 역순으로 우회 규칙을 제거하여 즉시 주 경로로 복귀.
        """
        path = self.reroute_engine.compute_reroute_path(
            source_dpid, target_dpid, congested_intermediate_dpid=1
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
        """Redis sdn:topology:sync 채널로 실시간 8-스위치 5-Zone 토폴로지 링크/노드 상태 브로드캐스트"""
        attacked = (phase_name == "ATTACK_DETECTED")
        mitigated = (phase_name in ("MITIGATED", "COOLDOWN_VERIFY", "COOLDOWN"))

        s1_status = "ATTACKED" if attacked else "MITIGATED" if mitigated else "NORMAL"
        nodes = [
            # 8 Switches (S1~S8)
            TopologyNode(id="s1", label="S1 (Core 1)", node_type="switch", dpid=1, status=s1_status),
            TopologyNode(id="s2", label="S2 (Core 2)", node_type="switch", dpid=2),
            TopologyNode(id="s3", label="S3 (User A)", node_type="switch", dpid=3),
            TopologyNode(id="s4", label="S4 (User B)", node_type="switch", dpid=4),
            TopologyNode(id="s5", label="S5 (Server A)", node_type="switch", dpid=5),
            TopologyNode(id="s6", label="S6 (Server B)", node_type="switch", dpid=6),
            TopologyNode(id="s7", label="S7 (Admin)", node_type="switch", dpid=7),
            TopologyNode(id="s8", label="S8 (Quarantine)", node_type="switch", dpid=8),
        ]
        # 11 Hosts
        for ip, h in self.arp_table.items():
            lbl = h.get("label", ip)
            h_status = "QUARANTINED" if ip in self.quarantined_hosts else "NORMAL"
            nodes.append(
                TopologyNode(
                    id=lbl, label=lbl, node_type="host",
                    ip=ip, mac=h.get("mac", ""), status=h_status
                )
            )

        # Trunk Links
        links = [
            # Core Inter-switch
            TopologyLink(source="s1", target="s2", src_port=1, dst_port=1, is_trunk=True),
            # S1 to Edges
            TopologyLink(source="s1", target="s3", src_port=2, dst_port=99, is_trunk=True),
            TopologyLink(source="s1", target="s5", src_port=3, dst_port=99, is_trunk=True),
            TopologyLink(source="s1", target="s7", src_port=4, dst_port=98, is_trunk=True),
            TopologyLink(source="s1", target="s8", src_port=5, dst_port=98, is_trunk=True),
            # S2 to Edges
            TopologyLink(source="s2", target="s4", src_port=2, dst_port=99, is_trunk=True),
            TopologyLink(source="s2", target="s6", src_port=3, dst_port=99, is_trunk=True),
            TopologyLink(source="s2", target="s7", src_port=4, dst_port=99, is_trunk=True),
            TopologyLink(source="s2", target="s8", src_port=5, dst_port=99, is_trunk=True),
        ]
        # Host access links
        for ip, h in self.arp_table.items():
            lbl = h.get("label", ip)
            l_status = "BLOCKED" if ip in self.quarantined_hosts else "ACTIVE"
            sw_id = f"s{h['dpid']}"
            links.append(
                TopologyLink(
                    source=sw_id, target=lbl,
                    src_port=h["port"], dst_port=1, status=l_status
                )
            )

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

    def _publish_control_command(
        self,
        action: str,
        dpid: int,
        port: int,
        reason: str,
        priority: int = 100,
        target_ip: Optional[str] = None,
        target_mac: Optional[str] = None,
    ):
        """자율 방어 조치 내역을 sdn:control:command 채널에 발행하여 웹 대시보드 이벤트 타임라인에 기록"""
        cmd = ControlCommandMessage(
            command_id=f"auto-{action.lower()}-{int(time.time()*1000)}",
            action=action,
            target_dpid=dpid,
            target_port=port,
            reason=reason,
            priority=priority,
            timestamp=time.time(),
            target_ip=target_ip,
            target_mac=target_mac,
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
                        source_dpid=info["dpid"], target_dpid=5, dst_ip="10.0.0.11"
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
                        # 타깃 호스트 IP 식별
                        target_ip = next((ip for ip, host in self.arp_table.items()
                                          if host["dpid"] == alert.dpid and host["port"] == alert.in_port), None)

                        # 내부 확산 / 망 경계 위반: 포트 전체가 아닌 호스트 단위 QUARANTINE 발동
                        if target_ip and alert.threat_type == ThreatType.INTERNAL_SPREAD.value:
                            self.quarantine_host(target_ip, dpid=alert.dpid, port=alert.in_port)
                            self._publish_control_command(
                                action=DefenseAction.QUARANTINE.value,
                                dpid=alert.dpid,
                                port=alert.in_port,
                                reason=f"Autonomous Host Quarantine: {alert.threat_type} (score {alert.score:.2f})",
                                priority=300,
                                target_ip=target_ip,
                            )
                            self.fsm.trigger_anomaly(alert.dpid, alert.in_port, threat_info=alert.model_dump())
                            self._publish_topology_sync("MITIGATED")
                        else:
                            # Flood 계열(SYN/UDP/ICMP 등): 기존 인그레스 포트 격리 + 우회 유지
                            self.isolate_port(alert.dpid, alert.in_port, priority=100)
                            self._publish_control_command(
                                action=DefenseAction.ISOLATE.value,
                                dpid=alert.dpid,
                                port=alert.in_port,
                                reason=f"Autonomous In_port Drop: {alert.threat_type} (score {alert.score:.2f})",
                                priority=100,
                            )
                            # 2. 다중 홉 우회 라우팅 선제 설치
                            self.reroute_traffic(source_dpid=alert.dpid, target_dpid=5, dst_ip="10.0.0.11")
                            self._publish_control_command(
                                action=DefenseAction.REROUTE.value,
                                dpid=alert.dpid,
                                port=99,
                                reason="Autonomous Bypass: Proactive Core Backbone Rerouting",
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
                        source_dpid=cmd.target_dpid, target_dpid=5, dst_ip="10.0.0.11"
                    )
                    self.fsm.force_restore()
                    if is_manual:
                        # 공격이 이어져도 다음 경보(2초 이내)가 바로 다시 막지 않도록 자동 재격리 보류
                        self.manual_holds[target_key] = time.time() + MANUAL_RESTORE_HOLD_SEC
                    self._publish_topology_sync("NORMAL")
                elif cmd.action == "REROUTE":
                    self.reroute_traffic(source_dpid=cmd.target_dpid, target_dpid=5, dst_ip="10.0.0.11")
                    self._publish_topology_sync("MITIGATED")
                elif cmd.action in ("QUARANTINE", DefenseAction.QUARANTINE.value):
                    self.quarantine_host(cmd.target_ip, cmd.target_mac, cmd.target_dpid, cmd.target_port)
                    self._publish_topology_sync("MITIGATED")
                elif cmd.action in ("RELEASE", DefenseAction.RELEASE.value):
                    self.release_host(cmd.target_ip, cmd.target_mac, cmd.target_dpid, cmd.target_port)
                    self._publish_topology_sync("NORMAL")
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
            if ip_pkt.dst == SERVICE_PROBE_IP:
                self._handle_probe_reply(datapath, in_port, pkt, msg.data)
                return
            self.handle_ipv4(datapath, in_port, eth, ip_pkt, msg.data)

    def handle_arp(self, datapath, in_port, eth, arp_pkt):
        if arp_pkt.opcode == arp.ARP_REQUEST:
            target_ip = arp_pkt.dst_ip
            if target_ip == SERVICE_PROBE_IP:
                # 서비스 상태 확인 ping의 가상 출발지: 서버가 응답을 보낼 수 있게 대신 답한다
                self.send_arp_reply(datapath, SERVICE_PROBE_MAC, target_ip, eth.src, arp_pkt.src_ip, in_port)
                return
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
                # 없는 주소: 답하지 않는다. 접속 호스트가 물어봤으면 내부 확산 판단용으로 기록
                targets = self.arp_fail_targets.get((datapath.id, in_port))
                if targets is not None and target_ip != arp_pkt.src_ip:
                    targets.add(target_ip)
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
