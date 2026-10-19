import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.main import app
from app.models import Click, Link
from app.services.click_limits import counter_key
from tests.unit.test_user_agent import CHROME_WINDOWS

HUMAN = {"User-Agent": CHROME_WINDOWS}
SLACK = {"User-Agent": "Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)"}


async def _create(client: AsyncClient, headers: dict[str, str], **fields: Any) -> dict[str, Any]:
    response = await client.post(
        "/api/links", json={"url": "https://example.com", **fields}, headers=headers
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def _future(**delta: float) -> str:
    return (datetime.now(UTC) + timedelta(**delta)).isoformat()


async def test_create_with_expiry_and_max_clicks(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    link = await _create(client, auth_headers, expires_at=_future(days=7), max_clicks=10)

    assert link["max_clicks"] == 10
    assert datetime.fromisoformat(link["expires_at"]) > datetime.now(UTC)
    assert link["status"] == "active"


async def test_expiry_must_be_future_and_timezone_aware(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    past = await client.post(
        "/api/links",
        json={"url": "https://e.example", "expires_at": _future(minutes=-5)},
        headers=auth_headers,
    )
    naive = await client.post(
        "/api/links",
        json={"url": "https://e.example", "expires_at": "2099-01-01T00:00:00"},
        headers=auth_headers,
    )
    zero_clicks = await client.post(
        "/api/links", json={"url": "https://e.example", "max_clicks": 0}, headers=auth_headers
    )

    assert past.status_code == 422
    assert past.json()["error"]["code"] == "invalid_expiry"
    assert naive.status_code == 422
    assert zero_clicks.status_code == 422


async def test_expired_link_reports_status_and_410(
    client: AsyncClient, auth_headers: dict[str, str], db: AsyncSession
) -> None:
    link = await _create(client, auth_headers, expires_at=_future(hours=1))
    await db.execute(
        update(Link)
        .where(Link.id == link["id"])
        .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    )
    await db.commit()

    detail = await client.get(f"/api/links/{link['id']}", headers=auth_headers)
    redirect = await client.get(f"/{link['short_code']}")

    assert detail.json()["status"] == "expired"
    assert redirect.status_code == 410


async def test_patch_can_clear_expiry(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    link = await _create(client, auth_headers, expires_at=_future(days=1), max_clicks=5)
    url = f"/api/links/{link['id']}"

    cleared = await client.patch(url, json={"expires_at": None}, headers=auth_headers)
    untouched = await client.patch(url, json={"is_active": True}, headers=auth_headers)

    assert cleared.json()["expires_at"] is None
    assert cleared.json()["max_clicks"] == 5
    assert untouched.json()["max_clicks"] == 5  # omitted field is left alone


async def test_max_clicks_allows_exactly_n_human_clicks(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    link = await _create(client, auth_headers, max_clicks=2)
    path = f"/{link['short_code']}"

    statuses = [(await client.get(path, headers=HUMAN)).status_code for _ in range(3)]

    assert statuses == [302, 302, 410]
    gone = await client.get(path, headers=HUMAN)
    assert gone.json()["error"]["code"] == "link_limit_reached"


async def test_link_previews_do_not_consume_clicks(
    client: AsyncClient, auth_headers: dict[str, str], redis: Redis
) -> None:
    link = await _create(client, auth_headers, max_clicks=1)
    path = f"/{link['short_code']}"

    preview = await client.get(path, headers=SLACK)
    human = await client.get(path, headers=HUMAN)
    second_human = await client.get(path, headers=HUMAN)
    late_preview = await client.get(path, headers=SLACK)

    assert (preview.status_code, human.status_code) == (302, 302)
    assert second_human.status_code == 410
    assert late_preview.status_code == 410  # budget used up: bots are turned away too
    assert await redis.get(counter_key(link["id"])) == "1"


async def test_counter_is_rebuilt_from_postgres(
    client: AsyncClient, auth_headers: dict[str, str], db: AsyncSession
) -> None:
    link = await _create(client, auth_headers, max_clicks=3)
    now = datetime.now(UTC)
    common = {
        "link_id": link["id"],
        "clicked_at": now,
        "browser": "Chrome",
        "os": "Windows",
        "ip_hash": "f" * 64,
    }
    db.add_all(
        [
            Click(event_id=uuid.uuid4(), device_type="desktop", **common),
            Click(event_id=uuid.uuid4(), device_type="desktop", **common),
            Click(event_id=uuid.uuid4(), device_type="bot", **common),  # not counted
        ]
    )
    await db.commit()

    path = f"/{link['short_code']}"
    assert (await client.get(path, headers=HUMAN)).status_code == 302
    assert (await client.get(path, headers=HUMAN)).status_code == 410


async def test_redis_down_enforces_limit_from_postgres(
    client: AsyncClient, auth_headers: dict[str, str], db: AsyncSession
) -> None:
    link = await _create(client, auth_headers, max_clicks=1)
    db.add(
        Click(
            event_id=uuid.uuid4(),
            link_id=link["id"],
            clicked_at=datetime.now(UTC),
            browser="Chrome",
            os="Windows",
            device_type="desktop",
            ip_hash="e" * 64,
        )
    )
    await db.commit()
    broken = Redis.from_url("redis://127.0.0.1:1/0", socket_connect_timeout=0.2)
    app.dependency_overrides[get_redis] = lambda: broken
    try:
        response = await client.get(f"/{link['short_code']}", headers=HUMAN)
    finally:
        app.dependency_overrides.pop(get_redis)
        await broken.aclose()

    assert response.status_code == 410


async def test_raising_max_clicks_reopens_link(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    link = await _create(client, auth_headers, max_clicks=1)
    path = f"/{link['short_code']}"
    await client.get(path, headers=HUMAN)
    assert (await client.get(path, headers=HUMAN)).status_code == 410

    await client.patch(f"/api/links/{link['id']}", json={"max_clicks": 2}, headers=auth_headers)

    assert (await client.get(path, headers=HUMAN)).status_code == 302
    assert (await client.get(path, headers=HUMAN)).status_code == 410


async def test_status_reports_limit_reached_and_paused(
    client: AsyncClient, auth_headers: dict[str, str], db: AsyncSession
) -> None:
    limited = await _create(client, auth_headers, max_clicks=1)
    paused = await _create(client, auth_headers)
    db.add(
        Click(
            event_id=uuid.uuid4(),
            link_id=limited["id"],
            clicked_at=datetime.now(UTC),
            browser="Chrome",
            os="Windows",
            device_type="desktop",
            ip_hash="d" * 64,
        )
    )
    await db.commit()
    await client.patch(
        f"/api/links/{paused['id']}", json={"is_active": False}, headers=auth_headers
    )

    items = {
        i["id"]: i for i in (await client.get("/api/links", headers=auth_headers)).json()["items"]
    }

    assert items[limited["id"]]["status"] == "limit_reached"
    assert items[paused["id"]]["status"] == "paused"
