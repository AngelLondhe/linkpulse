import pytest
from httpx import AsyncClient

from app.models import User
from tests.conftest import bearer


async def test_create_with_custom_alias_and_redirect(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/api/links",
        json={"url": "https://example.com/launch", "custom_alias": "launch-day"},
        headers=auth_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["short_code"] == "launch-day"
    assert body["is_custom"] is True
    redirect = await client.get("/launch-day")
    assert redirect.status_code == 302
    assert redirect.headers["location"] == "https://example.com/launch"


async def test_alias_taken_is_409_even_across_users(
    client: AsyncClient, user: User, other_user: User
) -> None:
    payload = {"url": "https://example.com", "custom_alias": "promo"}
    first = await client.post("/api/links", json=payload, headers=bearer(user))
    second = await client.post("/api/links", json=payload, headers=bearer(other_user))

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "alias_taken"


async def test_alias_colliding_with_generated_code_is_409(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    generated = (
        await client.post("/api/links", json={"url": "https://a.example"}, headers=auth_headers)
    ).json()

    response = await client.post(
        "/api/links",
        json={"url": "https://b.example", "custom_alias": generated["short_code"]},
        headers=auth_headers,
    )

    assert response.status_code == 409


@pytest.mark.parametrize("alias", ["ab", "bad alias", "api", "Docs", "x" * 31])
async def test_invalid_or_reserved_alias_is_422(
    client: AsyncClient, auth_headers: dict[str, str], alias: str
) -> None:
    response = await client.post(
        "/api/links",
        json={"url": "https://example.com", "custom_alias": alias},
        headers=auth_headers,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_alias"


async def test_aliases_are_case_sensitive(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    for alias, url in (("Sale", "https://upper.example"), ("sale", "https://lower.example")):
        response = await client.post(
            "/api/links", json={"url": url, "custom_alias": alias}, headers=auth_headers
        )
        assert response.status_code == 201

    assert (await client.get("/Sale")).headers["location"] == "https://upper.example"
    assert (await client.get("/sale")).headers["location"] == "https://lower.example"
