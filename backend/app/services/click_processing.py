"""Turn raw click events into analytics rows and bulk-insert them.

Shared by the worker (normal path) and the API's degraded-mode fallback.
"""

import logging
import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Click, Link
from app.services.click_queue import ClickEvent
from app.services.geo import GeoLookup, get_geo_lookup
from app.utils.ip_hash import hash_ip
from app.utils.referrer import referrer_host
from app.utils.user_agent import parse_user_agent

logger = logging.getLogger(__name__)

ClickRow = dict[str, Any]


def enrich(event: ClickEvent, geo: GeoLookup, salt: str) -> ClickRow:
    """Parse the UA, geolocate and hash the IP. The raw IP does not leave this function."""
    agent = parse_user_agent(event.user_agent)
    location = geo.lookup(event.ip)
    return {
        "event_id": uuid.UUID(event.event_id),
        "link_id": event.link_id,
        "clicked_at": datetime.fromisoformat(event.clicked_at),
        "referrer": referrer_host(event.referrer),
        "browser": agent.browser,
        "os": agent.os,
        "device_type": agent.device_type,
        "country": location.country,
        "city": location.city,
        "ip_hash": hash_ip(event.ip, salt),
    }


async def insert_clicks(db: AsyncSession, rows: Sequence[ClickRow]) -> int:
    """Bulk-insert rows in one statement and commit; returns the number actually inserted.

    Rows for links deleted since the click happened are dropped (they would violate the FK
    and poison the whole batch). Duplicate event_ids are skipped, making retries idempotent.
    """
    if not rows:
        return 0
    link_ids = {row["link_id"] for row in rows}
    existing = set((await db.scalars(select(Link.id).where(Link.id.in_(link_ids)))).all())
    live_rows = [row for row in rows if row["link_id"] in existing]
    if dropped := len(rows) - len(live_rows):
        logger.info("Dropped %d click(s) for deleted links", dropped)
    if not live_rows:
        return 0

    statement = (
        pg_insert(Click).values(live_rows).on_conflict_do_nothing(index_elements=["event_id"])
    )
    result = await db.execute(statement)
    await db.commit()
    return int(getattr(result, "rowcount", 0) or 0)


async def persist_directly(event: ClickEvent) -> None:
    """Degraded mode: Redis was down at redirect time, so write the click ourselves.

    Runs as a background task after the redirect response has been sent, so it does not
    slow the user down. Failures are logged rather than raised (the response is gone).
    """
    try:
        row = enrich(event, get_geo_lookup(), get_settings().ip_hash_salt.get_secret_value())
        async with SessionLocal() as db:
            await insert_clicks(db, [row])
    except Exception:
        logger.exception("Could not persist click for link %s directly", event.link_id)
