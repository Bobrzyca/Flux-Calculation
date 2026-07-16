# Operations — logging & observability

How the Flux Calculation stack logs, how to read the logs, and how to change the
verbosity. Logging is structured (JSON) on both the **backend** (Python) and the
**frontend** (browser), and a single **correlation id** ties one browser action to
its backend request.

---

## 1. At a glance

| | Backend | Frontend |
|---|---|---|
| Where | `backend/app/core/logging.py`, `middleware.py` | `frontend/src/lib/logger.ts` |
| Built on | stdlib `logging` (no extra dependency) | thin wrapper over `console.*` |
| Output | one JSON object per line to **stdout** | one JSON string per line to the **browser console** |
| Level env var | `LOG_LEVEL` | `VITE_LOG_LEVEL` |
| Format env var | `LOG_FORMAT` (`json` \| `console`) | always JSON string |
| Correlation id | `X-Request-ID` (in + echoed out) | generated per request, sent as `X-Request-ID` |
| Redaction | keys matching auth/token/cookie/… masked | same key list, masked before print |

The two sides share the **same correlation id**: the frontend generates an
`X-Request-ID` per API call, sends it, and the backend logs and echoes that id — so
a console line and a server line for the same click carry the same id.

---

## 2. Backend logging

### Environment variables (`.env`, read by pydantic-settings)

| Variable | Default | Meaning |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Minimum level emitted: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. Unknown → `INFO`. |
| `LOG_FORMAT` | `json` | `json` (production, one object per line) or `console` (compact, human-friendly for local dev). |
| `SLOW_REQUEST_MS` | `1000` | Requests slower than this (ms) also emit a `slow_request` **WARNING**. |

Set them in the project-root `.env` (see `.env.example`). Example for a noisy local
session:

```bash
LOG_LEVEL=DEBUG
LOG_FORMAT=console
```

### JSON shape

```json
{
  "timestamp": "2026-07-16T10:22:31.014Z",
  "level": "INFO",
  "logger": "app.request",
  "message": "request.completed",
  "request_id": "9f2c…",
  "method": "POST",
  "path": "/api/analyses",
  "client": "172.18.0.1",
  "status_code": 201,
  "duration_ms": 42.7
}
```

`exception` (full traceback) and `stack` fields are added automatically when a log
call carries exception/stack info.

### Events logged

- **`app.startup`** — non-secret effective config (app name, data dir, log level/format,
  slow-request threshold, CORS origins, and `llm_configured` — a *boolean*, never the key).
- **`app.shutdown`** — clean shutdown.
- **`request.completed`** — one per request: method, path, client, status, `duration_ms`.
  Emitted at `INFO` for 2xx/3xx, **`WARNING`** for 4xx, **`ERROR`** for 5xx.
- **`slow_request`** — `WARNING` when `duration_ms > SLOW_REQUEST_MS`.
- **`request.failed`** — `ERROR` with full traceback (`exc_info`) when a handler raises;
  the exception then propagates to FastAPI's handler, which returns the 500.
- Any `log.*` call elsewhere in the app inherits the request's correlation id.

> **Auth / failed logins:** this app is **local, single-user, and has no
> authentication** (per the brief), so there is no login flow to log. The
> security-relevant signals that *do* exist — 4xx/5xx responses and unhandled
> exceptions with tracebacks — are logged as above. If auth is ever added, log
> failed-login attempts at `WARNING` here.

### Usage in code

```python
from app.core.logging import get_logger

log = get_logger(__name__)
log.info("analysis.matched", extra={"analysis_id": aid, "n_spots": n})
```

Pass structured fields via `extra=` — they become top-level JSON keys and are
redacted if their key looks sensitive. **Do not** log full request/response bodies.

---

## 3. Frontend logging

### Environment variable

| Variable | Default | Meaning |
|---|---|---|
| `VITE_LOG_LEVEL` | `debug` in dev, `warn` in production build | `debug` \| `info` \| `warn` \| `error` \| `silent`. Baked in at **build time** (Vite). |

Set in `frontend/.env` (see `frontend/.env.example`). Tests force `silent` via
`vite.config.ts`.

### What it logs

The API client (`src/api/client.ts`) logs each call's lifecycle through a child
logger pinned to that request's id:

- **`api.request`** (`debug`) — method + path at the start.
- **`api.response`** — method, path, `status`, `durationMs`, `correlationId`.
  `info` for 2xx/3xx, `warn` for 4xx, `error` for 5xx.
- **`api.network_error`** (`error`) — the fetch threw (offline, DNS, CORS).

Each record is `{ ts, level, msg, requestId, ...fields }`, redacted, printed as a
JSON string via the matching `console.*` method (so devtools level filtering works).

---

## 4. Redaction

Both sides mask any field whose **key** contains (case-insensitive) one of:
`authorization`, `cookie` (incl. `set-cookie`), `password`/`passwd`/`pwd`,
`secret`, `token` (access/refresh/csrf), `api_key`/`apikey`/`x-api-key`,
`access_key`, `private_key`, `credential`, `session`, `auth`. The value becomes
`***REDACTED***`. Redaction recurses into nested objects/arrays (depth-capped).

Request/response **bodies and query strings are never logged** — only method, path,
status, and timing. This keeps hand-typed field notes and any personal data out of
the logs.

---

## 5. Docker log rotation

All three services (`traefik`, `backend`, `frontend`) use the `json-file` driver
with rotation, set once via a YAML anchor in `docker-compose.yml`:

```yaml
x-logging: &default-logging
  driver: json-file
  options:
    max-size: "10m"
    max-file: "3"
```

≈ 30 MB max per container, so logs can't fill the disk. **Applying a change to this
block needs a container recreate** (`docker compose up -d`) — it does not affect an
already-running container. (Backup of the pre-logging compose file:
`docker-compose.yml.bak-before-logging`.)

---

## 6. Troubleshooting

**Read the logs**

```bash
docker compose logs -f backend            # follow backend (structured JSON lines)
docker compose logs --since 15m traefik   # last 15 min of the proxy
docker compose logs backend | jq 'select(.level=="ERROR")'   # errors only
```

**Trace one request end-to-end** — grab the `request_id`/`correlationId` from the
browser console line, then:

```bash
docker compose logs backend | jq 'select(.request_id=="9f2c…")'
```

**Turn up verbosity temporarily**

```bash
# backend: edit .env then recreate the backend container
LOG_LEVEL=DEBUG
docker compose up -d backend

# local dev, human-readable:
LOG_FORMAT=console LOG_LEVEL=DEBUG uvicorn app.main:app --reload
```

**Nothing in the logs?** Check the service is up (`docker compose ps`), that
`LOG_LEVEL` isn't set above the level you expect, and (frontend) that
`VITE_LOG_LEVEL` wasn't baked to `silent`/`error` at build time.

**A secret appears in a log line?** It means a field key wasn't recognised as
sensitive — add the substring to `SENSITIVE_KEY_PARTS` in **both**
`backend/app/core/logging.py` and `frontend/src/lib/logger.ts`, and add a test.
