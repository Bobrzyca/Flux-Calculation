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
**failing test first**, then the code to pass it (root rule 1). `pytest` discovers
tests recursively: the flat `tests/*.py` (unit + API integration) plus
`tests/security/` (security baseline). `tests/unit/` and `tests/integration/` are
placeholders mirroring the target layout — see `tests/README.md`. CI runs the whole
suite + ruff + mypy (`.github/workflows/test.yml`); checkov scans the Dockerfile.

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
- `GET /api/analyses/{id}/results?fit_mode=auto|full` → `ResultsPayload`
  (per-spot table; flags
  `low_r2`/`short_window`/`dropped_nan`/`no_pressure`; skipped spots carry a
  `skip_reason`). **`fit_mode`** (default `auto`; `full` blocks automatic window
  fitting → whole-recording flux for every spot; 422 `bad_fit_mode` otherwise).
  `quality_check.available` is **false** with a pending message —
  n8n is deferred (`# TODO: n8n quality check`).
- `GET /api/analyses/{id}/spots/{nr}?fit_mode=auto|full` → `SpotDetail` (per-gas
  points with `in_window`, fit incl. `n_dropped_nan` + `n_spikes`, `fit_window`,
  flux ladder, **plus `context`** — a faint wider raw record `SPOT_CONTEXT_EXTRA_SECONDS`
  before/after the stored window, re-parsed from the LI file, display-only, so the
  manual-shift control has visible surroundings) plus the fit meta `mode`,
  `fit_offset_s`, `fit_window_s`, `window_shortened`. **`fit_mode`** (default `auto`) selects the best/shortened
  window; **`full`** fits the whole recorded window as-is (no window search) — the
  "use the file's time series without fitting" view. A saved manual offset on the
  spot overrides both (`mode="manual"`). `null` for a skipped spot, 404 if the spot
  doesn't exist, 422 (`bad_fit_mode`) on an unknown `fit_mode`.
- `PUT /api/analyses/{id}/spots/{nr}/fit` (body `SpotFitUpdate` = `{offset_s: float
  | null}`) — set (or clear with `null`) a spot's **manual fit-window offset**: the
  per-spot correction for a mis-placed automatic window. `offset_s` is **relative to
  the recorded start** — positive = later, **negative = earlier** (moves the window
  into the lead margin of data before the recorded start). Persists
  `Spot.manual_offset_s`, **rewrites that spot's `FluxResult`** so the results table
  and export follow, logs the change, and returns the recomputed `SpotDetail`. 404
  if the spot doesn't exist. Manual offsets survive a re-`match` (the match step
  honours them).
- `GET /api/analyses/{id}/timeseries?fit_mode=auto|full` → `Timeseries` (per gas:
  every computed spot's points on the absolute time axis with `in_window`, the
  fit-line endpoints, **and `background`** — the rest of the raw concentration
  record not assigned to any spot, re-parsed from the stored LI-7810 file with the
  analysis offset applied, so the overview graph shows the **complete** record —
  **uniformly downsampled to `TIMESERIES_MAX_BACKGROUND_POINTS`** so a long campaign
  doesn't make Plotly stutter. A missing/unreadable stored file degrades to an empty
  `background`). 422 (`bad_fit_mode`) on an unknown `fit_mode`.
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
core/         config/settings (config.py), logging (logging.py + middleware.py),
              monitoring (monitoring.py — Sentry), chamber-constant defaults
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
- `tabular.py` (shared) centralises the tolerant reading used by the temperature
  **and** pressure parsers: `read_table` (xlsx/csv/txt, wrong-extension fallback,
  encoding + delimiter sniffing, clean `ValueError` on legacy `.xls`),
  `resolve_temporal_columns` + `to_unix_seconds` (date/time in **one or two**
  columns, unix-seconds passthrough, day/month/year order inferred from the
  values), and **`to_float_series`** — numeric coercion that tolerates
  **European comma decimals** (`13,35` → 13.35) and thousands commas
  (`1,013.25`), used by temperature, pressure, **and** the LI-7810 gases. A
  comma-decimal file used to coerce to all-NaN silently; it now parses.
