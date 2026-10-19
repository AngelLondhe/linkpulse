# Deployment

A low-cost setup that fits a portfolio demo:

| Piece | Service | Notes |
| --- | --- | --- |
| API | **Render** Web Service (or Fly.io / Railway) | Docker, from `backend/` |
| Worker | **Render** Background Worker (or a Fly.io process) | Same image, different start command |
| PostgreSQL | **Neon** (or Supabase) | Use the *direct* (non-pooled) connection string |
| Redis | **Upstash** | TLS (`rediss://`) |
| Frontend | **Vercel** | Root directory `frontend/` |

> Free tiers, sleep behavior and pricing change often. Check each provider's current plans:
> background workers and always-on services sometimes need a paid tier.
> A free API that sleeps makes the first redirect after idling slow.

Deploy in this order: **database → Redis → API → worker → frontend**, then come back and set the API's `CORS_ORIGINS` to the frontend URL.

---

## 1. PostgreSQL: Neon (or Supabase)

1. Create a project and a database (e.g. `linkpulse`).
2. Copy the **direct** connection string (Neon: turn *off* "Pooled connection". Supabase: use the direct connection or the *session* pooler on port 5432).
3. Convert it for SQLAlchemy + asyncpg:
   - scheme `postgresql://` → `postgresql+asyncpg://`
   - `?sslmode=require` → `?ssl=require` (asyncpg's parameter name)

   ```
   DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@ep-xxx.region.aws.neon.tech/linkpulse?ssl=require
   ```

   Why direct: transaction-mode poolers (PgBouncer) break asyncpg's prepared-statement cache.

## 2. Redis: Upstash

1. Create a Redis database in the same region as the API.
2. Copy the TLS URL:

   ```
   REDIS_URL=rediss://default:PASSWORD@xxx.upstash.io:6379
   ```

3. Things to check against your plan:
   - The app uses Lua scripts (`EVALSHA`), `BLMOVE`/`LMOVE`, and AOF-style durability for the click queue. Confirm your plan supports them.
   - The worker polls with a blocking `BLMOVE` every `WORKER_BLOCK_TIMEOUT_SECONDS` (default 1 s) while idle. On request-metered plans, raise it (e.g. `10`) to cut idle command usage.

## 3. API: Render Web Service

1. **New → Web Service** → connect the repo.
   - Root directory: `backend`, Runtime: **Docker**
   - Health check path: `/api/health`
2. **Start command.** Render injects `$PORT`. Migrations run before the server starts, because pre-deploy commands may need a paid plan:

   ```sh
   sh -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT --no-proxy-headers"
   ```

3. **Environment variables:**

   | Variable | Value |
   | --- | --- |
   | `ENVIRONMENT` | `production` |
   | `DATABASE_URL` | from step 1 |
   | `REDIS_URL` | from step 2 |
   | `JWT_SECRET_KEY` | `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
   | `IP_HASH_SALT` | another random value (never change it later, or unique-visitor history resets) |
   | `PUBLIC_BASE_URL` | the API's public URL, e.g. `https://linkpulse-api.onrender.com` (short links are built from it) |
   | `CORS_ORIGINS` | the Vercel URL, e.g. `https://linkpulse.vercel.app` (comma-separated; no `*`) |
   | `TRUSTED_PROXIES` | the platform proxy's address range (see below) |
   | `RATE_LIMIT_ENABLED` | `true` |
   | `LOG_LEVEL` | `INFO` |
   | `SAFE_BROWSING_API_KEY` | optional (Google Cloud → enable Safe Browsing API → API key) |
   | `MAXMIND_ACCOUNT_ID`, `MAXMIND_LICENSE_KEY` | optional, for geo (see step 6) |

4. **`TRUSTED_PROXIES`** matters for correct IPs (rate limiting, unique visitors, geo). Behind Render or Fly, the direct peer is the platform's internal proxy, and the real client is in `X-Forwarded-For`.
   - To find the proxy's range, temporarily log `request.client.host` (or check the platform docs), then set it, e.g. `TRUSTED_PROXIES=10.0.0.0/8`.
   - If it's left empty, every visitor appears to come from the proxy's IP, which collapses unique-visitor counts and makes rate limits global.
   - Only trust ranges that random internet clients can't connect from.

## 4. Worker: Render Background Worker

Same repo, root `backend`, Docker runtime, **the same environment variables as the API**, plus:

| Variable | Value |
| --- | --- |
| `WORKER_ID` | a stable name, e.g. `worker-1` (one per worker instance) |
| `WORKER_BLOCK_TIMEOUT_SECONDS` | `1` (or higher on request-metered Redis plans) |

Start command:

```sh
python -m app.worker
```

`WORKER_ID` names the worker's in-flight list, so after a restart it resumes its own unfinished batch. Each worker instance needs a different id.

### Alternative: Fly.io (API and worker as two processes)

```toml
# backend/fly.toml (sketch)
app = "linkpulse-api"
primary_region = "iad"

[processes]
  app = "sh -c 'alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-proxy-headers'"
  worker = "python -m app.worker"

[http_service]
  internal_port = 8000
  processes = ["app"]
  force_https = true

[[http_service.checks]]
  path = "/api/health"
  interval = "15s"
  timeout = "3s"
```

Set the same variables with `fly secrets set KEY=value …`. Give the worker a stable `WORKER_ID`, e.g. from the machine's environment.

## 5. Frontend: Vercel

1. **New Project** → import the repo → **Root Directory: `frontend`**. The framework preset should detect Vite.
2. Build command `npm run build`, output directory `dist`. `frontend/vercel.json` already rewrites all paths to `index.html`, so client-side routes work on reload.
3. Environment variables (Vite inlines them **at build time**, so redeploy after changing them):

   | Variable | Value |
   | --- | --- |
   | `VITE_API_BASE_URL` | the API URL, e.g. `https://linkpulse-api.onrender.com` |
   | `VITE_SHOW_DEMO_LOGIN` | `true` for the portfolio demo |

4. Add the Vercel URL to the API's `CORS_ORIGINS` and redeploy the API.

## 6. Optional: GeoLite2 (country/city)

1. Create a free MaxMind account and generate a license key.
2. Set `MAXMIND_ACCOUNT_ID` and `MAXMIND_LICENSE_KEY` on the API and the worker.
3. Download the database at build time:
   - Docker: add `RUN ./scripts/download_geolite.sh` to the Dockerfile (pass the credentials as build args or secrets).
   - Without Docker: run it in the build command.

   Without credentials the script skips the download and geo shows "Unknown". MaxMind's license doesn't allow committing the `.mmdb` file to the repo.

## 7. Seed the demo account

Run once (Render: **Shell** tab; Fly: `fly ssh console`):

```sh
python -m scripts.seed
```

This creates `demo@linkpulse.dev` / `demo-password-123` with 8 links and about 5,000 clicks. Re-running only replaces the demo user's own data.

## 8. Post-deploy checklist

- [ ] `GET https://<api>/api/health` → `{"status":"ok", …}`
- [ ] Sign in on the frontend with **Explore the demo account**; every chart renders
- [ ] Create a link, open it in a private window, and see the click appear within ~30 s
- [ ] Worker logs show `Processed N event(s)`
- [ ] Unique visitors > 1 when testing from two networks (confirms `TRUSTED_PROXIES`)
- [ ] Add the live URL to the README and update the CI and coverage badge owner/repo
