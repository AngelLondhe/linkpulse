import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.redis import get_redis
from app.db.session import SessionLocal
from app.main import app
from app.models import Click, Link, User
from app.services.click_queue import ClickEvent
from app.services.geo import GeoLookup
from app.utils.ip_hash import hash_ip
from app.worker import runner
from app.worker.runner import ClickWorker
from tests.unit.test_geo import FakeReader
from tests.unit.test_user_agent import CHROME_WINDOWS

SETTINGS = get_settings()
QUEUE = SETTINGS.click_queue_key


@pytest.fixture
async def worker_redis() -> AsyncIterator[Redis]:
    # The worker blocks on BLMOVE, so it needs a longer socket timeout than the API client.
    client = Redis.from_url(SETTINGS.redis_url, decode_responses=True, socket_timeout=5)
    yield client
    await client.aclose()


def make_worker(redis: Redis, geo: GeoLookup | None = None) -> ClickWorker:
    return ClickWorker(
        redis=redis,
        session_factory=SessionLocal,
        geo=geo or GeoLookup(None),
        settings=SETTINGS,
    )


@pytest.fixture
def worker(worker_redis: Redis) -> ClickWorker:
    return make_worker(worker_redis)


async def _link(db: AsyncSession, user: User, code: str = "abc1234") -> Link:
    link = Link(user_id=user.id, short_code=code, original_url="https://example.com")
    db.add(link)
    await db.commit()
    return link


def _event(link_id: int, *, ip: str = "203.0.113.9", event_id: str | None = None) -> str:
    return ClickEvent(
        event_id=event_id or str(uuid.uuid4()),
        link_id=link_id,
        clicked_at=datetime.now(UTC).isoformat(),
        ip=ip,
        user_agent=CHROME_WINDOWS,
        referrer="https://www.news.example/story?id=7",
    ).to_json()


async def _count(db: AsyncSession) -> int:
    return await db.scalar(select(func.count(Click.id))) or 0


async def test_redirect_to_stored_click_end_to_end(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db: AsyncSession,
    worker_redis: Redis,
) -> None:
    created = (
        await client.post("/api/links", json={"url": "https://example.com"}, headers=auth_headers)
    ).json()
    await client.get(
        f"/{created['short_code']}",
        headers={"User-Agent": CHROME_WINDOWS, "Referer": "https://www.news.example/a"},
    )
    geo_worker = make_worker(worker_redis, GeoLookup(FakeReader()))

    assert await geo_worker.run_once() == 1

    click = await db.scalar(select(Click))
    assert click is not None
    assert click.link_id == created["id"]
    assert (click.browser, click.os, click.device_type) == ("Chrome", "Windows", "desktop")
    assert click.referrer == "news.example"
    assert click.ip_hash == hash_ip("127.0.0.1", SETTINGS.ip_hash_salt.get_secret_value())
    # Loopback is never geolocated.
    assert (click.country, click.city) == (None, None)
    # Nothing left in Redis, and the raw IP is stored nowhere in the row.
    assert await worker_redis.llen(QUEUE) == 0
    assert await worker_redis.llen(geo_worker.processing_key) == 0
    row_values = [str(getattr(click, col.key)) for col in Click.__table__.columns]
    assert "127.0.0.1" not in row_values

    detail = await client.get(f"/api/links/{created['id']}", headers=auth_headers)
    assert detail.json()["total_clicks"] == 1


async def test_geo_enrichment_for_public_ip(
    db: AsyncSession, user: User, worker_redis: Redis
) -> None:
    link = await _link(db, user)
    await worker_redis.lpush(QUEUE, _event(link.id, ip="8.8.8.8"))

    await make_worker(worker_redis, GeoLookup(FakeReader())).run_once()

    click = await db.scalar(select(Click))
    assert click is not None
    assert (click.country, click.city) == ("DE", "Berlin")


async def test_batches_are_capped_at_batch_size(
    db: AsyncSession, user: User, worker: ClickWorker, worker_redis: Redis
) -> None:
    link = await _link(db, user)
    await worker_redis.lpush(QUEUE, *[_event(link.id) for _ in range(250)])

    assert await worker.run_once() == SETTINGS.worker_batch_size
    assert await worker_redis.llen(QUEUE) == 250 - SETTINGS.worker_batch_size


