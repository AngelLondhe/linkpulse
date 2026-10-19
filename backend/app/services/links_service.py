"""Business logic for creating, listing, updating and deleting short links."""

import logging
from collections.abc import Sequence

from sqlalchemy import ScalarSelect, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import (
    ForbiddenError,
    NotFoundError,
    ServiceUnavailableError,
    ValidationError,
)
from app.models import Click, Link, User
from app.schemas.links import LinkUpdate
from app.utils.db_errors import is_unique_violation
from app.utils.shortcode import generate_short_code
from app.utils.url_validation import InvalidURLError, own_hosts_from_urls, validate_target_url

logger = logging.getLogger(__name__)

MAX_CODE_ATTEMPTS = 5
SHORT_CODE_INDEX = "ix_links_short_code"


def validate_destination(url: str) -> str:
    """Validate a destination URL against the rules in ``validate_target_url``.

    Raises ValidationError (422, code ``invalid_url``) with the specific reason.
    """
    own_hosts = own_hosts_from_urls(str(get_settings().public_base_url))
    try:
        return validate_target_url(url, own_hosts)
    except InvalidURLError as exc:
        raise ValidationError(str(exc), code="invalid_url") from exc


async def create_link(db: AsyncSession, owner: User, url: str) -> Link:
    """Create a link with a random 7-char Base62 code.

    Collisions are handled optimistically: insert, and if the unique index on ``short_code``
    rejects it, retry with a fresh code (up to MAX_CODE_ATTEMPTS). This is race-free, unlike
    "SELECT then INSERT", and costs nothing in the overwhelmingly common no-collision case.
    """
    destination = validate_destination(url)
    # Read before the loop: a rollback expires every object in the session, including `owner`.
    owner_id = owner.id
    for attempt in range(1, MAX_CODE_ATTEMPTS + 1):
        link = Link(
            user_id=owner_id,
            short_code=generate_short_code(),
            original_url=destination,
            is_custom=False,
        )
        db.add(link)
        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            if not is_unique_violation(exc, SHORT_CODE_INDEX):
                raise
            logger.warning("Short code collision on attempt %d/%d", attempt, MAX_CODE_ATTEMPTS)
            continue
        await db.refresh(link)
        return link

    raise ServiceUnavailableError(
        "Could not allocate a unique short code, please retry", code="code_generation_failed"
    )


def _click_count_subquery() -> ScalarSelect[int]:
    """Correlated COUNT(*) of clicks per link, served by the (link_id, clicked_at) index."""
    return (
        select(func.count(Click.id))
        .where(Click.link_id == Link.id)
        .correlate(Link)
        .scalar_subquery()
    )


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def list_links(
    db: AsyncSession,
    owner: User,
    *,
    search: str | None,
    page: int,
    page_size: int,
) -> tuple[Sequence[tuple[Link, int]], int]:
    """Return one page of the owner's links (newest first) with click totals, plus the total
    number of matching links. ``search`` matches the destination URL or short code."""
    filters = [Link.user_id == owner.id]
    if search and search.strip():
        pattern = f"%{_escape_like(search.strip())}%"
        filters.append(
            or_(
                Link.original_url.ilike(pattern, escape="\\"),
                Link.short_code.ilike(pattern, escape="\\"),
            )
        )

    total = await db.scalar(select(func.count(Link.id)).where(*filters)) or 0
    rows = await db.execute(
        select(Link, _click_count_subquery())
        .where(*filters)
        .order_by(Link.created_at.desc(), Link.id.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    return [(link, clicks) for link, clicks in rows.all()], total


async def get_owned_link(db: AsyncSession, owner: User, link_id: int) -> Link:
    """Load a link and enforce ownership: 404 if it does not exist, 403 if owned by someone
    else. Every single-link operation goes through this function."""
    link = await db.get(Link, link_id)
    if link is None:
        raise NotFoundError("Link not found")
    if link.user_id != owner.id:
        raise ForbiddenError("You do not have access to this link", code="not_owner")
    return link


async def count_clicks(db: AsyncSession, link_id: int) -> int:
    return await db.scalar(select(func.count(Click.id)).where(Click.link_id == link_id)) or 0


async def update_link(db: AsyncSession, owner: User, link_id: int, changes: LinkUpdate) -> Link:
    """Apply a partial update to an owned link (destination URL and/or active flag)."""
    link = await get_owned_link(db, owner, link_id)
    if changes.url is not None:
        link.original_url = validate_destination(changes.url)
    if changes.is_active is not None:
        link.is_active = changes.is_active
    await db.commit()
    await db.refresh(link)
    return link


async def delete_link(db: AsyncSession, owner: User, link_id: int) -> None:
    """Delete an owned link; its clicks are removed by ON DELETE CASCADE."""
    link = await get_owned_link(db, owner, link_id)
    await db.delete(link)
    await db.commit()