- `li7810.py` locates the `SECONDS/CO2/CH4` header anywhere in the metadata
  preamble (handles LI-COR `DATAH`/`DATAU`/`DATA` markers, case-insensitive). **The
  matching timeline is built from the local `DATE`+`TIME` columns when present**, not
  the `SECONDS` column — real exports put true-unix in `SECONDS` (a different
  timezone from the field notes), so using it would misalign matching by the UTC
  offset. Falls back to `SECONDS` only when DATE/TIME are absent (or when Excel
  re-cast the DATE/TIME cells so none parse). **The DATE format is chosen by
  separator:** dotted `DD.MM.YYYY` (European, e.g. `06.10.2025` = 6 October) is
  parsed **day-first** to match the temperature loader; dashed `YYYY-MM-DD` (ISO)
  is year-first (forcing day-first on ISO makes pandas flip it to the wrong
  month).
  - **Encoding + Excel tolerance:** the text reader sniffs the encoding via the
    shared `parsing/encoding.py` (`utf-8-sig`, then Polish Windows `cp1250`, then
    `latin-1`, and honours a UTF-16 BOM) — so a Windows
    export with non-ASCII preamble bytes (`°C`, a Polish site name) or a legacy
    code page no longer raises `UnicodeDecodeError` and gets wrongly rejected as
    "not a LI-7810 export"; the header/columns/numbers we use are ASCII, so any
    encoding decodes them identically. Both `looks_like_li7810` and `parse_li7810`
    also accept the same layout saved as **`.xlsx`/`.xlsm`** (openpyxl; sniffed by
    suffix or ZIP magic) — the "open the .txt in Excel and Save As" file — reading
    it header-less, finding the header row by name, and re-keying the data. Legacy
    `.xls` is not supported (no `xlrd` dependency). The frontend concentration
    dropzone accepts `.txt,.xlsx,.xlsm` accordingly.
- `temperature.py` reads `.xlsx`/`.csv`/`.txt` and is **format-agnostic** — it
  resolves which column is which by name *and* by content, so a new logger export
  doesn't need a code change. It sniffs the **encoding** (shared
  `parsing/encoding.py`; a cp1250 `°C` no longer rejects the file). Delimiters:
  tab/`;`/`,` plus a **2+-space** fallback
  for space-aligned/fixed-width exports (keeps the single space inside a
  `YYYY-MM-DD HH:MM:SS` datetime intact). Temperature column: exact aliases, then any
  header containing `temp`/`°C`/`(c)` (ignoring extra Status/Type/CO2/RH columns).
  Date/time: the date + time may be in **one combined column** or **two separate
  columns** (English `Date`/`Time`, Polish `Data`+`Godzina`/`Czas`) — separate
  columns are recombined, and an Excel date-only cell's `00:00:00` tail is stripped
  so a separate time attaches. The **day/month/year order is inferred from the
  values**: a 4-digit leading part → ISO year-first (`2025-10-06`); a part > 12 →
  fixes the day (day-first `13.10.2025`) or the month (US `10/13/2025`); ambiguous →
  European day-first. When headers are unrecognised it falls back to the column that
  parses as the most datetimes. Unreadable / no date / no temp column → clean
  `ValueError` (→ 422).
