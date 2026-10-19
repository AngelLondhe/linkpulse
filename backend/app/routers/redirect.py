from urllib.parse import parse_qs

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.db.session import get_db
from app.routers.deps import get_client_ip
from app.services import click_processing, redirect_service
from app.services.link_cache import CachedLink
from app.utils.bots import looks_like_bot
from app.utils.unlock_page import SECURITY_HEADERS, render_unlock_page

router = APIRouter(tags=["redirect"])

MAX_FORM_BYTES = 1024


async def _complete_visit(
    *,
    code: str,
    target: CachedLink,
    request: Request,
    client_ip: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession,
    redis: Redis,
    status_code: int,
) -> RedirectResponse:
    """Consume the click budget, record the click, and redirect."""
    user_agent = request.headers.get("user-agent")
    await redirect_service.enforce_click_limit(
        db, redis, code, target, is_bot=looks_like_bot(user_agent)
    )
    unqueued = await redirect_service.record_click(
        redis,
        target,
        ip=client_ip,
        user_agent=user_agent,
        referrer=request.headers.get("referer"),
    )
    if unqueued is not None:  # Redis down: write the click after the response is sent
        background_tasks.add_task(click_processing.persist_directly, unqueued)
    return RedirectResponse(
        target.url, status_code=status_code, headers={"Cache-Control": "private, no-store"}
    )


@router.get(
    "/{short_code}",
    status_code=status.HTTP_302_FOUND,
    response_class=RedirectResponse,
    responses={
        200: {"description": "Password form (protected links)", "content": {"text/html": {}}},
        404: {"description": "Unknown or inactive link"},
        410: {"description": "Expired or click limit reached"},
    },
)
async def follow_short_link(
    short_code: str,
    request: Request,
    background_tasks: BackgroundTasks,
    client_ip: str = Depends(get_client_ip),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> Response:
    """302 (not 301) so browsers never cache the hop and every click reaches us."""
    target = await redirect_service.resolve(db, redis, short_code)
    if target.has_password:
        # Check (without consuming) that the link is still usable before asking.
        await redirect_service.enforce_click_limit(db, redis, short_code, target, is_bot=True)
        return HTMLResponse(render_unlock_page(short_code), headers=SECURITY_HEADERS)
    return await _complete_visit(
        code=short_code,
        target=target,
        request=request,
        client_ip=client_ip,
        background_tasks=background_tasks,
        db=db,
        redis=redis,
        status_code=status.HTTP_302_FOUND,
    )


@router.post(
    "/{short_code}",
    response_class=RedirectResponse,
    include_in_schema=False,
)
async def unlock_short_link(
    short_code: str,
    request: Request,
    background_tasks: BackgroundTasks,
    client_ip: str = Depends(get_client_ip),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> Response:
    """Password form submission. 303 sends the browser on to the destination with a GET."""
    target = await redirect_service.resolve(db, redis, short_code)
    if target.has_password:
        body = (await request.body())[:MAX_FORM_BYTES].decode(errors="replace")
        password = parse_qs(body).get("password", [""])[0]
        if not await redirect_service.check_link_password(db, target, password):
            return HTMLResponse(
                render_unlock_page(short_code, error="Incorrect password, please try again."),
                status_code=status.HTTP_401_UNAUTHORIZED,
                headers=SECURITY_HEADERS,
            )
    return await _complete_visit(
        code=short_code,
        target=target,
        request=request,
        client_ip=client_ip,
        background_tasks=background_tasks,
        db=db,
        redis=redis,
        status_code=status.HTTP_303_SEE_OTHER,
    )
