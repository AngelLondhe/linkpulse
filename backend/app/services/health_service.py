"""Dependency health checks used by the /api/health endpoint."""

import logging
from typing import Literal

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.health import HealthReport

logger = logging.getLogger(__name__)

CheckStatus = Literal["ok", "error"]


async def check_database(db: AsyncSession) -> CheckStatus:
    """Return "ok" if Postgres answers a trivial query."""
    try:
        await db.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError):
        logger.warning("Database health check failed", exc_info=True)
        return "error"
    return "ok"


async def check_redis(redis: Redis) -> CheckStatus:
    """Return "ok" if Redis answers PING."""
    try:
        await redis.ping()
    except (RedisError, OSError):
        logger.warning("Redis health check failed", exc_info=True)
        return "error"
    return "ok"


async def build_health_report(db: AsyncSession, redis: Redis) -> HealthReport:
    """Aggregate dependency checks.

    Postgres is the source of truth, so it being down makes the service "unhealthy".
    Redis being down only makes it "degraded": redirects fall back to Postgres.
    """
    database = await check_database(db)
    cache = await check_redis(redis)
    if database == "error":
        overall: Literal["ok", "degraded", "unhealthy"] = "unhealthy"
    elif cache == "error":
        overall = "degraded"
    else:
        overall = "ok"
    return HealthReport(status=overall, database=database, redis=cache)
