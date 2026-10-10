"""
Self-Defending SDN Tower: Single Source of Truth (SSOT) IPC Contract Schemas
Author: Sihyeon Park (22101489 / Tech Lead)
Phase 2 (Week 4) Milestone

Redis Pub/Sub Channels:
- sdn:stats:port      : Ryu -> AI Worker, FastAPI
- sdn:anomaly:alert   : AI Worker -> Ryu, FastAPI
- sdn:control:command : AI Worker / Web UI -> Ryu
- sdn:topology:sync   : Ryu -> FastAPI, Web UI
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


# =====================================================================
# Action and Threat Enumerations
# =====================================================================
class DefenseAction(str, Enum):
    ISOLATE = "ISOLATE"
    RESTORE = "RESTORE"
    REROUTE = "REROUTE"


class ThreatType(str, Enum):
    SYN_FLOOD_SPOOFING = "SYN_FLOOD_SPOOFING"
    UDP_FLOOD = "UDP_FLOOD"
    ICMP_FLOOD = "ICMP_FLOOD"
    SLOW_DDOS = "SLOW_DDOS"
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
        description="Bytes per second rate (ΔBPS)",
    )
    bpp: float = Field(..., description="Bytes per packet (BPP)")
    err_rate: float = Field(
        default=0.0,
        description="Error packet rate (Δrx_errors / Δpackets)",
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
    action: str = Field(..., description="ISOLATE | RESTORE | REROUTE")
    target_dpid: int = Field(..., description="Target switch DPID")
    target_port: int = Field(..., description="Target switch port number")
    reason: str = Field(..., description="Human or AI rationale for mitigation")
    priority: int = Field(100, description="OpenFlow flow rule priority to install/modify")


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
    nodes: List[TopologyNode] = Field(default_factory=list)
    links: List[TopologyLink] = Field(default_factory=list)
