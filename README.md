# Linkpulse

A URL shortener with a real-time click-analytics dashboard (FastAPI · PostgreSQL · Redis · React).

> 🚧 Work in progress: this README is completed in the final phase.

## Quick start

```bash
cp .env.example .env
docker compose up --build
curl http://localhost:8000/api/health
```

## Backend development (without Docker)

Requires Python 3.12 and a local Postgres + Redis matching `.env`.

```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload --no-proxy-headers

# quality checks (tests use the `shortener_test` database and Redis DB 15)
pytest --cov
ruff check . && ruff format --check . && mypy app tests
```
