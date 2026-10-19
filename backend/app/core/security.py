"""Password hashing (Argon2id) and JWT access tokens."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings

_hasher = PasswordHasher()  # Argon2id with the library's (OWASP-aligned) defaults

TOKEN_TYPE = "access"  # noqa: S105  (a claim label, not a secret)


@dataclass(frozen=True)
class AccessToken:
    token: str
    expires_in: int  # seconds


class InvalidTokenError(Exception):
    """Raised when a JWT is missing, malformed, expired or signed with the wrong key."""


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


# Verifying against a real hash when the user does not exist keeps login timing uniform,
# so response time does not reveal which emails are registered.
_DUMMY_HASH = _hasher.hash("timing-equaliser-not-a-real-password")


def burn_password_check(password: str) -> None:
    verify_password(password, _DUMMY_HASH)


def create_access_token(user_id: int, *, now: datetime | None = None) -> AccessToken:
    settings = get_settings()
    issued_at = now or datetime.now(UTC)
    lifetime = timedelta(minutes=settings.access_token_expire_minutes)
    claims = {
        "sub": str(user_id),
        "type": TOKEN_TYPE,
        "iat": issued_at,
        "exp": issued_at + lifetime,
    }
    token = jwt.encode(
        claims, settings.jwt_secret_key.get_secret_value(), algorithm=settings.jwt_algorithm
    )
    return AccessToken(token=token, expires_in=int(lifetime.total_seconds()))


def decode_access_token(token: str) -> int:
    """Return the user id encoded in a valid access token, else raise InvalidTokenError."""
    settings = get_settings()
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],  # explicit allow-list blocks alg=none/confusion
            options={"require": ["sub", "exp", "iat"]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc

    if claims.get("type") != TOKEN_TYPE:
        raise InvalidTokenError("Wrong token type")
    try:
        return int(claims["sub"])
    except (TypeError, ValueError) as exc:
        raise InvalidTokenError("Malformed subject") from exc
