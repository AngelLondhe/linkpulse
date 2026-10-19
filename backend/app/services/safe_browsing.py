"""Google Safe Browsing (v4 Lookup API) check for destination URLs.

Optional: without SAFE_BROWSING_API_KEY no check is made. The check fails open: if Google is
slow or unreachable we log and allow the URL rather than block link creation.
"""

import logging
from functools import lru_cache
from typing import Protocol

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

LOOKUP_URL = "https://safebrowsing.googleapis.com/v4/threatMatches:find"
THREAT_TYPES = [
    "MALWARE",
    "SOCIAL_ENGINEERING",
    "UNWANTED_SOFTWARE",
    "POTENTIALLY_HARMFUL_APPLICATION",
]


class URLSafetyChecker(Protocol):
    async def threats(self, url: str) -> list[str]:
        """Return the threat types matched by ``url`` (empty when safe or unknown)."""
        ...


class SafeBrowsingChecker:
    def __init__(self, api_key: str, client: httpx.AsyncClient) -> None:
        self._api_key = api_key
        self._client = client

    async def threats(self, url: str) -> list[str]:
        payload = {
            "client": {"clientId": "linkpulse", "clientVersion": "0.1.0"},
            "threatInfo": {
                "threatTypes": THREAT_TYPES,
                "platformTypes": ["ANY_PLATFORM"],
                "threatEntryTypes": ["URL"],
                "threatEntries": [{"url": url}],
            },
        }
        try:
            response = await self._client.post(
                LOOKUP_URL, params={"key": self._api_key}, json=payload
            )
            response.raise_for_status()
            matches = response.json().get("matches", [])
        except (httpx.HTTPError, ValueError):
            logger.warning("Safe Browsing lookup failed; allowing URL (fail open)", exc_info=True)
            return []
        return sorted({str(match.get("threatType", "UNKNOWN")) for match in matches})


@lru_cache
def _http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=get_settings().safe_browsing_timeout_seconds)


def get_url_checker() -> URLSafetyChecker | None:
    """FastAPI dependency: the configured checker, or None when no API key is set."""
    key = get_settings().safe_browsing_api_key
    if key is None or not key.get_secret_value():
        return None
    return SafeBrowsingChecker(key.get_secret_value(), _http_client())


async def close() -> None:
    if _http_client.cache_info().currsize:
        await _http_client().aclose()
        _http_client.cache_clear()
