import io

import pytest
import segno
from httpx import AsyncClient

from app.models import User
from tests.conftest import bearer


async def _link(client: AsyncClient, headers: dict[str, str]) -> dict[str, object]:
    response = await client.post(
        "/api/links",
        json={"url": "https://example.com", "custom_alias": "qr-demo"},
        headers=headers,
    )
    body: dict[str, object] = response.json()
    return body


async def test_png_qr_code(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    link = await _link(client, auth_headers)

    response = await client.get(f"/api/links/{link['id']}/qr", headers=auth_headers)

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert response.headers["content-disposition"] == 'inline; filename="qr-demo-qr.png"'


async def test_svg_download(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    link = await _link(client, auth_headers)

    response = await client.get(
        f"/api/links/{link['id']}/qr?format=svg&download=true&scale=4", headers=auth_headers
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert response.text.lstrip().startswith("<svg")
    assert response.headers["content-disposition"].startswith("attachment;")


async def test_qr_encodes_the_short_url(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    link = await _link(client, auth_headers)

    response = await client.get(
        f"/api/links/{link['id']}/qr?format=svg&scale=4", headers=auth_headers
    )

    expected = io.BytesIO()
    segno.make("http://testserver/qr-demo", error="m", micro=False).save(
        expected, kind="svg", scale=4, border=4, xmldecl=False, svgns=True
    )
    assert response.content == expected.getvalue()


@pytest.mark.parametrize("query", ["format=gif", "scale=0", "scale=41"])
async def test_invalid_qr_parameters(
    client: AsyncClient, auth_headers: dict[str, str], query: str
) -> None:
    link = await _link(client, auth_headers)
    response = await client.get(f"/api/links/{link['id']}/qr?{query}", headers=auth_headers)
    assert response.status_code == 422


async def test_qr_requires_ownership(client: AsyncClient, user: User, other_user: User) -> None:
    link = await _link(client, bearer(user))

    assert (
        await client.get(f"/api/links/{link['id']}/qr", headers=bearer(other_user))
    ).status_code == 403
    assert (await client.get(f"/api/links/{link['id']}/qr")).status_code == 401
