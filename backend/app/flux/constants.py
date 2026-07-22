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
# Extra seconds of raw record shown on EACH side of a spot's stored window in the
# per-spot detail plot (a faint context trace), so the researcher can see well
# beyond the fit window when judging a manual shift. This is display-only — it does
# not change the stored readings or the fit.
SPOT_CONTEXT_EXTRA_SECONDS = 300

# Cap on the overview graph's background trace (the whole raw record minus the
# spot slices). Beyond this the record is uniformly thinned, so Plotly stays
# responsive on long campaigns instead of stuttering on tens of thousands of
# points; the thinned shape is indistinguishable at overview zoom.
TIMESERIES_MAX_BACKGROUND_POINTS = 2000

# How far *before* the recorded start the fitter may also look (and the user may
# shift the window). Hand-recorded start times are often late, or the instrument
# clock runs ahead, so the real chamber-closure rise can sit earlier than the
# noted start. We slice this many seconds of lead data before each spot's start
# so the auto-search and the manual shift both have data to move back into —
# without it, a backward shift has nothing to land on and the window can't reach
# an earlier slope (the cause of many low-R² auto fits).
FIT_SEARCH_BACK_SECONDS = 180
# If the fitted window ends up with less than this many seconds of usable data
# (short measurement, gaps, dropped spikes), flag it prominently — the flux is
# less reliable over a short window.
FIT_MIN_WINDOW_SECONDS = 240
# Fewer valid points than this in a gas's window → skip that gas.
MIN_FIT_POINTS = 10
# R² below this flags a spot's fit as untrustworthy.
# (assumption — the brief says default 0.80, adjustable in settings.)
LOW_R2_THRESHOLD = 0.80

# --- Auto window-shortening (fixes a low-R² 5-min fit) ----------------------
# When the best 5-min window is still below LOW_R2_THRESHOLD, the fitter may
# *shorten* the window (keeping its best position) down to FIT_SHORTEN_MIN_SECONDS
# in FIT_SHORTEN_STEP_SECONDS steps, and adopt the shorter length only if it
# raises R² by at least FIT_SHORTEN_MIN_GAIN. A clean spot (already ≥ threshold)
# is never shortened, so nothing changes for good measurements. A shortened spot
# is reported (``window_shortened``) and noted in the processing log.
FIT_SHORTEN_MIN_SECONDS = 240  # 4 minutes — the shortest window we'll cut to
FIT_SHORTEN_STEP_SECONDS = 30
FIT_SHORTEN_MIN_GAIN = 0.02  # required R² improvement to justify a shorter window

# --- Isolated single-point spike removal (despike) -------------------------
# Field sensors occasionally emit a lone bad value — one sample far off its two
# immediate neighbours, which agree with each other (a single-point peak/trough
# every few hundred readings). We drop only such *isolated* spikes (never a run
# of consecutive off values, which is real signal or a gap). A point is a spike
# when it deviates from BOTH neighbours in the same direction by more than
# DESPIKE_K × the robust step scale (median absolute step of the series) while
# the neighbours themselves stay consistent. Each drop is counted and logged.
DESPIKE_K = 5.0
