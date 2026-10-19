from typing import Any

import pytest
from pydantic import ValidationError

from app.core.config import Settings

BASE: dict[str, Any] = {
    "database_url": "postgresql+asyncpg://u:p@localhost/db",
    "jwt_secret_key": "x" * 32,
    "ip_hash_salt": "y" * 16,
}


def test_comma_separated_lists_are_split() -> None:
    settings = Settings(**BASE, cors_origins="http://a.test, http://b.test", trusted_proxies="")

    assert settings.cors_origins == ["http://a.test", "http://b.test"]
    assert settings.trusted_proxies == []


def test_wildcard_cors_is_rejected() -> None:
    with pytest.raises(ValidationError, match="Wildcard CORS"):
        Settings(**BASE, cors_origins="*")


def test_short_jwt_secret_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(**{**BASE, "jwt_secret_key": "too-short"})
