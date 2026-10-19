from collections.abc import Iterator

import pytest
from httpx import AsyncClient
from redis.asyncio import Redis

from app.core.config import get_settings
from app.models import User
from app.services import rate_limiter
from app.services.rate_limiter import RateLimiter, RateLimitRule
from tests.conftest import DEFAULT_PASSWORD, bearer

RULE = RateLimitRule("test", limit=10, window_seconds=60)
WINDOW_MS = 60_000
T0 = 1_700_000_040_000 - (1_700_000_040_000 % WINDOW_MS)  # start of a window


async def _hits(limiter: RateLimiter, n: int, now_ms: int, identity: str = "1.2.3.4") -> list[bool]:
    return [(await limiter.hit(RULE, identity, now_ms=now_ms)).allowed for _ in range(n)]


async def test_allows_exactly_the_limit_then_blocks(redis: Redis) -> None:
    limiter = RateLimiter(redis)

    results = await _hits(limiter, 11, T0 + 1_000)

    assert results == [True] * 10 + [False]
    blocked = await limiter.hit(RULE, "1.2.3.4", now_ms=T0 + 1_000)
    assert blocked.remaining == 0
    assert blocked.retry_after == 59  # nothing frees up until the next window


async def test_previous_window_still_counts_with_decaying_weight(redis: Redis) -> None:
    limiter = RateLimiter(redis)
    await _hits(limiter, 10, T0 + 59_000)  # full window just before the boundary

    # Half-way through the next window the previous 10 weigh 5, so 5 more fit.
    results = await _hits(limiter, 6, T0 + WINDOW_MS + 30_000)

    assert results == [True] * 5 + [False]
    blocked = await limiter.hit(RULE, "1.2.3.4", now_ms=T0 + WINDOW_MS + 30_000)
    # 10 * (30s - wait)/60s + 5 + 1 <= 10  ->  wait >= 6s
    assert blocked.retry_after == 6


async def test_no_double_burst_at_window_boundary(redis: Redis) -> None:
    limiter = RateLimiter(redis)
    await _hits(limiter, 10, T0 + 59_900)

    # A fixed-window limiter would allow 10 more right after the boundary.
    assert await _hits(limiter, 1, T0 + WINDOW_MS + 100) == [False]


async def test_identities_and_rules_are_isolated(redis: Redis) -> None:
    limiter = RateLimiter(redis)
    await _hits(limiter, 10, T0 + 1_000, identity="a")

    other_ip = await limiter.hit(RULE, "b", now_ms=T0 + 1_000)
    other_rule = await limiter.hit(RateLimitRule("other", 10, 60), "a", now_ms=T0 + 1_000)

    assert other_ip.allowed and other_rule.allowed


async def test_fails_open_when_redis_is_down() -> None:
    dead = Redis.from_url("redis://127.0.0.1:1/0", socket_connect_timeout=0.2)
    try:
        result = await RateLimiter(dead).hit(RULE, "x")
    finally:
        await dead.aclose()

    assert result.allowed


async def test_login_is_rate_limited_per_ip(client: AsyncClient, user: User) -> None:
    ok = await client.post(
        "/api/auth/login", json={"email": user.email, "password": DEFAULT_PASSWORD}
    )
    body = {"email": user.email, "password": "wrong-password"}
    responses = [await client.post("/api/auth/login", json=body) for _ in range(10)]

    assert ok.headers["ratelimit-limit"] == "10"
    assert ok.headers["ratelimit-remaining"] == "9"
    assert [r.status_code for r in responses] == [401] * 9 + [429]
    limited = responses[-1]
    assert limited.json()["error"]["code"] == "rate_limited"
    assert int(limited.headers["retry-after"]) > 0


async def test_correct_password_is_also_blocked_once_limited(
    client: AsyncClient, user: User
) -> None:
    for _ in range(10):
        await client.post("/api/auth/login", json={"email": user.email, "password": "bad-guess"})

    response = await client.post(
        "/api/auth/login", json={"email": user.email, "password": DEFAULT_PASSWORD}
    )

    assert response.status_code == 429


async def test_password_unlock_is_brute_force_protected(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    link = (
        await client.post(
            "/api/links",
            json={"url": "https://e.example", "password": "right-one"},
            headers=auth_headers,
        )
    ).json()
    form = {"Content-Type": "application/x-www-form-urlencoded"}
    path = f"/{link['short_code']}"

    guesses = [(await client.post(path, content="password=guess", headers=form)) for _ in range(5)]
    final = await client.post(path, content="password=right-one", headers=form)

    assert [g.status_code for g in guesses] == [401] * 5
    assert final.status_code == 429


async def test_link_creation_is_limited_per_user(
    client: AsyncClient, user: User, other_user: User
) -> None:
    limit = rate_limiter.CREATE_LINK.limit
    statuses = [
        (
            await client.post("/api/links", json={"url": "https://e.example"}, headers=bearer(user))
        ).status_code
        for _ in range(limit + 1)
    ]
    other = await client.post(
        "/api/links", json={"url": "https://e.example"}, headers=bearer(other_user)
    )

    assert statuses == [201] * limit + [429]
    assert other.status_code == 201  # same IP, different user: separate budget


@pytest.fixture
def limits_disabled() -> Iterator[None]:
    settings = get_settings()
    settings.rate_limit_enabled = False
    yield
    settings.rate_limit_enabled = True


async def test_rate_limiting_can_be_disabled(
    client: AsyncClient, user: User, limits_disabled: None
) -> None:
    body = {"email": "alice@example.com", "password": "wrong-password"}
    responses = [await client.post("/api/auth/login", json=body) for _ in range(12)]

    assert {r.status_code for r in responses} == {401}
