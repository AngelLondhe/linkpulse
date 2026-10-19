from pathlib import Path
from types import SimpleNamespace

from geoip2.errors import AddressNotFoundError

from app.services.geo import UNKNOWN_LOCATION, GeoLookup, GeoResult


class FakeReader:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def city(self, ip_address: str) -> object:
        self.calls.append(ip_address)
        if ip_address == "203.0.113.200":
            raise AddressNotFoundError("not in database")
        return SimpleNamespace(
            country=SimpleNamespace(iso_code="DE"), city=SimpleNamespace(name="Berlin")
        )


def test_missing_database_degrades_to_unknown(tmp_path: Path) -> None:
    geo = GeoLookup.from_path(str(tmp_path / "absent.mmdb"))

    assert not geo.available
    assert geo.lookup("8.8.8.8") == UNKNOWN_LOCATION


def test_corrupt_database_degrades_to_unknown(tmp_path: Path) -> None:
    bogus = tmp_path / "bogus.mmdb"
    bogus.write_bytes(b"definitely not a maxmind database")

    assert not GeoLookup.from_path(str(bogus)).available


def test_lookup_returns_country_code_and_city() -> None:
    assert GeoLookup(FakeReader()).lookup("8.8.8.8") == GeoResult(country="DE", city="Berlin")


def test_unknown_address_is_unknown() -> None:
    assert GeoLookup(FakeReader()).lookup("203.0.113.200") == UNKNOWN_LOCATION


def test_private_and_invalid_addresses_skip_the_database() -> None:
    reader = FakeReader()
    geo = GeoLookup(reader)

    for ip in ("127.0.0.1", "10.1.2.3", "192.168.0.1", "::1", "unknown", "999.1.1.1"):
        assert geo.lookup(ip) == UNKNOWN_LOCATION
    assert reader.calls == []
