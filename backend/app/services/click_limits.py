"""Enforcement of per-link ``max_clicks`` on the redirect path.

The clicks table lags behind reality (the worker writes asynchronously), so it cannot be the
gate. Instead a Redis counter per link is checked-and-incremented atomically in Lua. If the
counter is missing (first use, Redis restart), it is rebuilt from the human clicks already in
Postgres. If Redis is down, the Postgres count is used directly (approximate, fails closed
only once the stored count reaches the limit).
"""

import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Click

logger = logging.getLogger(__name__)

KEY_MISSING = -2
LIMIT_REACHED = -1

# KEYS[1] counter; ARGV[1] max; ARGV[2] "1" to consume a click; ARGV[3] optional seed value.
_RESERVE = """
local used = redis.call('GET', KEYS[1])
if not used then
  if ARGV[3] == '' then return -2 end
  redis.call('SET', KEYS[1], ARGV[3], 'NX')
  used = redis.call('GET', KEYS[1])
end
used = tonumber(used)
if used >= tonumber(ARGV[1]) then return -1 end
if ARGV[2] == '1' then used = redis.call('INCR', KEYS[1]) end
return used
"""


def counter_key(link_id: int) -> str:
    return f"clicks:used:{link_id}"


async def human_clicks_in_db(db: AsyncSession, link_id: int) -> int:
    statement = select(func.count(Click.id)).where(
        Click.link_id == link_id, Click.device_type != "bot"
    )
    return await db.scalar(statement) or 0


async def try_admit(
    db: AsyncSession, redis: Redis, link_id: int, max_clicks: int, *, consume: bool
) -> bool:
    """Return True if this visit is within the link's click budget.

    ``consume`` reserves one click (human visitors); bots only check the budget.
    """
    try:
        script = redis.register_script(_RESERVE)
        args = [max_clicks, "1" if consume else "0", ""]
        result = int(await script(keys=[counter_key(link_id)], args=args))
        if result == KEY_MISSING:
            args[2] = await human_clicks_in_db(db, link_id)
            result = int(await script(keys=[counter_key(link_id)], args=args))
    except (RedisError, OSError):
        logger.warning("Redis unavailable; enforcing max_clicks from Postgres for %s", link_id)
        return await human_clicks_in_db(db, link_id) < max_clicks
    return result != LIMIT_REACHED


async def forget(redis: Redis, link_id: int) -> None:
    try:
        await redis.delete(counter_key(link_id))
    except (RedisError, OSError):
        logger.warning("Redis unavailable; stale click counter for deleted link %s", link_id)
