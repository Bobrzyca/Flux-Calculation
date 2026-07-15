# Flux calculation — method of record

This is the exact math the backend uses (`backend/app/flux/`), written out so it
can be checked by hand and against the R method-of-record. **The flux math is
pure code and never LLM-touched.**

## 1. Core equation (closed, static chamber)

For each spot and gas, fit a linear regression of concentration vs. time over the
chosen window to get the slope `dC/dt`, then apply the ideal-gas relation for the
chamber headspace:

```
F = (dC/dt) · (P · V) / (R · T · A)
```

| symbol | meaning | unit | source |
|--------|---------|------|--------|
| `F`     | gas flux                     | µmol·m⁻²·s⁻¹ | computed |
| `dC/dt` | concentration slope          | ppm·s⁻¹ (= µmol·mol⁻¹·s⁻¹) | linear fit |
| `P`     | ambient pressure             | Pa | IMGW file, else **1 atm = 101325 Pa** |
| `V`     | chamber volume               | m³ | `chamber_volume_l / 1000` |
| `R`     | universal gas constant       | 8.314462618 J·mol⁻¹·K⁻¹ | constant |
| `T`     | ambient temperature          | K (= °C + 273.15) | **mean over the fit window** |
| `A`     | chamber footprint area       | m² | `chamber_area_m2` |

`(P·V)/(R·T·A)` is the moles of air per m² of chamber footprint; times a ppm
(µmol·mol⁻¹) slope gives µmol·m⁻²·s⁻¹.

**CH₄** is measured in **ppb**, so its slope is converted first:
`dC/dt[ppm·s⁻¹] = slope[ppb·s⁻¹] × 1e-3`.

## 2. Unit ladder (derived from `F` in µmol·m⁻²·s⁻¹)

```
umol_m2_h            = umol_m2_s × 3600
mol_m2_h             = umol_m2_h × 1e-6
gC_m2_day            = mol_m2_h × 24 × 12.011            # 1 C atom / molecule (CO₂ and CH₄)
kg_m2_h              = mol_m2_h × M_gas / 1000           # M(CO₂)=44.0095, M(CH₄)=16.0425 g·mol⁻¹
kg_ha_h              = kg_m2_h × 1e4                     # 1 ha = 10⁴ m²
kg_ha_day            = kg_ha_h × 24
kg_ha_year           = kg_ha_day × 365
Mg_ha_year           = kg_ha_year / 1000                # 1 Mg (tonne) = 10³ kg
Mg_ha_year_co2equiv  = Mg_ha_year × GWP                 # GWP: CO₂=1, CH₄=28 (IPCC AR5, 100-yr)
```

## 3. Window selection (per spot, applied to both gases)

The fit window is **not** a fixed offset from the recorded start. A
`FIT_WINDOW_SECONDS` (= 300 s) window is slid over the data and the position with
the **highest CO₂ R²** is chosen, up to `FIT_SEARCH_MAX_OFFSET_SECONDS` (= 180 s)
after the recorded start. Ties (within 0.02 R²) resolve toward `FIT_SKIP_SECONDS`
(= 30 s), so clean measurements are unchanged and only lagged ones shift. The same
window is used for CO₂ and CH₄ (one physical closure period). The chosen offset is
reported (`fit_offset_s`, flag `time_shifted`). This absorbs the lag between the
hand-recorded times and the instrument clock / chamber settling.

## 4. Data handling / QC

- **Timeline:** built from the LI-7810 local `DATE` + `TIME` columns (not the
  `SECONDS` unix column, which is a different timezone), so it aligns with the
  local-time field notes and temperature log. The matching date is taken from the
  concentration file itself.
- **Temperature:** the logger samples ~every 30 s. The nearest reading is attached
  to **each** concentration reading; the flux uses the **mean over the fit window**
  and the result reports the **range (min–max)**.
- **Pressure:** optional. With no IMGW file the flux uses **1 atm** (1013.25 hPa)
  and the spot is flagged `no_pressure`.
- **CO₂ spike filter:** readings with CO₂ ≥ 1500 ppm are dropped (nan) as sensor
  spikes — matching the R script's `subset(fx, CO2 < 1500)`.
- **Flags:** `low_r2` (R² < 0.80), `short_window` (< 4 min of usable data after the
  window is chosen), `time_shifted`, `dropped_nan`, `no_pressure`.

## 5. Worked check (single value)

Slope 0.30 ppm·s⁻¹ CO₂, A = 0.0625 m², V = 15.625 L = 0.015625 m³, T = 25 °C =
298.15 K, P = 1 atm = 101325 Pa, R = 8.314462618:

```
mol_air_per_m2 = (101325 · 0.015625) / (8.314462618 · 298.15 · 0.0625)
               = 1583.20 / 154.95  ≈ 10.217 mol·m⁻²
F = 0.30 · 10.217 ≈ 3.065 µmol·m⁻²·s⁻¹
```

The full ladder is locked by hand-computed expected values in
`backend/tests/test_flux.py`. Validate against the R method-of-record
(`reference/flux_reference.R`, to be replaced by the independent R script) on the
2026-07-02 Kampinos campaign; investigate any disagreement.
