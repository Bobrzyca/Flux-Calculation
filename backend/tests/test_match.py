"""Auto-match: window slicing, offset, nearest temp/pressure, skip flags."""

from datetime import date

import numpy as np
import pandas as pd

from app.matching.match import (
    NO_PRESSURE,
    match_spot,
    nearest_pressure,
    nearest_temperature,
    note_time_to_unix,
    slice_spot,
)
from app.parsing.pressure import PressureReading

WORK_DATE = date(2026, 7, 2)
BASE = note_time_to_unix(WORK_DATE, "09:00:00")


def _stream() -> pd.DataFrame:
    t = np.arange(1200, dtype=float)  # 09:00:00 .. 09:19:59, 1 Hz
    return pd.DataFrame(
        {
            "timestamp": BASE + t,
            "co2_ppm": 400.0 + 0.02 * t,
            "ch4_ppb": 1900.0 + 0.05 * t,
        }
    )


def _temperature() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": [BASE + 0, BASE + 300, BASE + 600, BASE + 900],
            "temperature_c": [18.0, 18.5, 19.0, 19.5],
        }
    )


def _pressure() -> list[PressureReading]:
    return [
        PressureReading(BASE + 0, 1013.0),
        PressureReading(BASE + 600, 1013.5),
    ]


def test_slice_spot_selects_in_window() -> None:
    window = slice_spot(_stream(), "09:01:00", "09:03:00", WORK_DATE, 0)
    assert len(window) == 121  # inclusive 120 s window at 1 Hz
    assert window["timestamp"].min() == BASE + 60
    assert window["timestamp"].max() == BASE + 180


def test_slice_spot_offset_shifts_inclusion() -> None:
    df = pd.DataFrame({"timestamp": BASE + np.array([58.0, 59.0, 60.0, 61.0])})
    df["co2_ppm"] = [1.0, 2.0, 3.0, 4.0]
    # Window [09:01:00, 09:01:02] = [BASE+60, BASE+62].
    assert len(slice_spot(df, "09:01:00", "09:01:02", WORK_DATE, 0)) == 2  # 60, 61
    with_offset = slice_spot(df, "09:01:00", "09:01:02", WORK_DATE, 2)
    assert len(with_offset) == 3  # 58,59,60 shift to 60,61,62
    assert with_offset["timestamp"].min() == BASE + 60


def test_nearest_temperature_and_pressure() -> None:
    assert nearest_temperature(_temperature(), BASE + 310) == 18.5
    assert (
        nearest_temperature(pd.DataFrame({"timestamp": [], "temperature_c": []}), 0)
        is None
    )
    assert nearest_pressure(_pressure(), BASE + 590) == 1013.5
    assert nearest_pressure([], 0.0) is None


def test_match_spot_normal() -> None:
    match = match_spot(
        1, _stream(), "09:01:00", "09:03:00", WORK_DATE, 0, _temperature(), _pressure()
    )
    assert not match.skipped
    # A fixed-length window is sliced from the start (FIT_WINDOW + search offset =
    # 480 s) so the fit step can find the most-linear sub-window; the recorded
    # stop is only used to reject stop-before-start.
    assert len(match.readings) == 480
    # Temperature is attached per-reading (nearest in time), so several logger
    # values fall inside the 480 s window; the scalar is their mean.
    assert set(match.readings["temperature_used"].unique()) <= {18.0, 18.5, 19.0}
    assert match.readings["temperature_used"].nunique() >= 2
    assert match.temperature_used is not None
    assert 18.0 <= match.temperature_used <= 19.0
    # Pressure is a single nearest value (BASE+0 -> 1013.0).
    assert match.pressure_used == 1013.0
    assert (match.readings["pressure_used"] == 1013.0).all()


def test_match_spot_empty_window_skips() -> None:
    match = match_spot(
        3, _stream(), "10:00:00", "10:06:00", WORK_DATE, 0, _temperature(), _pressure()
    )
    assert match.skipped
    assert match.skip_reason == "empty window"


def test_match_spot_stop_before_start_skips() -> None:
    match = match_spot(
        4, _stream(), "09:05:00", "09:04:00", WORK_DATE, 0, _temperature(), _pressure()
    )
    assert match.skipped
    assert match.skip_reason == "stop before start"


def test_match_spot_unparseable_time_skips() -> None:
    match = match_spot(
        5, _stream(), "", "09:04:00", WORK_DATE, 0, _temperature(), _pressure()
    )
    assert match.skipped
    assert match.skip_reason == "unparseable time"


def test_match_spot_no_pressure_flag() -> None:
    match = match_spot(
        6, _stream(), "09:01:00", "09:03:00", WORK_DATE, 0, _temperature(), []
    )
    assert not match.skipped
    assert match.pressure_used is None
    assert NO_PRESSURE in match.flags


def test_shared_gps_spots_stay_distinct() -> None:
    # Two spots at the same GPS (a light/dark pair) are matched independently.
    stream, temp, press = _stream(), _temperature(), _pressure()
    light = match_spot(7, stream, "09:01:00", "09:03:00", WORK_DATE, 0, temp, press)
    dark = match_spot(8, stream, "09:05:00", "09:07:00", WORK_DATE, 0, temp, press)
    assert light.nr != dark.nr
    assert light.readings["timestamp"].min() != dark.readings["timestamp"].min()
