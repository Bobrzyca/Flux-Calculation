# CLAUDE.md — Flux Calculation

Standing instructions for developing this app. Base decisions on `project-brief.md`;
where the brief is silent I use common defaults, marked **(assumption)**.

## Project
Flux Calculation is a **local, single-user desktop-style web tool** for closed-chamber
greenhouse-gas researchers (the author and lab friends, LI-7810 instrument family). It
ingests up to four raw field files — a 1 Hz LI-7810 CO₂/CH₄ concentration log, hand-typed
start/stop time notes, a temperature xlsx, and (optionally) an IMGW pressure file; when the
pressure file is omitted the flux math falls back to a default sea-level pressure and the
affected spots are flagged `no_pressure` — auto-matches them
by timestamp (with a correctable instrument-clock offset), fits a linear regression of
concentration vs. time per gas per spot, and computes CO₂/CH₄ flux across a full unit
ladder. An LLM normalises the messy notes/pressure into strict JSON (human-confirmed
before use); the physics/flux math is pure code and never LLM-touched. Every
transformation is exposed for supervision (per-spot regression plots, a processing log).

### Two apps, one repo
This is a **two-app monorepo**; each app is self-contained (its own deps, tests,
config, and run commands) and has its own standing instructions:
- **`frontend/`** — React 19 + Vite + TypeScript UI (Tailwind, Plotly), talking to
  the backend over HTTP. See [`frontend/CLAUDE.md`](frontend/CLAUDE.md).
- **`backend/`** — Python 3.14 + FastAPI app (parsing, matching, flux math, API).
  See [`backend/CLAUDE.md`](backend/CLAUDE.md).
- **`reference/`** — the R method-of-record used to validate the Python fluxes,
  cleaned to run on the repo's sample files. **Not** called by the app. Currently
  a **Python-derived scaffold** (`flux_reference.R`) — replace it with the real,
  independent R script (see `reference/README.md`).

**How they fit together:** the frontend talks to the backend over **HTTP under the
`/api` prefix** (via the typed `fetch` client in `frontend/src/api/client.ts`,
base URL `VITE_API_BASE_URL`). The backend is **local and single-user** — no auth,
one SQLite file per install, run on the researcher's own machine. **Secrets** (e.g. the LLM API key) live in
`backend/.env`, which is git-ignored and **never committed**; `backend/.env.example`
documents the keys with empty values.

