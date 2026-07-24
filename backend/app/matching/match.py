"""Auto-match by timestamp (pure): slice per-spot windows, attach temp/pressure.

Converts each note's ``HH:MM:SS`` on the work date to unix, slices the (offset-
corrected) concentration stream into that window, and attaches the nearest-in-time
temperature and pressure. Emits structured log messages; persistence is the match
endpoint's job. Spots are matched independently — repeated GPS (a redo, or a
light/dark pair sharing a location) stays distinct; light and dark are never merged.
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime

import pandas as pd

from app.flux import constants as C
from app.matching.timeshift import apply_offset
from app.parsing.pressure import PressureReading

# Per-spot flag emitted here (mirrors the frontend SpotFlag union).
NO_PRESSURE = "no_pressure"

# Seconds of concentration data to slice from each spot's start: enough for the
# fit step to slide its FIT_WINDOW to the most-linear position.
_SLICE_SECONDS = C.FIT_WINDOW_SECONDS + C.FIT_SEARCH_MAX_OFFSET_SECONDS

# The brief wants temperature matched "nearest ≤ ~30 s"; if the closest reading
# is further than this we still use it but warn so the supervisor can see it.
TEMP_NEAR_GAP_S = 30.0


@dataclass
class LogMessage:
    """A structured processing-log line (severity: info | warning | error)."""

    severity: str
    message: str


@dataclass
class SpotMatch:
    """The matching outcome for one spot."""

    nr: int
    readings: pd.DataFrame  # in-window, annotated with temperature_used/pressure_used
    temperature_used: float | None
    pressure_used: float | None
    skipped: bool
    skip_reason: str | None
    flags: list[str] = field(default_factory=list)
    logs: list[LogMessage] = field(default_factory=list)


def parse_note_time(hhmmss: str) -> tuple[int, int, int]:
    """Split a note time into (hour, minute, second); seconds are optional.

    Hand-typed notes often carry ``HH:MM`` — treat that as ``:00`` rather than
    failing. Raises ``ValueError`` for anything else.
    """
    parts = [int(part) for part in hhmmss.split(":")]
    if len(parts) == 2:
        return parts[0], parts[1], 0
    if len(parts) == 3:
        return parts[0], parts[1], parts[2]
    raise ValueError(f"expected HH:MM:SS or HH:MM, got {hhmmss!r}")


def note_time_to_unix(work_date: date, hhmmss: str) -> float:
    """Combine a note time (``HH:MM:SS`` or ``HH:MM``) with the work date (UTC)."""
    hour, minute, second = parse_note_time(hhmmss)
    when = datetime(
        work_date.year, work_date.month, work_date.day, hour, minute, second, tzinfo=UTC
    )
    return when.timestamp()


def slice_spot(
    readings: pd.DataFrame,
    start: str,
    stop: str,
    work_date: date,
    offset_seconds: float,
) -> pd.DataFrame:
    """Offset-correct ``readings`` and return those inside ``[start, stop]``.

    The returned frame carries the corrected timestamps.
    """
    shifted = apply_offset(readings, offset_seconds)
    start_unix = note_time_to_unix(work_date, start)
    stop_unix = note_time_to_unix(work_date, stop)
    mask = (shifted["timestamp"] >= start_unix) & (shifted["timestamp"] <= stop_unix)
    return shifted[mask].reset_index(drop=True)


def slice_from_start(
    readings: pd.DataFrame,
    start: str,
    work_date: date,
    offset_seconds: float,
    seconds: float,
    lead_seconds: float = 0.0,
    lo_bound: float | None = None,
    hi_bound: float | None = None,
) -> pd.DataFrame:
    """Offset-correct ``readings`` and return a window around ``start``.

    Returns rows with corrected timestamps in
    ``[start - lead_seconds, start + seconds)``. The ``lead_seconds`` of data
    *before* the recorded start let the fit step search — and the user shift —
    the window to an earlier slope than the hand-recorded start.

    ``lo_bound``/``hi_bound`` are optional absolute (unix) limits that further
    clamp the window so it cannot extend into an adjacent spot's window — the
    guard against two spots being computed on the same readings. They only ever
    *narrow* the ``[start - lead, start + seconds)`` span, so far-apart spots are
    unaffected.
    """
    shifted = apply_offset(readings, offset_seconds)
    start_unix = note_time_to_unix(work_date, start)
    lo = start_unix - lead_seconds
    hi = start_unix + seconds
    if lo_bound is not None:
        lo = max(lo, lo_bound)
    if hi_bound is not None:
        hi = min(hi, hi_bound)
    mask = (shifted["timestamp"] >= lo) & (shifted["timestamp"] < hi)
    return shifted[mask].reset_index(drop=True)


def overlap_cut(prev_start: float, prev_stop: float | None, next_start: float) -> float:
    """Boundary time between two consecutive spots so their windows don't overlap.

    Placed at the midpoint of the earlier spot's recorded *stop* and the later
    spot's recorded *start*, so each spot keeps its own measurement region and the
    gap between them is split evenly. Falls back to the midpoint of the two starts
    when the stop is missing or itself overlaps the next start. Always clamped to
    lie within ``[prev_start, next_start]``.
    """
    if prev_stop is not None and prev_start < prev_stop <= next_start:
        cut = (prev_stop + next_start) / 2.0
    else:
        cut = (prev_start + next_start) / 2.0
    return min(max(cut, prev_start), next_start)


def non_overlapping_bounds(
    spans: list[tuple[float, float | None]],
) -> list[tuple[float | None, float | None]]:
    """Per-spot ``(lo, hi)`` unix limits that keep consecutive windows apart.

    ``spans`` is ``(start_unix, stop_unix | None)`` **sorted ascending by
    start_unix**. Between each adjacent pair a single shared cut (see
    ``overlap_cut``) becomes the earlier spot's upper limit and the later spot's
    lower limit, so their sliced readings can never coincide. The first spot has
    no lower limit and the last no upper limit (both ``None``).
    """
    n = len(spans)
    los: list[float | None] = [None] * n
    his: list[float | None] = [None] * n
    for i in range(n - 1):
        cut = overlap_cut(spans[i][0], spans[i][1], spans[i + 1][0])
        his[i] = cut
        los[i + 1] = cut
    return list(zip(los, his, strict=True))


def nearest_temperature(temperature: pd.DataFrame, t: float) -> float | None:
    """Temperature (°C) nearest in time to ``t``; None if the series is empty."""
    if temperature.empty:
        return None
    idx = (temperature["timestamp"].astype(float) - t).abs().idxmin()
    return float(temperature.loc[idx, "temperature_c"])


def nearest_pressure(readings: list[PressureReading], t: float) -> float | None:
    """Pressure (hPa) nearest in time to ``t``; None if there are no readings."""
    if not readings:
        return None
    return min(readings, key=lambda r: abs(r.timestamp - t)).pressure_hpa


def match_spot(
    nr: int,
    readings: pd.DataFrame,
    start: str,
    stop: str,
    work_date: date,
    offset_seconds: float,
    temperature: pd.DataFrame,
    pressure: list[PressureReading],
    lo_bound: float | None = None,
    hi_bound: float | None = None,
) -> SpotMatch:
    """Match one spot: validate its window, slice readings, attach temp/pressure.

    ``lo_bound``/``hi_bound`` are optional unix limits (from
    ``non_overlapping_bounds``) that stop this spot's window from reaching into a
    neighbouring spot's window, so no two spots are computed on the same readings.
    """
    empty = readings.iloc[0:0].copy()

    try:
        # Empty strings and malformed times take the same skip path: a bad
        # hand-typed time must skip one spot, never 500 the whole match run.
        if not start or not stop:
            raise ValueError("missing time")
        start_unix = note_time_to_unix(work_date, start)
        stop_unix = note_time_to_unix(work_date, stop)
    except ValueError:
        return SpotMatch(
            nr,
            empty,
            None,
            None,
            skipped=True,
            skip_reason="unparseable time",
            logs=[
                LogMessage("error", f"Spot {nr} skipped: unparseable start/stop time")
            ],
        )
    if stop_unix <= start_unix:
        return SpotMatch(
            nr,
            empty,
            None,
            None,
            skipped=True,
            skip_reason="stop before start",
            logs=[LogMessage("error", f"Spot {nr} skipped: stop before start")],
        )

    # Slice a window around the recorded start: a FIT_SEARCH_BACK_SECONDS lead
    # *before* it plus a forward span long enough for the fit step to search for
    # the most-linear sub-window (FIT_WINDOW + max search offset). The lead lets
    # the fit — and a manual shift — reach an earlier slope when the hand-recorded
    # start is late; the recorded stop is only used to reject stop-before-start.
    window = slice_from_start(
        readings,
        start,
        work_date,
        offset_seconds,
        _SLICE_SECONDS,
        lead_seconds=C.FIT_SEARCH_BACK_SECONDS,
        lo_bound=lo_bound,
        hi_bound=hi_bound,
    )
    if window.empty:
        return SpotMatch(
            nr,
            window,
            None,
            None,
            skipped=True,
            skip_reason="empty window",
            logs=[
                LogMessage(
                    "warning",
                    f"Spot {nr} skipped: no concentration data in {start}–{stop}",
                )
            ],
        )

    pressure_used = nearest_pressure(pressure, start_unix)

    # Attach the nearest temperature to EACH reading (the logger samples ~every
    # 30 s), so the fit step can use the mean over its window and report a range
    # rather than a single start-of-spot value.
    annotated = _attach_temperature(window.copy(), temperature)
    annotated["pressure_used"] = pressure_used
    temps = annotated["temperature_used"].dropna()
    temperature_used = float(temps.mean()) if not temps.empty else None

    logs: list[LogMessage] = []
    flags: list[str] = []
    if pressure_used is None:
        flags.append(NO_PRESSURE)
        logs.append(LogMessage("warning", f"Spot {nr}: no pressure available"))
    if temperature_used is not None and not temperature.empty:
        gap = float((temperature["timestamp"].astype(float) - start_unix).abs().min())
        if gap > TEMP_NEAR_GAP_S:
            logs.append(
                LogMessage(
                    "warning",
                    f"Spot {nr}: nearest temperature is {gap:.0f}s away "
                    f"(> {TEMP_NEAR_GAP_S:.0f}s)",
                )
            )

    return SpotMatch(
        nr,
        annotated,
        temperature_used,
        pressure_used,
        skipped=False,
        skip_reason=None,
        flags=flags,
        logs=logs,
    )


def _attach_temperature(
    window: pd.DataFrame, temperature: pd.DataFrame
) -> pd.DataFrame:
    """Add a per-reading ``temperature_used`` column (nearest in time)."""
    if temperature.empty:
        window["temperature_used"] = float("nan")
        return window
    merged = pd.merge_asof(
        window.sort_values("timestamp").reset_index(drop=True),
        temperature[["timestamp", "temperature_c"]].sort_values("timestamp"),
        on="timestamp",
        direction="nearest",
    )
    return merged.rename(columns={"temperature_c": "temperature_used"})
