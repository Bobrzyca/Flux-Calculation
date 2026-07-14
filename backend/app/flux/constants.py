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

# --- Per-spot fit window and flags -----------------------------------------
# Fit the regression over start+30 s → start+5 min 30 s: skip the first 30 s,
# then fit the next 300 one-second points.
FIT_SKIP_SECONDS = 30
FIT_WINDOW_SECONDS = 300
# Fewer valid points than this in a gas's window → skip that gas.
MIN_FIT_POINTS = 10
# R² below this flags a spot's fit as untrustworthy.
# (assumption — the brief says default 0.80, adjustable in settings.)
LOW_R2_THRESHOLD = 0.80
