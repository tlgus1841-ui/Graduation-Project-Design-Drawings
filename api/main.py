"""
Self-Defending SDN Tower: FastAPI Control Tower Backend
Author: Gwanwoo Kim (22102237 / PM & Tech Writer)
Phase 2 (Week 4) Milestone

Endpoints:
- GET /api/health   : liveness + active WebSocket session count
- GET /api/topology : current topology snapshot (TopologySyncMessage)
- WS  /ws           : real-time envelope stream (docs/specs/defense_scenarios.md §5.1)

Week 4 runs in mock mode (api/mock_generator.py). The Redis Pub/Sub bridge
replaces the generator in week 6 once Ryu publishes real telemetry.

Run:
    uv run uvicorn api.main:app --reload --port 8000
    SDN_MOCK=0 uv run uvicorn api.main:app --port 8000   # hub only, no dummy telemetry
"""

import asyncio
import contextlib
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from api.mock_generator import SYSTEM_STATUS_TYPE, MockTelemetryGenerator
from api.websocket_hub import ConnectionManager, make_envelope
from harness.contracts import REDIS_CHANNEL_TOPOLOGY_SYNC

logger = logging.getLogger(__name__)


def create_app(enable_mock: Optional[bool] = None) -> FastAPI:
    """Application factory; enable_mock defaults to the SDN_MOCK env var (on unless '0')."""
    if enable_mock is None:
        enable_mock = os.getenv("SDN_MOCK", "1") != "0"

    hub = ConnectionManager()
    generator = MockTelemetryGenerator()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        task = asyncio.create_task(generator.run(hub)) if enable_mock else None
        try:
            yield
        finally:
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    app = FastAPI(title="Self-Defending SDN Tower API", version="0.1.0", lifespan=lifespan)
    app.state.hub = hub
    app.state.generator = generator

    # React dev server (localhost:5173) calls this API cross-origin (roadmap_v2.md §25)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    async def health() -> Dict[str, Any]:
        return {
            "status": "ok",
            "mode": "mock" if enable_mock else "live",
            "active_connections": hub.count,
            "phase": generator.status_payload()["phase"],
        }

    @app.get("/api/topology")
    async def topology() -> Dict[str, Any]:
        return generator.topology_snapshot().model_dump(mode="json")

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        await hub.register(websocket)
        try:
            # Initial snapshot so a freshly (re)loaded page renders immediately
            await hub.send_to(websocket, make_envelope(
                REDIS_CHANNEL_TOPOLOGY_SYNC, generator.topology_snapshot().model_dump(mode="json")))
            await hub.send_to(websocket, make_envelope(SYSTEM_STATUS_TYPE, generator.status_payload()))
            while True:
                # Clients only send keepalives; receiving detects F5 / tab close promptly
                if await websocket.receive_text() == "ping":
                    await websocket.send_text("pong")
        except WebSocketDisconnect:
            pass
        except Exception:
            logger.exception("Unexpected WebSocket error")
        finally:
            await hub.disconnect(websocket)

    return app


app = create_app()
