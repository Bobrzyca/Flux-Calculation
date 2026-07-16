# Report — production-grade structured logging

Task: set up structured logging across the whole app (backend + frontend), with
correlation ids, redaction, key-event logging, Docker log rotation, tests, and docs.

## Summary

A well-built logging implementation was **already in progress** on this branch
(uncommitted). I evaluated it against best practice, found it sound, and **did not
duplicate it**. My additions closed the three remaining gaps: Docker log rotation,
operational documentation, and a report. Everything is verified green.

## 1. Stack & existing logging (detected)

- **Backend:** Python 3.14 + FastAPI (uvicorn), pydantic-settings, pytest, ruff, mypy.
- **Frontend:** React 19 + Vite + TypeScript, Vitest, oxlint + Prettier.
- **Deploy:** Docker Compose — `traefik` (TLS edge) + `backend` + `frontend`, all
  `restart: always`, behind Traefik at `flux-calculation.aibr.cz`.
- **Existing logging (uncommitted, kept as-is):**
  - `backend/app/core/logging.py` — stdlib `logging` with a JSON formatter and a
    console formatter, a `request_id` `ContextVar`, a redaction helper, and uvicorn
    log takeover.
  - `backend/app/core/middleware.py` — `RequestContextMiddleware`: correlation id
    in/out, per-request completion log, slow-request warning, exception logging.
  - `backend/app/core/config.py` — `LOG_LEVEL`, `LOG_FORMAT`, `SLOW_REQUEST_MS`.
  - `backend/app/main.py` — configures logging at import, logs `app.startup` with
    non-secret config, wires the middleware outermost.
  - `frontend/src/lib/logger.ts` — leveled, structured, redacting console logger;
    `frontend/src/api/client.ts` threads a per-request `X-Request-ID` and logs the
    request lifecycle.
  - Tests already present: `backend/tests/test_logging.py`,
    `frontend/src/lib/logger.test.ts`, correlation-id cases in `client.test.ts`.

**Evaluation:** this already meets task items 2–5 to a high standard — stdlib JSON
logging gated by `LOG_LEVEL`; correlation id generated/propagated and echoed in the
`X-Request-ID` response header and every related log line; recursive key-based
redaction (auth, cookie/set-cookie, password, token, api key, session, credential,
…) on both sides; and key events logged (startup + non-secret config, per-request
completion at level-by-status, slow requests, unhandled exceptions with traceback).
Bodies and query strings are deliberately never logged. No changes were needed.

## 2. Changes I made (the gaps)

| Item | File | Change |
|---|---|---|
| Docker log rotation (task 6) | `docker-compose.yml` | Added an `x-logging` anchor (`json-file`, `max-size: 10m`, `max-file: 3`) applied to all three services. Backup: `docker-compose.yml.bak-before-logging`. |
| Docs (task 8) | `docs/operations.md` (new) | Full logging reference: env vars, JSON shapes, events, redaction, rotation, and troubleshooting (incl. tracing one request across frontend↔backend by id). |
| Docs pointer | `backend/README.md` | Short "Logging" section linking to `docs/operations.md`. |
| Report (task 8) | `report.md` (this file) | — |

Note on **failed logins / auth events**: the app is local, single-user, and has
**no authentication** (per the brief), so there is no login flow to log. The
security-relevant signals that do exist (4xx/5xx and unhandled exceptions) are
logged. Documented as such in `docs/operations.md`.

## 3. Verification (all green)

Backend (`backend/`, venv):

```
pytest                 -> 138 passed
ruff check .           -> All checks passed!
ruff format --check .  -> 60 files already formatted
mypy .                 -> Success: no issues found in 60 source files
```

Frontend (`frontend/`):

```
npm test               -> 56 passed (7 files)
npm run lint           -> clean except one PRE-EXISTING warning in SpotDetail.tsx
                          (react-hooks/exhaustive-deps; unrelated to logging)
npm run format:check   -> All matched files use Prettier code style!
npm run typecheck      -> clean
npm run build          -> built OK (pre-existing Plotly chunk-size note only)
```

Docker: `docker compose config` renders the rotation block on all three services.
The **running stack was not touched** — the compose edit only takes effect on the
next `docker compose up -d` (container recreate).

The logging test coverage (task 7) — redaction, correlation-id middleware, and error
logging — was already present and passes; no new tests were required since I added no
new application logic (only config/docs).