**The update rule (applies to both apps):** when you add a feature, add or change
an endpoint, or change the structure/commands, update the relevant `CLAUDE.md`
(the app's own, plus this root file if the cross-app picture changed) **in the same
commit**. Docs drift is a bug.

## Tech stack
**Frontend**
- React 19 + **Vite** + **TypeScript**, Tailwind CSS for styling.
- **Plotly** (`react-plotly.js`) for the per-spot regression plot (zoom/pan).
- Package manager: **npm** (matches the server's installed toolchain).
- Test runner: **Vitest** + React Testing Library.
- Lint/format: **oxlint** + **Prettier**. (The current Vite `react-ts` template
  ships oxlint, not ESLint, so we kept it and added Prettier for formatting.)
- Routing: **react-router-dom** v7. Path alias `@/*` → `src/*` (Vite + tsconfig).
- Plotly is loaded lazily (`React.lazy`) so it stays in its own code-split chunk.

**Backend**
- **Python 3.14** + **FastAPI**, served with **uvicorn**.
- Data/math: **pandas**, **numpy**, **scipy** (`scipy.stats.linregress` for slope + R²).
- Files: **openpyxl** (xlsx), **python-docx** (Word notes).
- LLM: an official Python LLM SDK in **structured/JSON-output mode** for the notes +
  pressure parser. Default to the latest capable **Anthropic** model **(assumption —
  confirm provider)**; keep the key in `.env`, never committed.
- Package/deps: **pip** + `requirements.txt` inside a **venv** (or `pyproject.toml`)
  **(assumption)**.
- Test runner: **pytest**.
- Lint/format + types: **ruff** (lint + format) and **mypy** **(assumption)**.

**Database**
- **SQLite**, one file per install (zero setup, travels with the analysis). Tables per
  the brief: `Analysis`, `Spot`, `Reading`, `FluxResult`. Raw uploaded files are also
  saved on disk and referenced by the `Analysis`, so any campaign can be re-run.
  ORM: **SQLModel/SQLAlchemy** **(assumption)**.

**External workflow**
- **n8n** for the on-demand, per-campaign AI quality-check (app → n8n results out, n8n →
  app report back). The app never depends on n8n being up.

## Repository structure
```
frontend/                 self-contained React app
  src/
    components/           shared UI
    pages/                Upload, ConfirmNotes, Results, SpotDetail, ProcessingLog
    api/                  typed client for the backend
    lib/                  helpers, formatting, unit ladder display
  tests/                  Vitest specs (co-located *.test.tsx also fine)
  index.html, vite.config.ts, package.json, tailwind.config.*

backend/                  self-contained FastAPI app
  app/
    main.py               FastAPI entry, route wiring
    api/                  routers (upload, analyses, results, webhooks)
    core/                 config, settings, chamber-constant defaults
    parsing/              LI-7810, temperature, notes, pressure loaders
    llm/                  notes/pressure parser (prompt + schema + validation)
    matching/            time-shift + auto-match by timestamp
    flux/                 regression + closed-chamber flux + unit ladder (pure)
    db/                   SQLite models, session, migrations
    schemas/              Pydantic request/response models
  tests/                  pytest, mirrors app/ layout
  sample_data/            small fixture files for tests
  requirements.txt / pyproject.toml, .env.example

reference/               original R script, cleaned to run on repo sample files;
                         method-of-record for validation. NOT called by the app.
```
Each app is self-contained: its own deps, tests, config, and run commands.

## How we work (engineering rules)
1. **Test-driven.** Write or update a *failing* test first, then the code to pass it.
   Keep tests fast and close to the code.
2. **Green before commit.** Linter, formatter, and type checker (mypy / tsc) must be
   clean on every change.
3. **Small, focused commits**, Conventional Commits style: `feat:`, `fix:`, `chore:`,
   `test:`, `docs:`.
4. **Never commit secrets.** Keep a `.env.example` with empty values; `.env` in
   `.gitignore`. Never print `.env` contents.
5. **Readable over clever.** Match existing patterns; prefer conventional code.
6. **Explain non-obvious decisions** in the commit message or a comment — I am learning.
7. **The flux math is pure code**, validated against the R reference; the LLM only
   normalises input formats, and its output is always human-confirmed before use.
8. **Validate the reference.** On a known campaign (e.g. 2 July 2026 Kampinos), the
   Python fluxes must match the R script; investigate any disagreement.

## Commands
_Fill in as each app is scaffolded._

**Backend** (from `backend/`)
- Install: `python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"`
- Dev: `uvicorn app.main:app --reload`
- Test: `pytest`
- Lint/format/types: `ruff check . && ruff format --check . && mypy .`

**Frontend** (from `frontend/`)
- Install: `npm install`
- Dev: `npm run dev`
- Build: `npm run build`
- Test: `npm test` (watch: `npm run test:watch`)
- Lint/format/types: `npm run lint && npm run format:check && npm run typecheck`
- Talks to the **real backend** over HTTP (`src/api/client.ts`); base URL is
  `VITE_API_BASE_URL` (default `http://localhost:8000/api`). Run `uvicorn` in
  `backend/` alongside `npm run dev`. Tests use a fetch stub (no live backend).

## Docker / deployment
Production runs as three containers on a shared bridge network (`flux-net`), defined
by the root **`docker-compose.yml`**. **Traefik** is the edge; the app containers are
reachable **only through it** (no host port mappings of their own):
- **`traefik`** — `traefik:v3.3`, the reverse proxy / TLS terminator and the **only**
  service published to the host (**80 + 443**). Two entrypoints: `web` (:80) and
  `websecure` (:443), with a global **HTTP→HTTPS redirect** (the ACME challenge is
  still answered on :80). Certificates come from **Let's Encrypt via the ACME
  HTTP-01 challenge** (resolver `letsencrypt`, email `${ACME_EMAIL}`) and persist in
  the **`letsencrypt`** volume at `/letsencrypt/acme.json`. Provider is **docker**
  with `exposedbydefault=false`, so only containers labelled `traefik.enable=true`
  are routed; it watches the Docker socket read-only (`/var/run/docker.sock:ro`).
- **`backend`** — `backend/Dockerfile`, a multi-stage build: a `python:3.14-slim`
  build stage installs runtime deps into a venv (`pip install .`, no dev extras);
  the slim runtime stage copies the venv + `app/`, runs as a non-root user, and
  serves `uvicorn app.main:app --host 0.0.0.0 --port 8000`. Internal only (`expose`,
  not published). Config comes from the project **`.env`** via `env_file`
  (pydantic-settings). Uploads + SQLite persist in the **`backend-data`** volume at
  `/app/data`. Traefik route (router `flux-backend`, **priority 100**):
  **`Host(kulis.aibr.cz) && PathPrefix(/api)`** → container port 8000. The `/api`
  prefix is **not** stripped (the backend mounts every route under `/api`).
- **`frontend`** — `frontend/Dockerfile`, multi-stage: a `node:24-slim` stage runs
  `npm ci && npm run build`; an `nginx:1.27-alpine` stage serves the static bundle.
  `frontend/nginx.conf` does SPA fallback and still reverse-proxies `/api` (a
  harmless fallback for non-Traefik runs). Traefik route (router `flux-frontend`):
  **`Host(kulis.aibr.cz)`** → container port 80. This is the catch-all; the
  higher-priority backend router claims `/api` first, so everything else (SPA +
  assets) lands here. Same-origin, so no prod CORS.
- **Routing rule of thumb:** `kulis.aibr.cz/api/...` → backend; everything else →
  frontend. Both app routers use `entrypoints=websecure` + `tls.certresolver=letsencrypt`.
- `VITE_API_BASE_URL` (default `/api`, relative) is baked into the bundle at build
  time via a compose build `arg` — not a runtime env var. The browser hits
  `kulis.aibr.cz/api`, which Traefik routes to the backend.
- **All three** services use `restart: always`; Docker is `systemctl enable`d so the
  stack comes back on reboot. `.dockerignore` in each app keeps `node_modules`,
  `.env`, local `data/`, and caches out of the images.

Env: copy **`.env.example`** → `.env` (git-ignored) at the repo root; it lists every
variable the stack needs, including **`DOMAIN`** (`kulis.aibr.cz`) and **`ACME_EMAIL`**
used by Traefik. Build & run: `docker compose up -d --build` (nothing is started
automatically). Validate config without starting: `docker compose config`. DNS for
`kulis.aibr.cz` must point at this host before the first request, or ACME issuance
(HTTP-01) will fail.

## Definition of done
A change is done when: the relevant tests pass, lint/format/type-check are clean, the
app runs, and this `CLAUDE.md` is updated if the workflow or commands changed.

## Open questions to confirm (from the brief)
Chamber constants (0.0625 m² / 15.625 L), IMGW pressure format & units, low-R² flag
threshold (default 0.80), and whether CSV is a third export format — confirm before
building the affected parts.
