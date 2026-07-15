# CLAUDE.md — Flux Calculation backend

Standing instructions for the **Python + FastAPI backend**. Read this alongside the
root [`../CLAUDE.md`](../CLAUDE.md) (cross-app picture and engineering rules) and
[`../project-brief.md`](../project-brief.md) (the product spec — the source of truth
for behaviour, data, and edge cases).

The backend ingests raw closed-chamber greenhouse-gas files — concentration, time
notes, and temperature are required; the IMGW **pressure file is optional** (when
absent the flux math falls back to a default sea-level pressure, and every affected
spot is flagged `no_pressure`). It matches them by
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
- **Errors** use `app/api/errors.py:api_error(...)` → body
  `{"detail": {code, message, field?}}` so the frontend rebuilds its
  `ApiError { code, field }`.

**Endpoints so far:**
- `GET /api/health` — liveness.
- `POST /api/analyses` — multipart (`name, work_date, chamber_area_m2,
  chamber_volume_l, time_offset_seconds` + files `concentration, notes,
  temperature` required, `pressure` **optional**). 422 `missing_file` (only for a
  missing *required* file)/`bad_li7810`, 409 `duplicate_name`; on success stores the
  uploaded files, creates the `Analysis` (status `needs_review`), and parses notes
  into unconfirmed `Spot` rows.
- `PUT /api/analyses/{id}` — edit an existing analysis (the "change files / re-run"
  flow). Same multipart shape as create, but **all files optional**: only uploaded
  files are replaced (old file for that role removed first), the rest kept; a
  replaced concentration is re-validated as LI-7810; rename collisions 409. Replacing
  inputs resets status to `needs_review` and clears prior `Reading`/`FluxResult`/log
  rows (re-confirm + re-match); if the notes file was replaced the `Spot` set is
  rebuilt from it. 404 if unknown.
- `GET /api/analyses` — summaries, newest first. `GET /api/analyses/{id}` — one
  (404). `DELETE /api/analyses/{id}` — removes the analysis, its children, and its
  stored files (204).
- `GET /api/analyses/{id}/notes` → `ParsedNotes` (Spot rows with freshly computed
  `NoteFlag`s; `parse_failed` always False for now — `# TODO: LLM fallback`).
  `PUT /api/analyses/{id}/notes` (body: `NoteRow[]`) replaces the spot set with the
  confirmed/edited rows, re-validates, and returns the saved `ParsedNotes` (404 if
  the analysis is missing).
- `POST /api/analyses/{id}/match` — the pipeline core: parse stored files → apply
  offset → per-spot slice + attach temp/pressure → fit both gases → persist
  `Reading` + `FluxResult` + `ProcessingLogEntry` → status `complete`. Skips
  empty-window / stop-before-start spots (logged). **Pressure is optional**: with no
  pressure file (or no reading near a spot) the flux uses
  `constants.DEFAULT_PRESSURE_HPA` (1013.25 hPa = 1 atm) and the spot is
  flagged/logged `no_pressure`; temperature is still required to compute a spot. An
  unreadable stored file returns a clean **422** (`bad_concentration`/
  `bad_temperature`/`bad_pressure`) on the right field rather than a 500.
  **Idempotent**: clears the previous run's rows first. Returns a `MatchSummary`. The
  router is thin — all math is in `flux/` + `matching/`. **The matching date comes
  from the concentration file's own `DATE`, not the form's `work_date`** (a wrong
  hand-typed date would otherwise put every window on the wrong day → all empty);
  the analysis's `work_date` is corrected to the data's date.
- `GET /api/analyses/{id}/results` → `ResultsPayload` (per-spot table; flags
  `low_r2`/`short_window`/`dropped_nan`/`no_pressure`; skipped spots carry a
  `skip_reason`). `quality_check.available` is **false** with a pending message —
  n8n is deferred (`# TODO: n8n quality check`).
- `GET /api/analyses/{id}/spots/{nr}` → `SpotDetail` (per-gas points with
  `in_window`, fit incl. `n_dropped_nan`, `fit_window`, flux ladder); `null` for a
  skipped spot, 404 if the spot doesn't exist.
- `GET /api/analyses/{id}/log` → the `ProcessingLogEntry` rows in order.
- Read endpoints recompute per-spot fits from the persisted `Reading` rows via the
  same `fit_spot` pipeline (one code path); `FluxResult` stays the durable record
  the export reads.
- `GET /api/analyses/{id}/export?format=xlsx|txt|csv` (default `xlsx`, 422 on
  unknown, 404 on unknown analysis) — streams a download with the identity columns
  + conditions + **full unit ladder per gas**, built from `FluxResult` by the
  reusable `app/export/tabular.py:build_table`. `Content-Disposition` uses the
  analysis name.

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
`tests/` mirrors this layout. `sample_data/` holds small, realistic parser
fixtures (`li7810_sample.txt`, `temperature_sample.xlsx`, …) used by tests and the
demo; `sample_data/generate_samples.py` regenerates them deterministically. The
`parsing/` modules are pure functions (no FastAPI): `li7810.py` (`parse_li7810`,
`looks_like_li7810`), `temperature.py` (`parse_temperature`), `notes.py`
(`parse_notes` + `validate_notes` producing the `NoteFlag`s; CSV/XLSX/DOCX, English
+ simple Polish headers), and `pressure.py` (`parse_pressure`, hPa). The
notes/pressure parsers are deterministic and cover well-formed files only; tolerant
parsing of messy notes is the deferred LLM feature (`# TODO ... seminar 6`).