## 4. Follow-ups for the user

1. **Apply log rotation to the live stack** when convenient:
   `docker compose up -d` from the repo root. This **recreates** the containers
   (brief proxy blip; certs persist in the `letsencrypt` volume) — per the project
   rule I did not restart running services without asking. To roll back the compose
   change: restore `docker-compose.yml.bak-before-logging`.
2. **Commit** the changes (nothing is committed yet). Suggested split:
   `feat(logging): structured JSON logging + request correlation + redaction`
   (backend + frontend code) and `chore(ops): docker log rotation + logging docs`.
3. The frontend `README.md` is still the Vite template stub; the real frontend guide
   lives in `frontend/CLAUDE.md`. Left as-is to keep this change focused.

## Files touched

New: `docs/operations.md`, `report.md`, `docker-compose.yml.bak-before-logging`.
Edited: `docker-compose.yml`, `backend/README.md`.
Pre-existing logging work (kept, verified): `backend/app/core/logging.py`,
`backend/app/core/middleware.py`, `backend/app/core/config.py`, `backend/app/main.py`,
`backend/tests/test_logging.py`, `frontend/src/lib/logger.ts`,
`frontend/src/lib/logger.test.ts`, `frontend/src/api/client.ts`,
`frontend/src/api/client.test.ts`, `frontend/src/vite-env.d.ts`,
`frontend/vite.config.ts`, `frontend/.env.example`.

---

# Report — error/performance monitoring (Sentry + Uptime Kuma)

Task: set up error/performance monitoring, integrate the SDK into backend +
frontend, connect it to logging/releases/alerts, and add uptime monitoring —
all through the Docker/Traefik deployment.

## Summary

- **Error/performance monitoring → hosted Sentry (free tier).** Self-hosting was
  ruled out on the numbers (see below) — the box has ~1.6 GiB RAM free.
- **SDK integrated** into both apps (backend `sentry-sdk[fastapi]`, frontend
  `@sentry/react`), **disabled unless a DSN is set** so the app runs unchanged
  today. Wired to the correlation id, redaction, releases (git SHA) and source
  maps.
- **Uptime Kuma deployed** (`/root/uptime-kuma`), **localhost-only** (127.0.0.1),
  reached via SSH tunnel — no new public surface, no DNS/cert needed.
- Nothing new is exposed without HTTPS; no secrets committed; Traefik config was
  **not** touched (Kuma needs no route).

## 1. Server map & the hosting decision (with numbers)

| Resource | Value | Verdict |
|---|---|---|
| RAM | 3.7 GiB total, **~1.6 GiB available**; swap 2 GiB (417 MiB used) | tight |
| CPU | 2 vCPUs, load ~0.3 | ok |
| Disk | 75 GB, **47 GB free** | ok |
| Running | Traefik, backend (247 MiB), frontend, n8n (213 MiB), VS Code server (~500 MiB) | — |
| Existing monitoring | **none** | — |

- **Self-hosted Sentry**: official minimum **16 GB RAM** (~20 containers). Impossible.
- **GlitchTip** (lighter): ~1–2 GB realistic; with ~1.6 GB free and a live pandas
  backend that spikes, it risks OOM-killing production. Rejected.
- **DNS**: only `flux-calculation.aibr.cz` → `65.21.2.126` (this host). Every
  `*.kulis.aibr.cz` (incl. `sentry.kulis.aibr.cz`) points to a **different host**
  (185.102.21.194) with a broken AAAA — so a `sentry.<surname>` subdomain could not
  get a cert here anyway. Second, independent reason not to self-host.
- **→ Hosted Sentry** (zero server load) + **Uptime Kuma** (~114 MiB, localhost).

## 2. SDK integration

### Backend (`backend/app/core/monitoring.py`)
- `sentry-sdk[fastapi]` — FastAPI/Starlette integrations auto-capture **unhandled
  exceptions (→ 5xx)** and performance transactions. Handled 4xx `api_error`s are
  intentionally *not* sent (expected validation, not incidents).
- `configure_monitoring(...)` called in `app/main.py` **before** the app is built;
  **no-op when `SENTRY_DSN` is unset** (verified: app + 144 tests run without it).
- **Correlation id link**: `before_send` reads the same `request_id` context var the
  logger uses and stamps it as a `request_id` **tag** on every event → an issue
  links straight to the `request.*` log lines.