- `notes.py` sniffs the **encoding** (shared `parsing/encoding.py`:
  utf-8-sig/cp1250/latin-1 + UTF-16 BOM — a cp1250 site name like `nad tamą` no
  longer rejects the file) and auto-detects the delimiter for `.csv`/`.txt`/`.tsv`
  (tab/`;`/`,`, plus a **2+-space** fallback for space-aligned exports so verbose
  headers/values keep their single internal spaces). Columns are resolved **intelligently** by
  `_FIELD_MATCHERS` — an exact whole-header token *and* a substring keyword, in
  English + simple Polish — so verbose real headers resolve without a hard-coded
  alias: `Start`/`End` (start/stop), `Light or Dark`/`Chamber`/`Komora`
  (light/dark), `GPS`, `Punkt`/`Pkt`/`numer` (number), `Gdzie`/`Other site
  Info`/`comment`/`uwagi` (location). Unrelated columns (`Date`,
  `Type Of Measurement` — only an exact `type` maps to light/dark —, `TEMPERATURA`)
  are ignored; each header is claimed once, in priority order, so specific fields
  win over the broad location keywords. Header whitespace/newlines are stripped
  first (a Word table may wrap `Light/dark` as `"Light\n/dark"`); a bare `?` GPS
  counts as missing.
  Spot `nr` is renumbered 1..N when the file's numbers are absent/zero or collide
  (e.g. a `4` and a `4.5` light/dark pair). All note/temperature times are read as
  naive wall-clock so they line up with the LI-7810 DATE/TIME. Legacy `.xls` is
  rejected with a clear message (openpyxl can't read it; no `xlrd` dependency).
- `pressure.py` (optional IMGW file) is built on the shared `tabular.py`, so it
  has the **same tolerance as temperature**: `.csv`/`.txt`/`.xlsx`, cp1250/UTF-16
  encodings, tab/`;`/`,`/2-space delimiters, **comma decimals**, unix-seconds
  **or** datetime timestamps in **one or two** columns, and day/month/year order
  inferred from the values. The pressure column is resolved by exact alias
  (`pressure`/`hpa`/`cisnienie`/`ciśnienie`/…) then a substring keyword. Values
  are hPa unless `assume_unit` says otherwise (kPa/Pa/mbar). A truly free-form,
  header-less IMGW export is still deferred to the LLM (`# TODO seminar 6`). The
  frontend pressure dropzone now advertises `.csv,.txt,.tsv,.xlsx` (was "any
  format", which let people drop files the backend then rejected).
- **Silent-drop logging:** `parse_li7810` records, on `df.attrs`, how many
  readings it invalidated per reason (`n_diag_invalid` = red-DIAG rows,
  `n_co2_out_of_range`/`n_ch4_out_of_range` = values outside the plausible
  ranges); the match endpoint (`_drop_log_messages`) turns each non-zero count
  into a processing-log line, so drops that used to vanish are now visible. The
  CO₂ `>= 1500` ppm plausibility bound (mirrors the R method-of-record) is
  unchanged — it can clip genuine high-flux readings, so the log now surfaces it.

The `flux/` package is the scientific core (pure, **never LLM-touched**):
`regression.py` (`fit_slope` via `scipy.stats.linregress`), `flux.py`
(`compute_flux` → the `FluxLadder`, closed-chamber formula `F = dC/dt · P·V/(R·T·A)`,
CH₄ ppb→ppm, CO₂-equivalent via GWP), `pipeline.py` (`fit_spot`: window
start+30 s→+5 min 30 s, nan drop/count, `low_r2`/`short_window` flags), and
`constants.py` (gas constants, molar masses, GWP, thresholds — the tunable numbers).
**Fit window:** `fit_spot` no longer uses a fixed offset — it **slides a
`FIT_WINDOW_SECONDS` window and picks the most-linear position** (max CO₂ R², ties
broken toward `FIT_SKIP_SECONDS` so clean spots are unchanged). The search is
**centred on the recorded start** (the `anchor_ts` passed by the API): it looks from
`FIT_SEARCH_BACK_SECONDS` *before* to `FIT_SEARCH_MAX_OFFSET_SECONDS` *after* it, so
it can reach an **earlier** slope when the hand-recorded start is late or the
instrument clock runs ahead — the main cause of spuriously low R². This needs the
matcher's lead margin (below); the reported `fit_offset_s` is relative to the
recorded start and may be **negative** (window sits earlier). The same window is
applied to both gases and the chosen offset is logged + shown. (With no anchor —
the pre-lead-margin path — offsets are measured from the first reading, unchanged.)
**Auto window-shortening:** when the best 5-min window is still below
`LOW_R2_THRESHOLD`, `fit_spot` may **shorten** it (keeping its best position) down
to `FIT_SHORTEN_MIN_SECONDS` (4 min) in `FIT_SHORTEN_STEP_SECONDS` steps, adopting a
shorter length only if it lifts R² by `FIT_SHORTEN_MIN_GAIN`. A clean spot is never
shortened; a shortened one reports `window_shortened=True`/`fit_window_s` and is
noted in the log.
**Despike:** `fit_spot` first drops **isolated single-point spikes** (`_despike_mask`
— a lone value off both agreeing neighbours by > `DESPIKE_K` × the robust step
scale; runs are never cut), counted per gas as `n_spikes` (separate from `nan`
gaps) and logged. `parse_li7810` also drops (nan) **both gases on rows the
instrument itself marks INVALID** — a `DIAG` status bit ≥ 32 ("red" codes per
LI-COR's manual Table 2-2: spectral-fit residual too high, unregulated
pressures/temperatures, inlet clogged, not ready). "Yellow" `DIAG` codes
(1–16: frequency/laser-temperature adjustment, incomplete scan, start-up) mean
*noisy but valid* and are **kept** — dropping them lost whole spots on real
campaigns. Noise on kept rows is handled **per gas** by plausibility ranges:
CO₂ in [`MIN_VALID_CO2_PPM`, `MAX_VALID_CO2_PPM`) = [0, 1500) ppm (upper bound
matches the R method; negative CO₂ is physically impossible) and CH₄ in
[`MIN_VALID_CH4_PPB`, `MAX_VALID_CH4_PPB`) = [0, 100 000) ppb (ambient ~2 000,
real chamber rises peak in the tens of thousands; laser mode-hop artefacts
cluster from ~130k up) — an implausible value nulls only that gas.
**Whole-recording mode:** `fit_spot(..., mode="full")` skips the window search and
fits the entire recorded span as-is (despiking still applies) — surfaced via the
`fit_mode=full` query param on the **results, timeseries, and spot-detail**
endpoints (the frontend Results page drives all three from one "Block auto-fit"
switch).
**Manual per-spot offset:** `fit_spot(..., manual_offset_s=…)` uses a fixed
`FIT_WINDOW_SECONDS` window starting `manual_offset_s` seconds from the recorded
start — **positive = later, negative = earlier** — and **overrides** auto/full. It
keeps its full length (shifting never truncates the window, given the lead margin),
so the researcher can slide it onto the visible slope without cutting the
measurement. The saved correction (`Spot.manual_offset_s`) is set/cleared via
`PUT …/spots/{nr}/fit`, which rewrites the spot's `FluxResult` so results + export
follow.
**Validation:** the ladder is locked by hand-computed values in `tests/test_flux.py`.
`reference/flux_reference.R` exists but is a **Python-derived scaffold** (so it can't
independently validate yet) — `# TODO: re-validate` once the real, independent R
script replaces it and is run on the 2026-07-02 Kampinos campaign.

The `matching/` package is pure: `timeshift.py` (`apply_offset` adds the
instrument-clock offset to the concentration timestamps) and `match.py`
(`slice_spot` windows the offset-corrected stream by a note's `HH:MM:SS` — or
`HH:MM`, seconds default to 0 — on the
work date; `nearest_temperature`/`nearest_pressure`; `match_spot` returns the
annotated in-window readings, the per-spot temp/pressure, skip reasons — empty
window / stop-before-start / unparseable time — the `no_pressure` flag, and
structured `LogMessage`s). **`match_spot` slices a window with a
`FIT_SEARCH_BACK_SECONDS` lead *before* the recorded start** (plus the forward
`_SLICE_SECONDS = FIT_WINDOW + FIT_SEARCH_MAX_OFFSET`), so the stored `Reading`
rows include data on both sides of the recorded start — the raw material the fit
step's backward search and the user's backward manual shift need. Spots are matched
independently, so a shared GPS (light/dark pair or redo) stays distinct. **Note:**
analyses matched before the lead margin existed store no pre-start data — re-run the
match to shift a spot earlier.

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
  stop_time, manual_offset_s)` — `start_time`/`stop_time` are `HH:MM:SS` strings
  (`PUT …/notes` normalises hand-edited times, e.g. `9:41` → `09:41:00`; a
  malformed time is stored as `""` and skips just that spot at match time);
  `manual_offset_s` (nullable) is the saved manual fit-window override (None =
  automatic). Added after initial release, so `create_db_and_tables` runs a tiny
  idempotent `ADD COLUMN` migration (`session.py:_run_lightweight_migrations`) for
  DBs created before it existed.
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

## Observability (logging + monitoring)
Structured JSON logging (`core/logging.py`) with a per-request correlation id
(`X-Request-ID`, `core/middleware.py`) and secret redaction; levels via
`LOG_LEVEL`. **Error/performance monitoring is optional Sentry** (`core/monitoring.py`,
`sentry-sdk[fastapi]`): **off unless `SENTRY_DSN` is set** — the app must always
start/run without it. When on, it auto-captures unhandled exceptions (→5xx),
stamps the same `request_id` on every event (so an issue links to the logs), and
redacts sensitive values with the logger's key list. Env: `SENTRY_DSN`,
`SENTRY_ENVIRONMENT`, `SENTRY_RELEASE` (git SHA), `SENTRY_TRACES_SAMPLE_RATE`. See
`../docs/operations.md` (logging) and `../report.md` (monitoring, alert rules).

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
