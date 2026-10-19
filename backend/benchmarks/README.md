# Redirect benchmark

Measures `GET /{short_code}`, the hot path, with the Redis link cache **on** and **off**
(`LINK_CACHE_ENABLED=false` makes every redirect query Postgres).

## What the run does

1. `prepare.py` creates a `bench@linkpulse.dev` user with 1,000 links and writes their codes to
   `results/codes.txt`.
2. For each mode, it starts uvicorn (`WORKERS` processes) with rate limiting off. One load
   generator is a single IP and would otherwise get throttled.
3. A 10 s warm-up (not recorded) fills the cache and connection pools.
4. Locust drives `USERS` concurrent clients for `DURATION`. 95% of requests hit existing codes
   (expect 302) and 5% hit unknown codes (expect 404). Redirects are **not** followed.
5. A scratch Redis DB (`BENCH_REDIS_URL`, default DB 2) is flushed before and after each pass to
   drop the queued click events.
6. `summarize.py` writes `results/summary.md` (req/s, p50/p95/p99).

## Run it

```bash
cd backend
source .venv/bin/activate          # dev deps include locust
# Postgres + Redis running, DATABASE_URL set (../.env works)
./benchmarks/run_benchmark.sh
# Tunables: USERS=100 SPAWN=25 DURATION=60s WORKERS=2 PORT=8100 LINKS=1000
```

On macOS the script re-runs itself under `caffeinate` so the machine can't sleep mid-run. An
earlier attempt without it produced garbage: a "60 s" run took 15 minutes of wall-clock time.

## Reading the results honestly

- Locust and the API share one machine, so they compete for CPU. Absolute numbers are a
  lower bound, and the **cache on vs off comparison** is the meaningful part.
- Laptop results on battery are throttled. Plug in for a fair run.
- The worker isn't running during the benchmark, so click events just accumulate in the
  scratch Redis DB. This isolates the request path, which is exactly what is being measured.
- For production-like numbers, run Locust from a separate machine against the deployed API.