- **Redaction**: `before_send` scrubs request headers/cookies/body, `extra`,
  `contexts`, and **captured stack-frame locals** by key, reusing the logger's
  `SENSITIVE_KEY_PARTS`. `send_default_pii=False`; `user` (IP/id) dropped.
- `capture_exception(err, **tags)` helper for explicit domain-error reporting.

### Frontend (`frontend/src/lib/monitoring.ts`)
- `@sentry/react` — auto-captures **uncaught errors + unhandled promise
  rejections**; `browserTracingIntegration` adds navigation performance.
  `Sentry.ErrorBoundary` wraps the app in `main.tsx`.
- **Route context**: `App.tsx` tags the active scope with `route = pathname` on
  each navigation.
- **Correlation id link**: the API client adds a **breadcrumb per request** carrying
  the same `requestId` it sends as `X-Request-ID`, and `captureApiError` reports
  network failures tagged with that id → frontend and backend events share the id.
- **Redaction**: `scrubEvent` masks the same key list before send;
  `sendDefaultPii=false`; `user` dropped.
- **Disabled unless `VITE_SENTRY_DSN` is set** (inlined at build time).

### Releases & source maps
- **Release = git SHA** in both apps. Backend reads `SENTRY_RELEASE` (compose
  `environment:`), falling back to `git rev-parse HEAD` in a dev checkout; frontend
  bakes `VITE_SENTRY_RELEASE` at build. Deploy with
  `export SENTRY_RELEASE=$(git rev-parse HEAD)` before `docker compose ... --build`.
- **Frontend source maps** upload to Sentry **only when `SENTRY_AUTH_TOKEN` is set**
  at build; they are generated **`hidden`** (no `sourceMappingURL`) and **deleted
  from `dist` after upload** (`@sentry/vite-plugin`), so nginx never serves them.
  Verified: a build without the token emits **no `.map` files**.

## 3. Environment variables

| Variable | App | Where | Default | Purpose |
|---|---|---|---|---|
| `SENTRY_DSN` | backend | root `.env` (`env_file`) | empty=off | server DSN |
| `VITE_SENTRY_DSN` | frontend | build arg | empty=off | browser DSN (public) |
| `SENTRY_ENVIRONMENT` / `VITE_SENTRY_ENVIRONMENT` | both | `.env` / build arg | production | event env tag |
| `SENTRY_RELEASE` | both | shell → compose | empty | git SHA (release) |
| `SENTRY_TRACES_SAMPLE_RATE` / `VITE_SENTRY_TRACES_SAMPLE_RATE` | both | `.env` / build arg | 0 | perf sampling 0..1 |
| `SENTRY_AUTH_TOKEN` | frontend build | shell/`.env` (**secret**) | empty | source-map upload |
| `SENTRY_ORG`, `SENTRY_PROJECT` | frontend build | `.env` | empty | source-map upload |

All blank by default → **monitoring is fully off and the app is unchanged**.

## 4. Proposed alert rules (configure in Sentry — no tokens in repo)

Set these in the Sentry project (Alerts → Create). Route to **one owner** (below).
Thresholds chosen to avoid spam; Sentry dedups by issue fingerprint automatically.

| # | Rule | Condition | Why it won't spam |
|---|---|---|---|
| 1 | **New production error** | An issue is *first seen*, `environment:production` | Fires once per new issue, not per event |
| 2 | **Critical backend error** | New/regressed issue tagged `level:error` from `logger:app.*` or `project:backend` | Scoped to real server errors |
| 3 | **Elevated error rate** | # errors > **20 in 1h** (per project) | Rate window + threshold; one alert per window |
| 4 | **Regression after release** | Issue changes state to *regressed* (resolved→reappeared), any release | Only on genuine reopen; ties to the release SHA |
| 5 | **Slow endpoint** | p95 transaction duration > **1000 ms** over 10 min (matches backend `SLOW_REQUEST_MS`) | Percentile + window; needs traces on |

- **Ownership/routing**: point all five at a single channel with a named owner.
  Recommended: **email to `zuzakulis@gmail.com`** (zero setup, no token) as the
  default owner; optionally add a **Slack** or **Telegram** integration later via
  Sentry's UI (its OAuth — **no token stored in this repo**). A generic **webhook**
  (e.g. into the existing n8n) is also possible; keep any webhook URL/token in the
  server `.env`, never committed.
