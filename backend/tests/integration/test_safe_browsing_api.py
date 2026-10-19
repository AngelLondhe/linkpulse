from collections.abc import Iterator

import pytest
from httpx import AsyncClient

from app.main import app
from app.services.safe_browsing import get_url_checker


class FakeChecker:
    def __init__(self, flagged: set[str]) -> None:
        self.flagged = flagged
        self.checked: list[str] = []

    async def threats(self, url: str) -> list[str]:
        self.checked.append(url)
        return ["SOCIAL_ENGINEERING"] if url in self.flagged else []


@pytest.fixture
def checker() -> Iterator[FakeChecker]:
    fake = FakeChecker({"https://phish.example/login"})
    app.dependency_overrides[get_url_checker] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_url_checker)


async def test_flagged_url_is_rejected_on_create(
    client: AsyncClient, auth_headers: dict[str, str], checker: FakeChecker
) -> None:
    response = await client.post(
        "/api/links", json={"url": "https://phish.example/login"}, headers=auth_headers
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "unsafe_url"
    assert error["details"] == {"threats": ["SOCIAL_ENGINEERING"]}


async def test_flagged_url_is_rejected_on_edit(
    client: AsyncClient, auth_headers: dict[str, str], checker: FakeChecker
) -> None:
    created = (
        await client.post("/api/links", json={"url": "https://fine.example"}, headers=auth_headers)
    ).json()

    response = await client.patch(
        f"/api/links/{created['id']}",
        json={"url": "https://phish.example/login"},
        headers=auth_headers,
    )

    assert response.status_code == 422
    assert checker.checked == ["https://fine.example", "https://phish.example/login"]


async def test_no_api_key_means_no_check(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    assert get_url_checker() is None
    response = await client.post(
        "/api/links", json={"url": "https://phish.example/login"}, headers=auth_headers
    )
    assert response.status_code == 201
