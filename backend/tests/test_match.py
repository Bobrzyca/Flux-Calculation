"""Auto-match: window slicing, offset, nearest temp/pressure, skip flags."""

from datetime import date

import numpy as np
import pandas as pd

from app.matching.match import (
    NO_PRESSURE,
    match_spot,
    nearest_pressure,
    nearest_temperature,
    non_overlapping_bounds,
    note_time_to_unix,
    overlap_cut,
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
    # The window is sliced around the recorded start: a FIT_SEARCH_BACK (180 s)
    # lead *before* it plus FIT_WINDOW + search offset (480 s) after, so the fit
    # step can search — and the user shift — an earlier or later sub-window. Here
    # the start is 09:01:00 (BASE+60) and the stream begins at BASE, so the lead is
    # clipped to 60 s: 60 (lead) + 480 (forward) = 540 readings.
    assert len(match.readings) == 540
    # The lead margin means readings now exist *before* the recorded start.
    assert (match.readings["timestamp"] < BASE + 60).any()
    assert match.readings["timestamp"].min() == BASE
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


def test_note_time_accepts_hhmm() -> None:
    # Hand-typed notes often omit seconds; "HH:MM" must mean ":00".
    assert note_time_to_unix(WORK_DATE, "09:05") == note_time_to_unix(
        WORK_DATE, "09:05:00"
    )


def test_match_spot_accepts_hhmm_times() -> None:
    match = match_spot(
        9, _stream(), "09:01", "09:07", WORK_DATE, 0, _temperature(), _pressure()
    )
    assert not match.skipped
    assert len(match.readings) > 0


def test_match_spot_garbage_time_skips_not_crashes() -> None:
    match = match_spot(
        10, _stream(), "9h05", "09:07:00", WORK_DATE, 0, _temperature(), _pressure()
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


def test_overlap_cut_splits_the_gap() -> None:
    # Cut sits between the earlier spot's stop and the later spot's start.
    assert overlap_cut(0.0, 120.0, 300.0) == 210.0
    # No usable stop -> midpoint of the two starts.
    assert overlap_cut(0.0, None, 300.0) == 150.0
    # A stop that runs past the next start falls back to the start midpoint.
    assert overlap_cut(0.0, 400.0, 300.0) == 150.0
    # Always clamped inside [prev_start, next_start].
    assert overlap_cut(100.0, 100.0, 100.0) == 100.0


def test_non_overlapping_bounds_share_one_cut() -> None:
    bounds = non_overlapping_bounds([(0.0, 120.0), (300.0, 420.0), (600.0, None)])
    assert bounds[0][0] is None  # first: no lower limit
    assert bounds[-1][1] is None  # last: no upper limit
    # Each interior boundary is one shared cut (upper of i == lower of i+1).
    assert bounds[0][1] == bounds[1][0]
    assert bounds[1][1] == bounds[2][0]
    assert bounds[0][1] == 210.0  # midpoint of stop 120 and next start 300


def test_match_spot_bounds_prevent_overlap() -> None:
    # Two closely-spaced spots whose default windows would overlap: with a shared
    # cut, neither reads the other's readings (no double-counted data).
    stream, temp, press = _stream(), _temperature(), _pressure()
    # starts 09:01:00 (BASE+60) and 09:05:00 (BASE+300); cut at their midpoint.
    spans: list[tuple[float, float | None]] = [
        (
            note_time_to_unix(WORK_DATE, "09:01:00"),
            note_time_to_unix(WORK_DATE, "09:03:00"),
        ),
        (
            note_time_to_unix(WORK_DATE, "09:05:00"),
            note_time_to_unix(WORK_DATE, "09:07:00"),
        ),
    ]
    (lo0, hi0), (lo1, hi1) = non_overlapping_bounds(spans)
    a = match_spot(
        1,
        stream,
        "09:01:00",
        "09:03:00",
        WORK_DATE,
        0,
        temp,
        press,
        lo_bound=lo0,
        hi_bound=hi0,
    )
    b = match_spot(
        2,
        stream,
        "09:05:00",
        "09:07:00",
        WORK_DATE,
        0,
        temp,
        press,
        lo_bound=lo1,
        hi_bound=hi1,
    )
    assert not a.skipped and not b.skipped
    # No timestamp appears in both spots' readings.
    overlap = set(a.readings["timestamp"]).intersection(b.readings["timestamp"])
    assert overlap == set()
    # Without the bounds the same two spots DO share readings (the old behaviour).
    a_free = match_spot(1, stream, "09:01:00", "09:03:00", WORK_DATE, 0, temp, press)
    b_free = match_spot(2, stream, "09:05:00", "09:07:00", WORK_DATE, 0, temp, press)
    shared = set(a_free.readings["timestamp"]).intersection(
        b_free.readings["timestamp"]
    )
    assert shared  # they overlapped before the fix
