# Chunk 14 — End-to-end testing and polish

**Description:** Prove the whole app works together and tidy the rough edges.
One automated end-to-end pass over the real pipeline, a validation check against
the scientific method-of-record, and a polish sweep of states, accessibility,
and docs.

## Exactly what to do
1. **Backend E2E test** (`backend/tests/test_e2e.py`): drive the full pipeline
   through the HTTP API in one test — create an analysis from the `sample_data`
   files → GET notes → PUT confirmed notes → POST match → GET results, a spot
   detail, the log → export. Assert the numbers are stable and the skipped/low-R²
   spots behave as expected.
2. **Scientific validation:** confirm the computed fluxes for a known campaign
   match the method-of-record. If `reference/` (the cleaned R script + its sample
   output) exists, compare Python vs R for a known spot and assert they agree
   within tolerance; if it doesn't exist yet, assert against the locked
   hand-computed expected values from chunk 6 and note the R cross-check as
   follow-up. Investigate any disagreement.
3. **Frontend polish sweep:** verify every data screen's **empty / loading /
   error** states against the real API (stop the backend to see error states;
   an analysis with all spots skipped to see the results empty message). Confirm
   skeletons match layout (no shift), toasts fire on export/delete, the pipeline
   step indicator shows during real match latency.
4. **Accessibility pass:** keyboard-only walk of the main flow (stepper, dropzones,
   editable notes cells, table rows, export menu, spot drawer Esc-to-close);
   check focus rings, focus trap, and that the regression plot's text alternative
   is present. Spot-check WCAG AA contrast in light and dark.
5. **Cross-cutting checks:** CORS works from the dev origin; file-size limit
   (~50 MB) handled; a re-run overwrites cleanly; `.env` still git-ignored; no
   mock imports remain in the frontend runtime.
6. **Docs:** update root `CLAUDE.md`, `backend/CLAUDE.md`, `frontend/CLAUDE.md`
   "Commands" / run instructions so a fresh clone can start both apps. Confirm
   the deferred features are clearly marked everywhere they surface: `TODO: LLM
   field-notes parser (seminar 6)`, `TODO: n8n quality check (later seminar)`.

## Files created / changed
- New: `backend/tests/test_e2e.py` (and any small frontend integration test
  added).
- Changed: minor fixes surfaced by the sweep; `CLAUDE.md` files.

## How to verify
- `backend`: `pytest` (incl. the E2E test), `ruff`, `mypy` all clean.
- `frontend`: `npm run lint && npm run format:check && npm run typecheck &&
  npm test` all clean; production `npm run build` succeeds.
- A manual run of both apps completes the full happy path and the main error
  paths in the browser.
- The two deferred features are visibly stubbed with their TODO notes and the
  app is fully usable without them.

## Dependencies
All previous chunks (this is the capstone).

## Reminder
Follow the repo `CLAUDE.md` rules: tests first where you add them, keep
lint/format/type-check clean, Conventional Commits (`test:`/`fix:`/`docs:`).

Commit and push.
