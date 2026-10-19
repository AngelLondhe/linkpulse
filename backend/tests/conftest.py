"""Shared fixtures. Tests run against a real Postgres + Redis (never the dev databases).

Override with TEST_DATABASE_URL / TEST_REDIS_URL (CI sets these to its service containers).
"""

import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

# Point the app at the test infrastructure *before* any app module reads settings.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://shortener:shortener@localhost:5432/shortener_test",
)
os.environ["REDIS_URL"] = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15")
os.environ["ENVIRONMENT"] = "test"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-that-is-long-enough-0123456789")
os.environ.setdefault("IP_HASH_SALT", "test-ip-hash-salt-0123456789")
os.environ["PUBLIC_BASE_URL"] = "http://testserver"
os.environ["CORS_ORIGINS"] = "http://localhost:5173"

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import redis_client
from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.main import app
from app.models import User
from app.services.auth_service import register_user

BACKEND_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session", autouse=True)
def _migrated_database() -> Iterator[None]:
    """Rebuild the test schema from migrations once per run (also exercises downgrade)."""
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    cfg.attributes["configure_logger"] = False
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
async def _clean_state() -> AsyncIterator[None]:
    """Give every test empty tables and an empty Redis DB, so tests are order-independent."""
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    await redis_client.flushdb()
    yield


@pytest.fixture
async def db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


@pytest.fixture
def redis() -> Redis:
    return redis_client


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http:
        yield http


DEFAULT_PASSWORD = "correct-horse-battery"


@pytest.fixture
async def user(db: AsyncSession) -> User:
    return await register_user(db, "alice@example.com", DEFAULT_PASSWORD)


@pytest.fixture
async def other_user(db: AsyncSession) -> User:
    return await register_user(db, "mallory@example.com", DEFAULT_PASSWORD)


def bearer(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id).token}"}


@pytest.fixture
def auth_headers(user: User) -> dict[str, str]:
    return bearer(user)
