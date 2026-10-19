from collections.abc import Iterator

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Link, User
from app.services import links_service
from tests.conftest import bearer


async def _create(client: AsyncClient, headers: dict[str, str], url: str) -> dict[str, object]:
    response = await client.post("/api/links", json={"url": url}, headers=headers)
    assert response.status_code == 201, response.text
    body: dict[str, object] = response.json()
    return body


async def test_create_link(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    body = await _create(client, auth_headers, "https://example.com/some/long/path")

    assert body["original_url"] == "https://example.com/some/long/path"
    code = str(body["short_code"])
    assert len(code) == 7
    assert body["short_url"] == f"http://testserver/{code}"
    assert body["is_custom"] is False
    assert body["is_active"] is True
    assert body["has_password"] is False
    assert body["total_clicks"] == 0


async def test_create_requires_auth(client: AsyncClient) -> None:
    response = await client.post("/api/links", json={"url": "https://example.com"})
    assert response.status_code == 401


@pytest.mark.parametrize(
    "url", ["javascript:alert(1)", "data:text/html,hi", "not a url", "http://testserver/abc"]
)
async def test_create_rejects_malformed_or_unsafe_urls(
    client: AsyncClient, auth_headers: dict[str, str], url: str
) -> None:
    response = await client.post("/api/links", json={"url": url}, headers=auth_headers)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_url"


async def test_create_rejects_missing_body_field(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.post("/api/links", json={}, headers=auth_headers)
    assert response.status_code == 422


@pytest.fixture
def scripted_codes(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """Make the code generator return a scripted sequence of codes."""
    queue: list[str] = []
    monkeypatch.setattr(links_service, "generate_short_code", lambda: queue.pop(0))
    yield queue


async def test_collision_is_retried_with_a_new_code(
    client: AsyncClient, auth_headers: dict[str, str], scripted_codes: list[str]
) -> None:
    scripted_codes.extend(["AAAAAAA", "AAAAAAA", "AAAAAAA", "BBBBBBB"])

    first = await _create(client, auth_headers, "https://one.example")
    second = await _create(client, auth_headers, "https://two.example")

    assert first["short_code"] == "AAAAAAA"
    assert second["short_code"] == "BBBBBBB"  # two collisions, third attempt succeeded


async def test_gives_up_after_max_attempts(
    client: AsyncClient, auth_headers: dict[str, str], db: AsyncSession, scripted_codes: list[str]
) -> None:
    scripted_codes.extend(["CCCCCCC"] * (1 + links_service.MAX_CODE_ATTEMPTS))
    await _create(client, auth_headers, "https://one.example")

    response = await client.post(
        "/api/links", json={"url": "https://two.example"}, headers=auth_headers
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "code_generation_failed"
    assert await db.scalar(select(func.count(Link.id))) == 1
    assert scripted_codes == []  # exactly MAX_CODE_ATTEMPTS were tried


async def test_list_only_returns_own_links_newest_first(
    client: AsyncClient, user: User, other_user: User
) -> None:
    mine, theirs = bearer(user), bearer(other_user)
    await _create(client, mine, "https://first.example")
    await _create(client, mine, "https://second.example")
    await _create(client, theirs, "https://not-mine.example")

    response = await client.get("/api/links", headers=mine)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [item["original_url"] for item in body["items"]] == [
        "https://second.example",
        "https://first.example",
    ]


async def test_list_pagination(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    for i in range(5):
        await _create(client, auth_headers, f"https://site{i}.example")

    page1 = (await client.get("/api/links?page=1&page_size=2", headers=auth_headers)).json()
    page3 = (await client.get("/api/links?page=3&page_size=2", headers=auth_headers)).json()

    assert page1["total"] == 5
    assert len(page1["items"]) == 2
    assert len(page3["items"]) == 1
    assert page3["items"][0]["original_url"] == "https://site0.example"


async def test_list_rejects_bad_pagination(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.get("/api/links?page=0&page_size=1000", headers=auth_headers)
    assert response.status_code == 422


async def test_list_search_matches_url_and_code_and_escapes_wildcards(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    github = await _create(client, auth_headers, "https://github.com/octocat")
    await _create(client, auth_headers, "https://news.example/100%_real")
    await _create(client, auth_headers, "https://other.example")

    by_url = (await client.get("/api/links?q=GITHUB", headers=auth_headers)).json()
    by_code = (
        await client.get(f"/api/links?q={github['short_code']}", headers=auth_headers)
    ).json()
    literal_percent = (await client.get("/api/links?q=%25_", headers=auth_headers)).json()

    assert [i["original_url"] for i in by_url["items"]] == ["https://github.com/octocat"]
    assert by_code["total"] == 1
    assert [i["original_url"] for i in literal_percent["items"]] == [
        "https://news.example/100%_real"
    ]


async def test_get_link(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    created = await _create(client, auth_headers, "https://example.com")

    response = await client.get(f"/api/links/{created['id']}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == created


async def test_unknown_link_is_404(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    for method in ("GET", "PATCH", "DELETE"):
        response = await client.request(
            method, "/api/links/999999", headers=auth_headers, json={"is_active": False}
        )
        assert response.status_code == 404, method
        assert response.json()["error"]["code"] == "not_found"


async def test_other_users_link_is_403_for_every_operation(
    client: AsyncClient, db: AsyncSession, user: User, other_user: User
) -> None:
    created = await _create(client, bearer(user), "https://example.com/private")
    intruder = bearer(other_user)
    url = f"/api/links/{created['id']}"

    get = await client.get(url, headers=intruder)
    patch = await client.patch(url, json={"url": "https://evil.example"}, headers=intruder)
    delete = await client.delete(url, headers=intruder)

    for response in (get, patch, delete):
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "not_owner"
    link = await db.get(Link, created["id"])
    assert link is not None
    assert link.original_url == "https://example.com/private"


async def test_update_link(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    created = await _create(client, auth_headers, "https://old.example")
    url = f"/api/links/{created['id']}"

    response = await client.patch(
        url, json={"url": "https://new.example", "is_active": False}, headers=auth_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["original_url"] == "https://new.example"
    assert body["is_active"] is False
    assert body["short_code"] == created["short_code"]


async def test_update_validates_input(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    created = await _create(client, auth_headers, "https://old.example")
    url = f"/api/links/{created['id']}"

    empty = await client.patch(url, json={}, headers=auth_headers)
    unsafe = await client.patch(url, json={"url": "javascript:alert(1)"}, headers=auth_headers)

    assert empty.status_code == 422
    assert unsafe.status_code == 422
    assert unsafe.json()["error"]["code"] == "invalid_url"


async def test_delete_link(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    created = await _create(client, auth_headers, "https://example.com")
    url = f"/api/links/{created['id']}"

    deleted = await client.delete(url, headers=auth_headers)
    after = await client.get(url, headers=auth_headers)

    assert deleted.status_code == 204
    assert after.status_code == 404


async def test_out_of_range_id_is_422(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await client.get(f"/api/links/{2**63}", headers=auth_headers)
    assert response.status_code == 422
