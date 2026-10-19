#!/usr/bin/env bash
# Benchmark GET /{short_code} with the Redis link cache enabled vs disabled.
#
# Prereqs: Postgres + Redis running and DATABASE_URL set (e.g. via ../.env), dev deps installed.
# Usage (from backend/):  ./benchmarks/run_benchmark.sh
# Tunables: USERS=100 SPAWN=25 DURATION=60s WORKERS=2 PORT=8100 LINKS=1000
#           BENCH_REDIS_URL=redis://localhost:6379/2  (a scratch DB: it is FLUSHED)
set -euo pipefail
cd "$(dirname "$0")/.."

# On macOS, keep the machine awake: idle sleep suspends both Locust and the server and
# silently ruins the measurement (a "60s" run once took 15 minutes of wall time).
if [[ -z "${BENCH_CAFFEINATED:-}" ]] && command -v caffeinate >/dev/null; then
  export BENCH_CAFFEINATED=1
  exec caffeinate -dimsu "$0" "$@"
fi

PY=${PYTHON:-python}
USERS=${USERS:-100}
SPAWN=${SPAWN:-25}
DURATION=${DURATION:-60s}
WORKERS=${WORKERS:-2}
PORT=${PORT:-8100}
LINKS=${LINKS:-1000}
BENCH_REDIS_URL=${BENCH_REDIS_URL:-redis://localhost:6379/2}
RESULTS=benchmarks/results
mkdir -p "$RESULTS"

flush_bench_redis() {
  "$PY" -c "import redis,sys; redis.Redis.from_url(sys.argv[1]).flushdb()" "$BENCH_REDIS_URL"
}

"$PY" -m benchmarks.prepare --links "$LINKS"

for mode in cached uncached; do
  [[ $mode == cached ]] && cache=true || cache=false
  echo "=== $mode (LINK_CACHE_ENABLED=$cache) ==="
  flush_bench_redis
  # Rate limiting off: the load generator is one IP. Access log off: measure the app, not I/O.
  REDIS_URL=$BENCH_REDIS_URL LINK_CACHE_ENABLED=$cache RATE_LIMIT_ENABLED=false LOG_LEVEL=WARNING \
    "$PY" -m uvicorn app.main:app --port "$PORT" --workers "$WORKERS" \
    --no-access-log --no-proxy-headers --log-level warning &
  server=$!
  trap 'kill $server 2>/dev/null || true' EXIT
  for _ in $(seq 1 60); do curl -sf "http://localhost:$PORT/api/health" >/dev/null && break; sleep 0.5; done

  # Warm-up (not recorded): fills the cache and the connection pools.
  "$PY" -m locust -f benchmarks/locustfile.py --headless -u 20 -r 20 -t 10s \
    --host "http://localhost:$PORT" --only-summary >/dev/null 2>&1 || true

  # Locust exits 1 if any request failed; failures are already in the CSV, so keep going.
  "$PY" -m locust -f benchmarks/locustfile.py --headless -u "$USERS" -r "$SPAWN" -t "$DURATION" \
    --host "http://localhost:$PORT" --csv "$RESULTS/$mode" --only-summary || true

  kill "$server"; wait "$server" 2>/dev/null || true
  trap - EXIT
  flush_bench_redis   # drop the click events queued during the run
done

"$PY" -m benchmarks.summarize
