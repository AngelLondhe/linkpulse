"""Entry point: ``python -m app.worker``."""

import asyncio
import logging
import signal

from redis.asyncio import Redis

from app.core.config import get_settings
from app.db.session import SessionLocal, engine
from app.services.geo import get_geo_lookup
from app.worker.runner import ClickWorker


async def main() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    # Own client: blocking BLMOVE needs a socket timeout longer than the block timeout.
    redis = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_timeout=settings.worker_block_timeout_seconds + 5,
        health_check_interval=30,
    )
    worker = ClickWorker(
        redis=redis, session_factory=SessionLocal, geo=get_geo_lookup(), settings=settings
    )
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, worker.stop)  # finish the current batch, then exit
    try:
        await worker.run_forever()
    finally:
        await redis.aclose()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
