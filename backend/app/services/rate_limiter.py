"""Redis sliding-window rate limiter (implemented here, not via a library).

Algorithm: "sliding window counter". Requests are counted in fixed windows; the estimate for
the sliding window ending now is

    previous_window_count * (overlap of the sliding window with the previous window) + current

This is O(1) memory per client (two integers) yet avoids the 2x burst a plain fixed window
allows at window boundaries. The check-and-increment runs in a single Lua script, so it is
atomic across all API replicas (one round trip per request).
"""

import logging
import math
import time
from dataclasses import dataclass

from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

# KEYS[1] current window, KEYS[2] previous window.
# ARGV[1] limit, ARGV[2] window (ms), ARGV[3] now (ms).
# Returns {allowed (0/1), current_count, previous_count, elapsed_ms_in_window}.
_SLIDING_WINDOW = """
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local elapsed = tonumber(ARGV[3]) % window
local current = tonumber(redis.call('GET', KEYS[1]) or '0')
local previous = tonumber(redis.call('GET', KEYS[2]) or '0')
local estimate = previous * ((window - elapsed) / window) + current
if estimate + 1 > limit then
  return {0, current, previous, elapsed}
end
current = redis.call('INCR', KEYS[1])
redis.call('PEXPIRE', KEYS[1], window * 2)
return {1, current, previous, elapsed}
"""


@dataclass(frozen=True)
class RateLimitRule:
    name: str
    limit: int
    window_seconds: int


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    retry_after: int  # seconds; 0 when allowed


def _retry_after_ms(rule: RateLimitRule, current: int, previous: int, elapsed: int) -> int:
    """Smallest wait after which one more request fits under the limit."""
    window = rule.window_seconds * 1000
    if current + 1 > rule.limit or previous == 0:
        return window - elapsed  # only the next window can help
    # Need previous * (window - elapsed - wait) / window + current + 1 <= limit
    wait = (window - elapsed) - (rule.limit - current - 1) * window / previous
    return max(1, math.ceil(wait))


class RateLimiter:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis
        self._script = redis.register_script(_SLIDING_WINDOW)

    async def hit(
        self, rule: RateLimitRule, identity: str, *, now_ms: int | None = None
    ) -> RateLimitResult:
        """Count one request for ``identity`` under ``rule``; fails open if Redis is down."""
        window_ms = rule.window_seconds * 1000
        now = now_ms if now_ms is not None else int(time.time() * 1000)
        index = now // window_ms
        # The {hash tag} keeps both keys in one cluster slot, so the multi-key script also
        # works on Redis Cluster / Upstash.
        tag = f"{{rl:{rule.name}:{identity}}}"
        keys = [f"{tag}:{index}", f"{tag}:{index - 1}"]
        try:
            allowed, current, previous, elapsed = await self._script(
                keys=keys,
                args=[rule.limit, window_ms, now],
            )
        except (RedisError, OSError):
            logger.warning("Redis unavailable; rate limit %s not enforced", rule.name)
            return RateLimitResult(True, rule.limit, rule.limit, 0)

        if allowed:
            estimate = previous * ((window_ms - elapsed) / window_ms) + current
            return RateLimitResult(True, rule.limit, max(0, rule.limit - math.ceil(estimate)), 0)
        retry_ms = _retry_after_ms(rule, int(current), int(previous), int(elapsed))
        return RateLimitResult(False, rule.limit, 0, max(1, math.ceil(retry_ms / 1000)))


# Default policy. Tuned to stop abuse without bothering real users.
LOGIN = RateLimitRule("login", limit=10, window_seconds=60)
REGISTER = RateLimitRule("register", limit=5, window_seconds=3600)
CREATE_LINK = RateLimitRule("create_link", limit=30, window_seconds=60)
REDIRECT = RateLimitRule("redirect", limit=300, window_seconds=60)
UNLOCK = RateLimitRule("unlock", limit=5, window_seconds=60)
