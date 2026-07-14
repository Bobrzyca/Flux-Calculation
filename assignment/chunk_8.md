# Chunk 8 — Analyses API: create, list, get, delete

**Description:** The first HTTP surface. Implement the analysis lifecycle
endpoints the frontend's Home and Upload screens call: create (multipart upload
of the four files + constants), list, get one, delete. On create, store the raw
files, validate the LI-7810 format, persist the `Analysis`, and parse the notes
so the Confirm screen has rows.

## Exactly what to do
1. **`app/schemas/analysis.py`** — Pydantic response models matching the
   frontend `types.ts`: `AnalysisSummary` (`id, name, work_date, spot_count,
   status, created_at`) and `Analysis` (adds `chamber_area_m2,
   chamber_volume_l, time_offset_seconds`).
2. **`app/api/analyses.py`** — an `APIRouter` (mounted at `/api/analyses` in
   `main.py`):
   - `POST /api/analyses` — `multipart/form-data`: fields `name, work_date,
     chamber_area_m2, chamber_volume_l, time_offset_seconds` + files
     `concentration, notes, temperature, pressure`. Steps:
     1. Validate all four files present (else 422 naming the missing one).
     2. Validate the LI-7810 file with `looks_like_li7810` (else 422 with the
        exact message from chunk 4).
     3. Reject a duplicate `name` (409, so the frontend can offer rename/overwrite).
     4. Create the `Analysis` (status `needs_review`), save files via storage,
        parse notes (chunk 5) into `Spot` rows (unconfirmed), write initial log
        entries.
     5. Return the created `Analysis`.
   - `GET /api/analyses` — list `AnalysisSummary`, newest first.
   - `GET /api/analyses/{id}` — one `Analysis` (404 if missing).
   - `DELETE /api/analyses/{id}` — remove the analysis, its children, and its
     stored files (204/200).
3. Match the frontend's error branches: the mock injects a duplicate-name error
   and a bad-LI-7810 error — mirror those with real 409/422 responses and clear
   messages.

## Files created / changed
- New: `app/schemas/analysis.py`, `app/api/analyses.py`.
- Changed: `app/main.py` (include the router).
- New tests: `tests/test_api_analyses.py`.

## How to verify
- Tests with `TestClient` (multipart): create returns 201/200 with an id and
  `status: needs_review`; missing a file → 422 naming it; bad LI-7810 → 422 with
  the expected message; duplicate name → 409; list returns it newest-first; get
  returns full constants; delete removes it and its files from `data/`.
- `pytest`, `ruff`, `mypy` clean; server boots.

## Dependencies
Chunks 1, 3 (DB + storage), 4 (LI-7810 validation), 5 (notes parser).

## Reminder
Follow the repo `CLAUDE.md` rules: tests first, lint/format/type-check clean,
Conventional Commits (`feat:`). Update `backend/CLAUDE.md` "API structure" with
the new endpoints.

Commit and push.