- **Dedup/quiet hours**: enable Sentry's *issue-level* alerting (not per-event), a
  default **rate limit of 1 notification / issue / hour**, and spike protection.

## 5. Uptime Kuma

- `/root/uptime-kuma/docker-compose.yml`: `louislam/uptime-kuma:1`,
  `restart: always`, named volume `uptime-kuma-data`, **healthcheck**, **log
  rotation** (10 MB × 3). Bound to **`127.0.0.1:3001`** only — verified via `ss`
  (loopback), status `healthy`, 114 MiB RAM.
- **Access**: `ssh -L 3001:localhost:3001 root@65.21.2.126` → http://localhost:3001.
  Create the owner account on first visit (like n8n). Not on `flux-net` — it probes
  from the outside like a real user.
- **Monitors to add** (in the UI): HTTPS keyword/status monitors for
  `https://flux-calculation.aibr.cz/api/health` (expect `"status":"ok"`),
  `https://flux-calculation.aibr.cz/` (200), and `https://flux-calculation.aibr.cz/n8n/`
  (200). Add a TLS-cert-expiry notification. Interval 60 s; retries 3 before "down".

## 6. Verification

- **Backend**: `pytest` **144 passed** (6 new in `test_monitoring.py`); `ruff`,
  `ruff format --check`, `mypy .` all clean. Runtime smoke test: Sentry `init`
  succeeds with a DSN, `before_send` attaches the `request_id` tag and redacts the
  `Authorization` header.
- **Frontend**: `typecheck` clean; `format:check` clean; my tests
  (`monitoring` + `logger` + `client`) **35/35 deterministic over 5 runs**;
  `npm run build` succeeds and emits **no public `.map` files**.
- **Docker**: `docker compose config` valid with the new env/build args. Uptime Kuma
  live and healthy on loopback.

## 7. Residual risks / follow-ups

1. **Deploy step (needs your go-ahead).** The SDK ships **dormant**. To activate:
   create a Sentry project, put the DSNs in `.env`, then
   `export SENTRY_RELEASE=$(git rev-parse HEAD) && docker compose up -d --build`.
   This **recreates the running app containers** (brief blip) — I did not do it
   (project rule: ask before restarting running services). Backup of the pre-Sentry
   compose: `docker-compose.yml.bak-before-sentry`.
2. **`SENTRY_AUTH_TOKEN` as a build arg** lands in image layer history. It is a
   *secret*. Mitigations: build with BuildKit `--secret` instead, or run the
   source-map upload outside Docker (`sentry-cli sourcemaps upload`) and never pass
   the token as an arg. Documented in compose/Dockerfile comments. Low risk on a
   single-user private host, but noted.
3. **Frontend test suite is flaky on this 2-vCPU box** — one pre-existing RTL test
   (`SpotDetail.test.tsx`, `userEvent.type` + `findBy`, ~2 s) intermittently times
   out under CPU contention. **Not caused by this change**: the stashed baseline
   flaked *more* (3–4 tests/run) than my version (0–1). My own tests are
   deterministic. Suggested later fix: raise that test's `findBy` timeout or reduce
   vitest concurrency; out of scope here.
4. `@sentry/cli` postinstall was skipped by npm's allow-scripts; run
   `npm approve-scripts @sentry/cli` (or install its binary) before the first
   source-map upload build.
5. **Free-tier quota**: `traces_sample_rate` defaults to **0** (no perf events) to
   protect the quota; raise it (e.g. 0.1) once volume is known.

## Files touched (this task)

New: `backend/app/core/monitoring.py`, `backend/tests/test_monitoring.py`,
`frontend/src/lib/monitoring.ts`, `frontend/src/lib/monitoring.test.ts`,
`/root/uptime-kuma/docker-compose.yml`, `docker-compose.yml.bak-before-sentry`.
Edited: `backend/pyproject.toml`, `backend/app/core/config.py`,
`backend/app/main.py`, `backend/.env.example`, `frontend/package.json`
(+ lockfile), `frontend/src/main.tsx`, `frontend/src/App.tsx`,
`frontend/src/api/client.ts`, `frontend/src/vite-env.d.ts`,
`frontend/vite.config.ts`, `frontend/.env.example`, `frontend/Dockerfile`,
`docker-compose.yml`, root `.env.example`, `CLAUDE.md` files.
