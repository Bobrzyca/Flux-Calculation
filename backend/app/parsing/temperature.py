"""Temperature-log parser (pure; no HTTP).

Reads the temperature xlsx (columns ``Date`` ~every 30 s and ``Temp`` in °C) into
``timestamp`` (unix seconds) + ``temperature_c``, sorted by time, ready for the
nearest-in-time matching step.
"""

from pathlib import Path

import pandas as pd


def parse_temperature(path: str | Path) -> pd.DataFrame:
    """Parse the temperature xlsx into ``timestamp`` + ``temperature_c``.

    Sorted by time; ``timestamp`` is unix seconds.
    """
    raw = pd.read_excel(path, engine="openpyxl")
    raw.columns = [str(c).strip() for c in raw.columns]
    # Interpret naive datetimes as UTC wall-clock, matching the LI-7810 unix
    # timestamps. Subtracting the epoch is resolution-independent (openpyxl may
    # yield micro- or nanosecond datetimes), unlike a raw int64 cast.
    when = pd.to_datetime(raw["Date"], utc=True)
    epoch = pd.Timestamp("1970-01-01", tz="UTC")
    timestamp = ((when - epoch) // pd.Timedelta(seconds=1)).astype(float)
    out = pd.DataFrame(
        {
            "timestamp": timestamp,
            "temperature_c": pd.to_numeric(raw["Temp"], errors="coerce").astype(float),
        }
    )
    return out.sort_values("timestamp", ignore_index=True)
