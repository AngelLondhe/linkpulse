"""Shared FastAPI dependencies."""

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import UnauthorizedError
from app.db.session import get_db
from app.models import User
from app.services.auth_service import get_user_from_token
from app.utils.client_ip import parse_networks, resolve_client_ip

# auto_error=False so a missing header goes through our error envelope (401), not FastAPI's 403.
_bearer = HTTPBearer(auto_error=False, description="JWT from /api/auth/login")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise UnauthorizedError("Not authenticated", code="not_authenticated")
    return await get_user_from_token(db, credentials.credentials)


def get_client_ip(request: Request) -> str:
    """Real client IP; X-Forwarded-For is honoured only when sent by a TRUSTED_PROXIES peer."""
    trusted = parse_networks(tuple(get_settings().trusted_proxies))
    peer = request.client.host if request.client else None
    return resolve_client_ip(peer, request.headers.get("x-forwarded-for"), trusted)
