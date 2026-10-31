"""
Self-Defending SDN Tower: Single Source of Truth (SSOT) IPC Contract Schemas
Author: Sihyeon Park (22101489 / Tech Lead)
Phase 2 (Week 4) Milestone

Redis Pub/Sub Channels:
- sdn:stats:port      : Ryu -> AI Worker, FastAPI
- sdn:anomaly:alert   : AI Worker -> Ryu, FastAPI
- sdn:control:command : AI Worker / Web UI -> Ryu
- sdn:topology:sync   : Ryu -> FastAPI, Web UI
- sdn:stats:flowcount : Ryu -> AI Worker (패킷 종류별 개수)
- sdn:health:service  : Ryu -> AI Worker (보호 서버 응답 확인)
- sdn:stats:serverconn: 서버 연결 수집기 -> AI Worker (Slow HTTP)
"""

import time
from enum import Enum
from typing import Dict, List, Optional
from pydantic import AliasChoices, BaseModel, Field


# =====================================================================
# Redis Channel Constant Definitions (SSOT)
# =====================================================================
REDIS_CHANNEL_PORT_STATS = "sdn:stats:port"
REDIS_CHANNEL_ANOMALY_ALERT = "sdn:anomaly:alert"
REDIS_CHANNEL_CONTROL_COMMAND = "sdn:control:command"
REDIS_CHANNEL_TOPOLOGY_SYNC = "sdn:topology:sync"
# Ryu -> AI Worker: 접속 포트별·패킷 종류별 누적 개수 (공격 종류별 판단 기준용, 1초 주기)
REDIS_CHANNEL_FLOW_COUNTS = "sdn:stats:flowcount"
# 컨트롤러가 스위치에 묻는 주기(초). 종류별 개수는 탐지가 빠르도록 1초, 포트 통계·서비스 상태는 2초
# (2회 연속 확인 = 2초. 2초 주기일 때는 공격이 보고 직후에 시작하면 확정까지 약 4초가 걸렸다)
FLOW_COUNT_INTERVAL_SEC = 1.0
PORT_STATS_INTERVAL_SEC = 2.0
# Ryu -> AI Worker: 보호 서버 응답 확인(손실·지연) 결과, 2초 주기 (위험 단계의 서비스 악화 조건)
REDIS_CHANNEL_SERVICE_HEALTH = "sdn:health:service"

# 서비스 상태 확인: 컨트롤러가 정상 사용자 자리(S3)에서 보호 서버(h5 Web)로 보내는 ICMP echo의 가상 출발지.
# 실제 호스트가 없는 주소라 컨트롤러가 ARP에 대신 답하고, 응답은 S3으로 돌아와 컨트롤러가 받는다.
SERVICE_PROBE_IP = "10.0.0.250"
SERVICE_PROBE_MAC = "00:00:00:00:00:fa"
SERVICE_PROBE_TARGET_IP = "10.0.0.11"
SERVICE_PROBE_DPID = 3
SERVICE_PROBE_INTERVAL_SEC = 0.2
# 이 시간 안에 응답이 없으면 손실로 센다
SERVICE_PROBE_TIMEOUT_SEC = 1.0

# 서버 연결 수집기(pipeline/server_conn_agent.py) -> AI Worker: 접속한 PC마다 열린 HTTP 연결·느린 요청 수 (Slow HTTP)
REDIS_CHANNEL_SERVER_CONNS = "sdn:stats:serverconn"
# 8-스위치 접속 호스트 IP → (dpid, 포트). 컨트롤러의 arp_table과 같아야 한다.
ACCESS_HOST_PORTS = {
    "10.0.0.1": (3, 1),
    "10.0.0.2": (3, 2),
    "10.0.0.3": (4, 1),
    "10.0.0.4": (4, 2),
    "10.0.0.11": (5, 1),
    "10.0.0.12": (5, 2),
    "10.0.0.21": (6, 1),
    "10.0.0.22": (6, 2),
    "10.0.0.254": (7, 1),
    "10.0.0.253": (7, 2),
    "10.0.0.250": (8, 1),
}

