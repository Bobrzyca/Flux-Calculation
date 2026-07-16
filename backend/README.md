# Flux Calculation — backend

Python + FastAPI backend for the Flux Calculation app. Ingests raw closed-chamber
greenhouse-gas measurement files, matches them by timestamp, and computes CO₂ and
CH₄ flux. See `backend/CLAUDE.md` for the full developer guide.

## Quick start

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload
curl localhost:8000/api/health
```

## Test & lint

```bash
pytest
ruff check . && ruff format --check .
mypy .
```

## Logging

Structured JSON logging (levels via `LOG_LEVEL`, format via `LOG_FORMAT`, slow-request
threshold via `SLOW_REQUEST_MS`), a per-request correlation id (`X-Request-ID`), and
secret redaction. See [`../docs/operations.md`](../docs/operations.md) for the full
reference (env vars, log shape, and troubleshooting).
