import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.main import app
from app.models import Click, Link, User
from app.services import stats_service
from app.services.stats_service import build_window
from tests.conftest import bearer


async def _link(db: AsyncSession, user: User, code: str = "stats01") -> Link:
    link = Link(user_id=user.id, short_code=code, original_url="https://example.com")
    db.add(link)
    await db.commit()
    return link


def _click(link: Link, at: datetime, **overrides: Any) -> Click:
    values: dict[str, Any] = {
        "event_id": uuid.uuid4(),
        "link_id": link.id,
        "clicked_at": at,
        "referrer": "twitter.com",
        "browser": "Chrome",
        "os": "Windows",
        "device_type": "desktop",
        "country": "US",
        "city": "Austin",
        "ip_hash": "a" * 64,
    }
    values.update(overrides)
    return Click(**values)


async def _add(db: AsyncSession, clicks: Sequence[Click]) -> None:
    db.add_all(clicks)
    await db.commit()


def _at(day: int, hour: int = 12) -> datetime:
    return datetime(2026, 1, day, hour, tzinfo=UTC)


async def _stats(
    client: AsyncClient, user: User, link: Link, query: str = "from=2026-01-01&to=2026-01-07"
) -> dict[str, Any]:
    response = await client.get(f"/api/links/{link.id}/stats?{query}", headers=bearer(user))
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


async def test_totals_uniques_and_zero_filled_timeseries(
    client: AsyncClient, db: AsyncSession, user: User
) -> None:
    link = await _link(db, user)
    await _add(
        db,
        [
            _click(link, _at(2), ip_hash="1" * 64),
            _click(link, _at(2, 15), ip_hash="1" * 64),  # same visitor again
            _click(link, _at(2, 18), ip_hash="2" * 64),
            _click(link, _at(5), ip_hash="3" * 64),
            _click(link, _at(9), ip_hash="4" * 64),  # outside range
            _click(link, datetime(2025, 12, 31, 23, 59, tzinfo=UTC)),  # outside range
        ],
    )

    stats = await _stats(client, user, link)

    assert stats["total_clicks"] == 4
    assert stats["unique_visitors"] == 3
    assert stats["all_time_clicks"] == 6
    assert stats["timeseries"] == [
        {"date": "2026-01-01", "clicks": 0, "unique_visitors": 0},
        {"date": "2026-01-02", "clicks": 3, "unique_visitors": 2},
        {"date": "2026-01-03", "clicks": 0, "unique_visitors": 0},
        {"date": "2026-01-04", "clicks": 0, "unique_visitors": 0},
        {"date": "2026-01-05", "clicks": 1, "unique_visitors": 1},
        {"date": "2026-01-06", "clicks": 0, "unique_visitors": 0},
        {"date": "2026-01-07", "clicks": 0, "unique_visitors": 0},
    ]


async def test_empty_link_returns_full_zero_series(
    client: AsyncClient, db: AsyncSession, user: User
) -> None:
    link = await _link(db, user)

    stats = await _stats(client, user, link, "from=2026-03-01&to=2026-03-31")

    assert stats["total_clicks"] == 0
    assert len(stats["timeseries"]) == 31
    assert all(point["clicks"] == 0 for point in stats["timeseries"])
    assert stats["referrers"] == stats["countries"] == []


async def test_breakdowns_are_sorted_labelled_and_limited(
    client: AsyncClient, db: AsyncSession, user: User
) -> None:
    link = await _link(db, user)
    clicks = [
        _click(link, _at(3), referrer=None, country=None),
        _click(link, _at(3), referrer=None, country=None),
        _click(link, _at(3), referrer=None, country="DE", device_type="mobile", os="iOS"),
        _click(link, _at(3), referrer="news.example", browser="Firefox"),
    ]
    # 12 more distinct referrers with one click each, to exercise the top-10 cut-off.
    clicks += [_click(link, _at(4), referrer=f"site{i:02d}.example") for i in range(12)]
    await _add(db, clicks)

    stats = await _stats(client, user, link)

    referrers = stats["referrers"]
    assert len(referrers) == 10
    assert referrers[0] == {"label": "Direct", "count": 3}  # NULL referrer = direct traffic
    assert referrers[1:3] == [
        {"label": "news.example", "count": 1},
        {"label": "site00.example", "count": 1},  # ties ordered alphabetically
    ]
    assert stats["countries"] == [
        {"label": "US", "count": 13},
        {"label": "Unknown", "count": 2},
        {"label": "DE", "count": 1},
    ]
    assert stats["devices"] == [
        {"label": "desktop", "count": 15},
        {"label": "mobile", "count": 1},
    ]
    assert {"label": "Firefox", "count": 1} in stats["browsers"]
    assert {"label": "iOS", "count": 1} in stats["os"]


