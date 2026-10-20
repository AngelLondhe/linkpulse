import zoneinfo
from collections.abc import Iterator

import pytest

from app.services.stats_service import build_window


@pytest.fixture
def without_system_tzdata() -> Iterator[None]:
    """Simulate a slim container image: only the bundled `tzdata` package is available."""
    original = zoneinfo.TZPATH
    zoneinfo.reset_tzpath(to=[])
    zoneinfo.ZoneInfo.clear_cache()
    yield
    zoneinfo.reset_tzpath(to=original)
    zoneinfo.ZoneInfo.clear_cache()


@pytest.mark.parametrize(
    "zone",
    [
        "UTC",
        "Asia/Kolkata",
        "Asia/Calcutta",  # legacy alias Chrome still reports on many Indian systems
        "America/New_York",
        "US/Pacific",  # legacy alias
    ],
)
def test_zones_resolve_without_system_tzdata(without_system_tzdata: None, zone: str) -> None:
    assert build_window(None, None, zone).timezone == zone
