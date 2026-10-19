import json

import httpx
import pytest

from app.services.safe_browsing import LOOKUP_URL, SafeBrowsingChecker


def _checker(handler: httpx.MockTransport) -> SafeBrowsingChecker:
    return SafeBrowsingChecker("test-key", httpx.AsyncClient(transport=handler))


async def test_safe_url_has_no_threats() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={})

    threats = await _checker(httpx.MockTransport(handler)).threats("https://example.com")

    assert threats == []
    request = seen[0]
    assert str(request.url).startswith(LOOKUP_URL)
    assert request.url.params["key"] == "test-key"
    body = json.loads(request.content)
    assert body["threatInfo"]["threatEntries"] == [{"url": "https://example.com"}]
    assert "SOCIAL_ENGINEERING" in body["threatInfo"]["threatTypes"]


async def test_flagged_url_returns_threat_types() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        matches = [
            {"threatType": "SOCIAL_ENGINEERING"},
            {"threatType": "MALWARE"},
            {"threatType": "MALWARE"},
        ]
        return httpx.Response(200, json={"matches": matches})

    threats = await _checker(httpx.MockTransport(handler)).threats("http://phish.test")

    assert threats == ["MALWARE", "SOCIAL_ENGINEERING"]


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, text="boom"),
        httpx.Response(403, json={"error": "bad key"}),
        httpx.Response(200, text="not json"),
    ],
)
async def test_errors_fail_open(response: httpx.Response) -> None:
    checker = _checker(httpx.MockTransport(lambda request: response))
    assert await checker.threats("https://example.com") == []


async def test_timeouts_fail_open() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("too slow", request=request)

    assert await _checker(httpx.MockTransport(handler)).threats("https://example.com") == []