# 수동 RESTORE(command_id "manual-…") 직후 같은 포트의 자동 재격리를 보류하는 시간(초).
# 운영자가 AI 오탐을 의심해 풀어 준 포트를, 2초 뒤 다음 경보가 곧바로 다시 막지 않게 한다.
MANUAL_RESTORE_HOLD_SEC = 60.0

# 경고(WARNING) 단계 대응: 해당 포트에서 그 공격 종류의 패킷만 이 속도(초당 패킷)로 제한한다.
# 공격 최소 규모(초당 50개, docs/specs/attack_criteria.md)와 같게 둬서 공격으로 볼 만큼은 못 지나가게 하고,
# 정상 사용자의 같은 종류 패킷(실측 최대 UDP 2.5, ICMP 18.5, SYN 55 — SYN은 몰릴 때만)은 거의 그대로 지나간다.
WARNING_RATE_LIMIT_PPS = 50
# 마지막 WARNING 경보 뒤 이 시간(초) 동안 경보가 없으면 속도 제한을 푼다 (경고는 10초 유지).
WARNING_HOLD_SEC = 10.0


# =====================================================================
# Action and Threat Enumerations
# =====================================================================
class DefenseAction(str, Enum):
    ISOLATE = "ISOLATE"
    RESTORE = "RESTORE"
    REROUTE = "REROUTE"
    RATE_LIMIT = "RATE_LIMIT"
    UNLIMIT = "UNLIMIT"
    RELEARN = "RELEARN"  # 특수 상황 재학습 승인 (관리자 → AI Worker). 컨트롤러는 아무것도 하지 않는다
    QUARANTINE = "QUARANTINE"  # 감염 호스트 동적 격리망 이동 (IP/MAC 단위)
    RELEASE = "RELEASE"        # 격리 해제 및 원래 망 복원 (관리자 수동 승인)


class ZoneKind(str, Enum):
    """논리 망 구분 (SSOT)"""
    USER = "USER"
    SERVER = "SERVER"
    ADMIN = "ADMIN"
    QUARANTINE = "QUARANTINE"


class RiskStage(str, Enum):
    """위험도 단계 (docs/specs/attack_criteria.md). 경보는 WARNING·DANGER만 발행한다."""
    NORMAL = "NORMAL"
    WATCH = "WATCH"        # 주의: 지표 하나가 기준선을 넘음 → 기록만
    WARNING = "WARNING"    # 경고: 공격 종류 확정(2회 연속) → 해당 포트만 속도 제한
    DANGER = "DANGER"      # 위험: 기준의 몇 배 이상 → 격리 + 우회 (기존 방식)


class CountKind(str, Enum):
    """스위치 0번 테이블의 세는 규칙 종류. *_IN은 그 호스트로 '들어가는' 실패 응답이다."""
    SYN = "syn"                # TCP SYN(ACK 없음) — 연결 요청
    FIN = "fin"                # TCP FIN — 정상 종료
    RST = "rst"                # TCP RST — 거절/강제 종료
    UDP = "udp"
    ICMP = "icmp"
    RST_IN = "rst_in"          # 이 호스트가 받은 RST (닫힌 포트의 거절)
    UNREACH_IN = "unreach_in"  # 이 호스트가 받은 ICMP 도달 불가(type 3)
    # 스위치 규칙이 아니라 컨트롤러가 센다(Proxy ARP): 이 호스트가 ARP로 물어본 '없는 내부 주소'의 누적 개수(서로 다른 주소)
    ARP_FAIL = "arp_fail"
    # Table 1 망 정책 위반 (USER -> USER 차단 등) 누적 패킷 수
    ZONE_DENY = "zone_deny"


