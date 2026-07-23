"""IMGW pressure parser (deterministic; no LLM).

Reads a pressure file into time-sorted ``PressureReading``s (unix seconds + hPa).
Like the temperature parser it uses the shared tolerant reader
(``app.parsing.tabular``), so it copes with real exports: ``.csv``/``.txt``/
``.xlsx``, Windows encodings (cp1250/UTF-16), tab/``;``/``,``/space delimiters,
**comma decimals** (``1013,2``), a date+time in one column or two, ISO or
European day-first dates, and plain unix-seconds timestamps. Pressure is
assumed to be in **hPa** unless a different ``assume_unit`` is given.

# TODO: LLM tolerant parsing of the truly free-form IMGW export (seminar 6) —
# e.g. a station-coded file with no friendly header. This deterministic parser
# now covers the common well-formed/European shapes.
"""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from app.parsing.tabular import (
    read_table,
    resolve_temporal_columns,
    to_float_series,
    to_unix_seconds,
)

# Assumed unit of the uploaded pressure values — confirm against real IMGW data.
DEFAULT_PRESSURE_UNIT = "hPa"
# Multiplier to convert a supported unit into hPa.
_TO_HPA = {"hpa": 1.0, "kpa": 10.0, "pa": 0.01, "mbar": 1.0}

# Exact header spellings that name the pressure column, then loose substring keys.
_PRESSURE_ALIASES = frozenset(
    {"pressure_hpa", "pressure", "hpa", "cisnienie", "ciśnienie", "p", "pa", "mbar"}
)
_PRESSURE_KEYS = ("pressure", "cisnien", "ciśnien", "hpa", "mbar", " hpa")


@dataclass
class PressureReading:
    """A single pressure observation, normalised to unix seconds + hPa."""

    timestamp: float
    pressure_hpa: float


def _resolve_pressure_column(columns: list[str]) -> str:
    """Find the pressure column by exact alias, then by a loose keyword match."""
    lookup = {c.strip().lower(): c for c in columns}
    for alias in _PRESSURE_ALIASES:
        if alias in lookup:
            return lookup[alias]
    for lowered, original in lookup.items():
        if any(k in lowered for k in _PRESSURE_KEYS):
            return original
    raise ValueError(
        f"Pressure file has no recognisable pressure column "
        f"(looked for a name containing 'pressure'/'ciśnienie'/'hPa'); found {columns}."
    )


def parse_pressure(
    path: str | Path, *, assume_unit: str = DEFAULT_PRESSURE_UNIT
) -> list[PressureReading]:
    """Parse a pressure file into time-sorted ``PressureReading``s (hPa)."""
    factor = _TO_HPA.get(assume_unit.lower())
    if factor is None:
        raise ValueError(f"Unsupported pressure unit: {assume_unit!r}")

    raw = read_table(path)
    raw.columns = [str(c).strip() for c in raw.columns]
    columns = list(raw.columns)
    pr_col = _resolve_pressure_column(columns)
    date_col, time_col = resolve_temporal_columns(columns, raw, exclude=(pr_col,))

    out = pd.DataFrame(
        {
            "timestamp": to_unix_seconds(raw, date_col, time_col),
            "pressure_hpa": to_float_series(raw[pr_col]) * factor,
        }
    )
    out = out.dropna(subset=["timestamp", "pressure_hpa"]).sort_values(
        "timestamp", ignore_index=True
    )
    return [
        PressureReading(timestamp=row.timestamp, pressure_hpa=row.pressure_hpa)
        for row in out.itertuples(index=False)
    ]
