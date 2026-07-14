# Chunk 5 — Notes and pressure parsers (deterministic; LLM deferred)

**Description:** Parse the time-window notes and the IMGW pressure file with
**plain deterministic code** — no LLM. The brief's tolerant, messy-format parsing
is the seminar-6 smart feature; here we handle the well-formed cases and leave a
clear TODO for the LLM upgrade. The pipeline must work end-to-end without any AI.

## Exactly what to do
1. **`app/parsing/notes.py`** — `parse_notes(path) -> list[NoteRow-like dicts]`
   for CSV/XLSX/DOCX inputs with columns `Nr, Start, Stop, GPS, light/dark,
   location` (accept common header spellings, including simple Polish ones like
   `Nr, Początek, Koniec`). For each row return `nr, start_time (HH:MM:SS),
   stop_time, gps, light_dark ('light'|'dark'), location`.
   - Normalise clean time formats: `9.38`, `9:38`, `09:38:00` → `HH:MM:SS`.
   - Do **not** attempt to repair genuinely messy handwriting/OCR noise — that is
     the LLM's job. Where a value can't be parsed, keep it blank/raw and let the
     validation step flag it.
   - Add a module-level comment: `# TODO: LLM tolerant parsing of messy field
     notes (seminar 6). This deterministic parser covers well-formed files.`
2. **`app/parsing/pressure.py`** — `parse_pressure(path) -> list[{timestamp,
   pressure_hpa}]` for a CSV/XLSX with a timestamp column and a pressure column
   (assume hPa; make the unit a parameter/constant so it's easy to confirm
   later). Same TODO comment for the LLM "unknown-format" tolerance.
3. **Validation helper** `validate_notes(rows) -> rows with flags` producing the
   frontend's `NoteFlag`s: `stop_before_start`, `gps_missing`,
   `unparseable_time`, `location_missing`. (Times parse; stop > start.)
4. **Fixtures:** add `sample_data/notes_sample.csv` (or `.xlsx`) and
   `sample_data/pressure_sample.csv` matching the shapes above, including at
   least one row with a blank GPS and one clean row.

## Files created / changed
- New: `app/parsing/notes.py`, `app/parsing/pressure.py`, notes/pressure
  fixtures under `sample_data/`.
- New tests: `tests/test_parse_notes.py`, `tests/test_parse_pressure.py`.

## How to verify
- Notes test: clean rows parse to `HH:MM:SS`; `9.38` → `09:38:00`; a stop-before-
  start row gets the `stop_before_start` flag; a blank GPS gets `gps_missing`.
- Pressure test: parses timestamps + hPa values, sorted by time.
- `pytest`, `ruff`, `mypy` clean.

## Dependencies
Chunk 1; shares the fixtures pattern from chunk 4.

## Reminder
Follow the repo `CLAUDE.md` rules: tests first, lint/format/type-check clean,
Conventional Commits (`feat:`). Keep the LLM strictly out of scope here — only
the `# TODO: LLM ... (seminar 6)` markers.

Commit and push.
