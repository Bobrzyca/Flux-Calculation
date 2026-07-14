"""Per-spot fit orchestration: window selection, nan handling, fit + flux (pure).

Given a spot's in-window concentration readings and its conditions, select the
fit sub-window (skip the first 30 s, fit the next 300 s), drop and count ``nan``
rows, fit each gas, compute the flux ladder, and raise the ``low_r2`` /
``short_window`` flags. Skips a gas that has too few valid points.
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


def fit_spot(
    readings: pd.DataFrame,
    area_m2: float,
    volume_l: float,
    temp_c: float,
    pressure_hpa: float,
) -> dict[str, GasResult]:
    """Fit both gases for a spot.

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
    lo = C.FIT_SKIP_SECONDS
    hi = C.FIT_SKIP_SECONDS + C.FIT_WINDOW_SECONDS
    window = readings[(rel >= lo) & (rel < hi)]
    short = len(window) < C.FIT_WINDOW_SECONDS

    results: dict[str, GasResult] = {}
    for gas, column in GAS_COLUMN.items():
        values = window[column]
        valid = values.notna()
        n_dropped = int((~valid).sum())
        y = values[valid].astype(float).to_numpy()
        x = (window["timestamp"][valid].astype(float) - t0).to_numpy()
        n_points = int(y.size)

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
            )
            continue

        fit = fit_slope(x, y)
        ladder = compute_flux(fit.slope, area_m2, volume_l, temp_c, pressure_hpa, gas)
        if fit.r2 < C.LOW_R2_THRESHOLD:
            flags.append(LOW_R2)
        results[gas] = GasResult(gas, fit, ladder, n_points, n_dropped, flags=flags)

    return results
