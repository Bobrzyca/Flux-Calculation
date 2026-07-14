"""IMGW pressure parser (deterministic; no LLM).

Handles a well-formed CSV / XLSX with a timestamp column and a pressure column.
Pressure is assumed to be in **hPa** (the unit is a parameter so it's easy to
confirm against real IMGW files later). Timestamps may be datetime strings or
unix seconds; both are normalised to unix seconds.

# TODO: LLM tolerant parsing of the unknown-format IMGW pressure file
# (seminar 6). This deterministic parser covers well-formed CSV/XLSX.
"""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

# Assumed unit of the uploaded pressure values — confirm against real IMGW data.
DEFAULT_PRESSURE_UNIT = "hPa"
# Multiplier to convert a supported unit into hPa.
_TO_HPA = {"hpa": 1.0, "kpa": 10.0, "pa": 0.01, "mbar": 1.0}

_TIMESTAMP_ALIASES = {"timestamp", "time", "datetime", "date", "data", "czas"}
_PRESSURE_ALIASES = {"pressure_hpa", "pressure", "hpa", "cisnienie", "ciśnienie", "p"}


@dataclass
class PressureReading:
    """A single pressure observation, normalised to unix seconds + hPa."""

    timestamp: float
    pressure_hpa: float


def _find_column(headers: list[str], aliases: set[str]) -> str:
    for header in headers:
        if header.strip().lower() in aliases:
            return header
    raise ValueError(f"No column matching {sorted(aliases)} in {headers}")


def _to_unix_seconds(series: pd.Series) -> pd.Series:
    """Coerce a timestamp column (unix numbers or datetime strings) to unix seconds."""
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().all():
        return numeric.astype(float)
    when = pd.to_datetime(series, utc=True)
    epoch = pd.Timestamp("1970-01-01", tz="UTC")
    return ((when - epoch) // pd.Timedelta(seconds=1)).astype(float)


def parse_pressure(
    path: str | Path, *, assume_unit: str = DEFAULT_PRESSURE_UNIT
) -> list[PressureReading]:
    """Parse a pressure file into time-sorted ``PressureReading``s (hPa)."""
    suffix = Path(path).suffix.lower()
    if suffix == ".csv":
        frame = pd.read_csv(path)
    elif suffix in {".xlsx", ".xls"}:
        frame = pd.read_excel(path, engine="openpyxl")
    else:
        raise ValueError(f"Unsupported pressure format: {suffix!r}")

    headers = [str(c) for c in frame.columns]
    ts_col = _find_column(headers, _TIMESTAMP_ALIASES)
    pr_col = _find_column(headers, _PRESSURE_ALIASES)

    factor = _TO_HPA.get(assume_unit.lower())
    if factor is None:
        raise ValueError(f"Unsupported pressure unit: {assume_unit!r}")

    out = pd.DataFrame(
        {
            "timestamp": _to_unix_seconds(frame[ts_col]),
            "pressure_hpa": pd.to_numeric(frame[pr_col], errors="coerce").astype(float)
            * factor,
        }
    ).sort_values("timestamp", ignore_index=True)

    return [
        PressureReading(timestamp=row.timestamp, pressure_hpa=row.pressure_hpa)
        for row in out.itertuples(index=False)
    ]
