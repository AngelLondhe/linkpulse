"""Load test for the redirect endpoint (GET /{short_code}).

Run via benchmarks/run_benchmark.sh, or directly:
    locust -f benchmarks/locustfile.py --host http://localhost:8000

Redirects are NOT followed: we measure our API, not the destination site.
"""

import random
from pathlib import Path

from locust import FastHttpUser, between, task

CODES = [
    line.strip()
    for line in (Path(__file__).parent / "results" / "codes.txt").read_text().splitlines()
    if line.strip()
]
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)


class RedirectUser(FastHttpUser):
    wait_time = between(0, 0.05)  # near-saturation; each user is a fast-clicking client
    default_headers = {"User-Agent": BROWSER_UA}  # noqa: RUF012  (Locust's documented API)

    @task(19)
    def follow_existing_link(self) -> None:
        code = random.choice(CODES)  # noqa: S311
        with self.client.get(
            f"/{code}", name="/{code} (302)", allow_redirects=False, catch_response=True
        ) as response:
            if response.status_code != 302:
                response.failure(f"expected 302, got {response.status_code}")

    @task(1)
    def follow_unknown_link(self) -> None:
        code = f"zz{random.randint(0, 10**8)}"  # noqa: S311
        with self.client.get(
            f"/{code}", name="/{code} (404)", allow_redirects=False, catch_response=True
        ) as response:
            if response.status_code == 404:
                response.success()
            else:
                response.failure(f"expected 404, got {response.status_code}")
