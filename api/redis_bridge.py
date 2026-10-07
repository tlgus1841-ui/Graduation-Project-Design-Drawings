"""
Self-Defending SDN Tower: Redis Pub/Sub -> WebSocket Bridge (Live Mode)
Author: Gwanwoo Kim (22102237 / PM & Tech Writer)
Phase 2 (Week 6) Milestone

Subscribes to the four SSOT Redis channels, validates every payload with the
contract models in harness/contracts, and relays it to browsers as the
WebSocket envelope of docs/specs/defense_scenarios.md §5.1.

- Invalid payloads are dropped (never forwarded) and logged with the reason,
  so a field-name mismatch on the Ryu side is visible immediately.
- Losing Redis never kills the backend: the bridge retries with backoff.
- The FSM phase is not on a Redis channel yet (spec §8 Q3), so it is inferred
  from alerts and control commands until that decision is made.
"""

import asyncio
import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Type

import redis.asyncio as aioredis
from pydantic import BaseModel, ValidationError

from api.mock_generator import SYSTEM_STATUS_TYPE, MockTelemetryGenerator, Phase
from api.websocket_hub import ConnectionManager, make_envelope
from harness.contracts import (
    REDIS_CHANNEL_ANOMALY_ALERT,
    REDIS_CHANNEL_CONTROL_COMMAND,
    REDIS_CHANNEL_PORT_STATS,
    REDIS_CHANNEL_TOPOLOGY_SYNC,
    AnomalyAlertMessage,
    ControlCommandMessage,
    DefenseAction,
    PortStatsMessage,
    TopologySyncMessage,
)

logger = logging.getLogger(__name__)

CHANNEL_MODELS: Dict[str, Type[BaseModel]] = {
    REDIS_CHANNEL_PORT_STATS: PortStatsMessage,
    REDIS_CHANNEL_ANOMALY_ALERT: AnomalyAlertMessage,
    REDIS_CHANNEL_CONTROL_COMMAND: ControlCommandMessage,
    REDIS_CHANNEL_TOPOLOGY_SYNC: TopologySyncMessage,
}
MAX_BACKOFF_SEC = 10.0

RedisFactory = Callable[[], "aioredis.Redis"]


class LivePhaseTracker:
    """Provisional FSM phase inferred from the contract messages (spec §8 Q3)."""

    def __init__(self) -> None:
        self.phase: Optional[Phase] = None

    def observe(self, channel: str, message: BaseModel) -> bool:
        """Update the phase from one validated message. Returns True when it changed."""
        previous = self.phase
        if channel == REDIS_CHANNEL_ANOMALY_ALERT and self.phase != Phase.MITIGATED:
            self.phase = Phase.ATTACK_DETECTED
        elif channel == REDIS_CHANNEL_CONTROL_COMMAND and isinstance(message, ControlCommandMessage):
            if message.action in (DefenseAction.ISOLATE.value, DefenseAction.REROUTE.value):
                self.phase = Phase.MITIGATED
            elif message.action == DefenseAction.RESTORE.value:
                self.phase = Phase.NORMAL
        elif self.phase is None:
            self.phase = Phase.NORMAL
        return self.phase != previous


class RedisBridge:
    """Relays validated Redis Pub/Sub messages to the WebSocket hub."""

    def __init__(self, redis_url: str = "redis://localhost:6379/0",
                 redis_factory: Optional[RedisFactory] = None) -> None:
        self.redis_url = redis_url
        self._redis_factory = redis_factory or (lambda: aioredis.from_url(redis_url))
        self.tracker = LivePhaseTracker()
        self.topology: Optional[TopologySyncMessage] = None
        self.connected = False
        self.received = 0
        self.dropped = 0
        # Physical layout is known from topo/diamond_topo.py; shown until Ryu sends a sync
        self._static_topology = MockTelemetryGenerator().topology_snapshot(Phase.NORMAL)

    # ------------------------------------------------------------------
    # Source interface shared with MockTelemetryGenerator (used by api.main)
    # ------------------------------------------------------------------
    def topology_snapshot(self) -> TopologySyncMessage:
        return self.topology or self._static_topology

    def status_payload(self) -> Dict[str, Any]:
        phase = self.tracker.phase.value if self.tracker.phase else None
        return {"phase": phase, "mode": "live", "upstream": "connected" if self.connected else "disconnected",
                "timestamp": time.time()}

    # ------------------------------------------------------------------
    # Message handling (pure apart from bridge counters and state)
    # ------------------------------------------------------------------
    def handle_message(self, channel: str, raw: Any) -> List[Dict[str, Any]]:
        """Validate one Redis message and return the envelopes to broadcast (empty if dropped)."""
        self.received += 1
        model = CHANNEL_MODELS.get(channel)
        if model is None:
            self.dropped += 1
            logger.warning("Dropped message on unknown channel %r", channel)
            return []
        try:
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            message = model.model_validate_json(raw) if isinstance(raw, str) else model.model_validate(raw)
        except (ValidationError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            self.dropped += 1
            logger.warning("Dropped invalid %s payload: %s", channel, str(exc).splitlines()[0])
            return []

        if isinstance(message, TopologySyncMessage):
            self.topology = message
        envelopes = [make_envelope(channel, message.model_dump(mode="json"))]
        if self.tracker.observe(channel, message):
            envelopes.append(make_envelope(SYSTEM_STATUS_TYPE, self.status_payload()))
        return envelopes

    # ------------------------------------------------------------------
    # Subscription loop
    # ------------------------------------------------------------------
    async def publish(self, channel: str, message: BaseModel) -> int:
        """Publish one contract message (week 13 manual control). Returns the subscriber count.

        The bridge's own subscription receives it back, so the UI sees exactly what Ryu sees.
        """
        client = self._redis_factory()
        try:
            return int(await client.publish(channel, message.model_dump_json()))
        finally:
            await client.aclose()

    async def _set_connected(self, hub: ConnectionManager, connected: bool) -> None:
        if self.connected != connected:
            self.connected = connected
            await hub.broadcast(make_envelope(SYSTEM_STATUS_TYPE, self.status_payload()))

    async def run(self, hub: ConnectionManager) -> None:
        """Subscribe forever, reconnecting with backoff (cancel the task to stop)."""
        attempt = 0
        while True:
            client = self._redis_factory()
            pubsub = client.pubsub()
            try:
                await pubsub.subscribe(*CHANNEL_MODELS)
                await self._set_connected(hub, True)
                attempt = 0
                logger.info("Redis bridge subscribed to %s", ", ".join(CHANNEL_MODELS))
                async for item in pubsub.listen():
                    if item.get("type") != "message":
                        continue
                    channel = item["channel"]
                    if isinstance(channel, bytes):
                        channel = channel.decode("utf-8")
                    for envelope in self.handle_message(channel, item["data"]):
                        await hub.broadcast(envelope)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await self._set_connected(hub, False)
                attempt += 1
                delay = min(2 ** (attempt - 1), MAX_BACKOFF_SEC)
                logger.warning("Redis bridge disconnected (%s); retrying in %.0fs", exc, delay)
                await asyncio.sleep(delay)
            finally:
                try:
                    await pubsub.aclose()
                    await client.aclose()
                except Exception:
                    pass
