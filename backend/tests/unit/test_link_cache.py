from datetime import UTC, datetime, timedelta

from app.services.link_cache import CachedLink, _ttl_for


def _entry(expires_at: datetime | None) -> CachedLink:
    return CachedLink(
        id=1,
        url="https://example.com",
        is_active=True,
        expires_at=expires_at.isoformat() if expires_at else None,
        max_clicks=None,
        has_password=False,
    )


def test_ttl_defaults_to_one_hour() -> None:
    assert _ttl_for(_entry(None), datetime.now(UTC)) == 3600


def test_ttl_is_capped_at_link_expiry() -> None:
    now = datetime.now(UTC)
    assert _ttl_for(_entry(now + timedelta(seconds=90)), now) == 90


def test_ttl_is_at_least_one_second() -> None:
    now = datetime.now(UTC)
    assert _ttl_for(_entry(now - timedelta(days=1)), now) == 1