**Real-export robustness (all times treated as naive local wall-clock):**
- `li7810.py` locates the `SECONDS/CO2/CH4` header anywhere in the metadata
  preamble (handles LI-COR `DATAH`/`DATAU`/`DATA` markers, case-insensitive). **The
  matching timeline is built from the local `DATE`+`TIME` columns when present**, not
  the `SECONDS` column — real exports put true-unix in `SECONDS` (a different
  timezone from the field notes), so using it would misalign matching by the UTC
  offset. Falls back to `SECONDS` only when DATE/TIME are absent.
- `temperature.py` reads `.xlsx`/`.csv`/`.txt`, auto-detects tab/`;`/`,` delimiters,
  resolves the date and temperature columns flexibly (e.g. `Temp(°C)`), and parses
  **day-first** dotted dates (`DD.MM.YYYY HH:MM`). Unreadable → clean `ValueError`.
- `notes.py` auto-detects the delimiter for `.csv`/`.txt`/`.tsv` (tab/`;`/`,`);
  **normalises header whitespace** (a Word table cell may wrap `Light/dark` as
  `"Light\n/dark"` — the newline must not break resolution); recognises Polish
  headers incl. `Punkt`/`Pkt` (number), `Chamber`/`Komora` (light/dark), `End`
  (stop), `Gdzie`/`comment`/`komentarz`/`uwagi` (location, shown as "Comment" in the
  UI + export); a bare `?` GPS counts as missing.
  Spot `nr` is renumbered 1..N when the file's numbers are absent/zero or collide
  (e.g. a `4` and a `4.5` light/dark pair). All note/temperature times are read as
  naive wall-clock so they line up with the LI-7810 DATE/TIME.

The `flux/` package is the scientific core (pure, **never LLM-touched**):
`regression.py` (`fit_slope` via `scipy.stats.linregress`), `flux.py`
(`compute_flux` → the `FluxLadder`, closed-chamber formula `F = dC/dt · P·V/(R·T·A)`,
CH₄ ppb→ppm, CO₂-equivalent via GWP), `pipeline.py` (`fit_spot`: window
start+30 s→+5 min 30 s, nan drop/count, `low_r2`/`short_window` flags), and
`constants.py` (gas constants, molar masses, GWP, thresholds — the tunable numbers).
**Fit window:** `fit_spot` no longer uses a fixed offset — it **slides a
`FIT_WINDOW_SECONDS` window and picks the most-linear position** (max CO₂ R², ties
broken toward `FIT_SKIP_SECONDS` so clean spots are unchanged), up to
`FIT_SEARCH_MAX_OFFSET_SECONDS` after the recorded start; the same window is applied
to both gases and the chosen offset is reported (`fit_offset_s`, logged + shown in
the per-spot fit window). This absorbs the lag between hand-recorded times and the
instrument clock (the main cause of spuriously low R²). `parse_li7810` also drops
CO₂ ≥ `MAX_VALID_CO2_PPM` (1500 ppm) sensor spikes, matching the R method.
**Validation:** the ladder is locked by hand-computed values in `tests/test_flux.py`.
`reference/flux_reference.R` exists but is a **Python-derived scaffold** (so it can't
independently validate yet) — `# TODO: re-validate` once the real, independent R
script replaces it and is run on the 2026-07-02 Kampinos campaign.

The `matching/` package is pure: `timeshift.py` (`apply_offset` adds the
instrument-clock offset to the concentration timestamps) and `match.py`
(`slice_spot` windows the offset-corrected stream by a note's `HH:MM:SS` on the
work date; `nearest_temperature`/`nearest_pressure`; `match_spot` returns the
annotated in-window readings, the per-spot temp/pressure, skip reasons — empty
window / stop-before-start / unparseable time — the `no_pressure` flag, and
structured `LogMessage`s). Spots are matched independently, so a shared GPS
(light/dark pair or redo) stays distinct.

Persistence lives in `app/db/`: `models.py` (SQLModel tables), `session.py` (the
engine, `get_session` dependency, and `create_db_and_tables`, called from the
startup lifespan in `main.py`), and `storage.py` (raw-file storage helpers). Raw
uploaded files are kept on disk under **`data/<analysis_id>/<role>.<ext>`** where
`role` is one of `concentration | notes | temperature | pressure` (original
extension preserved), so any campaign can be re-run. `DATA_DIR` sets the base dir
(default `./data`, created on startup); the SQLite DB defaults to `data/flux.db`
(`DATABASE_URL`).

## Database schema
SQLite via SQLModel, **five tables**. Primary keys are URL-safe UUID4 hex strings.
Columns mirror `project-brief.md` → "Data stored by the application" (with an added
`status` on `Analysis` and a `ProcessingLogEntry` table for the persisted log).

- **`Analysis`** `(id, name, work_date, chamber_area_m2, chamber_volume_l,
  time_offset_seconds, status, created_at)` — `status` is
  `draft | needs_review | complete`.
- **`Spot`** `(id, analysis_id, nr, gps, light_dark, location_desc, start_time,
  stop_time)` — `start_time`/`stop_time` are `HH:MM:SS` strings.
- **`Reading`** `(id, spot_id, timestamp, co2_ppm, ch4_ppb, temperature_used,
  pressure_used)` — concentrations are nullable (`nan` rows stored as null).
- **`FluxResult`** `(id, spot_id, gas, slope, r2, flux_umol_m2_s, flux_umol_m2_h,
  flux_mol_m2_h, flux_gC_m2_day, flux_kg_m2_h, flux_kg_ha_h, flux_kg_ha_day,
  flux_kg_ha_year, flux_Mg_ha_year, flux_Mg_ha_year_co2equiv, n_points)`
- **`ProcessingLogEntry`** `(id, analysis_id, ts, severity, message)` — `severity`
  is `info | warning | error`.

Relationships: `Analysis` → many `Spot` and `ProcessingLogEntry`; `Spot` → many
`Reading` and `FluxResult`.

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
