"""Create a benchmark user with N links and write their codes for Locust.

Usage (from backend/):  python -m benchmarks.prepare --links 1000
"""

import argparse
import asyncio
from pathlib import Path

from sqlalchemy import delete, insert

from app.core.security import hash_password
from app.db.session import SessionLocal, engine
from app.models import Link, User
from app.utils.shortcode import generate_short_code

BENCH_EMAIL = "bench@linkpulse.dev"
CODES_FILE = Path(__file__).parent / "results" / "codes.txt"


async def prepare(count: int) -> None:
    async with SessionLocal() as db:
        await db.execute(delete(User).where(User.email == BENCH_EMAIL))  # cascades to links
        user = User(email=BENCH_EMAIL, password_hash=hash_password("not-used-for-login"))
        db.add(user)
        await db.flush()
        codes = [f"b{generate_short_code(9)}" for _ in range(count)]
        await db.execute(
            insert(Link),
            [
                {"user_id": user.id, "short_code": code, "original_url": f"https://example.com/{i}"}
                for i, code in enumerate(codes)
            ],
        )
        await db.commit()
    await engine.dispose()
    CODES_FILE.parent.mkdir(parents=True, exist_ok=True)
    CODES_FILE.write_text("\n".join(codes) + "\n")
    print(f"Prepared {count} links for {BENCH_EMAIL}; codes in {CODES_FILE}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--links", type=int, default=1000)
    asyncio.run(prepare(parser.parse_args().links))


if __name__ == "__main__":
    main()
