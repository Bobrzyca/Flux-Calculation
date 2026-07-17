# Flux Calculation

A **local, single-user, desktop-style web tool** for closed-chamber greenhouse-gas
researchers (LI-7810 instrument family). It ingests up to four raw field files —
a 1 Hz LI-7810 CO₂/CH₄ concentration log, hand-typed start/stop time notes, a
temperature `.xlsx`, and an optional IMGW pressure file — auto-matches them by
timestamp (with a correctable instrument-clock offset), fits a linear regression of
concentration vs. time per gas per spot, and computes **CO₂/CH₄ flux across a full
unit ladder**. Every transformation is exposed for supervision: per-spot regression
plots and a processing log.

> The flux math is **pure code**, validated against an R method-of-record. An LLM is
> used only to normalise messy notes/pressure into strict JSON, and its output is
> always human-confirmed before use.

## Stack

| Layer | Tech |
|---|---|
| Frontend | React 19 + Vite + TypeScript, Tailwind, Plotly, react-router v7 |
| Backend | Python 3.14 + FastAPI (uvicorn), pandas / numpy / scipy |
| Database | SQLite (one file per install) via SQLModel |
| Edge / deploy | Docker Compose, Traefik (TLS via Let's Encrypt) |
| External (optional) | n8n quality-check workflow; Sentry monitoring |

## Architecture at a glance

```text
browser ──HTTP──▶ frontend (React SPA, nginx) ──/api──▶ backend (FastAPI) ──▶ SQLite
                                                              │
                                        raw uploads on disk (re-runnable campaigns)
```

The browser hits `…/api/*` (backend) and everything else (SPA + assets) is served by
the frontend. In production **Traefik** is the only host-exposed service; the app
containers are reachable only through it. Full component/data-flow diagram and trust
boundaries: **[`docs/architecture.md`](docs/architecture.md)**.

This is a **two-app monorepo**; each app is self-contained (its own deps, tests, and
run commands):

- **[`frontend/`](frontend/README.md)** — the React UI. Dev guide: [`frontend/CLAUDE.md`](frontend/CLAUDE.md).
- **[`backend/`](backend/README.md)** — the FastAPI app. Dev guide: [`backend/CLAUDE.md`](backend/CLAUDE.md).
- **`reference/`** — the R method-of-record used to validate the Python fluxes (not called by the app).

## Run it locally

Two processes: the backend API and the frontend dev server.

```bash
# 1. Backend  (terminal 1, from backend/)
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env                 # edit as needed; .env is git-ignored
uvicorn app.main:app --reload        # http://localhost:8000  (docs at /docs)

# 2. Frontend (terminal 2, from frontend/)
cd frontend
npm install
cp .env.example .env
npm run dev                          # http://localhost:5173
```

The frontend talks to the backend over HTTP at `VITE_API_BASE_URL`
(default `http://localhost:8000/api`). Keep the backend's `CORS_ORIGINS` in sync with
the dev origin.

## Configuration

Environment is set via `.env` files (copy each `.env.example`; all `.env` files are
git-ignored and **must never be committed**). The **root `.env`** (used by
`docker-compose`) is the full list; the key variables:

| Variable | Example / default | Purpose |
|---|---|---|
| `DOMAIN` | `flux-calculation.example.com` | Public hostname Traefik routes + gets a cert for |
| `ACME_EMAIL` | `you@example.com` | Let's Encrypt contact for cert expiry notices |
| `APP_NAME` | `Flux Calculation API` | API display name (shown by `/api/health`) |
| `DATA_DIR` | `/app/data` | Where uploads + the SQLite DB live in the container |
| `DATABASE_URL` | `sqlite:////app/data/flux.db` | SQLite connection string |
| `CORS_ORIGINS` | `["https://flux-calculation.example.com"]` | Allowed browser origins (JSON list) |
| `LLM_API_KEY` | *(blank)* | LLM notes/pressure parser key — **secret**, optional |
| `LOG_LEVEL` / `LOG_FORMAT` | `INFO` / `json` | Logging verbosity + format |
| `SENTRY_DSN` / `VITE_SENTRY_DSN` | *(blank)* | Monitoring; off when blank |
| `VITE_API_BASE_URL` | `/api` | API base baked into the frontend bundle at build |

Full annotated list with every Sentry knob: [`.env.example`](.env.example),
[`backend/.env.example`](backend/.env.example), [`frontend/.env.example`](frontend/.env.example).
Secrets (`LLM_API_KEY`, `SENTRY_DSN`, `SENTRY_AUTH_TOKEN`) live only in the untracked
`.env` on each machine — never in git.

## Commands

**Backend** (from `backend/`, venv active):

```bash
pytest                                   # test suite
ruff check . && ruff format --check .    # lint + format
mypy .                                   # type-check
```

**Frontend** (from `frontend/`):

```bash
npm test            # vitest unit/component tests
npm run test:e2e    # playwright e2e smoke (first run: npx playwright install --with-deps chromium)
npm run lint        # oxlint
npm run typecheck   # tsc -b --noEmit
npm run build       # production build
```

**Docs & security scanning** (from the repo root):

```bash
npm install                              # one-time: docs tooling (redocly + markdownlint)
npm run docs:generate                    # regenerate docs/openapi.json from FastAPI
npm run docs:validate                    # validate the OpenAPI spec (redocly)
npm run docs:lint                        # markdownlint the README + docs/

checkov --config-file infrastructure/checkov/.checkov.yaml   # IaC / container / secret scan
```

CI (`.github/workflows/test.yml`) runs all of the above on every push/PR, plus a
dependency-vulnerability audit, a Docker build with a Trivy image scan, and the docs
checks. See **[`.github/workflows`](.github/workflows)** and the CI/CD section of
[`report.md`](report.md).

## API documentation

The backend API is documented by a **generated OpenAPI 3.1 spec** at
[`docs/openapi.json`](docs/openapi.json) (regenerate with `npm run docs:generate`).
When the backend is running, interactive docs are served at
`http://localhost:8000/docs` (Swagger UI) and `/redoc`. All routes are under `/api`;
there are no hidden admin or internal endpoints.

## Docker & deployment

Production runs as three containers (`traefik` + `backend` + `frontend`) on a shared
bridge network, defined by the root [`docker-compose.yml`](docker-compose.yml):

```bash
cp .env.example .env                     # set DOMAIN + ACME_EMAIL (+ any secrets)
export SENTRY_RELEASE=$(git rev-parse HEAD)
docker compose up -d --build
```

CI/CD auto-deploys the tested commit on `main` over SSH with a health-check and
rollback. The full runbook — deploy, restart, rollback, logs, monitoring/alerts,
backup/restore, and incident response — is in **[`docs/operations.md`](docs/operations.md)**.

## Troubleshooting

| Symptom | First check |
|---|---|
| Frontend can't reach the API | Backend running? `curl localhost:8000/api/health`. `VITE_API_BASE_URL` and backend `CORS_ORIGINS` aligned? |
| Upload rejected (422) | The error `code`/`field` names the failing file (`bad_li7810`, `missing_file`, …); check the raw file format. |
| All spots skipped / empty windows | The matching date comes from the concentration file's own `DATE`; verify the notes' times fall inside the recording. |
| Low R² on a spot | Use the per-spot **manual fit-window shift**, or the global "block auto-fit" switch on Results. |
| Cert / HTTPS issues in prod | See [`docs/operations.md`](docs/operations.md) → Deploy & TLS, and check Traefik logs. |
| Reading logs / tracing a request | [`docs/operations.md`](docs/operations.md) → Logs (each request carries an `X-Request-ID`). |

More detail lives in the per-app dev guides ([`backend/CLAUDE.md`](backend/CLAUDE.md),
[`frontend/CLAUDE.md`](frontend/CLAUDE.md)) and the operations runbook.
