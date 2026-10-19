"""Per-link analytics computed with SQL aggregation, cached briefly in Redis."""

import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import ColumnElement, Date, cast, desc, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import QueryableAttribute

from app.core.config import get_settings
from app.core.errors import ValidationError
from app.models import Click, User
from app.schemas.stats import Bucket, LinkStats, TimeseriesPoint
from app.services.links_service import get_owned_link

logger = logging.getLogger(__name__)

DEFAULT_RANGE_DAYS = 30
MAX_RANGE_DAYS = 366
TOP_N = 10
DIRECT = "Direct"
UNKNOWN = "Unknown"


@dataclass(frozen=True)
class StatsWindow:
    """An inclusive range of local calendar days, plus its exact UTC instant bounds."""

    start: date
    end: date
    timezone: str

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def starts_at(self) -> datetime:
        return datetime.combine(self.start, time.min, tzinfo=self.zone)

    @property
    def ends_before(self) -> datetime:
        return datetime.combine(self.end + timedelta(days=1), time.min, tzinfo=self.zone)


def build_window(start: date | None, end: date | None, timezone: str) -> StatsWindow:
    """Validate the requested range; defaults to the last 30 days ending today (in ``timezone``)."""
    try:
        zone = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValidationError(f"Unknown timezone: {timezone}", code="invalid_timezone") from exc

    end = end or datetime.now(zone).date()
    start = start or end - timedelta(days=DEFAULT_RANGE_DAYS - 1)
    if start > end:
        raise ValidationError("'from' must be on or before 'to'", code="invalid_range")
    if (end - start).days + 1 > MAX_RANGE_DAYS:
        raise ValidationError(
            f"Date range must be at most {MAX_RANGE_DAYS} days", code="invalid_range"
        )
    return StatsWindow(start=start, end=end, timezone=timezone)


def _cache_key(link_id: int, window: StatsWindow) -> str:
    return f"stats:{link_id}:{window.start}:{window.end}:{window.timezone}"


async def _read_cache(redis: Redis, key: str) -> LinkStats | None:
    try:
        raw = await redis.get(key)
    except (RedisError, OSError):
        logger.warning("Redis unavailable; computing stats without cache")
        return None
    return LinkStats.model_validate_json(raw) if raw else None


async def _write_cache(redis: Redis, key: str, stats: LinkStats) -> None:
    try:
        await redis.set(key, stats.model_dump_json(), ex=get_settings().stats_cache_ttl_seconds)
    except (RedisError, OSError):
        logger.warning("Redis unavailable; stats not cached")


async def _timeseries(
    db: AsyncSession, filters: list[ColumnElement[bool]], window: StatsWindow
) -> list[TimeseriesPoint]:
    """Daily clicks/uniques with every day in the window present (zero-filled in SQL)."""
    local_day = cast(func.timezone(window.timezone, Click.clicked_at), Date).label("day")
    per_day = (
        select(
            local_day,
            func.count().label("clicks"),
            func.count(func.distinct(Click.ip_hash)).label("uniques"),
        )
        .where(*filters)
        .group_by(local_day)
        .subquery()
    )
    days = select(
        cast(func.generate_series(window.start, window.end, timedelta(days=1)), Date).label("day")
    ).subquery()
    statement = (
        select(
            days.c.day,
            func.coalesce(per_day.c.clicks, 0),
            func.coalesce(per_day.c.uniques, 0),
        )
        .select_from(days.outerjoin(per_day, per_day.c.day == days.c.day))
        .order_by(days.c.day)
    )
    rows = await db.execute(statement)
    return [
        TimeseriesPoint(date=day, clicks=clicks, unique_visitors=uniques)
        for day, clicks, uniques in rows.all()
    ]


async def _top(
    db: AsyncSession,
    column: QueryableAttribute[str] | QueryableAttribute[str | None],
    filters: list[ColumnElement[bool]],
    null_label: str,
) -> list[Bucket]:
    """Top-N values of ``column`` by click count (ties broken alphabetically)."""
    label = func.coalesce(column, literal(null_label)).label("label")
    count = func.count().label("count")
    statement = (
        select(label, count)
        .where(*filters)
        .group_by(label)
        .order_by(desc(count), label)
        .limit(TOP_N)
    )
    rows = await db.execute(statement)
    return [Bucket(label=value, count=total) for value, total in rows.all()]


async def compute_stats(db: AsyncSession, link_id: int, window: StatsWindow) -> LinkStats:
    """Run the aggregation queries for one link and window (no caching, no auth)."""
    filters: list[ColumnElement[bool]] = [
        Click.link_id == link_id,
        Click.clicked_at >= window.starts_at,
        Click.clicked_at < window.ends_before,
    ]
    totals = (
        await db.execute(
            select(func.count(), func.count(func.distinct(Click.ip_hash))).where(*filters)
        )
    ).one()
    all_time = await db.scalar(select(func.count()).where(Click.link_id == link_id)) or 0

    return LinkStats(
        link_id=link_id,
        start=window.start,
        end=window.end,
        timezone=window.timezone,
        total_clicks=totals[0],
        unique_visitors=totals[1],
        all_time_clicks=all_time,
        timeseries=await _timeseries(db, filters, window),
        referrers=await _top(db, Click.referrer, filters, DIRECT),
        devices=await _top(db, Click.device_type, filters, UNKNOWN),
        browsers=await _top(db, Click.browser, filters, UNKNOWN),
        os=await _top(db, Click.os, filters, UNKNOWN),
        countries=await _top(db, Click.country, filters, UNKNOWN),
    )


async def get_link_stats(
    db: AsyncSession,
    redis: Redis,
    owner: User,
    link_id: int,
    *,
    start: date | None,
    end: date | None,
    timezone: str,
) -> LinkStats:
    """Ownership-checked stats for a link, served from a 60 s Redis cache when possible.

    The ownership check always hits Postgres (never the cache), so a deleted or foreign
    link can never be read through a stale cache entry.
    """
    link = await get_owned_link(db, owner, link_id)
    window = build_window(start, end, timezone)
    key = _cache_key(link.id, window)

    cached = await _read_cache(redis, key)
    if cached is not None:
        return cached
    stats = await compute_stats(db, link.id, window)
    await _write_cache(redis, key, stats)
    return stats
