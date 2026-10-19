from typing import Any

from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Link
from tests.unit.test_user_agent import CHROME_WINDOWS

QUEUE = get_settings().click_queue_key
HUMAN = {"User-Agent": CHROME_WINDOWS}
FORM = {"Content-Type": "application/x-www-form-urlencoded", **HUMAN}


async def _protected(client: AsyncClient, headers: dict[str, str], **extra: Any) -> dict[str, Any]:
    response = await client.post(
        "/api/links",
        json={"url": "https://secret.example/doc", "password": "open-sesame", **extra},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def test_password_is_hashed_and_flagged(
    client: AsyncClient, auth_headers: dict[str, str], db: AsyncSession
) -> None:
    link = await _protected(client, auth_headers)

    stored = await db.scalar(select(Link.password_hash).where(Link.id == link["id"]))
    assert link["has_password"] is True
    assert "password" not in link
    assert stored is not None
    assert stored.startswith("$argon2id$")


async def test_get_shows_form_without_recording_a_click(
    client: AsyncClient, auth_headers: dict[str, str], redis: Redis
) -> None:
    link = await _protected(client, auth_headers)

    response = await client.get(f"/{link['short_code']}", headers=HUMAN)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert '<form method="post"' in response.text
    assert "secret.example" not in response.text  # destination is not leaked
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert await redis.llen(QUEUE) == 0


async def test_wrong_password_is_401_and_not_counted(
    client: AsyncClient, auth_headers: dict[str, str], redis: Redis
) -> None:
    link = await _protected(client, auth_headers)

    response = await client.post(f"/{link['short_code']}", content="password=nope", headers=FORM)

    assert response.status_code == 401
    assert "Incorrect password" in response.text
    assert await redis.llen(QUEUE) == 0


async def test_correct_password_redirects_with_303_and_counts(
    client: AsyncClient, auth_headers: dict[str, str], redis: Redis
) -> None:
    link = await _protected(client, auth_headers)

    response = await client.post(
        f"/{link['short_code']}", content="password=open-sesame", headers=FORM
    )

    assert response.status_code == 303
    assert response.headers["location"] == "https://secret.example/doc"
    assert await redis.llen(QUEUE) == 1


async def test_password_and_max_clicks_combine(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    link = await _protected(client, auth_headers, max_clicks=1)
    path = f"/{link['short_code']}"

    first = await client.post(path, content="password=open-sesame", headers=FORM)
    second = await client.post(path, content="password=open-sesame", headers=FORM)
    form_after_limit = await client.get(path, headers=HUMAN)

    assert first.status_code == 303
    assert second.status_code == 410
    assert form_after_limit.status_code == 410  # no point asking for a password


async def test_removing_password_restores_plain_redirect(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    link = await _protected(client, auth_headers)
    assert (await client.get(f"/{link['short_code']}")).status_code == 200

    patched = await client.patch(
        f"/api/links/{link['id']}", json={"password": None}, headers=auth_headers
    )

    assert patched.json()["has_password"] is False
    assert (await client.get(f"/{link['short_code']}")).status_code == 302


async def test_post_to_unprotected_link_just_redirects(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    created = (
        await client.post("/api/links", json={"url": "https://open.example"}, headers=auth_headers)
    ).json()

    response = await client.post(f"/{created['short_code']}", content="", headers=FORM)

    assert response.status_code == 303
    assert response.headers["location"] == "https://open.example"


async def test_short_password_is_rejected(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/api/links", json={"url": "https://e.example", "password": "abc"}, headers=auth_headers
    )
    assert response.status_code == 422
