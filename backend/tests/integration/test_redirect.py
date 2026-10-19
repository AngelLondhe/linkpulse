import json
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.redis import get_redis
from app.main import app
from app.models import Link
from app.services import links_service
from app.services.link_cache import MISSING_MARKER, cache_key

QUEUE = get_settings().click_queue_key


async def _create(client: AsyncClient, headers: dict[str, str], url: str) -> dict[str, object]:
    response = await client.post("/api/links", json={"url": url}, headers=headers)
    assert response.status_code == 201
    body: dict[str, object] = response.json()
    return body


@pytest.fixture
async def dead_redis() -> AsyncIterator[Callable[[], None]]:
    """Point the app at a Redis that refuses connections."""
    broken = Redis.from_url("redis://127.0.0.1:1/0", socket_connect_timeout=0.2, socket_timeout=0.2)

    def activate() -> None:
        app.dependency_overrides[get_redis] = lambda: broken

    yield activate
    app.dependency_overrides.pop(get_redis, None)
    await broken.aclose()


async def test_redirect_returns_302_with_no_store(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    link = await _create(client, auth_headers, "https://example.com/landing?a=1")

    response = await client.get(f"/{link['short_code']}")

    assert response.status_code == 302
    assert response.headers["location"] == "https://example.com/landing?a=1"
    assert "no-store" in response.headers["cache-control"]


async def test_unknown_and_malformed_codes_are_404(client: AsyncClient) -> None:
    for path in ("/Zz9Zz9Z", "/ab", "/has.dot", "/" + "x" * 31):
        response = await client.get(path)
        assert response.status_code == 404, path
        assert response.json()["error"]["code"] == "not_found"


async def test_first_hit_populates_cache_with_ttl(
    client: AsyncClient, auth_headers: dict[str, str], redis: Redis
) -> None:
    link = await _create(client, auth_headers, "https://example.com")
    key = cache_key(str(link["short_code"]))
    assert await redis.get(key) is None

    await client.get(f"/{link['short_code']}")

    raw = await redis.get(key)
    assert raw is not None
    cached = json.loads(raw)
    assert cached["url"] == "https://example.com"
    assert cached["id"] == link["id"]
    assert 3590 < await redis.ttl(key) <= 3600


async def test_second_hit_is_served_from_cache_without_db(
    client: AsyncClient, auth_headers: dict[str, str], db: AsyncSession
) -> None:
    link = await _create(client, auth_headers, "https://example.com/cached")
    await client.get(f"/{link['short_code']}")  # warm the cache

    # Remove the row behind the service's back: only the cache can now answer.
    await db.execute(delete(Link).where(Link.id == link["id"]))
    await db.commit()

    response = await client.get(f"/{link['short_code']}")
    assert response.status_code == 302
    assert response.headers["location"] == "https://example.com/cached"


async def test_unknown_code_is_negative_cached_and_cleared_on_create(
    client: AsyncClient,
    auth_headers: dict[str, str],
    redis: Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert (await client.get("/Unknown")).status_code == 404
    assert await redis.get(cache_key("Unknown")) == MISSING_MARKER
    assert 0 < await redis.ttl(cache_key("Unknown")) <= 60

    # A link created with that code must be reachable immediately, not after the negative TTL.
    monkeypatch.setattr(links_service, "generate_short_code", lambda: "Unknown")
    await _create(client, auth_headers, "https://now-exists.example")

    response = await client.get("/Unknown")
    assert response.status_code == 302
    assert response.headers["location"] == "https://now-exists.example"


async def test_redis_down_falls_back_to_postgres(
    client: AsyncClient, auth_headers: dict[str, str], dead_redis: Callable[[], None]
) -> None:
    link = await _create(client, auth_headers, "https://example.com/fallback")
    dead_redis()

    response = await client.get(f"/{link['short_code']}")

    assert response.status_code == 302
    assert response.headers["location"] == "https://example.com/fallback"


async def test_edit_invalidates_cache(
    client: AsyncClient, auth_headers: dict[str, str], redis: Redis
) -> None:
    link = await _create(client, auth_headers, "https://old.example")
    await client.get(f"/{link['short_code']}")
    assert await redis.exists(cache_key(str(link["short_code"])))

    await client.patch(
        f"/api/links/{link['id']}", json={"url": "https://new.example"}, headers=auth_headers
    )
    response = await client.get(f"/{link['short_code']}")

    assert response.headers["location"] == "https://new.example"


async def test_deactivate_and_delete_invalidate_cache(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    first = await _create(client, auth_headers, "https://a.example")
    second = await _create(client, auth_headers, "https://b.example")
    for link in (first, second):
        assert (await client.get(f"/{link['short_code']}")).status_code == 302

    await client.patch(f"/api/links/{first['id']}", json={"is_active": False}, headers=auth_headers)
    await client.delete(f"/api/links/{second['id']}", headers=auth_headers)

    assert (await client.get(f"/{first['short_code']}")).status_code == 404
    assert (await client.get(f"/{second['short_code']}")).status_code == 404


async def test_reactivated_link_redirects_again(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    link = await _create(client, auth_headers, "https://a.example")
    url = f"/api/links/{link['id']}"
    await client.patch(url, json={"is_active": False}, headers=auth_headers)
    assert (await client.get(f"/{link['short_code']}")).status_code == 404

    await client.patch(url, json={"is_active": True}, headers=auth_headers)
    assert (await client.get(f"/{link['short_code']}")).status_code == 302


async def test_expired_link_is_410_and_evicted(
    client: AsyncClient, auth_headers: dict[str, str], db: AsyncSession, redis: Redis
) -> None:
    link = await _create(client, auth_headers, "https://example.com")
    await db.execute(
        update(Link)
        .where(Link.id == link["id"])
        .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
    )
    await db.commit()

    response = await client.get(f"/{link['short_code']}")

    assert response.status_code == 410
    assert response.json()["error"]["code"] == "link_expired"
    assert not await redis.exists(cache_key(str(link["short_code"])))
    assert await redis.llen(QUEUE) == 0  # expired hits are not counted as clicks


async def test_redirect_enqueues_raw_click_event(
    client: AsyncClient, auth_headers: dict[str, str], redis: Redis
) -> None:
    link = await _create(client, auth_headers, "https://example.com")

    await client.get(
        f"/{link['short_code']}",
        headers={"User-Agent": "Mozilla/5.0 Test", "Referer": "https://news.example/post"},
    )

    assert await redis.llen(QUEUE) == 1
    raw = await redis.lindex(QUEUE, 0)
    assert raw is not None
    event = json.loads(raw)
    assert event["link_id"] == link["id"]
    assert event["user_agent"] == "Mozilla/5.0 Test"
    assert event["referrer"] == "https://news.example/post"
    assert event["ip"] == "127.0.0.1"
    assert datetime.fromisoformat(event["clicked_at"]).tzinfo is not None


async def test_forwarded_for_is_ignored_unless_peer_is_trusted(
    client: AsyncClient, auth_headers: dict[str, str], redis: Redis
) -> None:
    link = await _create(client, auth_headers, "https://example.com")
    settings = get_settings()

    await client.get(f"/{link['short_code']}", headers={"X-Forwarded-For": "203.0.113.9"})
    settings.trusted_proxies = ["127.0.0.1"]
    try:
        await client.get(f"/{link['short_code']}", headers={"X-Forwarded-For": "203.0.113.9"})
    finally:
        settings.trusted_proxies = []

    newest, oldest = [json.loads(e) for e in await redis.lrange(QUEUE, 0, -1)]
    assert oldest["ip"] == "127.0.0.1"
    assert newest["ip"] == "203.0.113.9"


async def test_redirect_still_works_when_click_cannot_be_queued(
    client: AsyncClient, auth_headers: dict[str, str], dead_redis: Callable[[], None]
) -> None:
    link = await _create(client, auth_headers, "https://example.com")
    dead_redis()

    response = await client.get(f"/{link['short_code']}")

    assert response.status_code == 302


async def test_cache_can_be_disabled(
    client: AsyncClient, auth_headers: dict[str, str], redis: Redis
) -> None:
    link = await _create(client, auth_headers, "https://example.com/uncached")
    settings = get_settings()
    settings.link_cache_enabled = False
    try:
        response = await client.get(f"/{link['short_code']}")
        await client.get("/NoSuchCode")
    finally:
        settings.link_cache_enabled = True

    assert response.status_code == 302
    assert await redis.exists(cache_key(str(link["short_code"])), cache_key("NoSuchCode")) == 0
