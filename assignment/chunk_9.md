# Chunk 9 — Parsed-notes API: GET and PUT notes (Confirm screen)

**Description:** Back the Confirm screen. Return the parsed notes (with
per-row flags) for review, and accept the user's edited/confirmed rows before
matching. Human-in-the-loop checkpoint.

## Exactly what to do
1. **`app/schemas/notes.py`** — Pydantic models matching the frontend: `NoteRow`
   (`nr, start_time, stop_time, gps, light_dark, location, flags[]`) and
   `ParsedNotes` (`parse_failed: bool, rows: NoteRow[]`). `flags` values:
   `stop_before_start | gps_missing | unparseable_time | location_missing`.
2. **Extend `app/api/analyses.py`** (or a new `app/api/notes.py` router):
   - `GET /api/analyses/{id}/notes` → the `Spot` rows for the analysis as
     `ParsedNotes`, each row re-validated so flags are current (chunk 5's
     `validate_notes`). Set `parse_failed=false` for the deterministic path.
     (When the LLM parser exists in seminar 6 and fails, it will set
     `parse_failed=true` — leave a `# TODO: LLM parse_failed fallback (seminar
     6)` note.)
   - `PUT /api/analyses/{id}/notes` → accept edited rows, re-validate, and
     persist them as the analysis's `Spot` rows (replace the set; handle
     added/deleted rows). Return the saved `ParsedNotes`. Reject only on
     malformed payload — soft issues (missing GPS) are allowed through as flags;
     it's the match step that skips hard-error rows.
3. 404 if the analysis doesn't exist.

## Files created / changed
- New: `app/schemas/notes.py` (and optionally `app/api/notes.py`).
- Changed: notes endpoints wired into `main.py`.
- New tests: `tests/test_api_notes.py`.

## How to verify
- Tests: after creating an analysis (chunk 8), `GET .../notes` returns the parsed
  rows with correct flags (blank-GPS row flagged, stop-before-start row flagged);
  `PUT .../notes` with corrected times clears the hard-error flag and persists;
  adding and deleting a row round-trips; unknown id → 404.
- `pytest`, `ruff`, `mypy` clean.

## Dependencies
Chunks 3 (Spot model), 5 (notes parse + validate), 8 (an analysis to attach
notes to).

## Reminder
Follow the repo `CLAUDE.md` rules: tests first, lint/format/type-check clean,
Conventional Commits (`feat:`). Update `backend/CLAUDE.md` with the endpoints.

Commit and push.
