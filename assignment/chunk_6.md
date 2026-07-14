# Chunk 6 — Flux math: regression fit + closed-chamber flux + unit ladder

**Description:** The scientific core, and the one piece that must be exactly
right. Pure code, **no LLM ever**. Given a spot's concentration readings + chamber
constants + temperature + pressure, fit a linear slope per gas (with R²) and
compute flux across the full unit ladder.

## Exactly what to do
1. **`app/flux/regression.py`** — `fit_slope(times_s, values) -> {slope,
   intercept, r2, n_points}` using `scipy.stats.linregress`. Assume `nan`s were
   already removed by the caller (report count separately).
2. **`app/flux/flux.py`** — `compute_flux(slope, area_m2, volume_l, temp_c,
   pressure_hpa, gas) -> FluxLadder`:
   - Convert CH₄ slope from **ppb/s to ppm/s (÷1000)** before the flux math;
     CO₂ is already ppm/s.
   - Apply the closed-chamber flux formula to get **µmol · m⁻² · s⁻¹**, then
     derive every ladder unit: `umol_m2_s, umol_m2_h, mol_m2_h, gC_m2_day,
     kg_m2_h, kg_ha_h, kg_ha_day, kg_ha_year, Mg_ha_year, Mg_ha_year_co2equiv`
     (CO₂-equivalent uses the appropriate GWP for the gas).
   - The **method-of-record is the R script** in `reference/` (if present). Match
     its formula and conversion constants. If `reference/` is not in the repo
     yet, implement per `project-brief.md` and lock the numbers with explicit
     hand-computed expected values in the test, leaving a note to re-validate
     against R when it lands.
3. **`app/flux/pipeline.py`** — `fit_spot(readings, constants, temp, pressure)
   -> per-gas {fit, ladder, n_points, n_dropped_nan}` that:
   - Selects the fit window **start+30 s → start+5 min 30 s** (skip first 30 s,
     fit next 300 points).
   - Drops `nan` rows inside the window and reports how many.
   - Flags `short_window` if fewer points than expected, `low_r2` if R² < 0.80
     (threshold from a shared constant), and returns enough to skip a gas with
     too few points.

## Files created / changed
- New: `app/flux/regression.py`, `app/flux/flux.py`, `app/flux/pipeline.py`.
- New tests: `tests/test_regression.py`, `tests/test_flux.py`,
  `tests/test_flux_pipeline.py`.

## How to verify
- Regression test: on a synthetic perfectly-linear series, slope/intercept exact
  and R² == 1.0; on noisy data R² in a sane range.
- Flux test: for a known slope + constants, the ladder matches hand-computed
  values (assert each unit); CH₄ ppb→ppm conversion verified (a CH₄ slope
  produces flux 1000× smaller than the same numeric CO₂ slope, before GWP).
- Pipeline test: correct window selection (first 30 s excluded), `nan`-in-window
  dropped and counted, `low_r2`/`short_window` flags set correctly.
- `pytest`, `ruff`, `mypy` clean.

## Dependencies
Chunk 1. (Pure; independent of DB and parsers, though it consumes their output
shapes later.)

## Reminder
Follow the repo `CLAUDE.md` rules: **tests first and thorough** here — this is the
validated core. Keep lint/format/type-check clean, Conventional Commits
(`feat:`). If you add/clean the R reference to validate against, note it in
`CLAUDE.md`.

Commit and push.
