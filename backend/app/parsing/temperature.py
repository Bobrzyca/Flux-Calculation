"""Temperature-log parser (pure; no HTTP).

Reads a temperature log — an ``.xlsx`` (the common case) or a ``.csv`` — with a
date/time column (~every 30 s) and a temperature column (°C) into ``timestamp``
(unix seconds) + ``temperature_c``, sorted by time, ready for the nearest-in-time
matching step. Column names are matched flexibly (case-insensitive, common English
and Polish spellings). If the file can't be read as either a spreadsheet or a
table, or lacks the needed columns, a clear ``ValueError`` is raised (the API turns
that into a 422 with a helpful message rather than a 500).
"""

from pathlib import Path

import pandas as pd

# Accepted header spellings (lower-cased, stripped) for the two columns we need.
_TIME_ALIASES = frozenset(
    {"date", "time", "datetime", "date/time", "timestamp", "czas", "data"}
)
_TEMP_ALIASES = frozenset(
    {"temp", "temperature", "t", "temp_c", "temp (c)", "temperatura"}
)


def _read_frame(path: str | Path) -> pd.DataFrame:
    """Read the file into a DataFrame, tolerant of xlsx/csv and wrong extensions."""
    suffix = Path(path).suffix.lower()
    # Prefer the reader matching the extension, but fall back to the other so a
    # mislabelled file (e.g. a CSV saved as .xlsx, or vice versa) still parses.
    if suffix == ".csv":
        readers = (_read_csv, _read_excel)
    else:
        readers = (_read_excel, _read_csv)

    last_error: Exception | None = None
    for reader in readers:
        try:
            return reader(path)
        except Exception as exc:  # noqa: BLE001 - deliberately try the next reader
            last_error = exc
    raise ValueError(
        f"Could not read the temperature file as a spreadsheet or CSV ({last_error})."
    )


def _read_excel(path: str | Path) -> pd.DataFrame:
    return pd.read_excel(path, engine="openpyxl")


def _read_csv(path: str | Path) -> pd.DataFrame:
    # Exports are variously tab-, semicolon-, or comma-delimited; pick the
    # separator that actually splits the file into more than one column.
    for sep in ("\t", ";", ","):
        try:
            frame = pd.read_csv(path, sep=sep)
        except ValueError:  # pandas ParserError subclasses ValueError
            continue
        if frame.shape[1] > 1:
            return frame
    # Last resort: let pandas sniff the delimiter itself.
    return pd.read_csv(path, sep=None, engine="python")


def _resolve_column(columns: list[str], aliases: frozenset[str], kind: str) -> str:
    """Find the actual column matching one of ``aliases`` (or containing ``kind``)."""
    lookup = {c.strip().lower(): c for c in columns}
    for alias in aliases:
        if alias in lookup:
            return lookup[alias]
    # Loosest fallback: any column whose name contains the kind word.
    for lowered, original in lookup.items():
        if kind in lowered:
            return original
    raise ValueError(
        f"Temperature file has no recognisable {kind} column "
        f"(looked for {sorted(aliases)}); found {columns}."
    )


def parse_temperature(path: str | Path) -> pd.DataFrame:
    """Parse a temperature log into ``timestamp`` + ``temperature_c``.

    Sorted by time; ``timestamp`` is unix seconds. Raises ``ValueError`` if the
    file can't be read or lacks a date/time and temperature column.
    """
    raw = _read_frame(path)
    raw.columns = [str(c).strip() for c in raw.columns]
    time_col = _resolve_column(list(raw.columns), _TIME_ALIASES, "date")
    temp_col = _resolve_column(list(raw.columns), _TEMP_ALIASES, "temp")

    # Interpret naive datetimes as UTC wall-clock (matching the LI-7810 local
    # DATE/TIME timeline and the local-time notes). ``dayfirst`` handles the
    # European ``DD.MM.YYYY`` dates; unparseable rows become NaT and are dropped.
    when = pd.to_datetime(raw[time_col], utc=True, dayfirst=True, errors="coerce")
    epoch = pd.Timestamp("1970-01-01", tz="UTC")
    out = pd.DataFrame(
        {
            "timestamp": (when - epoch) / pd.Timedelta(seconds=1),
            "temperature_c": pd.to_numeric(raw[temp_col], errors="coerce").astype(
                float
            ),
        }
    )
    out = out.dropna(subset=["timestamp"])
    return out.sort_values("timestamp", ignore_index=True)
