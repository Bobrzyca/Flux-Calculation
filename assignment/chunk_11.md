# Chunk 11 — Read endpoints: results, per-spot detail, processing log

**Description:** Expose what the match step produced, in the exact shapes the
frontend's Results, Per-spot detail, and Processing log screens expect. Read-only.

## Exactly what to do
1. **`app/schemas/results.py`** — Pydantic models mirroring `types.ts`:
   - `SpotResult` (`nr, date, start, stop, gps, light_dark, location,
     co2_flux_umol_m2_s|null, ch4_flux_umol_m2_s|null, r2_co2|null, r2_ch4|null,
     temperature_used_c|null, pressure_used_hpa|null, time_offset_applied_s,
     n_points_co2, n_points_ch4, flags[], skipped, skip_reason|null`).
   - `QualityCheck` (`available, summary|null, flags[]`) and `QualityFlag`
     (`nr, gps, gas, issue, severity`).
   - `ResultsPayload` (`quality_check, spots[]`).
   - `GasPoint` (`t_s, value, in_window`), `GasFit` (`slope, intercept, r2,
     n_points, n_dropped_nan`), `GasDetail` (`unit, points[], fit, flux_ladder`),
     `SpotDetail` (`nr, gps, light_dark, fit_window{start,stop}, flags[],
     gases{CO2,CH4}`).
   - `LogEntry` (`ts, severity, message`).
2. **`app/api/results.py`**:
   - `GET /api/analyses/{id}/results` → assemble `SpotResult`s by joining
     `Spot` + `FluxResult`; set per-spot `flags` (`low_r2`, `dropped_nan`,
     `no_pressure`, `short_window`; `anomalous` comes from the quality check).
     For `quality_check`, return **`available: false`** with a short
     "quality check pending/unavailable" message and empty `flags` — the n8n
     workflow is deferred. Leave `# TODO: n8n quality check (later seminar)`.
   - `GET /api/analyses/{id}/spots/{nr}` → rebuild the per-gas points for the
     plot (re-read the stored file or persisted `Reading`s and mark
     `in_window`), the fit (`slope, intercept, r2, n_points, n_dropped_nan`), the
     `fit_window`, and the `flux_ladder`. Return `null`/404 for a skipped spot.
   - `GET /api/analyses/{id}/log` → the analysis's `ProcessingLogEntry` rows in
     order.
3. 404 for unknown analysis/spot.

## Files created / changed
- New: `app/schemas/results.py`, `app/api/results.py` (wired into `main.py`).
- New tests: `tests/test_api_results.py`.

## How to verify
- After match (chunk 10): `GET .../results` returns all spots incl. the skipped
  one (with `skip_reason`), low-R² spots flagged, and `quality_check.available ==
  false`; `GET .../spots/{nr}` returns CO₂ and CH₄ points with `in_window` set
  and a fit matching chunk-6 numbers; `GET .../log` returns the recorded entries.
- Shapes validate against the frontend `types.ts` field names.
- `pytest`, `ruff`, `mypy` clean.

## Dependencies
Chunk 10 (data to read).

## Reminder
Follow the repo `CLAUDE.md` rules: tests first, lint/format/type-check clean,
Conventional Commits (`feat:`). Update `backend/CLAUDE.md` with the endpoints and
the n8n-deferred note.

Commit and push.