async def test_timezone_shifts_day_buckets(
    client: AsyncClient, db: AsyncSession, user: User
) -> None:
    link = await _link(db, user)
    # 20:00 UTC on Jan 2 is 01:30 on Jan 3 in India (UTC+5:30).
    await _add(db, [_click(link, _at(2, 20))])

    utc = await _stats(client, user, link, "from=2026-01-02&to=2026-01-03")
    india = await _stats(client, user, link, "from=2026-01-02&to=2026-01-03&tz=Asia/Kolkata")

    assert [p["clicks"] for p in utc["timeseries"]] == [1, 0]
    assert [p["clicks"] for p in india["timeseries"]] == [0, 1]
    assert india["timezone"] == "Asia/Kolkata"


async def test_default_window_is_last_30_days(
    client: AsyncClient, db: AsyncSession, user: User
) -> None:
    link = await _link(db, user)
    now = datetime.now(UTC)
    await _add(db, [_click(link, now - timedelta(days=2)), _click(link, now - timedelta(days=45))])

    stats = await _stats(client, user, link, "")

    assert len(stats["timeseries"]) == 30
    assert stats["end"] == now.date().isoformat()
    assert stats["total_clicks"] == 1
    assert stats["all_time_clicks"] == 2


@pytest.mark.parametrize(
    ("query", "code"),
    [
        ("from=2026-02-01&to=2026-01-01", "invalid_range"),
        ("from=2024-01-01&to=2026-01-01", "invalid_range"),
        ("tz=Mars/Olympus_Mons", "invalid_timezone"),
        ("from=not-a-date", "validation_error"),
    ],
)
async def test_invalid_parameters_are_422(
    client: AsyncClient, db: AsyncSession, user: User, query: str, code: str
) -> None:
    link = await _link(db, user)

    response = await client.get(f"/api/links/{link.id}/stats?{query}", headers=bearer(user))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == code


async def test_stats_enforce_ownership(
    client: AsyncClient, db: AsyncSession, user: User, other_user: User
) -> None:
    link = await _link(db, user)

    foreign = await client.get(f"/api/links/{link.id}/stats", headers=bearer(other_user))
    missing = await client.get("/api/links/424242/stats", headers=bearer(user))
    anonymous = await client.get(f"/api/links/{link.id}/stats")

    assert foreign.status_code == 403
    assert missing.status_code == 404
    assert anonymous.status_code == 401


async def test_stats_are_cached_for_60_seconds(
    client: AsyncClient, db: AsyncSession, user: User, redis: Redis
) -> None:
    link = await _link(db, user)
    await _add(db, [_click(link, _at(2))])

    first = await _stats(client, user, link)
    await _add(db, [_click(link, _at(3))])  # arrives while the cache entry is warm
    second = await _stats(client, user, link)

    key = f"stats:{link.id}:2026-01-01:2026-01-07:UTC:humans"
    assert 0 < await redis.ttl(key) <= 60
    assert first == second
    assert second["total_clicks"] == 1

    await redis.delete(key)
    assert (await _stats(client, user, link))["total_clicks"] == 2


async def test_stats_work_without_redis(client: AsyncClient, db: AsyncSession, user: User) -> None:
    link = await _link(db, user)
    await _add(db, [_click(link, _at(2))])
    broken = Redis.from_url("redis://127.0.0.1:1/0", socket_connect_timeout=0.2)
    app.dependency_overrides[get_redis] = lambda: broken
    try:
        stats = await _stats(client, user, link)
    finally:
        app.dependency_overrides.pop(get_redis)
        await broken.aclose()

    assert stats["total_clicks"] == 1


def test_window_bounds_cover_whole_local_days() -> None:
    window = build_window(date(2026, 1, 1), date(2026, 1, 1), "Asia/Kolkata")

    assert window.starts_at.isoformat() == "2026-01-01T00:00:00+05:30"
    assert window.ends_before.isoformat() == "2026-01-02T00:00:00+05:30"


def test_max_range_is_inclusive() -> None:
    end = date(2026, 12, 31)
    start = end - timedelta(days=stats_service.MAX_RANGE_DAYS - 1)

    assert build_window(start, end, "UTC").start == start


async def test_bots_are_excluded_by_default(
    client: AsyncClient, db: AsyncSession, user: User
) -> None:
    link = await _link(db, user)
    await _add(
        db,
        [
            _click(link, _at(2), ip_hash="1" * 64),
            _click(link, _at(2), device_type="bot", browser="Googlebot", ip_hash="9" * 64),
            _click(link, _at(3), device_type="bot", browser="Slackbot", ip_hash="8" * 64),
        ],
    )

    humans = await _stats(client, user, link)
    everyone = await _stats(client, user, link, "from=2026-01-01&to=2026-01-07&include_bots=true")

    assert (humans["total_clicks"], humans["unique_visitors"], humans["bot_clicks"]) == (1, 1, 2)
    assert humans["all_time_clicks"] == 1
    assert [b["label"] for b in humans["browsers"]] == ["Chrome"]
    assert humans["include_bots"] is False
    assert (everyone["total_clicks"], everyone["unique_visitors"], everyone["bot_clicks"]) == (
        3,
        3,
        2,
    )
    assert {"label": "bot", "count": 2} in everyone["devices"]
