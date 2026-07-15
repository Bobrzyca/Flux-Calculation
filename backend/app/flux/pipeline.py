"""Per-spot fit orchestration: window selection, nan handling, fit + flux (pure).

Given a spot's readings and conditions, choose the **most-linear** ``FIT_WINDOW``-
long sub-window (slide the window and maximise CO₂ R², tie-broken toward the
+30 s skip so clean spots are unchanged), apply that one window to both gases,
drop and count ``nan`` rows, fit each gas, compute the flux ladder, and raise the
``low_r2`` / ``short_window`` flags. The chosen offset is reported (``fit_offset_s``)
so the shift stays visible. Skips a gas that has too few valid points.
"""

from dataclasses import dataclass, field

import pandas as pd

from app.flux import constants as C
from app.flux.flux import FluxLadder, compute_flux
from app.flux.regression import FitResult, fit_slope

# Per-spot flag values (mirrors the frontend SpotFlag union subset set here).
LOW_R2 = "low_r2"
SHORT_WINDOW = "short_window"

# Gas -> concentration column in the readings frame.
GAS_COLUMN = {"CO2": "co2_ppm", "CH4": "ch4_ppb"}


@dataclass
class GasResult:
    """Fit + flux outcome for one gas of one spot."""

    gas: str
    fit: FitResult | None
    ladder: FluxLadder | None
    n_points: int
    n_dropped_nan: int
    flags: list[str] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str | None = None
    # Chosen fit window, seconds relative to the spot's first reading (t0). Both
    # gases share one window per spot (chosen by CO₂), so the closure period is
    # consistent; ``fit_offset_s`` is how far it sits after the recorded start.
    fit_offset_s: float = float(C.FIT_SKIP_SECONDS)
    fit_start_s: float = float(C.FIT_SKIP_SECONDS)
    fit_stop_s: float = float(C.FIT_SKIP_SECONDS + C.FIT_WINDOW_SECONDS)
    # Temperature over the fit window: mean is used in the flux formula; min/max
    # give the range (the logger samples ~every 30 s, so several values fall in
    # the window).
    temp_mean_c: float | None = None
    temp_min_c: float | None = None
    temp_max_c: float | None = None


def _r2_over(
    readings: pd.DataFrame, rel: pd.Series, t0: float, column: str, lo: float, hi: float
) -> float | None:
    """R² of a linear fit of ``column`` over the window ``[lo, hi)`` (rel seconds)."""
    mask = (rel >= lo) & (rel < hi)
    values = readings.loc[mask, column]
    valid = values.notna()
    if int(valid.sum()) < C.MIN_FIT_POINTS:
        return None
    y = values[valid].astype(float).to_numpy()
    x = (readings["timestamp"][mask][valid].astype(float) - t0).to_numpy()
    r2 = fit_slope(x, y).r2
    return r2 if r2 == r2 else None  # drop NaN (flat/zero-variance window)


def _choose_offset(
    readings: pd.DataFrame, rel: pd.Series, t0: float, win: int, max_off: int
) -> float:
    """Slide a ``win``-long window over ``[0, max_off]`` and pick the most linear
    start offset — judged by CO₂ (the primary signal), else CH₄. Among windows
    within 0.02 R² of the best, choose the one closest to ``FIT_SKIP_SECONDS`` so
    clean measurements still start ~30 s in and only lagged ones shift.
    """
    for column in ("co2_ppm", "ch4_ppb"):
        scored = [
            (off, r2)
            for off in range(0, max_off + 1, 10)
            if (r2 := _r2_over(readings, rel, t0, column, off, off + win)) is not None
        ]
        if scored:
            best = max(r2 for _, r2 in scored)
            near = [off for off, r2 in scored if r2 >= best - 0.02]
            return float(min(near, key=lambda o: abs(o - C.FIT_SKIP_SECONDS)))
    return float(C.FIT_SKIP_SECONDS)


def fit_spot(
    readings: pd.DataFrame,
    area_m2: float,
    volume_l: float,
    temp_c: float,
    pressure_hpa: float,
) -> dict[str, GasResult]:
    """Fit both gases for a spot over the best (most-linear) window.

    ``readings`` needs ``timestamp``, ``co2_ppm`` and ``ch4_ppb`` columns.
    """
    if readings.empty:
        return {
            gas: GasResult(
                gas, None, None, 0, 0, skipped=True, skip_reason="no readings"
            )
            for gas in GAS_COLUMN
        }

    t0 = float(readings["timestamp"].min())
    rel = readings["timestamp"].astype(float) - t0
    span = float(rel.max())
    win = C.FIT_WINDOW_SECONDS
    max_off = min(int(span - win), C.FIT_SEARCH_MAX_OFFSET_SECONDS)
    offset = (
        _choose_offset(readings, rel, t0, win, max_off)
        if max_off >= 0
        else float(C.FIT_SKIP_SECONDS)
    )
    lo, hi = offset, offset + win
    window = readings[(rel >= lo) & (rel < hi)]

    # Temperature over the window: use the mean in the flux formula and report
    # the range. Fall back to the scalar ``temp_c`` if no per-reading column.
    temp_mean, temp_min, temp_max = temp_c, temp_c, temp_c
    if "temperature_used" in window.columns:
        wt = window["temperature_used"].dropna()
        if not wt.empty:
            temp_mean = float(wt.mean())
            temp_min, temp_max = float(wt.min()), float(wt.max())

    results: dict[str, GasResult] = {}
    for gas, column in GAS_COLUMN.items():
        values = window[column]
        valid = values.notna()
        n_dropped = int((~valid).sum())
        y = values[valid].astype(float).to_numpy()
        x = (window["timestamp"][valid].astype(float) - t0).to_numpy()
        n_points = int(y.size)
        # "Short" now means less than FIT_MIN_WINDOW_SECONDS of *usable* data.
        short = n_points < C.FIT_MIN_WINDOW_SECONDS

        flags: list[str] = [SHORT_WINDOW] if short else []
        if n_points < C.MIN_FIT_POINTS:
            results[gas] = GasResult(
                gas,
                None,
                None,
                n_points,
                n_dropped,
                flags=flags,
                skipped=True,
                skip_reason="too few points",
                fit_offset_s=offset,
                fit_start_s=lo,
                fit_stop_s=hi,
                temp_mean_c=temp_mean,
                temp_min_c=temp_min,
                temp_max_c=temp_max,
            )
            continue

        fit = fit_slope(x, y)
        ladder = compute_flux(
            fit.slope, area_m2, volume_l, temp_mean, pressure_hpa, gas
        )
        if fit.r2 < C.LOW_R2_THRESHOLD:
            flags.append(LOW_R2)
        results[gas] = GasResult(
            gas,
            fit,
            ladder,
            n_points,
            n_dropped,
            flags=flags,
            fit_offset_s=offset,
            fit_start_s=lo,
            fit_stop_s=hi,
            temp_mean_c=temp_mean,
            temp_min_c=temp_min,
            temp_max_c=temp_max,
        )

    return results