class ThreatType(str, Enum):
    SYN_FLOOD_SPOOFING = "SYN_FLOOD_SPOOFING"
    UDP_FLOOD = "UDP_FLOOD"
    ICMP_FLOOD = "ICMP_FLOOD"
    SLOW_DDOS = "SLOW_DDOS"
    PORT_SCAN = "PORT_SCAN"
    INTERNAL_SPREAD = "INTERNAL_SPREAD"  # 내부 확산 (랜섬웨어·웜이 내부 PC를 찾아다님)
    UNKNOWN = "UNKNOWN"


# =====================================================================
# 1. Port Statistics Models (Channel: sdn:stats:port)
# =====================================================================
class PortStatItem(BaseModel):
    """Port statistics collected by Ryu via OFPPortStatsReply."""
    dpid: int = Field(..., description="Switch Datapath ID (e.g. 1: S1, 2: S2)")
    port_no: int = Field(..., description="Switch Port Number")
    rx_packets: int = Field(..., description="Cumulative received packet count")
    tx_packets: int = Field(..., description="Cumulative transmitted packet count")
    rx_bytes: int = Field(..., description="Cumulative received byte count")
    tx_bytes: int = Field(..., description="Cumulative transmitted byte count")
    rx_errors: int = Field(0, description="Cumulative receive error count")
    duration_sec: int = Field(..., description="Port active duration in seconds")


class PortStatsMessage(BaseModel):
    """Periodic port statistics payload published by Ryu every 2 seconds."""
    timestamp: float = Field(default_factory=time.time, description="Unix timestamp (seconds)")
    dpid: int = Field(..., description="Switch Datapath ID reporting the stats")
    stats: List[PortStatItem] = Field(default_factory=list, description="List of per-port stats")


class FlowCountItem(BaseModel):
    """One counting rule's cumulative packet count (switch table 0)."""
    port_no: int = Field(..., description="Access port the count belongs to")
    kind: str = Field(..., description="CountKind value (syn, fin, rst, udp, icmp, rst_in, unreach_in)")
    packets: int = Field(..., description="Cumulative matched packets")


class FlowCountMessage(BaseModel):
    """Per-kind packet counts published by Ryu every FLOW_COUNT_INTERVAL_SEC (Channel: sdn:stats:flowcount)."""
    timestamp: float = Field(default_factory=time.time, description="Unix timestamp (seconds)")
    dpid: int = Field(..., description="Switch Datapath ID reporting the counts")
    counts: List[FlowCountItem] = Field(default_factory=list)


class ServiceHealthMessage(BaseModel):
    """Probe results for the protected server, published by Ryu every 2 seconds (Channel: sdn:health:service).

    A probe counts once its timeout has passed, so each message covers the probes sent roughly 1-3 s earlier.
    """
    timestamp: float = Field(default_factory=time.time, description="Unix timestamp (seconds)")
    target_ip: str = Field(..., description="Protected server being probed")
    sent: int = Field(..., description="Probes settled in this report")
    received: int = Field(..., description="Probes answered within the timeout")
    loss_percent: float = Field(..., description="100 * (sent - received) / sent, 0 when nothing was sent")
    rtt_avg_ms: Optional[float] = Field(None, description="Mean round-trip time of the answered probes")
    rtt_max_ms: Optional[float] = Field(None, description="Largest round-trip time of the answered probes")


class ServerConnItem(BaseModel):
    """One client's HTTP connections on the protected server."""
    client_ip: str
    open: int = Field(..., description="Established connections from this client")
    slow: int = Field(..., description="Of those, slow requests: open >= 20 s, no response sent yet, < 500 B/s")
    pending: int = Field(0, description="Of those, unfinished requests: request started, open >= 5 s, "
                                        "no response sent yet, < 500 B/s")


class ServerConnMessage(BaseModel):
    """Server-side connection summary published every second (Channel: sdn:stats:serverconn)."""
    timestamp: float = Field(default_factory=time.time, description="Unix timestamp (seconds)")
    server_ip: str
    port: int
    clients: List[ServerConnItem] = Field(default_factory=list)


