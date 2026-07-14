# Chunk 3 — Database models, session, and file storage

**Description:** Implement the SQLite persistence layer with SQLModel and a small
file-storage helper. This is the data foundation every endpoint builds on. No
HTTP routes yet — just models, a session/engine, table creation on startup, and
a place to save uploaded files.

## Exactly what to do
1. **`app/db/models.py`** — SQLModel table models matching `project-brief.md`
   "Data stored by the application":
   - `Analysis`: `id` (str/UUID PK), `name`, `work_date` (date), `chamber_area_m2`
     (float), `chamber_volume_l` (float), `time_offset_seconds` (int/float),
     `status` (str: `draft|needs_review|complete`), `created_at` (datetime).
   - `Spot`: `id` PK, `analysis_id` FK, `nr` (int), `gps` (str), `light_dark`
     (str), `location_desc` (str), `start_time` (str `HH:MM:SS`), `stop_time`
     (str).
   - `Reading`: `id` PK, `spot_id` FK, `timestamp` (float unix or datetime),
     `co2_ppm` (float|null), `ch4_ppb` (float|null), `temperature_used`
     (float|null), `pressure_used` (float|null).
   - `FluxResult`: `id` PK, `spot_id` FK, `gas` (str `CO2|CH4`), `slope`, `r2`,
     and the full unit ladder columns exactly as in the brief
     (`flux_umol_m2_s, flux_umol_m2_h, flux_mol_m2_h, flux_gC_m2_day,
     flux_kg_m2_h, flux_kg_ha_h, flux_kg_ha_day, flux_kg_ha_year,
     flux_Mg_ha_year, flux_Mg_ha_year_co2equiv`), `n_points` (int).
   - Add a `ProcessingLogEntry` table too: `id` PK, `analysis_id` FK, `ts`
     (datetime), `severity` (str `info|warning|error`), `message` (str) — the
     processing log needs to persist.
2. **`app/db/session.py`** — create the SQLModel engine from
   `settings.database_url`, a `get_session()` dependency (yields a `Session`),
   and `create_db_and_tables()`.
3. **`app/main.py`** — call `create_db_and_tables()` on startup (lifespan
   handler). Ensure `settings.data_dir` exists at startup.
4. **`app/db/storage.py`** — helpers to save an uploaded file to
   `data/<analysis_id>/<role>.<ext>` and return the stored path; and to read it
   back. Roles: `concentration`, `notes`, `temperature`, `pressure`. Keep raw
   files so a campaign can be re-run (per the brief).
5. Keep IDs stable and URL-safe (UUID4 hex is fine).

## Files created / changed
- New: `app/db/models.py`, `app/db/session.py`, `app/db/storage.py`.
- Changed: `app/main.py` (startup/lifespan), possibly `app/core/config.py`.
- New tests: `tests/test_db.py`, `tests/test_storage.py`.

## How to verify
- `tests/test_db.py`: create an in-memory (or temp-file) engine, create tables,
  insert an `Analysis` with child `Spot`/`Reading`/`FluxResult`/log rows, read
  them back, assert relationships and the full ladder columns exist.
- `tests/test_storage.py`: save a fake uploaded file, assert it lands under
  `data/<id>/concentration.txt` and reads back byte-identical.
- Server still boots; `GET /api/health` still 200.
- `pytest`, `ruff`, `mypy` all clean.

## Dependencies
Chunk 1 (project + config + server).

## Reminder
Follow the repo `CLAUDE.md` rules: write the failing DB/storage tests first,
keep lint/format/type-check clean, Conventional Commits (`feat:`). Update
`backend/CLAUDE.md` if the schema you implement differs from what you documented.

Commit and push.
