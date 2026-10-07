"""
Self-Defending SDN Tower: FastAPI Control Tower Backend
Author: Gwanwoo Kim (22102237 / PM & Tech Writer)
Phase 2 (Week 4, live mode added in Week 6)

Endpoints:
- GET /api/health   : liveness + active WebSocket session count
- GET /api/topology : current topology snapshot (TopologySyncMessage)
- WS  /ws           : real-time envelope stream (docs/specs/defense_scenarios.md §5.1)
- POST /api/control/manual : operator emergency ISOLATE/RESTORE (week 13, api/manual_control.py).
                             If SDN_ADMIN_TOKEN is set, the X-Admin-Token header must match.

Data source:
- mock (default): api/mock_generator.py replays the defense scenario in-process
- live (SDN_MOCK=0): api/redis_bridge.py relays the Redis channels (REDIS_URL)

Run:
    uv run uvicorn api.main:app --reload --port 8000
    SDN_MOCK=0 REDIS_URL=redis://localhost:6379/0 uv run uvicorn api.main:app --port 8000
"""

import asyncio
import contextlib
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional, Union

from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from api.manual_control import ManualControlRejected, ManualControlRequest, build_manual_command
from api.mock_generator import SYSTEM_STATUS_TYPE, MockTelemetryGenerator
from api.redis_bridge import RedisBridge, RedisFactory
from api.websocket_hub import ConnectionManager, make_envelope
from harness.contracts import REDIS_CHANNEL_CONTROL_COMMAND, REDIS_CHANNEL_TOPOLOGY_SYNC

logger = logging.getLogger(__name__)


def create_app(enable_mock: Optional[bool] = None, *, start_source: bool = True,
               redis_url: Optional[str] = None, redis_factory: Optional[RedisFactory] = None) -> FastAPI:
    """Application factory.

    enable_mock defaults to the SDN_MOCK env var (mock unless '0'); live mode reads REDIS_URL.
    start_source=False keeps the data source idle (endpoint tests).
    """
    if enable_mock is None:
        enable_mock = os.getenv("SDN_MOCK", "1") != "0"

    hub = ConnectionManager()
    source: Union[MockTelemetryGenerator, RedisBridge]
    if enable_mock:
        source = MockTelemetryGenerator()
    else:
        source = RedisBridge(redis_url or os.getenv("REDIS_URL") or "redis://localhost:6379/0", redis_factory)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        task = asyncio.create_task(source.run(hub)) if start_source else None
        try:
            yield
        finally:
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    app = FastAPI(title="Self-Defending SDN Tower API", version="0.1.0", lifespan=lifespan)
    app.state.hub = hub
    app.state.source = source

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
        body = {
            "status": "ok",
            "mode": "mock" if enable_mock else "live",
            "active_connections": hub.count,
            "phase": source.status_payload()["phase"],
        }
        if isinstance(source, RedisBridge):
            body["redis"] = {"connected": source.connected, "received": source.received, "dropped": source.dropped}
        return body

    @app.get("/api/topology")
    async def topology() -> Dict[str, Any]:
        return source.topology_snapshot().model_dump(mode="json")

    @app.post("/api/control/manual")
    async def manual_control(
        req: ManualControlRequest, x_admin_token: Optional[str] = Header(default=None)
    ) -> Dict[str, Any]:
        expected = os.getenv("SDN_ADMIN_TOKEN")
        if expected and x_admin_token != expected:
            raise HTTPException(status_code=401, detail="관리자 토큰이 올바르지 않습니다.")
        try:
            command = build_manual_command(req)
        except ManualControlRejected as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        payload = command.model_dump(mode="json")
        if isinstance(source, RedisBridge):
            try:
                receivers = await source.publish(REDIS_CHANNEL_CONTROL_COMMAND, command)
            except Exception as exc:
                logger.warning("Manual command publish failed: %s", exc)
                raise HTTPException(status_code=503, detail="Redis에 연결할 수 없어 명령을 보내지 못했습니다.") from exc
            # The bridge's subscription echoes it to the UI; no direct broadcast (avoids duplicates).
            return {"accepted": True, "delivered_to": "redis", "receivers": receivers, "command": payload}
        await hub.broadcast(make_envelope(REDIS_CHANNEL_CONTROL_COMMAND, payload))
        return {"accepted": True, "delivered_to": "mock", "receivers": 0, "command": payload}

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        await hub.register(websocket)
        try:
            # Initial snapshot so a freshly (re)loaded page renders immediately
            await hub.send_to(websocket, make_envelope(
                REDIS_CHANNEL_TOPOLOGY_SYNC, source.topology_snapshot().model_dump(mode="json")))
            await hub.send_to(websocket, make_envelope(SYSTEM_STATUS_TYPE, source.status_payload()))
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
