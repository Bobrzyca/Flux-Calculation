# CLAUDE.md — Flux Calculation backend

Standing instructions for the **Python + FastAPI backend**. Read this alongside the
root [`../CLAUDE.md`](../CLAUDE.md) (cross-app picture and engineering rules) and
[`../project-brief.md`](../project-brief.md) (the product spec — the source of truth
for behaviour, data, and edge cases).

The backend ingests four raw closed-chamber greenhouse-gas files, matches them by
timestamp, fits a linear regression per gas per spot, and computes CO₂/CH₄ flux
across a full unit ladder. **The flux math is pure code and never LLM-touched;** the
LLM only normalises messy input formats, and its output is always human-confirmed.

## Tech stack
- **Python 3.14**, **FastAPI** served with **uvicorn**.
- Data/math: **pandas**, **numpy**, **scipy** (`scipy.stats.linregress` for slope + R²).
- Files: **openpyxl** (xlsx), **python-docx** (Word notes).
- DB: **SQLite** via **SQLModel** (SQLAlchemy under the hood) — one file per install.
- Config: **pydantic-settings** (`app/core/config.py`, loads `.env`).
- Uploads: **python-multipart** (FastAPI file uploads).
- Tests: **pytest** (+ **httpx** / FastAPI `TestClient`).
- Lint/format + types: **ruff** (lint *and* format) and **mypy** (strict).
- Deps live in **`pyproject.toml`** (hatchling build), installed into a **venv**.

## How to run
From `backend/`:
```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"        # runtime + dev deps
cp .env.example .env           # then edit as needed; .env is git-ignored
uvicorn app.main:app --reload  # serves on http://localhost:8000
```
Health check (used by tests and ops):
```bash
curl http://localhost:8000/api/health   # -> {"status":"ok","app":"Flux Calculation API"}
```
CORS is preconfigured for the Vite dev server (`http://localhost:5173`); adjust
`CORS_ORIGINS` in `.env` if the frontend runs elsewhere.

## How to test / lint
From `backend/`, with the venv active:
```bash
pytest                    # run the suite (config in pyproject: testpaths=tests, -q)
ruff check .              # lint
ruff format --check .     # formatting (drop --check to apply)
mypy .                    # strict type-check (files = ["app"])
```
All four must be **green before every commit** (root rule 2). Write or update a
**failing test first**, then the code to pass it (root rule 1).

## API structure
- **Route prefix:** everything the frontend calls lives under **`/api`** (e.g.
  `/api/health`, later `/api/analyses`, `/api/results`).
- **Routers** live in **`app/api/`** — one module per resource area (upload,
  analyses, results, webhooks). Wire each router into the app in **`app/main.py`**
  via `app.include_router(...)`.
- **Request/response models** are Pydantic models in **`app/schemas/`**. Routers
  speak schemas, not raw dicts or ORM rows.
- **Pure logic stays out of routers.** Parsing, matching, and flux math live in
  `app/parsing/`, `app/matching/`, `app/flux/` as plain, testable functions;
  routers orchestrate and translate to/from schemas.

**Pipeline overview** (the end-to-end flow the endpoints assemble):
```
upload → parse notes (LLM, seminar 6) → confirm (human edits) → match by timestamp
       → fit slope + compute flux (pure code) → results / processing log / export
```

## Layout (`app/`)
```
main.py       FastAPI entry + route wiring; /api/health lives here for now
api/          routers (one module per resource area)
core/         config/settings (config.py), chamber-constant defaults
parsing/      LI-7810, temperature, notes, pressure loaders (pure)
llm/          notes/pressure parser — prompt + schema + validation (TODO: seminar 6)
matching/     time-shift + auto-match by timestamp (pure)
flux/         regression + closed-chamber flux + unit ladder (pure)
db/           SQLModel models, session, migrations
schemas/      Pydantic request/response models
```
`tests/` mirrors this layout; `sample_data/` holds small fixture files for tests.
Raw uploaded files are stored on disk under **`data/`** (created on startup, path
from `DATA_DIR`) and referenced by the `Analysis`, so any campaign can be re-run.
The SQLite DB defaults to `data/flux.db` (`DATABASE_URL`).

## Database schema
SQLite, four tables (columns copied from `project-brief.md` → "Data stored by the
application"). Raw files sit on disk under `data/` and are referenced by the
`Analysis`.

- **`Analysis`** `(id, name, work_date, chamber_area_m2, chamber_volume_l,
  time_offset_seconds, created_at)`
- **`Spot`** `(id, analysis_id, nr, gps, light_dark, location_desc, start_time,
  stop_time)`
- **`Reading`** `(id, spot_id, timestamp, co2_ppm, ch4_ppb, temperature_used,
  pressure_used)`
- **`FluxResult`** `(id, spot_id, gas, slope, r2, flux_umol_m2_s, flux_umol_m2_h,
  flux_mol_m2_h, flux_gC_m2_day, flux_kg_m2_h, flux_kg_ha_h, flux_kg_ha_day,
  flux_kg_ha_year, flux_Mg_ha_year, flux_Mg_ha_year_co2equiv, n_points)`

## How to add an endpoint (the recipe)
1. **Write the test first** in `backend/tests/` (mirror the `app/` path); assert the
   route, status, and response shape — watch it fail.
2. **Define the schemas** (request + response) in `app/schemas/`.
3. **Put the real work in a pure module** (`parsing/` / `matching/` / `flux/` /
   `db/`) as functions with no FastAPI imports — easy to unit-test in isolation.
4. **Add/extend a router** in `app/api/`: thin handler that validates input, calls
   the pure logic, returns a schema.
5. **Wire it** into `app/main.py` (`app.include_router(...)`), keeping the `/api`
   prefix.
6. **Green up:** `pytest`, `ruff check . && ruff format --check .`, `mypy .`.
7. **Update the docs in the same commit** (see the update rule below).

## Deferred features (the app must run fully without either)
- **LLM field-notes/pressure parser** (`app/llm/`) — **TODO: seminar 6.** Until then
  the notes/pressure are hand-editable; `LLM_API_KEY` in `.env` is a placeholder and
  stays blank. Nothing downstream may hard-depend on the LLM being configured.
- **n8n quality-check workflow** — **TODO: later seminar.** Results always compute
  and display without it; a missing quality check is a note on the results, never a
  failure.

## The update rule
**When you add a feature, add or change an endpoint, or change the
structure/commands, update this file (and the root `../CLAUDE.md` if the cross-app
picture changed) in the same commit.** Keep the API structure, DB schema, layout,
and commands here true to the code. Docs drift is a bug.
