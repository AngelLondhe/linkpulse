from collections.abc import AsyncIterator

from httpx import AsyncClient
from redis.exceptions import ConnectionError as RedisConnectionError

from app.core.redis import get_redis
from app.db.session import get_db
from app.main import app


class _DeadRedis:
    async def ping(self) -> bool:
        raise RedisConnectionError("redis is down")


async def test_health_reports_ok_when_dependencies_are_up(client: AsyncClient) -> None:
    response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "redis": "ok"}


async def test_health_is_degraded_but_200_when_redis_is_down(client: AsyncClient) -> None:
    app.dependency_overrides[get_redis] = lambda: _DeadRedis()
    try:
        response = await client.get("/api/health")
    finally:
        app.dependency_overrides.pop(get_redis)

    assert response.status_code == 200
    assert response.json() == {"status": "degraded", "database": "ok", "redis": "error"}


async def test_unknown_api_route_uses_error_envelope(client: AsyncClient) -> None:
    response = await client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_cors_allows_configured_origin_only(client: AsyncClient) -> None:
    allowed = await client.options(
        "/api/health",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    denied = await client.options(
        "/api/health",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )

    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-origin" not in denied.headers


class _DeadSession:
    async def execute(self, *args: object, **kwargs: object) -> None:
        raise OSError("connection refused")


async def test_health_is_503_when_database_is_down(client: AsyncClient) -> None:
    async def _dead_db() -> AsyncIterator[_DeadSession]:
        yield _DeadSession()

    app.dependency_overrides[get_db] = _dead_db
    try:
        response = await client.get("/api/health")
    finally:
        app.dependency_overrides.pop(get_db)

    assert response.status_code == 503
    assert response.json()["status"] == "unhealthy"
