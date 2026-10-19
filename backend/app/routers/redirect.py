from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import RedirectResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.db.session import get_db
from app.routers.deps import get_client_ip
from app.services import redirect_service

router = APIRouter(tags=["redirect"])


@router.get(
    "/{short_code}",
    status_code=status.HTTP_302_FOUND,
    response_class=RedirectResponse,
    responses={404: {"description": "Unknown or inactive link"}, 410: {"description": "Expired"}},
)
async def follow_short_link(
    short_code: str,
    request: Request,
    client_ip: str = Depends(get_client_ip),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> RedirectResponse:
    """302 (not 301) so browsers never cache the hop and every click reaches us."""
    target = await redirect_service.resolve(db, redis, short_code)
    await redirect_service.record_click(
        redis,
        target,
        ip=client_ip,
        user_agent=request.headers.get("user-agent"),
        referrer=request.headers.get("referer"),
    )
    return RedirectResponse(
        target.url,
        status_code=status.HTTP_302_FOUND,
        headers={"Cache-Control": "private, no-store"},
    )
