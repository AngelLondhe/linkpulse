"""Offline IP geolocation with MaxMind GeoLite2-City.

If the database file is missing or unreadable, every lookup returns (None, None) and the API
shows "Unknown"; the pipeline keeps working without it.
"""

import ipaddress
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from geoip2.database import Reader
from geoip2.errors import AddressNotFoundError
from maxminddb.errors import InvalidDatabaseError

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GeoResult:
    country: str | None  # ISO 3166-1 alpha-2
    city: str | None


UNKNOWN_LOCATION = GeoResult(country=None, city=None)


class CityReader(Protocol):
    def city(self, ip_address: str) -> object: ...


class GeoLookup:
    def __init__(self, reader: CityReader | None) -> None:
        self._reader = reader

    @property
    def available(self) -> bool:
        return self._reader is not None

    @classmethod
    def from_path(cls, path: str) -> "GeoLookup":
        db_path = Path(path)
        if not db_path.is_file():
            logger.warning("GeoLite2 database not found at %s; geo will be 'Unknown'", db_path)
            return cls(None)
        try:
            return cls(Reader(str(db_path)))
        except (OSError, InvalidDatabaseError, ValueError):
            logger.exception("Could not open GeoLite2 database at %s", db_path)
            return cls(None)

    def lookup(self, ip: str) -> GeoResult:
        if self._reader is None:
            return UNKNOWN_LOCATION
        try:
            address = ipaddress.ip_address(ip)
        except ValueError:
            return UNKNOWN_LOCATION
        if not address.is_global:
            return UNKNOWN_LOCATION
        try:
            record = self._reader.city(str(address))
        except AddressNotFoundError:
            return UNKNOWN_LOCATION
        except (ValueError, InvalidDatabaseError):
            logger.warning("GeoLite2 lookup failed for an address", exc_info=True)
            return UNKNOWN_LOCATION
        country = getattr(getattr(record, "country", None), "iso_code", None)
        city = getattr(getattr(record, "city", None), "name", None)
        return GeoResult(country=country, city=city[:128] if city else None)


@lru_cache
def get_geo_lookup() -> GeoLookup:
    """Process-wide lookup, opened once (the reader memory-maps the database file)."""
    return GeoLookup.from_path(get_settings().geoip_db_path)
