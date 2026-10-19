"""Shared async Redis client.

Short socket timeouts are deliberate: on the redirect path a slow/dead Redis must fail fast
so the request can fall back to Postgres instead of hanging.
"""

from redis.asyncio import Redis

from app.core.config import get_settings

_settings = get_settings()

redis_client: Redis = Redis.from_url(
    _settings.redis_url,
    decode_responses=True,
    socket_timeout=_settings.redis_socket_timeout_seconds,
    socket_connect_timeout=_settings.redis_socket_timeout_seconds,
    health_check_interval=30,
)


def get_redis() -> Redis:
    """FastAPI dependency returning the shared Redis client (overridable in tests)."""
    return redis_client
