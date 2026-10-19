"""Click worker: drains the Redis click queue into Postgres in batches.

Reliability model ("reliable queue" pattern):
  1. Events are moved atomically from the shared queue into this worker's own processing
     list (BLMOVE/LMOVE), so they always live in exactly one Redis list.
  2. The batch is enriched and bulk-inserted in one transaction.
  3. Only after the commit is the processing list cleared.
A crash or DB error at any step leaves the batch in the processing list, and it is retried
first on the next iteration (including after a restart). Inserts are idempotent on event_id,
so a retry after a commit-but-before-clear crash cannot double-count.
"""

import asyncio
import contextlib
import logging
from collections.abc import Callable

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.services.click_processing import ClickRow, enrich, insert_clicks
from app.services.click_queue import ClickEvent
from app.services.geo import GeoLookup

logger = logging.getLogger(__name__)

# Atomically move up to ARGV[1] events from the queue to the processing list.
CLAIM_SCRIPT = """
local moved = {}
for i = 1, tonumber(ARGV[1]) do
  local item = redis.call('LMOVE', KEYS[1], KEYS[2], 'RIGHT', 'LEFT')
  if not item then break end
  moved[#moved + 1] = item
end
return moved
"""


def _text(value: bytes | str) -> str:
    return value.decode() if isinstance(value, bytes) else value


class ClickWorker:
    def __init__(
        self,
        *,
        redis: Redis,
        session_factory: Callable[[], AsyncSession],
        geo: GeoLookup,
        settings: Settings,
    ) -> None:
        self.redis = redis
        self.session_factory = session_factory
        self.geo = geo
        self.batch_size = settings.worker_batch_size
        self.block_timeout = settings.worker_block_timeout_seconds
        self.max_backoff = settings.worker_max_backoff_seconds
        self.salt = settings.ip_hash_salt.get_secret_value()
        self.queue_key = settings.click_queue_key
        self.processing_key = f"{settings.click_queue_key}:processing:{settings.worker_id}"
        self.dead_letter_key = f"{settings.click_queue_key}:dead"
        self._claim = redis.register_script(CLAIM_SCRIPT)
        self._stopping = asyncio.Event()

    def stop(self) -> None:
        self._stopping.set()

    async def claim_batch(self) -> list[str]:
        """Return the next batch, retrying any unfinished batch from a previous run first."""
        pending = [_text(item) for item in await self.redis.lrange(self.processing_key, 0, -1)]
        if pending:
            logger.info("Retrying %d unfinished event(s)", len(pending))
            return pending

        first = await self.redis.blmove(
            self.queue_key, self.processing_key, self.block_timeout, "RIGHT", "LEFT"
        )
        if first is None:
            return []
        rest = await self._claim(
            keys=[self.queue_key, self.processing_key], args=[self.batch_size - 1]
        )
        return [_text(first), *(_text(item) for item in rest)]

    def _parse(self, raw_items: list[str]) -> tuple[list[ClickRow], list[str]]:
        rows: list[ClickRow] = []
        malformed: list[str] = []
        for raw in raw_items:
            try:
                rows.append(enrich(ClickEvent.from_json(raw), self.geo, self.salt))
            except (ValueError, TypeError, KeyError):
                malformed.append(raw)
        return rows, malformed

    async def process_batch(self, raw_items: list[str]) -> int:
        """Enrich and insert one batch, then acknowledge it. Returns rows inserted."""
        rows, malformed = self._parse(raw_items)
        async with self.session_factory() as db:
            inserted = await insert_clicks(db, rows)
        if malformed:
            logger.warning(
                "Moved %d malformed event(s) to %s", len(malformed), self.dead_letter_key
            )
            await self.redis.lpush(self.dead_letter_key, *malformed)
        await self.redis.delete(self.processing_key)  # ack: only after the commit
        return inserted

    async def run_once(self) -> int:
        batch = await self.claim_batch()
        if not batch:
            return 0
        inserted = await self.process_batch(batch)
        logger.info("Processed %d event(s), inserted %d click(s)", len(batch), inserted)
        return inserted

    async def run_forever(self) -> None:
        """Loop until stop() is called, backing off exponentially on infrastructure errors."""
        backoff = 0.5
        logger.info("Click worker started (processing list: %s)", self.processing_key)
        while not self._stopping.is_set():
            try:
                await self.run_once()
                backoff = 0.5
            except (RedisError, SQLAlchemyError, OSError):
                logger.exception("Worker iteration failed; retrying in %.1fs", backoff)
                with contextlib.suppress(TimeoutError):  # sleep, but wake early on stop()
                    await asyncio.wait_for(self._stopping.wait(), timeout=backoff)
                backoff = min(backoff * 2, self.max_backoff)
        logger.info("Click worker stopped")
