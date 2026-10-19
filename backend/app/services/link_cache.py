"""Redis cache for short-code lookups on the redirect path.

Every function here treats Redis as optional: on any Redis error it logs and degrades
(a read becomes a cache miss, a write is skipped) so redirects keep working from Postgres.
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings
from app.models import Link

logger = logging.getLogger(__name__)

KEY_PREFIX = "link:"
MISSING_MARKER = "__missing__"
NEGATIVE_TTL_SECONDS = 60  # brief, so a newly created code becomes visible quickly


@dataclass(frozen=True)
class CachedLink:
    """The subset of a link needed to serve a redirect without touching Postgres."""

    id: int
    url: str
    is_active: bool
    expires_at: str | None  # ISO-8601
    max_clicks: int | None
    has_password: bool

    @classmethod
    def from_model(cls, link: Link) -> "CachedLink":
        return cls(
            id=link.id,
            url=link.original_url,
            is_active=link.is_active,
            expires_at=link.expires_at.isoformat() if link.expires_at else None,
            max_clicks=link.max_clicks,
            has_password=link.password_hash is not None,
        )

    def expires_at_dt(self) -> datetime | None:
        return datetime.fromisoformat(self.expires_at) if self.expires_at else None


class Missing:
    """Sentinel: the cache knows this code does not exist (negative cache hit)."""


MISSING = Missing()


def cache_key(code: str) -> str:
    return f"{KEY_PREFIX}{code}"


async def get(redis: Redis, code: str) -> CachedLink | Missing | None:
    """Return the cached link, MISSING for a cached "not found", or None on a miss/error."""
    try:
        raw = await redis.get(cache_key(code))
    except (RedisError, OSError):
        logger.warning("Redis unavailable for cache read; falling back to Postgres")
        return None
    if raw is None:
        return None
    if raw == MISSING_MARKER:
        return MISSING
    try:
        return CachedLink(**json.loads(raw))
    except (TypeError, ValueError):
        logger.warning("Discarding malformed cache entry for %s", code)
        return None


def _ttl_for(entry: CachedLink, now: datetime) -> int:
    """Default TTL, capped so the entry never outlives the link's expiry by much."""
    ttl = get_settings().link_cache_ttl_seconds
    expires_at = entry.expires_at_dt()
    if expires_at is not None:
        ttl = min(ttl, max(1, int((expires_at - now).total_seconds())))
    return ttl


async def store(redis: Redis, code: str, entry: CachedLink) -> None:
    try:
        await redis.set(
            cache_key(code), json.dumps(asdict(entry)), ex=_ttl_for(entry, datetime.now(UTC))
        )
    except (RedisError, OSError):
        logger.warning("Redis unavailable; skipped caching %s", code)


async def store_missing(redis: Redis, code: str) -> None:
    try:
        await redis.set(cache_key(code), MISSING_MARKER, ex=NEGATIVE_TTL_SECONDS)
    except (RedisError, OSError):
        logger.warning("Redis unavailable; skipped negative-caching %s", code)


async def invalidate(redis: Redis, *codes: str) -> None:
    """Drop cached entries after a link is created, edited, deleted, deactivated or expires.

    If Redis is down the entry may be served stale until its TTL elapses; this is logged
    at ERROR so it is visible (see docs/DECISIONS.md).
    """
    if not codes:
        return
    try:
        await redis.delete(*(cache_key(code) for code in codes))
    except (RedisError, OSError):
        logger.error("Redis unavailable; could not invalidate cache for %s", codes)