async def test_crash_after_claim_loses_nothing(
    db: AsyncSession, user: User, worker_redis: Redis
) -> None:
    link = await _link(db, user)
    await worker_redis.lpush(QUEUE, *[_event(link.id) for _ in range(5)])

    crashed = make_worker(worker_redis)
    claimed = await crashed.claim_batch()  # ...and then the process dies
    assert len(claimed) == 5
    assert await worker_redis.llen(QUEUE) == 0
    assert await worker_redis.llen(crashed.processing_key) == 5

    restarted = make_worker(worker_redis)  # same WORKER_ID -> same processing list
    assert await restarted.run_once() == 5
    assert await _count(db) == 5
    assert await worker_redis.llen(restarted.processing_key) == 0


async def test_database_failure_keeps_batch_for_retry(
    db: AsyncSession,
    user: User,
    worker: ClickWorker,
    worker_redis: Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    link = await _link(db, user)
    await worker_redis.lpush(QUEUE, *[_event(link.id) for _ in range(3)])

    async def failing_insert(*args: object, **kwargs: object) -> int:
        raise OperationalError("INSERT", {}, Exception("database is down"))

    monkeypatch.setattr(runner, "insert_clicks", failing_insert)
    with pytest.raises(OperationalError):
        await worker.run_once()
    assert await worker_redis.llen(worker.processing_key) == 3

    monkeypatch.undo()
    assert await worker.run_once() == 3
    assert await _count(db) == 3


async def test_reprocessing_the_same_event_is_idempotent(
    db: AsyncSession, user: User, worker: ClickWorker, worker_redis: Redis
) -> None:
    link = await _link(db, user)
    duplicate = _event(link.id, event_id=str(uuid.uuid4()))
    await worker_redis.lpush(QUEUE, duplicate, duplicate)

    assert await worker.run_once() == 1
    await worker_redis.lpush(QUEUE, duplicate)
    assert await worker.run_once() == 0
    assert await _count(db) == 1


async def test_events_for_deleted_links_do_not_poison_the_batch(
    db: AsyncSession, user: User, worker: ClickWorker, worker_redis: Redis
) -> None:
    link = await _link(db, user)
    await worker_redis.lpush(QUEUE, _event(link.id), _event(999_999), _event(link.id))

    assert await worker.run_once() == 2
    assert await worker_redis.llen(worker.processing_key) == 0


async def test_malformed_events_go_to_dead_letter(
    db: AsyncSession, user: User, worker: ClickWorker, worker_redis: Redis
) -> None:
    link = await _link(db, user)
    bad = ["not json", json.dumps({"link_id": link.id}), json.dumps({"unexpected": 1})]
    await worker_redis.lpush(QUEUE, _event(link.id), *bad)

    assert await worker.run_once() == 1
    assert sorted(await worker_redis.lrange(worker.dead_letter_key, 0, -1)) == sorted(bad)


async def test_run_once_on_empty_queue_returns_zero(worker: ClickWorker) -> None:
    assert await worker.run_once() == 0


async def test_run_forever_processes_and_stops_gracefully(
    db: AsyncSession, user: User, worker: ClickWorker, worker_redis: Redis
) -> None:
    link = await _link(db, user)
    task = asyncio.create_task(worker.run_forever())
    await worker_redis.lpush(QUEUE, _event(link.id))

    for _ in range(50):
        if await _count(db) == 1:
            break
        await asyncio.sleep(0.05)
    worker.stop()
    await asyncio.wait_for(task, timeout=5)

    assert await _count(db) == 1


async def test_run_forever_survives_infrastructure_errors(
    worker: ClickWorker, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0

    async def flaky_run_once() -> int:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("redis connection reset")
        worker.stop()
        return 0

    monkeypatch.setattr(worker, "run_once", flaky_run_once)
    await asyncio.wait_for(worker.run_forever(), timeout=5)

    assert calls == 2


async def test_redis_down_at_redirect_persists_click_directly(
    client: AsyncClient, auth_headers: dict[str, str], db: AsyncSession
) -> None:
    created = (
        await client.post("/api/links", json={"url": "https://example.com"}, headers=auth_headers)
    ).json()
    broken = Redis.from_url("redis://127.0.0.1:1/0", socket_connect_timeout=0.2)
    app.dependency_overrides[get_redis] = lambda: broken
    try:
        response = await client.get(
            f"/{created['short_code']}", headers={"User-Agent": CHROME_WINDOWS}
        )
    finally:
        app.dependency_overrides.pop(get_redis)
        await broken.aclose()

    assert response.status_code == 302
    click = await db.scalar(select(Click))  # written by the background task
    assert click is not None
    assert click.browser == "Chrome"
