# Chunk 10 — Match & compute endpoint (the pipeline core)

**Description:** Wire the pure logic (time-shift, matching, flux) behind
`POST /api/analyses/{id}/match`. On approval this parses the concentration/
temperature/pressure files, applies the offset, slices per-spot windows,
attaches temperature/pressure, fits both gases, computes the full unit ladder,
and persists `Reading` + `FluxResult` + processing-log rows. Sets the analysis
status to `complete`.

## Exactly what to do
1. **`app/api/match.py`** (or extend the analyses router) — `POST
   /api/analyses/{id}/match`:
   1. Load the analysis + its confirmed `Spot` rows + stored file paths.
   2. Parse concentration (chunk 4), temperature (chunk 4), pressure (chunk 5).
   3. Apply the time-offset (chunk 7).
   4. For each spot: slice its window, attach nearest temperature/pressure
      (chunk 7); skip + log spots with empty windows or stop ≤ start.
   5. Persist the in-window `Reading` rows (with `temperature_used`,
      `pressure_used`).
   6. For each non-skipped spot × gas: drop in-window `nan`s (count them), fit
      slope + R² and compute the ladder (chunk 6); persist two `FluxResult` rows.
   7. Write `ProcessingLogEntry` rows throughout (offset applied, rows dropped,
      pressure matched, spots skipped, warm-up ignored silently, fit summary).
   8. Set `status = complete`. Return 200 (empty body or a small summary).
2. Make the operation idempotent-ish: re-running clears the previous `Reading`/
   `FluxResult`/log for that analysis before recomputing (supports the
   "overwrite" re-run path).
3. Keep the endpoint thin — it orchestrates the pure modules; no math inline.

## Files created / changed
- New/changed: `app/api/match.py` (wired into `main.py`).
- New tests: `tests/test_api_match.py`.

## How to verify
- Test: create an analysis from fixtures (chunk 8), confirm notes (chunk 9),
  `POST .../match` → 200; then assert in the DB that `Reading` rows exist for
  in-window readings, two `FluxResult` rows per non-skipped spot with sane
  slope/R²/ladder, the skipped spot has none, log entries recorded (offset,
  nan-drop, skip), and `status == complete`.
- Numbers line up with the chunk-6 flux tests for a known spot.
- `pytest`, `ruff`, `mypy` clean.

## Dependencies
Chunks 3, 4, 5, 6, 7, 8, 9 — this is where they all come together.

## Reminder
Follow the repo `CLAUDE.md` rules: tests first, lint/format/type-check clean,
Conventional Commits (`feat:`). Update `backend/CLAUDE.md` (pipeline + endpoint).

Commit and push.
