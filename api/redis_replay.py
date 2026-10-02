"""
Self-Defending SDN Tower: Mock Scenario -> Redis Replayer
Author: Gwanwoo Kim (22102237 / PM & Tech Writer)
Phase 2 (Week 6) Milestone

Publishes the mock defense scenario to the real Redis channels, standing in
for Ryu and the AI Worker. Lets the Redis -> FastAPI -> browser pipeline be
verified before controller.py exists.

Run (Redis on localhost:6379, backend in live mode):
    SDN_MOCK=0 uv run uvicorn api.main:app --port 8000
    uv run python -m api.redis_replay
"""

import argparse
import asyncio
import json

import redis.asyncio as aioredis

from api.mock_generator import SYSTEM_STATUS_TYPE, MockTelemetryGenerator


async def replay(redis_url: str, interval: float, ticks: int, speed: float = 1.0) -> None:
    client = aioredis.from_url(redis_url)
    generator = MockTelemetryGenerator(interval=interval)
    try:
        count = 0
        while ticks <= 0 or count < ticks:
            for envelope in generator.step():
                # The FSM phase has no Redis channel yet (spec §8 Q3); only contract channels are replayed
                if envelope["type"] != SYSTEM_STATUS_TYPE:
                    await client.publish(envelope["type"], json.dumps(envelope["data"]))
            phase = generator.phase.value if generator.phase else "-"
            print(f"[redis_replay] t={count * interval:5.0f}s phase={phase}")
            count += 1
            await asyncio.sleep(interval / speed)
    finally:
        await client.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish the mock defense scenario to Redis")
    parser.add_argument("--redis-url", default="redis://localhost:6379/0")
    parser.add_argument("--interval", type=float, default=2.0, help="seconds between polling ticks")
    parser.add_argument("--ticks", type=int, default=0, help="stop after N ticks (0 = forever)")
    parser.add_argument("--speed", type=float, default=1.0, help="playback speed (4 = scenario runs 4x faster)")
    args = parser.parse_args()
    asyncio.run(replay(args.redis_url, args.interval, args.ticks, args.speed))


if __name__ == "__main__":
    main()
