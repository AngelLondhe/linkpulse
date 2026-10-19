"""Shared FastAPI dependencies."""

from collections.abc import Awaitable, Callable
from typing import Literal

from fastapi import Depends, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import RateLimitedError, UnauthorizedError
from app.core.redis import get_redis
from app.db.session import get_db
from app.models import User
from app.services.auth_service import get_user_from_token
from app.services.rate_limiter import RateLimiter, RateLimitRule
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


async def _enforce(redis: Redis, response: Response, rule: RateLimitRule, identity: str) -> None:
    if not get_settings().rate_limit_enabled:
        return
    result = await RateLimiter(redis).hit(rule, identity)
    headers = {"RateLimit-Limit": str(result.limit), "RateLimit-Remaining": str(result.remaining)}
    if not result.allowed:
        raise RateLimitedError(
            "Too many requests, please slow down",
            details={"retry_after": result.retry_after},
            headers={**headers, "Retry-After": str(result.retry_after)},
        )
    response.headers.update(headers)


def rate_limit(
    rule: RateLimitRule, *, per: Literal["ip", "ip_and_path"] = "ip"
) -> Callable[..., Awaitable[None]]:
    """Dependency enforcing ``rule`` per client IP (optionally per IP + request path)."""

    async def dependency(
        request: Request,
        response: Response,
        client_ip: str = Depends(get_client_ip),
        redis: Redis = Depends(get_redis),
    ) -> None:
        identity = f"{client_ip}:{request.url.path}" if per == "ip_and_path" else client_ip
        await _enforce(redis, response, rule, identity)

    return dependency


def rate_limit_per_user(rule: RateLimitRule) -> Callable[..., Awaitable[None]]:
    """Dependency enforcing ``rule`` per authenticated user (FastAPI reuses the resolved user,
    so this adds no extra DB query)."""

    async def dependency(
        response: Response,
        user: User = Depends(get_current_user),
        redis: Redis = Depends(get_redis),
    ) -> None:
        await _enforce(redis, response, rule, f"user:{user.id}")

    return dependency
