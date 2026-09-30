"""
Self-Defending SDN Tower: WebSocket Connection Hub
Author: Gwanwoo Kim (22102237 / PM & Tech Writer)
Phase 2 (Week 4) Milestone

Keeps the set of live browser connections and multicasts envelopes to them.
Stale sessions (browser F5 / tab close) are dropped the moment a send fails,
so one dead socket can never crash the ASGI server (roadmap_v2.md §16).
"""

import asyncio
import logging
from typing import Any, Dict, List, Protocol

logger = logging.getLogger(__name__)


class SupportsSendJson(Protocol):
    """Minimal WebSocket surface the hub depends on (eases testing)."""

    async def send_json(self, data: Any, mode: str = "text") -> None: ...


def make_envelope(msg_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Wrap a payload in the WebSocket envelope defined in docs/specs/defense_scenarios.md §5.1."""
    return {"type": msg_type, "data": data}


class ConnectionManager:
    """Registry of active WebSocket sessions with stale-session cleanup."""

    def __init__(self) -> None:
        self._connections: List[SupportsSendJson] = []
        self._lock = asyncio.Lock()

    @property
    def count(self) -> int:
        return len(self._connections)

    async def register(self, websocket: SupportsSendJson) -> None:
        """Track an already-accepted WebSocket."""
        async with self._lock:
            self._connections.append(websocket)
        logger.info("WebSocket connected (active=%d)", self.count)

    async def disconnect(self, websocket: SupportsSendJson) -> None:
        """Remove a session; safe to call more than once for the same socket."""
        async with self._lock:
            if websocket in self._connections:
                self._connections.remove(websocket)
        logger.info("WebSocket disconnected (active=%d)", self.count)

    async def send_to(self, websocket: SupportsSendJson, message: Dict[str, Any]) -> bool:
        """Send to a single client; drops it on failure. Returns True on success."""
        try:
            await websocket.send_json(message)
            return True
        except Exception:
            await self.disconnect(websocket)
            return False

    async def broadcast(self, message: Dict[str, Any]) -> int:
        """Multicast to every client and purge sockets that fail. Returns delivered count."""
        async with self._lock:
            targets = list(self._connections)

        stale: List[SupportsSendJson] = []
        delivered = 0
        for connection in targets:
            try:
                await connection.send_json(message)
                delivered += 1
            except Exception:
                stale.append(connection)

        if stale:
            async with self._lock:
                for connection in stale:
                    if connection in self._connections:
                        self._connections.remove(connection)
            logger.warning("Purged %d stale WebSocket session(s) (active=%d)", len(stale), self.count)
        return delivered
