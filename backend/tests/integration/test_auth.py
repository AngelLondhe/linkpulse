from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from tests.conftest import DEFAULT_PASSWORD, bearer


async def test_register_returns_token_and_user(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/register", json={"email": "New.User@Example.com", "password": "long-enough"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == "new.user@example.com"  # normalised
    assert "password" not in str(body)

    me = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["email"] == "new.user@example.com"


async def test_password_is_stored_hashed(client: AsyncClient, db: AsyncSession) -> None:
    await client.post(
        "/api/auth/register", json={"email": "h@example.com", "password": "plain-pw-1"}
    )

    stored = await db.scalar(User.__table__.select().with_only_columns(User.password_hash))

    assert stored is not None
    assert stored != "plain-pw-1"
    assert stored.startswith("$argon2id$")


async def test_register_duplicate_email_is_409_case_insensitive(
    client: AsyncClient, user: User
) -> None:
    response = await client.post(
        "/api/auth/register", json={"email": "ALICE@example.com", "password": "another-pass"}
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_taken"


async def test_register_validates_email_and_password(client: AsyncClient) -> None:
    bad_email = await client.post(
        "/api/auth/register", json={"email": "not-an-email", "password": "long-enough"}
    )
    short_password = await client.post(
        "/api/auth/register", json={"email": "ok@example.com", "password": "short"}
    )

    assert bad_email.status_code == 422
    assert short_password.status_code == 422
    assert short_password.json()["error"]["code"] == "validation_error"


async def test_login_success(client: AsyncClient, user: User) -> None:
    response = await client.post(
        "/api/auth/login", json={"email": "Alice@Example.com", "password": DEFAULT_PASSWORD}
    )

    assert response.status_code == 200
    assert response.json()["user"]["id"] == user.id


async def test_login_wrong_password_and_unknown_email_look_identical(
    client: AsyncClient, user: User
) -> None:
    wrong_password = await client.post(
        "/api/auth/login", json={"email": "alice@example.com", "password": "nope-nope"}
    )
    unknown_email = await client.post(
        "/api/auth/login", json={"email": "ghost@example.com", "password": "nope-nope"}
    )

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()
    assert wrong_password.headers["www-authenticate"] == "Bearer"


async def test_me_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


async def test_me_rejects_invalid_token(client: AsyncClient) -> None:
    response = await client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"


async def test_token_for_deleted_user_is_rejected(
    client: AsyncClient, db: AsyncSession, user: User
) -> None:
    headers = bearer(user)
    await db.delete(user)
    await db.commit()

    response = await client.get("/api/auth/me", headers=headers)

    assert response.status_code == 401