# =====================================================================
# 2. AI Anomaly Alert Models (Channel: sdn:anomaly:alert)
# =====================================================================
class AnomalyAlertMessage(BaseModel):
    """Real-time anomaly alert published by AI Worker upon threat detection."""
    timestamp: float = Field(default_factory=time.time, description="Unix timestamp")
    dpid: int = Field(..., description="Ingress switch DPID experiencing anomaly")
    in_port: int = Field(..., description="Attacking traffic ingress port")
    threat_type: str = Field(
        ThreatType.SYN_FLOOD_SPOOFING.value,
        description="Detected threat type",
    )
    score: float = Field(..., description="Anomaly score from Isolation Forest (e.g., -1.0 to 0.0)")
    pps: float = Field(
        ...,
        validation_alias=AliasChoices("pps", "delta_pps"),
        description="Packet per second rate (ΔPPS)",
    )
    bps: float = Field(
        ...,
        validation_alias=AliasChoices("bps", "delta_bps"),
        description="Bits per second rate (ΔBPS)",
    )
    bpp: float = Field(..., description="Bytes per packet (BPP)")
    err_rate: float = Field(
        default=0.0,
        description="Error packet rate (Δrx_errors / Δpackets)",
    )
    stage: str = Field(
        RiskStage.DANGER.value,
        description="WARNING (rate limit) | DANGER (isolate + reroute); older senders mean DANGER",
    )
    metadata: Dict[str, str] = Field(
        default_factory=dict,
        description="Optional diagnostic attributes",
    )


# =====================================================================
# 3. Autonomous Defense Control Command (Channel: sdn:control:command)
# =====================================================================
class ControlCommandMessage(BaseModel):
    """Autonomous mitigation or manual intervention command published to Ryu."""
    timestamp: float = Field(default_factory=time.time, description="Unix timestamp")
    command_id: str = Field(..., description="Unique UUID or tracking identifier for this command")
    action: str = Field(..., description="ISOLATE | RESTORE | REROUTE | RELEARN | QUARANTINE | RELEASE")
    target_dpid: int = Field(..., description="Target switch DPID")
    target_port: int = Field(..., description="Target switch port number")
    reason: str = Field(..., description="Human or AI rationale for mitigation")
    priority: int = Field(100, description="OpenFlow flow rule priority to install/modify")
    duration_sec: Optional[float] = Field(None, description="RELEARN only: approved relearning period (seconds)")
    target_ip: Optional[str] = Field(None, description="QUARANTINE/RELEASE only: target host IP to isolate/release")
    target_mac: Optional[str] = Field(None, description="QUARANTINE/RELEASE only: target host MAC to isolate/release")


# =====================================================================
# 4. Topology Sync Message (Channel: sdn:topology:sync)
# =====================================================================
class TopologyNode(BaseModel):
    id: str = Field(..., description="Node ID (e.g., 's1', 'h_legit')")
    label: str = Field(..., description="Display label")
    node_type: str = Field(..., description="'switch' | 'host'")
    dpid: Optional[int] = None
    ip: Optional[str] = None
    mac: Optional[str] = None
    status: str = Field("NORMAL", description="NORMAL | ATTACKED | MITIGATED | OFFLINE")


class TopologyLink(BaseModel):
    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")
    src_port: int = Field(..., description="Source port")
    dst_port: int = Field(..., description="Destination port")
    is_trunk: bool = Field(False, description="True if link is a switch-to-switch trunk")
    status: str = Field("ACTIVE", description="ACTIVE | REROUTED | BLOCKED")


class TopologySyncMessage(BaseModel):
    """Topology state sync broadcast to frontend vis-network dashboard."""
    timestamp: float = Field(default_factory=time.time, description="Unix timestamp")
    phase: Optional[str] = Field(
        default=None,
        description="Optional FSM phase name (CALIBRATING | NORMAL | ATTACK_DETECTED | MITIGATED | COOLDOWN_VERIFY)",
    )
    nodes: List[TopologyNode] = Field(default_factory=list)
    links: List[TopologyLink] = Field(default_factory=list)
