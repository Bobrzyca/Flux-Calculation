"""Per-spot pipeline: window selection, nan handling, and flags."""

import numpy as np
import pandas as pd

from app.flux.pipeline import LOW_R2, SHORT_WINDOW, _despike_mask, fit_spot

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


def test_best_window_shifts_to_the_linear_part() -> None:
    # First ~200 s flat, then a clean linear rise: the fit window must shift off
    # the flat start to the linear part (this is the low-R² fix).
    n = 540
    t = np.arange(n + 1, dtype=float)
    co2 = np.where(t < 200, 400.0, 400.0 + 0.05 * (t - 200))
    df = pd.DataFrame(
        {"timestamp": 1000.0 + t, "co2_ppm": co2, "ch4_ppb": 1900.0 + 0.02 * t}
    )
    res = fit_spot(df, AREA, VOLUME, TEMP, PRESSURE)
    co2r = res["CO2"]
    assert co2r.fit_offset_s >= 120  # shifted well past the flat start
    assert co2r.fit is not None and co2r.fit.r2 > 0.95  # now a clean fit
    # Both gases share the same chosen window.
    assert res["CH4"].fit_start_s == co2r.fit_start_s


def test_clean_stream_keeps_default_skip() -> None:
    # A fully-linear stream must still start ~30 s in (tie-break), unchanged.
    df = _stream(360)
    res = fit_spot(df, AREA, VOLUME, TEMP, PRESSURE)
    assert res["CO2"].fit_offset_s == 30.0


def test_uses_window_temperature_mean_and_reports_range() -> None:
    # Per-reading temperatures in the window -> mean is used, min/max reported.
    df = _stream(360)
    df["temperature_used"] = 20.0 + 0.01 * np.arange(len(df))  # 20.0 .. 23.6
    res = fit_spot(df, AREA, VOLUME, TEMP, PRESSURE)
    co2 = res["CO2"]
    # Window is [30, 330): temps 20.3 .. 23.29, mean ~21.795.
    assert co2.temp_min_c is not None and abs(co2.temp_min_c - 20.30) < 0.02
    assert co2.temp_max_c is not None and abs(co2.temp_max_c - 23.29) < 0.02
    assert co2.temp_mean_c is not None and 21.5 < co2.temp_mean_c < 22.1


def test_short_window_flag_under_4_minutes() -> None:
    df = _stream(200)  # ~170 s land in the window -> under 4 min
    res = fit_spot(df, AREA, VOLUME, TEMP, PRESSURE)
    assert SHORT_WINDOW in res["CO2"].flags


# --- Despike (isolated single-point spikes) --------------------------------


def test_despike_mask_flags_lone_spike_not_a_run() -> None:
    v = np.full(50, 400.0) + 0.03 * np.arange(50)
    v[20] += 50.0  # a single lone spike
    mask = _despike_mask(v)
    assert mask[20] and int(mask.sum()) == 1

    # A run of two off values is NOT a lone spike -> nothing flagged.
    v2 = np.full(50, 400.0) + 0.03 * np.arange(50)
    v2[20] += 50.0
    v2[21] += 50.0
    assert not _despike_mask(v2).any()


def test_despike_drops_spike_from_fit_and_counts_it() -> None:
    df = _stream(360)
    df.loc[100, "co2_ppm"] += 80.0  # one lone spike inside the window (rel 100)
    res = fit_spot(df, AREA, VOLUME, TEMP, PRESSURE)
    co2 = res["CO2"]
    assert co2.n_spikes == 1
    assert co2.n_dropped_nan == 0  # a spike is counted separately from nan gaps
    assert co2.n_points == 299  # 300 window points minus the dropped spike
    assert co2.fit is not None and co2.fit.r2 > 0.99  # spike removed -> clean fit


def test_clean_stream_drops_no_spikes() -> None:
    res = fit_spot(_stream(360), AREA, VOLUME, TEMP, PRESSURE)
    assert res["CO2"].n_spikes == 0 and res["CH4"].n_spikes == 0


# --- Window shortening (low-R² fix) ----------------------------------------


def test_window_shortens_to_fix_low_r2() -> None:
    # A clean linear rise for the first 4 min, then noisy scatter: no 5-min window
    # avoids the noisy tail (low R²), but the 4-min head fits cleanly. The fitter
    # should shorten the window to recover the good fit.
    n = 540
    t = np.arange(n + 1, dtype=float)
    rng = np.random.default_rng(3)
    co2 = np.where(t <= 240, 400.0 + 0.05 * t, 412.0 + rng.normal(0, 8.0, size=n + 1))
    df = pd.DataFrame(
        {"timestamp": 1000.0 + t, "co2_ppm": co2, "ch4_ppb": 1900.0 + 0.02 * t}
    )
    res = fit_spot(df, AREA, VOLUME, TEMP, PRESSURE)
    co2r = res["CO2"]
    assert co2r.window_shortened
    assert 240.0 <= co2r.fit_window_s < 300.0
    assert co2r.fit is not None and co2r.fit.r2 > 0.95


def test_clean_stream_is_not_shortened() -> None:
    res = fit_spot(_stream(360), AREA, VOLUME, TEMP, PRESSURE)
    assert not res["CO2"].window_shortened
    assert res["CO2"].fit_window_s == 300.0


# --- Whole-recording ("full") mode -----------------------------------------


def test_full_mode_fits_whole_recording() -> None:
    df = _stream(360)  # 0..360 s
    res = fit_spot(df, AREA, VOLUME, TEMP, PRESSURE, mode="full")
    co2 = res["CO2"]
    assert co2.fit_offset_s == 0.0
    assert co2.fit_start_s == 0.0
    assert co2.n_points == 361  # every recorded second, not just the 5-min window
    assert co2.fit is not None and abs(co2.fit.slope - 0.03) < 1e-6
