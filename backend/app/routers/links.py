from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.redis import get_redis
from app.db.session import get_db
from app.models import User
from app.routers.deps import get_current_user
from app.schemas.links import LinkCreate, LinkPage, LinkRead, LinkUpdate
from app.services import links_service

router = APIRouter(prefix="/api/links", tags=["links"])

LinkId = Annotated[int, Path(ge=1, le=2**63 - 1)]


def _base_url() -> str:
    return str(get_settings().public_base_url)


@router.post("", response_model=LinkRead, status_code=status.HTTP_201_CREATED)
async def create_link(
    body: LinkCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> LinkRead:
    link = await links_service.create_link(db, redis, user, body.url)
    return LinkRead.from_model(link, total_clicks=0, base_url=_base_url())


@router.get("", response_model=LinkPage)
async def list_links(
    q: Annotated[str | None, Query(max_length=200, description="Search URL or code")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LinkPage:
    rows, total = await links_service.list_links(db, user, search=q, page=page, page_size=page_size)
    base_url = _base_url()
    return LinkPage(
        items=[
            LinkRead.from_model(link, total_clicks=clicks, base_url=base_url)
            for link, clicks in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{link_id}", response_model=LinkRead)
async def get_link(
    link_id: LinkId,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LinkRead:
    link = await links_service.get_owned_link(db, user, link_id)
    clicks = await links_service.count_clicks(db, link.id)
    return LinkRead.from_model(link, total_clicks=clicks, base_url=_base_url())


@router.patch("/{link_id}", response_model=LinkRead)
async def update_link(
    link_id: LinkId,
    body: LinkUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> LinkRead:
    link = await links_service.update_link(db, redis, user, link_id, body)
    clicks = await links_service.count_clicks(db, link.id)
    return LinkRead.from_model(link, total_clicks=clicks, base_url=_base_url())


@router.delete("/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_link(
    link_id: LinkId,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> Response:
    await links_service.delete_link(db, redis, user, link_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
