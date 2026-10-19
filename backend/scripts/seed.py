"""Seed a demo account with links and ~90 days of realistic fake clicks.

Usage (from backend/):           python -m scripts.seed
With Docker:                     docker compose exec api python -m scripts.seed

Re-running is safe: the demo user (and everything it owns) is deleted and recreated.
Clicks are inserted directly (bypassing the queue) so the dashboard is populated instantly.
The RNG is seeded, so every run produces the same data.
"""

import argparse
import asyncio
import math
import random
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, insert, select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import SessionLocal, engine
from app.models import Click, Link, User
from app.utils.ip_hash import hash_ip

DEMO_EMAIL = "demo@linkpulse.dev"
DEMO_PASSWORD = "demo-password-123"  # noqa: S105  (public demo credentials, documented)
DAYS = 90


@dataclass(frozen=True)
class DemoLink:
    code: str
    url: str
    weight: float  # relative popularity
    launch_day: int  # days ago the link was "shared" (traffic spike)


DEMO_LINKS = [
    DemoLink("launch24", "https://github.com/your-name/linkpulse", 3.0, 60),
    DemoLink("resume", "https://example.com/portfolio/resume.pdf", 1.6, 85),
    DemoLink("blogpost", "https://dev.to/your-name/how-i-built-a-url-shortener", 2.2, 30),
    DemoLink("talk", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", 1.2, 45),
    DemoLink("docs", "https://fastapi.tiangolo.com/tutorial/", 0.8, 88),
    DemoLink("meetup", "https://www.meetup.com/python-meetup/events/", 0.6, 14),
    DemoLink("newsletter", "https://example.substack.com/p/issue-12", 0.9, 7),
    DemoLink("old-promo", "https://example.com/spring-sale", 0.3, 89),
]

# (value, weight) tables shaped like typical web traffic.
COUNTRIES = [
    ("US", 30),
    ("IN", 18),
    ("GB", 8),
    ("DE", 7),
    ("CA", 5),
    ("FR", 4),
    ("BR", 4),
    ("NL", 3),
    ("AU", 3),
    ("JP", 3),
    ("SG", 2),
    ("ES", 2),
    ("SE", 2),
    ("NG", 2),
    ("PL", 1),
    ("MX", 1),
    ("ZA", 1),
    ("KR", 1),
    (None, 3),
]
CITIES = {
    "US": ["New York", "San Francisco", "Seattle", "Austin", "Chicago"],
    "IN": ["Bengaluru", "Mumbai", "Pune", "Hyderabad", "Delhi"],
    "GB": ["London", "Manchester"],
    "DE": ["Berlin", "Munich"],
    "CA": ["Toronto", "Vancouver"],
    "FR": ["Paris"],
    "BR": ["São Paulo"],
    "NL": ["Amsterdam"],
    "AU": ["Sydney"],
    "JP": ["Tokyo"],
    "SG": ["Singapore"],
    "ES": ["Madrid"],
    "SE": ["Stockholm"],
    "NG": ["Lagos"],
    "PL": ["Warsaw"],
    "MX": ["Mexico City"],
    "ZA": ["Cape Town"],
    "KR": ["Seoul"],
}
REFERRERS = [
    (None, 30),
    ("linkedin.com", 20),
    ("t.co", 12),
    ("news.ycombinator.com", 9),
    ("google.com", 8),
    ("reddit.com", 6),
    ("github.com", 5),
    ("dev.to", 4),
    ("mail.google.com", 3),
    ("bing.com", 1),
    ("duckduckgo.com", 1),
]
# (browser, os, device_type, weight)
AGENTS = [
    ("Chrome", "Windows", "desktop", 24),
    ("Chrome", "Mac OS X", "desktop", 12),
    ("Safari", "Mac OS X", "desktop", 7),
    ("Firefox", "Windows", "desktop", 4),
    ("Edge", "Windows", "desktop", 5),
    ("Chrome", "Linux", "desktop", 3),
    ("Chrome Mobile", "Android", "mobile", 18),
    ("Mobile Safari", "iOS", "mobile", 16),
    ("Samsung Internet", "Android", "mobile", 3),
    ("Mobile Safari", "iOS", "tablet", 3),
    ("Chrome", "Android", "tablet", 1),
    ("Googlebot", "Unknown", "bot", 1),
]


def _pick(rng: random.Random, table: list[tuple[Any, ...]]) -> tuple[Any, ...]:
    return rng.choices(table, weights=[row[-1] for row in table])[0]


def _daily_volume(link: DemoLink, days_ago: int, rng: random.Random) -> int:
    """Baseline growth + weekday rhythm + a decaying spike after the link's launch day."""
    if days_ago > link.launch_day:
        return 0
    age = link.launch_day - days_ago
    base = 3 + 0.08 * (DAYS - days_ago)
    weekday = (datetime.now(UTC) - timedelta(days=days_ago)).weekday()
    rhythm = 0.65 if weekday >= 5 else 1.0
    spike = 40 * math.exp(-age / 2.5)
    expected = link.weight * (base * rhythm + spike)
    return max(0, int(rng.gauss(expected, expected * 0.2)))


def build_clicks(link_ids: dict[str, int], rng: random.Random) -> list[dict[str, Any]]:
    salt = get_settings().ip_hash_salt.get_secret_value()
    # A finite pool of visitors (some return repeatedly) makes unique < total, as in real life.
    visitors = [f"198.51.{i // 250}.{i % 250}" for i in range(2500)]
    now = datetime.now(UTC)
    rows: list[dict[str, Any]] = []
    for link in DEMO_LINKS:
        for days_ago in range(DAYS):
            day_start = (now - timedelta(days=days_ago)).replace(hour=0, minute=0, second=0)
            for _ in range(_daily_volume(link, days_ago, rng)):
                clicked_at = day_start + timedelta(seconds=rng.randint(0, 86_399))
                if clicked_at > now:
                    clicked_at = now - timedelta(seconds=rng.randint(1, 3600))
                country = _pick(rng, COUNTRIES)[0]
                browser, os_name, device, _ = _pick(rng, AGENTS)
                visitor = visitors[min(int(rng.paretovariate(1.2)) - 1, len(visitors) - 1)]
                visitor = visitor if rng.random() < 0.35 else rng.choice(visitors)
                rows.append(
                    {
                        "event_id": uuid.uuid4(),
                        "link_id": link_ids[link.code],
                        "clicked_at": clicked_at,
                        "referrer": _pick(rng, REFERRERS)[0],
                        "browser": browser,
                        "os": os_name,
                        "device_type": device,
                        "country": country,
                        "city": rng.choice(CITIES[country]) if country else None,
                        "ip_hash": hash_ip(visitor, salt),
                    }
                )
    return rows


async def seed(seed_value: int) -> None:
    rng = random.Random(seed_value)  # noqa: S311  (fake demo data, not security-sensitive)
    async with SessionLocal() as db:
        # Only the demo user's own data is ever removed (links and clicks cascade).
        await db.execute(delete(User).where(User.email == DEMO_EMAIL))
        taken = (
            await db.scalars(
                select(Link.short_code).where(Link.short_code.in_([d.code for d in DEMO_LINKS]))
            )
        ).all()
        if taken:
            raise SystemExit(f"Demo short codes already used by another account: {list(taken)}")
        user = User(email=DEMO_EMAIL, password_hash=hash_password(DEMO_PASSWORD))
        db.add(user)
        await db.flush()

        now = datetime.now(UTC)
        for link in DEMO_LINKS:
            db.add(
                Link(
                    user_id=user.id,
                    short_code=link.code,
                    original_url=link.url,
                    is_custom=True,
                    is_active=link.code != "old-promo",
                    created_at=now - timedelta(days=link.launch_day, hours=2),
                )
            )
        await db.flush()
        result = await db.execute(select(Link.short_code, Link.id).where(Link.user_id == user.id))
        link_ids = {code: link_id for code, link_id in result.all()}

        rows = build_clicks(link_ids, rng)
        for start in range(0, len(rows), 1000):
            await db.execute(insert(Click), rows[start : start + 1000])
        await db.commit()

    print(f"Seeded {DEMO_EMAIL} / {DEMO_PASSWORD}: {len(DEMO_LINKS)} links, {len(rows)} clicks")
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42, help="RNG seed (default 42)")
    args = parser.parse_args()
    asyncio.run(seed(args.seed))


if __name__ == "__main__":
    main()
