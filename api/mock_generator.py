"""
Self-Defending SDN Tower: Dummy Telemetry Generator (Mock Mode)
Author: Gwanwoo Kim (22102237 / PM & Tech Writer)
Phase 2 (Week 4) Milestone

Replays the 4-stage defense scenario of docs/specs/defense_scenarios.md
without Mininet, Ryu, AI Worker or Redis, so the web control tower can be
built in parallel. Every payload is built from the SSOT contract models in
harness/contracts, then wrapped in the WebSocket envelope.

Timeline (default, seconds):
    CALIBRATING 15 (once) -> [NORMAL 20 -> ATTACK_DETECTED 6
                              -> MITIGATED 20 -> COOLDOWN_VERIFY 10] -> repeat
"""

import asyncio
import random
import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from api.websocket_hub import ConnectionManager, make_envelope
from harness.contracts import (
    REDIS_CHANNEL_ANOMALY_ALERT,
    REDIS_CHANNEL_CONTROL_COMMAND,
    REDIS_CHANNEL_PORT_STATS,
    REDIS_CHANNEL_TOPOLOGY_SYNC,
    AnomalyAlertMessage,
    ControlCommandMessage,
    DefenseAction,
    PortStatItem,
    PortStatsMessage,
    ThreatType,
    TopologyLink,
    TopologyNode,
    TopologySyncMessage,
)

SYSTEM_STATUS_TYPE = "system:status"

# Scenario parameters (docs/specs/defense_scenarios.md §6)
STATS_POLL_INTERVAL_SEC = 2.0
CALIBRATION_SEC = 15.0
COOLDOWN_SEC = 10.0
ATTACK_PPS = 3000.0
ATTACK_BPP = 64.0
LEGIT_PPS = 50.0
LEGIT_BPP = 800.0
REPLY_BPP = 200.0
SCORE_THRESHOLD = -0.5
PRIORITY_DROP = 100
PRIORITY_REROUTE = 100

ATTACKER_DPID = 1
ATTACKER_PORT = 2
BYPASS_EGRESS_PORT = 4

# Trunk ports are never isolatable (whitelist guard, spec §1)
TRUNK_PORTS = {(1, 3), (1, 4), (2, 1), (2, 2), (3, 1), (3, 2), (4, 2), (4, 3)}
SWITCH_PORTS: Dict[int, List[int]] = {1: [1, 2, 3, 4], 2: [1, 2], 3: [1, 2], 4: [1, 2, 3]}

# Forward hops as (dpid, in_port, out_port)
Hop = Tuple[int, int, int]
PRIMARY_PATH: List[Hop] = [(1, 1, 3), (2, 1, 2), (4, 2, 1)]
BYPASS_PATH: List[Hop] = [(1, 1, 4), (3, 1, 2), (4, 3, 1)]
ATTACK_PATH: List[Hop] = [(1, 2, 3), (2, 1, 2), (4, 2, 1)]


class Phase(str, Enum):
    CALIBRATING = "CALIBRATING"
    NORMAL = "NORMAL"
    ATTACK_DETECTED = "ATTACK_DETECTED"
    MITIGATED = "MITIGATED"
    COOLDOWN_VERIFY = "COOLDOWN_VERIFY"


def is_trunk_port(dpid: int, port_no: int) -> bool:
    return (dpid, port_no) in TRUNK_PORTS


def reverse_path(path: List[Hop]) -> List[Hop]:
    return [(dpid, out_port, in_port) for dpid, in_port, out_port in reversed(path)]


def _switch(node_id: str, label: str, dpid: int, status: str = "NORMAL") -> TopologyNode:
    return TopologyNode(id=node_id, label=label, node_type="switch", dpid=dpid, ip=None, mac=None, status=status)


def _host(node_id: str, label: str, ip: str, mac: str, status: str = "NORMAL") -> TopologyNode:
    return TopologyNode(id=node_id, label=label, node_type="host", dpid=None, ip=ip, mac=mac, status=status)


def _link(source: str, target: str, src_port: int, dst_port: int,
          is_trunk: bool = False, status: str = "ACTIVE") -> TopologyLink:
    return TopologyLink(source=source, target=target, src_port=src_port, dst_port=dst_port,
                        is_trunk=is_trunk, status=status)


