# Chunk 4 — Sample fixtures + LI-7810 and temperature parsers

**Description:** Build the two well-specified file parsers (pure functions, no
HTTP): the LI-7810 concentration log and the temperature xlsx. Create small
sample fixtures under `sample_data/` so tests (and later the running app) have
real files to work on.

## Exactly what to do
1. **`sample_data/`** — create small but realistic fixtures:
   - `li7810_sample.txt`: tab-delimited, **2 header rows** then `DATA` rows with
     columns including `SECONDS` (unix), `CO2` (ppm), `CH4` (**ppb**). Include a
     short warm-up block of `nan` rows at the top (laser stabilising) and a few
     `nan` rows mid-stream. ~a few hundred rows spanning two spot windows is
     plenty.
   - `temperature_sample.xlsx`: columns `Date` (timestamps ~every 30 s) and
     `Temp` (°C), openpyxl-written.
2. **`app/parsing/li7810.py`** — `parse_li7810(path) -> DataFrame` (or typed
   rows) with columns `timestamp` (unix seconds, float), `co2_ppm`, `ch4_ppb`:
   - Skip the 2 header rows; read the `DATA` rows.
   - Coerce numerics; keep `nan` as `nan` (do **not** drop here — dropping is the
     matching/fitting step's job, which also reports it).
   - Provide `looks_like_li7810(path) -> bool` (or a validation function) that
     checks for the expected `SECONDS`, `CO2`, `CH4` columns, used later by the
     upload endpoint to produce the message "This doesn't look like a LI-7810
     export — expected columns SECONDS, CO2, CH4."
3. **`app/parsing/temperature.py`** — `parse_temperature(path) -> DataFrame`
   with `timestamp` + `temperature_c`, sorted by time.
4. Keep both modules pure and importable without FastAPI.

## Files created / changed
- New: `sample_data/li7810_sample.txt`, `sample_data/temperature_sample.xlsx`
  (or a script that generates it), `app/parsing/li7810.py`,
  `app/parsing/temperature.py`.
- New tests: `tests/test_parse_li7810.py`, `tests/test_parse_temperature.py`.

## How to verify
- LI-7810 test: parses the sample, returns the right column set, preserves
  `nan`s, and `looks_like_li7810` returns `True` for the sample and `False` for a
  bogus file (e.g. the temperature file or a random CSV).
- Temperature test: parses the xlsx, timestamps monotonic, temperatures numeric.
- `pytest`, `ruff`, `mypy` clean.

## Dependencies
Chunk 1. (Independent of the DB; can be done any time after init.)

## Reminder
Follow the repo `CLAUDE.md` rules: tests first (fixtures + failing assertions),
keep lint/format/type-check clean, Conventional Commits (`feat:`). Note in
`backend/CLAUDE.md` that `sample_data/` holds parser fixtures.

Commit and push.
