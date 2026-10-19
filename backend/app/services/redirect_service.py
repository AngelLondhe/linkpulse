"""The hot path: resolve a short code to its destination and record the click.

Budget: one Redis GET (cache hit) + one Redis LPUSH. No UA parsing, geo lookup or DB writes
happen here; the worker does all enrichment asynchronously.
"""

import re
import uuid
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import GoneError, NotFoundError
from app.models import Link
from app.services import click_queue, link_cache
from app.services.click_queue import ClickEvent
from app.services.link_cache import CachedLink, Missing

# Generated codes are 7 Base62 chars; custom aliases are 3-30 of [A-Za-z0-9_-].
SHORT_CODE_PATTERN = re.compile(r"[A-Za-z0-9_-]{3,30}")
MAX_USER_AGENT_LENGTH = 512
MAX_REFERRER_LENGTH = 2048


def _not_found() -> NotFoundError:
    return NotFoundError("Short link not found")


async def _load(db: AsyncSession, redis: Redis, code: str) -> CachedLink:
    """Cache-aside lookup: Redis first, Postgres on a miss (then populate the cache)."""
    cached = await link_cache.get(redis, code)
    if isinstance(cached, Missing):
        raise _not_found()
    if cached is not None:
        return cached

    link = await db.scalar(select(Link).where(Link.short_code == code))
    if link is None:
        await link_cache.store_missing(redis, code)
        raise _not_found()
    entry = CachedLink.from_model(link)
    await link_cache.store(redis, code, entry)
    return entry


async def resolve(
    db: AsyncSession, redis: Redis, code: str, *, now: datetime | None = None
) -> CachedLink:
    """Return the redirect target for ``code``.

    Raises NotFoundError (404) for unknown or deactivated links and GoneError (410) for
    expired ones. An expired link's cache entry is evicted.
    """
    if not SHORT_CODE_PATTERN.fullmatch(code):
        raise _not_found()

    entry = await _load(db, redis, code)
    if not entry.is_active:
        raise _not_found()

    expires_at = entry.expires_at_dt()
    if expires_at is not None and expires_at <= (now or datetime.now(UTC)):
        await link_cache.invalidate(redis, code)
        raise GoneError("This link has expired", code="link_expired")
    return entry


async def record_click(
    redis: Redis,
    entry: CachedLink,
    *,
    ip: str,
    user_agent: str | None,
    referrer: str | None,
) -> ClickEvent | None:
    """Queue a raw click event for the worker.

    Returns None when queued, or the event itself if Redis is unavailable, so the caller can
    persist it directly after the response has been sent (no click is lost).
    """
    event = ClickEvent(
        event_id=str(uuid.uuid4()),
        link_id=entry.id,
        clicked_at=datetime.now(UTC).isoformat(),
        ip=ip,
        user_agent=user_agent[:MAX_USER_AGENT_LENGTH] if user_agent else None,
        referrer=referrer[:MAX_REFERRER_LENGTH] if referrer else None,
    )
    queued = await click_queue.enqueue(redis, event)
    return None if queued else event