class MockTelemetryGenerator:
    """Deterministic (seeded) scenario player producing WebSocket envelopes."""

    def __init__(
        self,
        interval: float = STATS_POLL_INTERVAL_SEC,
        calibration_sec: float = CALIBRATION_SEC,
        normal_sec: float = 20.0,
        attack_sec: float = 6.0,
        mitigated_sec: float = 20.0,
        cooldown_sec: float = COOLDOWN_SEC,
        seed: Optional[int] = 42,
    ) -> None:
        self.interval = interval
        self.calibration_sec = calibration_sec
        self._cycle: List[Tuple[Phase, float]] = [
            (Phase.NORMAL, normal_sec),
            (Phase.ATTACK_DETECTED, attack_sec),
            (Phase.MITIGATED, mitigated_sec),
            (Phase.COOLDOWN_VERIFY, cooldown_sec),
        ]
        self._rng = random.Random(seed)
        # (dpid, port) -> [rx_packets, tx_packets, rx_bytes, tx_bytes]
        self._counters: Dict[Tuple[int, int], List[int]] = {
            (dpid, port): [0, 0, 0, 0] for dpid, ports in SWITCH_PORTS.items() for port in ports
        }
        self._elapsed = 0.0
        self.phase: Optional[Phase] = None

    # ------------------------------------------------------------------
    # Timeline
    # ------------------------------------------------------------------
    def phase_at(self, elapsed: float) -> Phase:
        if elapsed < self.calibration_sec:
            return Phase.CALIBRATING
        offset = (elapsed - self.calibration_sec) % sum(d for _, d in self._cycle)
        for phase, duration in self._cycle:
            if offset < duration:
                return phase
            offset -= duration
        return Phase.NORMAL

    # ------------------------------------------------------------------
    # Traffic model
    # ------------------------------------------------------------------
    def _jitter(self, value: float) -> float:
        return value * self._rng.uniform(0.9, 1.1)

    def _apply_flow(self, path: List[Hop], pps: float, bpp: float, drop_at_ingress: bool = False) -> None:
        packets = int(self._jitter(pps) * self.interval)
        byte_count = int(packets * bpp)
        for index, (dpid, in_port, out_port) in enumerate(path):
            counter = self._counters[(dpid, in_port)]
            counter[0] += packets
            counter[2] += byte_count
            if drop_at_ingress and index == 0:
                return  # Priority 100 drop on the ingress port: counted on rx, never forwarded
            counter = self._counters[(dpid, out_port)]
            counter[1] += packets
            counter[3] += byte_count

    def _advance_traffic(self, phase: Phase) -> None:
        legit_path = BYPASS_PATH if phase in (Phase.MITIGATED, Phase.COOLDOWN_VERIFY) else PRIMARY_PATH
        self._apply_flow(legit_path, LEGIT_PPS, LEGIT_BPP)
        self._apply_flow(reverse_path(legit_path), LEGIT_PPS, REPLY_BPP)
        if phase == Phase.ATTACK_DETECTED:
            self._apply_flow(ATTACK_PATH, ATTACK_PPS, ATTACK_BPP)
        elif phase == Phase.MITIGATED:
            self._apply_flow(ATTACK_PATH, ATTACK_PPS, ATTACK_BPP, drop_at_ingress=True)

    def _port_stats(self, uptime: int) -> List[PortStatsMessage]:
        messages = []
        for dpid, ports in SWITCH_PORTS.items():
            stats = []
            for port in ports:
                rx_p, tx_p, rx_b, tx_b = self._counters[(dpid, port)]
                stats.append(
                    PortStatItem(
                        dpid=dpid, port_no=port, rx_packets=rx_p, tx_packets=tx_p,
                        rx_bytes=rx_b, tx_bytes=tx_b, rx_errors=0, duration_sec=uptime,
                    )
                )
            messages.append(PortStatsMessage(dpid=dpid, stats=stats))
        return messages

    # ------------------------------------------------------------------
    # Contract message builders
    # ------------------------------------------------------------------
    def _alert(self) -> AnomalyAlertMessage:
        pps = self._jitter(ATTACK_PPS)
        return AnomalyAlertMessage(
            dpid=ATTACKER_DPID,
            in_port=ATTACKER_PORT,
            threat_type=ThreatType.SYN_FLOOD_SPOOFING.value,
            score=round(self._rng.uniform(-0.9, -0.65), 3),
            pps=round(pps, 1),
            bps=round(pps * ATTACK_BPP, 1),
            bpp=ATTACK_BPP,
            metadata={"model": "mock", "threshold": f"{SCORE_THRESHOLD:.2f}"},
        )

    @staticmethod
    def _command(action: DefenseAction, dpid: int, port: int, reason: str, priority: int) -> ControlCommandMessage:
        if action == DefenseAction.ISOLATE and is_trunk_port(dpid, port):
            raise ValueError(f"Whitelist guard: refusing to isolate trunk port S{dpid}:{port}")
        return ControlCommandMessage(
            command_id=f"cmd-{action.value.lower()}-{uuid.uuid4().hex[:8]}",
            action=action.value,
            target_dpid=dpid,
            target_port=port,
            reason=reason,
            priority=priority,
        )

    def _transition_commands(self, previous: Optional[Phase], current: Phase) -> List[ControlCommandMessage]:
        if current == Phase.MITIGATED and previous == Phase.ATTACK_DETECTED:
            reason = f"{ThreatType.SYN_FLOOD_SPOOFING.value} on S{ATTACKER_DPID}:{ATTACKER_PORT}"
            return [
                self._command(DefenseAction.REROUTE, ATTACKER_DPID, BYPASS_EGRESS_PORT,
                              f"Bypass H_legit via S1-S3-S4 ({reason})", PRIORITY_REROUTE),
                self._command(DefenseAction.ISOLATE, ATTACKER_DPID, ATTACKER_PORT,
                              f"In_port drop ({reason})", PRIORITY_DROP),
            ]
        if current == Phase.NORMAL and previous == Phase.COOLDOWN_VERIFY:
            return [
                self._command(DefenseAction.RESTORE, ATTACKER_DPID, ATTACKER_PORT,
                              f"Cooldown {COOLDOWN_SEC:.0f}s passed: remove drop and bypass flows", PRIORITY_DROP),
            ]
        return []

    def topology_snapshot(self, phase: Optional[Phase] = None) -> TopologySyncMessage:
        phase = phase or self.phase or Phase.CALIBRATING
        attacked = phase == Phase.ATTACK_DETECTED
        mitigated = phase in (Phase.MITIGATED, Phase.COOLDOWN_VERIFY)

        s1_status = "ATTACKED" if attacked else "MITIGATED" if mitigated else "NORMAL"
        nodes = [
            _switch("s1", "S1 (Ingress)", 1, s1_status),
            _switch("s2", "S2 (Primary)", 2),
            _switch("s3", "S3 (Bypass)", 3),
            _switch("s4", "S4 (Egress)", 4),
            _host("h_legit", "H_legit", "10.0.0.1", "00:00:00:00:00:01"),
            _host("h_attacker", "H_attacker", "10.0.0.2", "00:00:00:00:00:02", s1_status),
            _host("h_server", "H_server", "10.0.0.4", "00:00:00:00:00:04"),
        ]
        bypass_status = "REROUTED" if mitigated else "ACTIVE"
        links = [
            _link("s1", "h_legit", 1, 1),
            _link("s1", "h_attacker", 2, 1, status="BLOCKED" if mitigated else "ACTIVE"),
            _link("s1", "s2", 3, 1, is_trunk=True),
            _link("s1", "s3", 4, 1, is_trunk=True, status=bypass_status),
            _link("s2", "s4", 2, 2, is_trunk=True),
            _link("s3", "s4", 2, 3, is_trunk=True, status=bypass_status),
            _link("s4", "h_server", 1, 1),
        ]
        return TopologySyncMessage(nodes=nodes, links=links)

    def status_payload(self) -> Dict[str, Any]:
        phase = self.phase or Phase.CALIBRATING
        return {"phase": phase.value, "mode": "mock", "timestamp": time.time()}

    # ------------------------------------------------------------------
    # Tick
    # ------------------------------------------------------------------
    def step(self) -> List[Dict[str, Any]]:
        """Advance one polling interval and return envelopes to broadcast, in order."""
        self._elapsed += self.interval
        previous, current = self.phase, self.phase_at(self._elapsed)
        self.phase = current

        self._advance_traffic(current)
        envelopes: List[Dict[str, Any]] = [
            make_envelope(REDIS_CHANNEL_PORT_STATS, msg.model_dump(mode="json"))
            for msg in self._port_stats(int(self._elapsed))
        ]
        if current == Phase.ATTACK_DETECTED:
            envelopes.append(make_envelope(REDIS_CHANNEL_ANOMALY_ALERT, self._alert().model_dump(mode="json")))
        for command in self._transition_commands(previous, current):
            envelopes.append(make_envelope(REDIS_CHANNEL_CONTROL_COMMAND, command.model_dump(mode="json")))
        if current != previous:
            envelopes.append(make_envelope(REDIS_CHANNEL_TOPOLOGY_SYNC,
                                           self.topology_snapshot(current).model_dump(mode="json")))
        envelopes.append(make_envelope(SYSTEM_STATUS_TYPE, self.status_payload()))
        return envelopes

    async def run(self, hub: ConnectionManager) -> None:
        """Broadcast forever at the polling interval (cancel the task to stop)."""
        while True:
            for envelope in self.step():
                await hub.broadcast(envelope)
            await asyncio.sleep(self.interval)
