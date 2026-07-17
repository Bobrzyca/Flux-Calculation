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

---

# Report — testing structure, security scanning & CI

Task: build out the test / CI / IaC-security structure from the target repo tree.

> **⚠ Superseded in part by [“Report — CI/CD pipeline (test → deploy)”](#report--cicd-pipeline-test--deploy) below.**
> That later task extended `test.yml` (added the `audit` and `docker-build`+Trivy jobs)
> and **rewrote `deploy.yml` to actually deploy** over SSH after tests pass on `main`.
> Where this section and the CI/CD section disagree, the CI/CD section is current. The
> bullets/paragraphs below are kept as the record of the original testing-structure task.

## Summary (scope confirmed with you)

- **Additive test layout** — the existing green suites stay where they are; the new
  `e2e` / `integration` / `security` dirs are added *around* them (no risky
  restructuring of passing tests).
- **CI wired to the current suites now**, deeper e2e/security tests later.
- **`deploy.yml` originally did NOT deploy** — it validated image builds only, with a
  disabled SSH-deploy scaffold. **This was later replaced** by a real test→deploy
  pipeline (see the CI/CD section); the description below is historical.
- All parts verified locally (CI itself only runs once pushed to GitHub).

## 1. Backend tests (`backend/tests/`)

- **New `tests/security/test_security.py`** (6 tests, real): app not in debug mode,
  CORS is not wildcard / doesn't reflect an arbitrary origin, unknown resource →
  clean structured 404 (no traceback / internal path leaked), a sensitive request
  header is never echoed, every response carries a correlation id.
- `tests/unit/` and `tests/integration/` created with READMEs mirroring the target
  tree; the existing flat suite (unit + `test_e2e.py` + `test_api_*.py`) stays and
  runs. `tests/README.md` documents the layout and why nothing was moved.
- **`pytest` → 150 passed** (144 + 6); ruff/format/mypy clean.

## 2. Frontend tests (`frontend/`)

- **Vitest** unit/component tests stay co-located under `src/**` (project
  convention); `vite.config.ts` `test.include` scopes Vitest to `src/**` so it never
  grabs the Playwright specs. **58 passed.**
- **Playwright** added: `playwright.config.ts` (builds + `vite preview` on :4173),
  `tests/e2e/smoke.spec.ts` (2 backend-independent smoke tests: app shell + title
  render, unknown route still renders). Script `npm run test:e2e`. **2 passed
  locally** (needed `playwright install --with-deps chromium`; `libnspr4` etc. were
  installed on this box). `tests/README.md` documents the two layers.

## 3. Security scanning (`infrastructure/checkov/`)

- `.checkov.yaml` scans **dockerfile + github_actions + secrets** (checkov v3 has no
  docker-compose scanner — noted; compose reviewed by hand). Vendored dirs skipped.
- **Findings fixed, not suppressed**: added a `HEALTHCHECK` to both Dockerfiles
  (was `CKV_DOCKER_2`). One justified skip: **`CKV_DOCKER_3`** (nginx master needs
  root to bind :80; frontend is internal-only behind Traefik; backend runs non-root).
- **Result: dockerfile 187/0, github_actions 156/0, secrets 0 findings → exit 0.**

## 4. CI (`.github/workflows/`)

**`test.yml`** (push to `main`/`flux-improvements`, PRs, manual) — `permissions:
contents: read`:
- `backend` — `pip install -e ".[dev]"` → ruff, ruff format --check, mypy, pytest.
- `frontend` — `npm ci` → lint, format:check, typecheck, vitest, build.
- `e2e` — `npm ci` → `playwright install --with-deps chromium` → `test:e2e`; uploads
  the Playwright report artifact.
- `checkov` — `pip install checkov` → scan with the config above.

**`deploy.yml`** — *(historical: originally `workflow_dispatch`-only, built the images
with no server contact and an `if: false` deploy scaffold.)* **Now a real deploy**:
triggered by `workflow_run` after `test` succeeds on `main`, it SSHes to the VPS and
runs `flux-deploy <tested-SHA>` (health-checked, rollback-safe). See the full
[CI/CD section](#report--cicd-pipeline-test--deploy) for the current design, secrets,
and server setup.

## 5. Verification (local)

Every command a workflow runs was executed locally and passes: backend
150 passed + ruff/format/mypy clean; frontend 58 unit + 2 e2e + lint/format/
typecheck/build clean; checkov exit 0. YAML of both workflows validated. The
workflows themselves run only after the branch is pushed to GitHub.

## 6. Residual notes / follow-ups

1. **Not committed / pushed** — you commit + push when ready; CI triggers on push.
2. **Deeper tests later** (as agreed): backend `unit`/`integration` split, and
   Playwright journeys that need a live backend (upload → confirm → results).
3. **Pre-existing frontend flake** (`SpotDetail.test.tsx`) under 2-vCPU contention
   still applies to the `frontend` CI job; GitHub runners have 2+ cores and vitest
   isn't parallel-heavy, but if it flakes there, raise that test's `findBy` timeout.
4. **Python 3.14 / Node 24** pinned in CI to match the server toolchain.
5. `@sentry/cli` postinstall is skipped by npm's allow-scripts — only matters for
   source-map upload, not these workflows.

## Files added/changed (this task)

New: `backend/tests/security/{__init__.py,test_security.py}`,
`backend/tests/{README.md,unit/README.md,integration/README.md}`,
`frontend/playwright.config.ts`, `frontend/tests/e2e/smoke.spec.ts`,
`frontend/tests/README.md`, `infrastructure/checkov/{.checkov.yaml,README.md}`,
`.github/workflows/{test.yml,deploy.yml}`.
Edited: `backend/Dockerfile`, `frontend/Dockerfile` (HEALTHCHECK),
`frontend/package.json` (+ lockfile: `@playwright/test`), `frontend/vite.config.ts`
(vitest `include`), `frontend/.gitignore` (Playwright artifacts), `CLAUDE.md` files.

---

# Report — security analysis

Static analysis + configuration review of the deployed Flux Calculation stack.
No aggressive/penetration testing against production; live checks were limited to
read-only HTTP requests and local inspection. Date: 2026-07-16.

## Executive summary

The **application code is in good shape** — parameterised DB queries, safe file
storage (server-generated UUIDs, allow-listed roles, 50 MB upload cap), thorough
log/monitoring redaction, no dependency CVEs (`npm audit` and `pip-audit` both
clean), and CORS that does not reflect hostile origins.

The material risk is at the **deployment/perimeter layer**, and the two headline
issues compound each other:

1. **`SEC-01` — the box accepts SSH passwords, has no firewall and no fail2ban, and
   is being actively brute-forced** (15,777 failed SSH logins in 7 days).
2. **`SEC-02` — an app designed to be "local, single-user, no auth" is deployed on
   the public internet with its API fully open** — anyone can read, create and
   **delete** all analyses/data unauthenticated.

Add **no security headers**, **no rate limiting**, a **publicly exposed n8n**, and
an **outdated frontend image (107 fixable OS CVEs)**. One quick win was applied
during the review (`.env` files 644 → 600). Nothing else was changed, because the
remaining fixes either restart running services or touch SSH/firewall, which this
server's rules require confirming first.

**Overall posture: MEDIUM-HIGH risk**, dominated by perimeter exposure, not code.

## Scope

- In scope: `Flux-Calculation` stack (Traefik, backend, frontend), the co-hosted
  `n8n` and `uptime-kuma`, the host's network/SSH/firewall posture, secrets
  handling, dependencies, and container images.
- Methods: config/code review; `npm audit`, `pip-audit`, `semgrep`, `gitleaks`
  (working tree + 27 commits of history), `checkov`, `trivy` (via its official
  Docker image); read-only `curl` against the live site; `docker inspect`, `ss`,
  `sshd -T`, `journalctl`.
- Out of scope: exploitation, credential attacks, load/DoS testing, third-party
  upstream images' internals beyond CVE enumeration.

## Architecture overview

```
Internet ──▶ Traefik v3.5 (host :80/:443, HTTP→HTTPS 301, Let's Encrypt)
             │  file provider (traefik/dynamic.yml); no Docker socket; dashboard OFF
             ├─ Host(flux-calculation.aibr.cz) && /api  ▶ backend  (FastAPI/uvicorn, :8000, user appuser)
             ├─ Host(flux-calculation.aibr.cz) && /n8n  ▶ n8n      (:5678, stripPrefix, own login)
             └─ Host(flux-calculation.aibr.cz)          ▶ frontend (nginx:1.27-alpine, :80, root)
Backend ──▶ SQLite file (backend-data volume) + raw uploads on disk; LLM key unset.
Localhost only: uptime-kuma (127.0.0.1:3001). Not on flux-net.
Env: DOMAIN, ACME_EMAIL, APP_NAME, DATA_DIR, DATABASE_URL, CORS_ORIGINS, LLM_API_KEY
     (empty), SENTRY_* (unset). No secret values printed here.
```

Positive baseline controls observed: HTTP→HTTPS redirect (301), valid Let's Encrypt
cert, Traefik API/dashboard disabled, backend runs non-root (`appuser` 10001), all
containers unprivileged with no added caps, `restart: always`, log rotation on the
Flux stack, n8n `N8N_SECURE_COOKIE=true` with the owner account already configured
(`/n8n/rest/login` → 401), upload size capped (50 MB app / 100 MB nginx).

## Findings table

| ID | Severity | Component | Finding | Status |
|----|----------|-----------|---------|--------|
| SEC-01 | **High** | Host / SSH | Password SSH auth + no firewall + no fail2ban; 15,777 failed logins/7d | open |
| SEC-02 | **High** | Backend / perimeter | Unauthenticated API exposed to the public internet (read/write/delete all data) | **fixed** |
| SEC-03 | Medium | HTTP (Traefik/nginx) | No security headers (HSTS, CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy) | open |
| SEC-04 | Medium | Frontend image | 107 fixable OS CVEs (2 Critical, 35 High) — outdated `nginx:1.27-alpine` | open |
| SEC-05 | Medium | HTTP / Traefik | No rate limiting (n8n + API brute-force / DoS) | open |
| SEC-06 | Medium | n8n | Admin/automation tool publicly reachable on the internet | **fixed** |
| SEC-07 | Medium | Secrets / Docker | `SENTRY_AUTH_TOKEN` passed as build-arg → baked into image history | open |
| SEC-08 | Medium | Secrets / files | `.env` files world-readable (644) | **fixed** |
| SEC-09 | Low | Backend image | OS CVEs (3 Critical, 19 High) with **no upstream fix available** (base OS) | accepted |
| SEC-10 | Low | n8n / secrets | Stale, unused `N8N_BASIC_AUTH_*` credentials in plaintext `.env` | open |
| SEC-11 | Low | DB migrations | `sqlalchemy.text(f"…")` dynamic SQL (semgrep) — inputs are static literals | open |
| SEC-12 | Low | HTTP | Server version disclosure (`server: nginx/1.27.5`, `server: uvicorn`) | open |
| SEC-13 | Low | Docker | frontend / traefik / uptime-kuma run as root (mitigated by isolation) | accepted |
| SEC-14 | Info | CORS | `allow_credentials=true` unnecessary (no cookie auth); origins not wildcard — OK | open |
| SEC-15 | Info | CSRF | No CSRF tokens, but no cookie-based auth → not exploitable | accepted |
| SEC-16 | Info | Scanners | gitleaks false positive; test files contain intentional fake secrets | accepted |
| SEC-17 | Info | Uploads / paths | Path-traversal review — safe (UUID ids, role allow-list, size cap) | accepted |

## Detailed findings

### SEC-01 — SSH: password auth, no firewall/fail2ban, active brute-force — **High**
- **Component:** host (`sshd`, port 22 on `0.0.0.0`/`[::]`).
- **Description/impact:** `sshd -T` → `passwordauthentication yes`, `permitrootlogin
  prohibit-password` (root is key-only, good; non-root users may use passwords).
  `ufw` is **inactive** and there is **no fail2ban**. `journalctl -u ssh` shows
  **15,777 "failed password" events in 7 days** — a sustained brute-force. A weak
  user password → full host compromise.
- **Evidence:** `sshd -T | grep -E 'password|permitroot'`; `ufw status` → inactive;
  `systemctl is-active fail2ban` → inactive; failed-login count above.
- **Remediation:** enable a firewall (allow only 22/80/443), install fail2ban, and
  set `PasswordAuthentication no` + `KbdInteractiveAuthentication no` (key-only)
  **after confirming key access**. Consider moving SSH off :22 / restricting source IPs.
- **Immediate mitigation (proposed, not applied — needs your OK; lockout risk):**
  `apt install fail2ban` (ships with an sshd jail) is the lowest-risk first step; it
  does not risk locking you out the way a firewall/SSH change can.

### SEC-02 — Public, unauthenticated API — **High**
- **Component:** `backend` via Traefik `Host(...)&&/api`.
- **Description/impact:** the brief describes a "local, single-user tool… no auth,"
  but it is deployed on the public internet. `GET https://…/api/analyses` returns
  **200 with no credentials**; the backend has **no authentication code at all**
  (`grep` for Depends/auth/jwt/login/HTTPBearer → none). Every endpoint — including
  `POST /api/analyses` and `DELETE /api/analyses/{id}` — is open, so anyone can read,
  tamper with, or **delete all research data**.
- **Evidence:** `curl` → `GET /api/analyses` = 200 unauthenticated; no auth symbols
  in `backend/app`.
- **Remediation:** put the site behind auth at the edge. Fastest: a Traefik
  **basicAuth** middleware (htpasswd) on the router(s); better: an IP allow-list or a
  VPN/SSO, or don't publish it (bind to localhost + SSH tunnel like uptime-kuma).
- **FIXED (applied 2026-07-16):** added a Traefik `basicAuth` **access gate** on the
  `flux-frontend`, `flux-backend`, and `n8n` routers. The whole site now requires a
  single shared key (fixed login `flux` + password) before anything is served.
  Verified: unauthenticated `curl` of `/`, `/api/health`, `/api/analyses`, `/n8n/`
  all return **401**; with the key all return **200**. Credentials live in the
  git-ignored `traefik/htpasswd` (apr1 hash); `removeHeader: true` strips the
  `Authorization` header before it reaches the backend/n8n. This is a **perimeter**
  control (one shared key), not per-user authorization — see Residual risks.
  Key management is documented in `~/CLAUDE.md` (Flux deployment).

### SEC-03 — Missing security headers — **Medium**
- **Description/impact:** no `Strict-Transport-Security`, `Content-Security-Policy`,
  `X-Frame-Options`/`frame-ancestors`, `X-Content-Type-Options`, or `Referrer-Policy`
  on any response (checked `/` and `/api/health`). Enables clickjacking, MIME
  sniffing, and SSL-strip on first visit (no HSTS). No header is set in `nginx.conf`,
  Traefik, or the app.
- **Evidence:** `curl -D -` on `/` and `/api/health` show only `server:` + app headers.
- **Remediation:** add a Traefik `headers` middleware applied to all routers (covers
  frontend, API, and n8n at once) — see Recommended fixes.

### SEC-04 — Outdated frontend image (fixable OS CVEs) — **Medium**
- **Evidence:** `trivy image flux-calculation-frontend` → 107 OS-package
  vulnerabilities (**2 Critical, 35 High, 44 Medium, 26 Low**), **all with a fix
  available** — the `nginx:1.27-alpine` layer is stale.
- **Remediation:** `docker compose build --pull frontend && docker compose up -d
  frontend` to pull the patched base and rebuild (recreates the container — needs
  your OK). Add periodic `--pull` rebuilds / image scanning in CI.

### SEC-05 — No rate limiting — **Medium**
- **Description/impact:** neither the app (only CORS + request-logging middleware)
  nor Traefik (`dynamic.yml` has only the n8n `stripPrefix`) rate-limits. The public
  n8n login and the open API can be brute-forced / cheaply DoS'd.
- **Remediation:** add a Traefik `rateLimit` middleware (e.g. average 20 r/s, burst
  50) to the routers.

### SEC-06 — n8n publicly exposed — **Medium**
- **Description/impact:** n8n (workflow automation, can run code / reach internal
  services) is reachable at `https://…/n8n`. The owner account is set and login
  returns 401 (good), but exposing an automation tool to the internet is a large
  attack surface, especially without rate limiting (SEC-05).
- **FIXED (applied 2026-07-16):** n8n now sits behind the same shared access gate as
  SEC-02 (`/n8n/` → 401 without the key). Its own owner login remains as a second
  layer. Note: rate limiting (SEC-05) is still recommended on top.

### SEC-07 — Sentry auth token as Docker build-arg — **Medium**
- **Description/impact:** `SENTRY_AUTH_TOKEN` (a secret) is passed as a
  `docker build` arg for frontend source-map upload; build args persist in image
  layer history, so anyone with the image can recover it.
- **Evidence:** `frontend/Dockerfile` `ARG SENTRY_AUTH_TOKEN` / `docker-compose.yml`
  build args (documented already in the monitoring report's residual risks).
- **Remediation:** use BuildKit `--secret` (mount, not arg), or upload source maps
  outside Docker with `sentry-cli`. Currently unset, so no token is exposed today.

### SEC-08 — `.env` world-readable — **Medium — FIXED**
- **Description/impact:** `.env` files were `644` (any local user could read the LLM
  key, Sentry DSN, n8n creds).
- **Fix applied:** `chmod 600` on `/root/Flux-Calculation/.env`, `backend/.env`,
  `frontend/.env`, `/root/n8n/.env`. Verified `600`; running containers unaffected
  (env is already loaded; `docker compose` reads as root). **Re-run:** all containers
  still healthy after the change.

### SEC-09 — Backend image OS CVEs, no fix available — **Low (accepted)**
- **Evidence:** `trivy image flux-calculation-backend` → 3 Critical / 19 High (perl,
  util-linux, …), **0 with a fix available** — upstream Debian hasn't patched them.
- **Assessment:** low real-world risk (perl/util-linux are not invoked by the FastAPI
  runtime). **Remediation:** rebuild with `--pull` when fixes land; consider a
  distroless/minimal runtime to shrink the OS surface.

### SEC-10 — Stale n8n basic-auth creds in plaintext — **Low**
- **Evidence:** `grep -c N8N_BASIC_AUTH /root/n8n/.env` → 2 lines. n8n 2.x ignores
  these (documented), so they are dead but still plaintext credentials on disk.
- **Remediation:** delete the `N8N_BASIC_AUTH_*` lines (rotate that password if it is
  reused anywhere). Exposure already reduced by SEC-08 (now `600`).

### SEC-11 — Dynamic SQL in migrations — **Low**
- **Evidence:** `semgrep` `avoid-sqlalchemy-text` on `app/db/session.py:49,51`
  (`text(f"PRAGMA table_info({table})")`, `ALTER TABLE {table} ADD COLUMN …`).
- **Assessment:** **not exploitable** — `table`/`column`/`sql_type` are hardcoded
  literals (`"spot"`, `"manual_offset_s"`, `"FLOAT"`); no user input reaches them.
- **Remediation:** annotate with `# nosemgrep: … reason` or switch to SQLAlchemy DDL
  helpers to keep SAST clean.

### SEC-12 — Server version disclosure — **Low**
- **Evidence:** `server: nginx/1.27.5` and `server: uvicorn` in responses.
- **Remediation:** `server_tokens off;` in nginx; strip/override the `Server` header
  in the Traefik headers middleware.

### SEC-13 — Containers running as root — **Low (accepted)**
- **Evidence:** `docker exec … id` → frontend, traefik, uptime-kuma = uid 0; backend
  = `appuser` (10001), n8n = `node` (1000).
- **Assessment:** frontend nginx master needs root to bind :80 (workers drop
  privileges) and is internal-only; traefik root is conventional; uptime-kuma is
  localhost-only. Low residual. **Remediation:** consider `nginx-unprivileged`;
  drop Linux capabilities on traefik.

### SEC-14/15 — CORS & CSRF — **Info**
- CORS: `allow_credentials=true` with an explicit origin list (not `*`); a hostile
  `Origin` is **not** reflected (`curl` preflight from `evil.example` returns no
  matching `Access-Control-Allow-Origin`). Credentials aren't needed (no cookies);
  drop `allow_credentials` to tighten. CSRF: no anti-CSRF tokens, but there is no
  cookie/session auth, so there are no ambient credentials to abuse — not exploitable.

### SEC-16 — Scanner false positives — **Info**
- gitleaks flagged `frontend/src/lib/constants.ts:43` (`generic-api-key`) — it is the
  `UNIT_LADDER` object's `key:` property (`key: 'umol_m2_s'`), **not a secret**; the
  `dist` bundle copy is the same. Test files (`monitoring.test.ts`, `logger.test.ts`)
  contain intentional fake secrets for redaction tests. **Remediation:** add a
  `.gitleaks.toml` allow-list so CI stays clean.

### SEC-17 — Upload / path-traversal review — **Info (safe)**
- `app/db/storage.py` builds paths from a **server-generated UUID** `analysis_id` and
  an **allow-listed** `role`; only the file **suffix** is taken from the user
  filename (never a full path), and uploads are capped at 50 MB. No traversal or
  command-injection paths found; no `os.system`/`shell=True`/`eval`/`pickle` in the
  code; the only `subprocess` call is a fixed-arg `git rev-parse HEAD`.

## Recommended fixes (ready to apply — most need a service restart, so held for your OK)

1. **Edge auth + headers + rate limit (SEC-02/03/05/06/12)** — one Traefik
   `dynamic.yml` change adding middlewares, chained on the routers:
   ```yaml
   middlewares:
     security-headers:
       headers:
         stsSeconds: 31536000
         stsIncludeSubdomains: true
         contentTypeNosniff: true
         frameDeny: true
         referrerPolicy: strict-origin-when-cross-origin
         customResponseHeaders: { Server: "" }
     ratelimit:
       rateLimit: { average: 20, burst: 50 }
     app-auth:
       basicAuth: { usersFile: "/etc/traefik/dynamic/htpasswd" }   # generate with htpasswd -B
   ```
   Apply order per router: `[app-auth, security-headers, ratelimit]` (+ n8n keeps
   `stripPrefix`). Requires backing up `dynamic.yml` and `docker restart
   flux-calculation-traefik-1` (single-file bind-mount; ~1–2 s blip).
2. **Frontend image (SEC-04):** `docker compose build --pull frontend && docker
   compose up -d frontend`.
3. **Host hardening (SEC-01):** `apt install fail2ban`; enable `ufw` (22/80/443);
   after confirming key login, `PasswordAuthentication no`.
4. **Secrets (SEC-07/10):** move `SENTRY_AUTH_TOKEN` to BuildKit `--secret`; delete
   dead `N8N_BASIC_AUTH_*` lines.

## Immediate actions (priority order)

1. **SEC-01** install fail2ban now (safe); plan the firewall/SSH-key cutover.
2. **SEC-02/06** put basicAuth (or IP allow-list) in front of the site + n8n.
3. **SEC-04** rebuild the frontend image with `--pull`.
4. **SEC-03/05** add the headers + rate-limit middleware (same Traefik edit as #2).

## Residual risks

- **SEC-09** backend base-OS CVEs remain until upstream patches exist (monitor).
- **SEC-01** any internet-facing SSH remains a target even with fail2ban; keys +
  firewall + source restrictions are the durable fix.
- The app has **no application-level authorization model**; edge auth (basicAuth) is
  a perimeter control, not per-user access control — acceptable for a single-user
  tool but note it if multi-user is ever needed.
- No changes were made to Traefik, SSH, the firewall, or any running container
  during this review (except the safe `chmod 600`), so production behaviour is
  unchanged pending your decisions above.

## Tooling evidence summary

| Tool | Result |
|------|--------|
| `npm audit` (frontend) | **0 vulnerabilities** |
| `pip-audit` (backend, 50 pkgs) | **0 vulnerabilities** |
| `semgrep --config auto` | 2 findings (SEC-11, non-exploitable) |
| `gitleaks` (tree + 27 commits) | 1 hit → false positive (SEC-16) |
| `checkov` (dockerfile/gha/secrets) | pass (187+156 checks; 1 justified skip) |
| `trivy` frontend image | 2 Crit / 35 High — all fixable (SEC-04) |
| `trivy` backend image | 3 Crit / 19 High — no fix available (SEC-09) |

---

# Report — CI/CD pipeline (test → deploy)

Goal: a push runs all checks in GitHub Actions and, **only if they pass and only on
`main`**, deploys the exact tested commit to the VPS — safely, with a health-check
and automatic rollback.

## ⚠ Prerequisite (must happen before the pipeline is safe to enable)

`main` is currently **8 commits behind** `flux-improvements`, and the server has
**~21 uncommitted changes** — including the **access gate** (the `htpasswd` volume
mount in `docker-compose.yml` and the `access-gate` middleware in
`traefik/dynamic.yml`). A deploy checks out `main` and force-resets tracked files,
so **deploying `main` today would remove the access gate and other work**.
Git-ignored/untracked files (`.env`, `traefik/htpasswd`, `data/`) are preserved, but
tracked config is not. **Action required:** commit the current work, open a PR from
`flux-improvements`, and merge to `main` so `main` reflects the desired production
state *before* enabling auto-deploy. (`deploy.yml` also only fires from the copy of
itself on `main`, so it can't run until merged anyway.)

## The flow

```
push / PR ─▶ test.yml (backend, frontend, e2e, checkov, audit, docker-build+Trivy)
                                   │ all green?  and branch == main?
                                   ▼
             deploy.yml  (workflow_run: test succeeded on main)
                                   │  SSH (key from Secrets)
                                   ▼
   VPS: /usr/local/bin/flux-deploy <tested-SHA>
        fetch → checkout SHA → docker compose up -d --build (migrations on startup)
        → health-check backend+frontend+edge → rollback to previous SHA on failure
```

- **Tests never gate-passed ⇒ no deploy.** `deploy.yml` triggers via `workflow_run`
  and runs only when `conclusion == 'success'` and `head_branch == 'main'`; a failed
  `test` run leaves the deploy job skipped. Manual `workflow_dispatch` is allowed but
  guarded to `main`.
- **Deploys the tested commit**, not "latest": it uses
  `github.event.workflow_run.head_sha`.
- **Auditable:** the whole thing is in the Actions log; secrets are GitHub-masked and
  never echoed.

## `test.yml` (extended)

Jobs (push to `main`/`flux-improvements`, all PRs, manual):

| Job | Does |
|-----|------|
| `backend` | `pip install -e .[dev]` → ruff, ruff format --check, mypy, **pytest** (unit + integration + security) |
| `frontend` | `npm ci` → oxlint, prettier, tsc, **vitest**, build |
| `e2e` | Playwright chromium → **e2e smoke** (`npm run test:e2e`) + report artifact |
| `checkov` | IaC/workflow/secret scan |
| `audit` | **pip-audit** (backend, `--strict`) + **npm audit** (`--omit=dev --audit-level=high`) |
| `docker-build` | build backend + frontend images, then **Trivy** scan (HIGH/CRITICAL, `ignore-unfixed`, fails on fixable) |

## `deploy.yml` (new)

- Trigger: `workflow_run` after `test` on `main` (+ guarded `workflow_dispatch`).
- `permissions: contents: read`; `concurrency: deploy-production` (no overlap);
  `environment: production` (attach required reviewers there for an approval gate).
- Steps: resolve tested SHA → write the SSH key to a 0600 file (never printed) +
  `known_hosts` → `ssh … "<SHA>"` → always remove the key.
- **SSH model chosen: forced-command key (safer than a self-hosted runner here).**
  A GitHub-hosted runner is ephemeral and clean each run; a self-hosted runner would
  be a *persistent* GitHub-controlled agent on the production box (bigger standing
  risk, and dangerous if the repo ever goes public / accepts fork PRs). With a
  forced-command key, even a leaked key can only trigger `flux-deploy` with a ref the
  script validates — not a shell.

## Server-side deploy script — `infrastructure/deploy/deploy.sh`

Idempotent, rollback-safe. Behaviour:
1. Resolve + **validate** the ref (only a hex SHA or `origin/main`; rejects anything
   else — injection-safe; verified with `; rm -rf /` etc. → REJECT).
2. Record `PREV_SHA`; `git fetch`; `git checkout --force <SHA>` (untracked/ignored
   files preserved).
3. `SENTRY_RELEASE=<SHA> docker compose up -d --build --remove-orphans`. **Migrations
   run idempotently** on backend startup (`create_db_and_tables →
   _run_lightweight_migrations`), so `up -d` applies them.
4. **Health-check** (≤150 s): poll Docker health of `backend` + `frontend` (both
   Dockerfiles have HEALTHCHECKs), then confirm the Traefik edge answers (200 or
   **401** = up behind the access gate).
5. **Rollback on failure:** checkout `PREV_SHA`, redeploy, re-check; exit non-zero so
   CI shows the failure. If rollback also fails → exit 2 (manual intervention).

Verified locally: `bash -n` OK; ref-validation accepts SHA/`origin/main` and rejects
injection; not executed against production.

## Required GitHub Secrets (set in repo → Settings → Secrets, environment `production`)

| Secret | Purpose |
|--------|---------|
| `SSH_HOST` | VPS hostname/IP (`65.21.2.126`) |
| `SSH_USER` | deploy user (see server setup) |
| `SSH_PRIVATE_KEY` | private half of the deploy key (**never committed**) |
| `SSH_KNOWN_HOSTS` | server host key (optional; else TOFU `ssh-keyscan`) |
| `DEPLOY_PATH` | repo path on the server (default `/root/Flux-Calculation`) |

Runtime app secrets (`SENTRY_DSN`, `LLM_API_KEY`, …) stay in the **server's** `.env`
(git-ignored, now `chmod 600`) — they are **not** transferred by CI.

## Server setup (one-time — YOU run this; it changes SSH access, so left for you)

```bash
# 1. Generate a deploy keypair (on your laptop, NOT the server):
ssh-keygen -t ed25519 -f flux_deploy -C "github-deploy" -N ''
#    -> put the PRIVATE key (flux_deploy) into the SSH_PRIVATE_KEY secret.

# 2. Install the deploy script on the server:
sudo install -m 0755 /root/Flux-Calculation/infrastructure/deploy/deploy.sh \
     /usr/local/bin/flux-deploy

# 3. Add a FORCED-COMMAND entry to the deploy user's ~/.ssh/authorized_keys
#    (recommended: a dedicated `deploy` user in the `docker` group; DEPLOY_PATH
#    baked in so the key can ONLY deploy):
command="DEPLOY_PATH=/root/Flux-Calculation /usr/local/bin/flux-deploy",\
no-agent-forwarding,no-port-forwarding,no-pty,no-X11-forwarding \
ssh-ed25519 AAAA...<PUBLIC key from step 1>... github-deploy

# 4. Pin the host key for the SSH_KNOWN_HOSTS secret:
ssh-keyscan -t ed25519 65.21.2.126
```

**Least privilege / honest caveat:** the deploy step runs `docker compose`, which
needs Docker access, and Docker access is effectively root. The forced-command key
contains that: the key can *only* invoke `flux-deploy` with a validated ref — not get
a shell — so a leaked key can trigger a deploy/rollback but nothing else. Prefer a
dedicated `deploy` user over root. Combine with the SSH hardening from the security
report (fail2ban, key-only auth) — those remain open.

## Branch protection (recommended — set in repo → Settings → Branches, `main`)

- Require a pull request before merging (no direct pushes to `main`).
- Require status checks to pass: **backend, frontend, e2e, checkov, audit,
  docker-build**.
- Require branches up to date before merging; **block force-pushes**; block deletion.
- Optionally require a review and enable the `production` environment approval gate.

## Verification done / not done

- **Done (local):** both workflows are valid YAML; `checkov` github_actions scan of
  `.github/workflows` = **196 passed / 0 failed**; `deploy.sh` syntax + ref-validation
  verified; `.env.example` covers every compose/backend variable.
- **Not done (needs you):** the pipeline can't run end-to-end until (a) the work is
  merged to `main`, (b) the 5 GitHub Secrets are set, and (c) the deploy user/key are
  created on the server. I did **not** create SSH users/keys, set secrets, push, or
  run a live deploy — those change SSH access / require GitHub access and are yours to
  approve. Happy to do the server-side user+key setup on your go-ahead.

## Rollback procedure (also automatic in the script)

- **Automatic:** a failed post-deploy health-check triggers checkout of the previous
  SHA + redeploy + re-check, inside `flux-deploy` (CI turns red).
- **Manual:** on the server, `cd $DEPLOY_PATH && git checkout <last-good-SHA> &&
  SENTRY_RELEASE=<sha> docker compose up -d --build`. To revert the CI/CD or gate
  config specifically, the backups exist: `docker-compose.yml.bak-before-auth`,
  `traefik/dynamic.yml.bak-before-auth`.

---

# Report — documentation audit & generated API docs

Goal: audit the docs, bring the README up to best practice, and produce **mostly
auto-generated** docs — especially the backend API, generated from the code rather
than hand-written.

## What existed before (audit)

| Doc | State found | Action |
|-----|-------------|--------|
| **Root `README.md`** | **Missing** | **Created** — signpost: purpose, stack, architecture, local run, env table, commands, Docker/deploy, troubleshooting |
| `frontend/README.md` | **Stale** — the default Vite `react-ts` template boilerplate, nothing about this app | **Rewritten** to the real app (run/test/lint, stack, layout, observability) |
| `backend/README.md` | Good, concise | Kept as-is |
| `docs/operations.md` | Useful but **logging-only** (titled "logging & observability") | **Expanded into a full runbook** (deploy, restart, rollback, logs, monitoring, backup/restore, maintenance, incident response); logging content preserved so existing links stay valid |
| `docs/architecture.md` | **Missing** | **Created** — components, data flow, DB ER, Docker/Traefik topology, trust boundaries, 4 Mermaid diagrams |
| Backend API docs / OpenAPI | **None on disk** (FastAPI served `/docs` at runtime only) | **Generated** `docs/openapi.json` from the app; enriched app metadata |
| `CLAUDE.md` files (root/backend/frontend) | Accurate, current | Kept; used as the source of truth for the new docs |
| `assignment/`, `project-brief.md`, `report.md` | Records / long-form | Left as-is; deliberately **not** markdown-linted (records, not published docs) |

The per-app dev guides (`CLAUDE.md`) already track the code well; the gap was
**user/operator-facing** docs (a root README, a full runbook, an architecture doc) and
a **generated, on-disk API spec**.

## Generated backend API docs (the emphasis)

- **Source of truth = the code.** `docs/openapi.json` (OpenAPI **3.1.0**, 11 paths) is
  generated straight from FastAPI's route decorators + Pydantic schemas by
  `backend/scripts/export_openapi.py`. Nothing is hand-written, so it can't drift.
- **App metadata enriched** (`backend/app/main.py`): added `version` (read from the
  installed package metadata, falls back to `0.0.0+local`), a `description`, and a
  relative `servers` entry so the spec documents its base and validates cleanly.
- **No leakage of admin/internal endpoints:** the app has none — all 11 endpoints are
  the documented `/api` surface (single-user, no auth; every endpoint on one trust
  level, stated in the spec description and `docs/architecture.md`). Verified by
  listing `schema["paths"]`. FastAPI's interactive `/docs` + `/redoc` remain available
  at runtime in dev; in production they aren't routed (Traefik only forwards `/api` to
  the backend).

## Tooling added

Repo-level docs tooling in a **root `package.json`** (kept separate from the two
self-contained apps; `node_modules` git-ignored):

| Script | Tool | Does |
|--------|------|------|
| `npm run docs:generate` | `backend/scripts/export_openapi.py` (FastAPI) | (Re)write `docs/openapi.json` from the app |
| `npm run docs:validate` | `@redocly/cli` (+ `redocly.yaml`) | Validate the OpenAPI spec structurally |
| `npm run docs:lint` | `markdownlint-cli2` (+ `.markdownlint-cli2.jsonc`) | Lint the README + `docs/` |

`redocly.yaml` uses the `minimal` ruleset and turns off the opinionated authoring rules
that don't apply to a no-auth local tool (`security-defined`, `info-license`), each with
a documented reason; the spec validates with **0 errors** (2 non-fatal warnings about
optional 4xx examples). `.markdownlint-cli2.jsonc` scopes linting to the docs we
maintain (root README, `docs/**`, the two app READMEs) and relaxes MD013/MD033/MD041 to
fit prose + Mermaid/`<details>`.

## CI checks added

New **`docs`** job in `.github/workflows/test.yml` (runs on every push/PR):

1. install the backend (so the app is importable) + the root docs tooling (`npm ci`);
2. `npm run docs:generate`, then **fail if `docs/openapi.json` is out of date**
   (`git diff --quiet`) — this keeps the committed spec honest with the code;
3. `npm run docs:validate` (redocly);
4. `npm run docs:lint` (markdownlint).

## Secrets / privacy check

Ran a leak scan over every doc/tooling file added or changed
(`README.md`, `docs/`, the app READMEs, `backend/scripts/`, `package.json`,
`redocly.yaml`) for the host IPs, the access-gate password, private keys, and personal
emails — **none present**. The runbook refers to the VPS by role and to the site by its
`<domain>` placeholder; all secrets are described only by where they live
(untracked `.env` / `traefik/htpasswd`), never by value. `checkov` (dockerfile +
github_actions + secrets) still passes (exit 0), so the new workflow job and root
tooling introduce no findings.

## How to regenerate / validate

```bash
# one-time: install repo-level docs tooling
npm install

# regenerate the API spec from the backend (after any endpoint/schema change)
cd backend && . .venv/bin/activate && python scripts/export_openapi.py   # or: npm run docs:generate
cd ..

# validate + lint (CI runs the same)
npm run docs:validate
npm run docs:lint
```

## Verification done

- `docs/openapi.json` generated (11 paths, OpenAPI 3.1.0); `redocly lint` → valid.
- `markdownlint-cli2` over the 5 maintained docs → **0 errors**.
- Backend still imports and `pytest -k health` passes after the `main.py` metadata edit;
  `ruff` clean.
- `checkov` (all three frameworks) → exit 0.
- Leak scan → clean.

## Files added/changed (this task)

New: `README.md`, `docs/architecture.md`, `backend/scripts/export_openapi.py`,
`docs/openapi.json`, `package.json`, `package-lock.json`, `redocly.yaml`,
`.markdownlint-cli2.jsonc`.
Edited: `frontend/README.md` (rewritten), `docs/operations.md` (expanded to a runbook),
`backend/app/main.py` (OpenAPI metadata: version + description + servers),
`.gitignore` (root `node_modules`), `.github/workflows/test.yml` (new `docs` job).
