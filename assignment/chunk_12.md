# Chunk 12 — Export endpoint (xlsx / txt / csv)

**Description:** Let the user download the results file. Implement
`GET /api/analyses/{id}/export?format=xlsx|txt|csv` producing the full column set
plus the unit ladder, as a streamed file download.

## Exactly what to do
1. **`app/api/export.py`** — `GET /api/analyses/{id}/export`:
   - Query param `format` in `{xlsx, txt, csv}` (default `xlsx`; 422 on unknown).
   - Build rows from the analysis's results: the results-table columns from the
     brief (`Nr, date, start, stop, GPS, light/dark, location, CO₂ flux, CH₄
     flux, R²_CO2, R²_CH4, temperature used, pressure used, time-offset applied`)
     **plus the full unit ladder columns** for each gas (that's the point of the
     export vs the on-screen table).
   - `xlsx` via **openpyxl**; `txt` tab-delimited; `csv` comma-delimited.
     *(CSV is an assumption in the brief — keep it, it's cheap.)*
   - Return with `Content-Disposition: attachment; filename="<analysis
     name>.<ext>"` and the right media type, as a `StreamingResponse`/
     `FileResponse`.
   - 404 for unknown analysis.
2. Keep table-building logic reusable (a small helper that both this and, later,
   an "export selection" could share).

## Files created / changed
- New: `app/api/export.py` (wired into `main.py`), maybe
  `app/export/tabular.py` helper.
- New tests: `tests/test_api_export.py`.

## How to verify
- Tests: after match, `GET .../export?format=txt` returns 200, a tab-delimited
  body with the header row and one line per spot incl. the ladder columns;
  `format=csv` is comma-delimited; `format=xlsx` returns a valid workbook
  (open it back with openpyxl and check the header + a data row); unknown format
  → 422; unknown id → 404; the `Content-Disposition` filename uses the analysis
  name.
- `pytest`, `ruff`, `mypy` clean.

## Dependencies
Chunk 11 (results assembly).

## Reminder
Follow the repo `CLAUDE.md` rules: tests first, lint/format/type-check clean,
Conventional Commits (`feat:`). Update `backend/CLAUDE.md` with the endpoint.

Commit and push.
