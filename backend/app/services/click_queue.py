"""Click events: produced on the redirect path, consumed in batches by the worker.

The queue is a Redis list. The API LPUSHes; the worker moves events to a processing list
atomically (LMOVE) before handling them, so a worker crash never loses events.
"""

import json
import logging
from dataclasses import asdict, dataclass

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ClickEvent:
    """Raw click data captured in the request path. Parsing/enrichment happens in the worker.

    ``ip`` is the raw client IP, kept only transiently in the queue because the worker needs
    it for the geo lookup; it is hashed before anything is written to Postgres.
    """

    link_id: int
    clicked_at: str  # ISO-8601, UTC
    ip: str
    user_agent: str | None
    referrer: str | None

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"))

    @classmethod
    def from_json(cls, raw: str) -> "ClickEvent":
        return cls(**json.loads(raw))


def queue_key() -> str:
    return get_settings().click_queue_key


async def enqueue(redis: Redis, event: ClickEvent) -> bool:
    """Push a click event; returns False (and logs) if Redis is unavailable."""
    try:
        await redis.lpush(queue_key(), event.to_json())
    except (RedisError, OSError):
        logger.warning("Redis unavailable; could not enqueue click for link %s", event.link_id)
        return False
    return True
