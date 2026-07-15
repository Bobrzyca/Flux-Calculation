"""Physical constants and fit thresholds for the flux math.

One source of truth for the numbers the closed-chamber flux formula and the
per-spot fit depend on. Constants flagged *(assumption)* should be confirmed
against the R method-of-record and the brief's open questions.
"""

# Universal gas constant, J·mol⁻¹·K⁻¹ (= m³·Pa·mol⁻¹·K⁻¹).
R_GAS = 8.314462618

# Molar mass of each whole gas molecule, g·mol⁻¹.
MOLAR_MASS_G = {"CO2": 44.0095, "CH4": 16.0425}
# Molar mass of carbon, g·mol⁻¹ — one C atom per molecule for both gases.
MOLAR_MASS_C = 12.011

# 100-year global warming potentials (IPCC AR5). CO₂ is the reference (1).
# (assumption — confirm the GWP set/vintage with the researcher.)
GWP_100YR = {"CO2": 1.0, "CH4": 28.0}

# CH₄ arrives in ppb; convert to ppm before the flux math.
CH4_PPB_TO_PPM = 1e-3

# Default pressure used when no IMGW file is supplied: 1 standard atmosphere
# (1013.25 hPa = 101325 Pa). Pressure is optional; spots computed with this
# default are flagged ``no_pressure`` so the substitution stays visible to the
# supervisor (a real barometric reading is always preferable).
DEFAULT_PRESSURE_HPA = 1013.25

# --- Per-spot fit window and flags -----------------------------------------
# Fit the regression over a FIT_WINDOW_SECONDS-long window. The window is slid to
# the most-linear position (best R²) up to FIT_SEARCH_MAX_OFFSET_SECONDS after the
# recorded start — this absorbs the lag between hand-recorded times, the chamber
# settling, and the instrument clock. Ties are broken toward FIT_SKIP_SECONDS, so
# clean measurements still start ~30 s in (as before); the chosen offset per spot
# is reported. FIT_SKIP_SECONDS is that tie-break/default baseline.
FIT_SKIP_SECONDS = 30
FIT_WINDOW_SECONDS = 300
FIT_SEARCH_MAX_OFFSET_SECONDS = 180
# If the fitted window ends up with less than this many seconds of usable data
# (short measurement, gaps, dropped spikes), flag it prominently — the flux is
# less reliable over a short window.
FIT_MIN_WINDOW_SECONDS = 240
# Fewer valid points than this in a gas's window → skip that gas.
MIN_FIT_POINTS = 10
# R² below this flags a spot's fit as untrustworthy.
# (assumption — the brief says default 0.80, adjustable in settings.)
LOW_R2_THRESHOLD = 0.80
