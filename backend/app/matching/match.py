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

from app.matching.timeshift import apply_offset
from app.parsing.pressure import PressureReading

# Per-spot flag emitted here (mirrors the frontend SpotFlag union).
NO_PRESSURE = "no_pressure"

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


def note_time_to_unix(work_date: date, hhmmss: str) -> float:
    """Combine a ``HH:MM:SS`` note time with the work date into unix seconds (UTC)."""
    hour, minute, second = (int(part) for part in hhmmss.split(":"))
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
) -> SpotMatch:
    """Match one spot: validate its window, slice readings, attach temp/pressure."""
    empty = readings.iloc[0:0].copy()

    if not start or not stop:
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

    start_unix = note_time_to_unix(work_date, start)
    stop_unix = note_time_to_unix(work_date, stop)
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

    window = slice_spot(readings, start, stop, work_date, offset_seconds)
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

    temperature_used = nearest_temperature(temperature, start_unix)
    pressure_used = nearest_pressure(pressure, start_unix)

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

    annotated = window.copy()
    annotated["temperature_used"] = temperature_used
    annotated["pressure_used"] = pressure_used
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
