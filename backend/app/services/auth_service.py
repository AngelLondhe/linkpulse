"""User registration and authentication."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, UnauthorizedError
from app.core.security import (
    InvalidTokenError,
    burn_password_check,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.models import User

INVALID_CREDENTIALS = "Invalid email or password"


async def register_user(db: AsyncSession, email: str, password: str) -> User:
    """Create a user with an Argon2id password hash.

    Relies on the unique constraint (not a pre-check) so concurrent sign-ups with the same
    email cannot both succeed. Raises ConflictError if the email is taken.
    """
    user = User(email=email.lower(), password_hash=hash_password(password))
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError(
            "An account with this email already exists", code="email_taken"
        ) from exc
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    """Return the user for valid credentials, else raise UnauthorizedError.

    Unknown email and wrong password produce the same error and similar timing, so the
    endpoint cannot be used to discover which emails are registered.
    """
    user = await db.scalar(select(User).where(User.email == email.lower()))
    if user is None:
        burn_password_check(password)
        raise UnauthorizedError(INVALID_CREDENTIALS, code="invalid_credentials")
    if not verify_password(password, user.password_hash):
        raise UnauthorizedError(INVALID_CREDENTIALS, code="invalid_credentials")
    return user


async def get_user_from_token(db: AsyncSession, token: str) -> User:
    """Resolve a bearer token to an existing user, else raise UnauthorizedError."""
    try:
        user_id = decode_access_token(token)
    except InvalidTokenError as exc:
        raise UnauthorizedError("Invalid or expired token", code="invalid_token") from exc
    user = await db.get(User, user_id)
    if user is None:
        raise UnauthorizedError("Invalid or expired token", code="invalid_token")
    return user
