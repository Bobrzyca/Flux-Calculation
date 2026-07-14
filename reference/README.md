# reference/ — method-of-record (validation only)

The original R script for computing closed-chamber CO₂/CH₄ fluxes, kept as an
**independent** expression of the same method. It is **not** called by the app —
it exists so the Python tool can be checked against a second implementation on a
known campaign (e.g. the 2 July 2026 Kampinos data). See `project-brief.md` →
"R script as reference".

## ⚠️ `flux_reference.R` is currently a SCAFFOLD, not the real reference

The committed `flux_reference.R` was **transcribed from the Python code**
(`backend/app/flux/`). Because it's a port, it reproduces the Python numbers by
construction, so **it does not yet provide independent validation** — it only
gives you a working, path-clean skeleton (no hard-coded `C:/Users/...` paths; it
reads the four files from `../backend/sample_data`).

**Replace it with your actual original R script**, cleaned only so it reads the
sample files. That version — written independently of the Python — is the true
method-of-record. If the two ever disagree, that disagreement is the useful
signal: port the fix into the Python code and re-validate.

Until then, the flux math is validated by the hand-computed expected values in
`backend/tests/test_flux.py`.

## Running it

```bash
Rscript reference/flux_reference.R
```

Needs the `readxl` package for the temperature `.xlsx`:

```r
install.packages("readxl")
```

It prints a per-spot × gas summary and writes `reference/reference_output.csv`
(slope, R², n, and the full flux unit ladder) for diffing against the app's
results (e.g. `GET /api/analyses/{id}/export?format=csv`).

## Cross-checking against the Python tool

1. Run an analysis in the app on the sample files (or the real campaign).
2. Run this script on the same files.
3. Compare per-spot `slope`, `r2`, and `umol_m2_s` (and the rest of the ladder).
   They should agree within floating-point tolerance for the same method.
