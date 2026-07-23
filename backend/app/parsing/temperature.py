"""Temperature-log parser (pure; no HTTP).

Reads a temperature log into ``timestamp`` (unix seconds) + ``temperature_c``,
sorted by time, ready for the nearest-in-time matching step.

Real logs arrive in **many shapes** and we must read them without a code change
per format — file type (``.xlsx`` / ``.csv`` / whitespace-aligned ``.txt``),
delimiter (tab / ``;`` / ``,`` / 2+ spaces), **comma decimals** (``13,35``),
the date and time in one combined column or two separate ones, and ISO vs
European day-first order. All of that tolerant reading lives in
``app.parsing.tabular``; this module only picks out the temperature column and
assembles the result.
"""

from pathlib import Path

import pandas as pd

from app.parsing.tabular import (
    read_table,
    resolve_temporal_columns,
    to_float_series,
    to_unix_seconds,
)

# Exact header spellings (lower-cased, stripped) that name the temperature column.
_TEMP_ALIASES = frozenset(
    {"temp", "temperature", "t", "temp_c", "temp (c)", "temperatura", "temp(°c)"}
)


def _resolve_temperature_column(columns: list[str]) -> str:
    """Find the temperature column by exact alias, then by a loose ``temp``/°C match."""
    lookup = {c.strip().lower(): c for c in columns}
    for alias in _TEMP_ALIASES:
        if alias in lookup:
            return lookup[alias]
    for lowered, original in lookup.items():
        if "temp" in lowered or "°c" in lowered or lowered.endswith("(c)"):
            return original
    raise ValueError(
        f"Temperature file has no recognisable temperature column "
        f"(looked for a name containing 'temp' or '°C'); found {columns}."
    )


def parse_temperature(path: str | Path) -> pd.DataFrame:
    """Parse a temperature log into ``timestamp`` + ``temperature_c``.

    Sorted by time; ``timestamp`` is unix seconds. Raises ``ValueError`` if the
    file can't be read, lacks a date/time or temperature column, or yields no
    parseable timestamps.
    """
    raw = read_table(path)
    raw.columns = [str(c).strip() for c in raw.columns]
    columns = list(raw.columns)
    temp_col = _resolve_temperature_column(columns)
    date_col, time_col = resolve_temporal_columns(columns, raw, exclude=(temp_col,))

    out = pd.DataFrame(
        {
            "timestamp": to_unix_seconds(raw, date_col, time_col),
            "temperature_c": to_float_series(raw[temp_col]),
        }
    )
    out = out.dropna(subset=["timestamp"])
    if out.empty:
        raise ValueError(
            f"Temperature file '{date_col}' column held no parseable dates."
        )
    return out.sort_values("timestamp", ignore_index=True)
