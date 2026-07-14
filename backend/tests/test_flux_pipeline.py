"""Per-spot pipeline: window selection, nan handling, and flags."""

import numpy as np
import pandas as pd

from app.flux.pipeline import LOW_R2, SHORT_WINDOW, fit_spot

AREA, VOLUME, TEMP, PRESSURE = 0.0625, 15.625, 20.0, 1013.25


def _stream(seconds: int) -> pd.DataFrame:
    t = np.arange(seconds + 1, dtype=float)
    return pd.DataFrame(
        {
            "timestamp": 1_000.0 + t,
            "co2_ppm": 400.0 + 0.03 * t,
            "ch4_ppb": 1900.0 + 0.08 * t,
        }
    )


def test_window_excludes_first_30s_and_counts_in_window_nans() -> None:
    df = _stream(360)  # 361 one-second rows, 0..360
    # nan in the first 30 s (excluded from the fit window -> not counted)...
    df.loc[0:9, "co2_ppm"] = np.nan
    # ...and nan inside the window (rel 50..54 -> counted as dropped).
    df.loc[50:54, "co2_ppm"] = np.nan

    res = fit_spot(df, AREA, VOLUME, TEMP, PRESSURE)
    co2 = res["CO2"]
    assert not co2.skipped
    # Window is rel [30, 330) = 300 rows; 5 in-window nans dropped -> 295 fit.
    assert co2.n_points == 295
    assert co2.n_dropped_nan == 5
    assert co2.flags == []  # clean rise, full window
    assert co2.fit is not None
    assert abs(co2.fit.slope - 0.03) < 1e-6

    ch4 = res["CH4"]
    assert ch4.n_points == 300
    assert ch4.n_dropped_nan == 0
    assert SHORT_WINDOW not in ch4.flags


def test_low_r2_flag_on_flat_noise() -> None:
    df = _stream(360)
    rng = np.random.default_rng(1)
    df["co2_ppm"] = 400.0 + rng.normal(0, 1.0, size=len(df))  # no real trend
    res = fit_spot(df, AREA, VOLUME, TEMP, PRESSURE)
    assert res["CO2"].fit is not None
    assert res["CO2"].fit.r2 < 0.80
    assert LOW_R2 in res["CO2"].flags


def test_short_window_flag() -> None:
    df = _stream(120)  # only ~90 points land in the [30, 330) window
    res = fit_spot(df, AREA, VOLUME, TEMP, PRESSURE)
    assert SHORT_WINDOW in res["CO2"].flags
    assert not res["CO2"].skipped  # still enough points to fit


def test_empty_readings_skips_both_gases() -> None:
    df = pd.DataFrame({"timestamp": [], "co2_ppm": [], "ch4_ppb": []})
    res = fit_spot(df, AREA, VOLUME, TEMP, PRESSURE)
    assert res["CO2"].skipped and res["CH4"].skipped
    assert res["CO2"].skip_reason == "no readings"
