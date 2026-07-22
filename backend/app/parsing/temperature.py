"""Temperature-log parser (pure; no HTTP).

Reads a temperature log into ``timestamp`` (unix seconds) + ``temperature_c``,
sorted by time, ready for the nearest-in-time matching step.

Real logs arrive in **many shapes** and we must read them without a code change
per format:

* file type — ``.xlsx`` (the common case), ``.csv``, or a whitespace-aligned
  ``.txt``; delimiter tab / ``;`` / ``,`` / runs of 2+ spaces;
* the date and time may sit in **one combined column** (``2025-10-06 09:22:20``,
  ``06.10.2025 09:22``) **or two separate columns** (a ``Date`` and a ``Time`` /
  Polish ``Data`` + ``Godzina`` / ``Czas``);
* the date order may be ISO ``YYYY-MM-DD``, European dotted ``DD.MM.YYYY``, or
  slashed ``MM/DD/YYYY``.

So we resolve which column is which by **name and by content**, and infer the
day/month/year order from the **values themselves** (a component > 12 fixes the
day; a 4-digit leading component fixes an ISO year). If the file can't be read,
or no date/temperature column can be found, a clear ``ValueError`` is raised
(the API turns that into a 422 with a helpful message rather than a 500).
"""

import re
from pathlib import Path

import pandas as pd

# Exact header spellings (lower-cased, stripped) that name the temperature column.
_TEMP_ALIASES = frozenset(
    {"temp", "temperature", "t", "temp_c", "temp (c)", "temperatura", "temp(°c)"}
)

# Substring keywords used to classify the temporal columns (lower-cased headers).
# 'date' words name the calendar date (or a combined datetime); 'time' words name
# a clock-time column. Polish 'czas' is a time/timestamp word; when a separate
# date column exists it is the time-of-day, otherwise it carries the full stamp.
_DATE_KEYS = ("date", "data", "datum", "fecha", "dzień", "dzien", "day")
_TIME_KEYS = ("time", "godzina", "godz", "hour", "czas")

# Leading date triple: A<sep>B<sep>C with . / or - separators (year may be last
# or, for ISO, first). Used only to infer the day/month/year order.
_DATE_LEAD = re.compile(r"(\d{1,4})\s*[./\-]\s*(\d{1,2})\s*[./\-]\s*(\d{1,4})")

# An Excel date-only cell round-trips to "YYYY-MM-DD 00:00:00"; a time-only cell
# may round-trip with a bogus 1899/1900 date. Strip both so a separate date and
# time column recombine cleanly.
_MIDNIGHT_TAIL = re.compile(r"[ T]00:00:00(\.0+)?$")
_BOGUS_DATE_HEAD = re.compile(r"^18\d\d-\d\d-\d\d[ T]|^19\d\d-\d\d-\d\d[ T]")


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
    # Space-aligned (fixed-width-ish) exports: split on runs of 2+ spaces so the
    # single space inside a "YYYY-MM-DD HH:MM:SS" datetime is preserved (a plain
    # single-space split would tear the date off the time).
    try:
        frame = pd.read_csv(path, sep=r"\s{2,}", engine="python")
        if frame.shape[1] > 1:
            return frame
    except ValueError:
        pass
    # Last resort: let pandas sniff the delimiter itself.
    return pd.read_csv(path, sep=None, engine="python")


def _find_by_keys(
    columns: list[str], keys: tuple[str, ...], exclude: tuple[str, ...] = ()
) -> str | None:
    """First column whose lower-cased header contains a key and no excluded word."""
    for col in columns:
        low = col.strip().lower()
        if any(k in low for k in keys) and not any(e in low for e in exclude):
            return col
    return None


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


def _resolve_temporal_columns(
    columns: list[str], temp_col: str, frame: pd.DataFrame
) -> tuple[str, str | None]:
    """Return ``(date_col, time_col_or_None)``.

    ``date_col`` may itself hold a full datetime. A separate ``time_col`` is
    returned only when a distinct clock-time column exists alongside a date
    column. Falls back to picking, by content, the column that parses as the most
    datetimes when the headers are unfamiliar.
    """
    candidates = [c for c in columns if c != temp_col]
    # Exclude 'time' when hunting the date column so a "Time"/"DateTime" header
    # isn't mistaken for the calendar date; the reverse for the time column.
    date_col = _find_by_keys(candidates, _DATE_KEYS, exclude=("time",))
    time_col = _find_by_keys(candidates, _TIME_KEYS, exclude=("date",))
    if date_col is None:
        # No plain date header: a lone time/czas/datetime column carries the stamp.
        date_col = _find_by_keys(candidates, _TIME_KEYS)
        time_col = None
    elif time_col == date_col:
        time_col = None

    if date_col is None:
        date_col = _first_datetime_like_column(frame, temp_col)
    if date_col is None:
        raise ValueError(
            f"Temperature file has no recognisable date/time column; found {columns}."
        )
    return date_col, time_col


def _first_datetime_like_column(frame: pd.DataFrame, temp_col: str) -> str | None:
    """The non-temp column whose values parse as the most datetimes (or None)."""
    best_col: str | None = None
    best_ok = 0
    for col in frame.columns:
        if col == temp_col:
            continue
        parsed = pd.to_datetime(frame[col].astype(str), errors="coerce", dayfirst=True)
        ok = int(parsed.notna().sum())
        if ok > best_ok:
            best_col, best_ok = col, ok
    return best_col if best_ok else None


def _infer_dayfirst(date_strings: pd.Series) -> bool:
    """Infer day-first vs year/month-first from the actual date values.

    A 4-digit leading component means ISO ``YYYY-MM-DD`` (year-first → not
    day-first). Otherwise a first component > 12 proves it's the day (day-first),
    a second component > 12 proves the first is the month (month-first, e.g. US
    ``MM/DD``). When genuinely ambiguous we default to **day-first** — the lab's
    files are European.
    """
    firsts: list[int] = []
    seconds: list[int] = []
    for value in date_strings:
        match = _DATE_LEAD.search(str(value))
        if match is None:
            continue
        first, second = int(match.group(1)), int(match.group(2))
        if first > 31:  # 4-digit year leads → ISO, year-first
            return False
        firsts.append(first)
        seconds.append(second)
    if any(f > 12 for f in firsts):
        return True
    if any(s > 12 for s in seconds):
        return False
    return True


def parse_temperature(path: str | Path) -> pd.DataFrame:
    """Parse a temperature log into ``timestamp`` + ``temperature_c``.

    Sorted by time; ``timestamp`` is unix seconds. Raises ``ValueError`` if the
    file can't be read, lacks a date/time or temperature column, or yields no
    parseable timestamps.
    """
    raw = _read_frame(path)
    raw.columns = [str(c).strip() for c in raw.columns]
    temp_col = _resolve_temperature_column(list(raw.columns))
    date_col, time_col = _resolve_temporal_columns(list(raw.columns), temp_col, raw)

    date_str = raw[date_col].astype(str).str.strip()
    # Drop an Excel midnight tail so a separate time column can supply the time.
    date_str = date_str.str.replace(_MIDNIGHT_TAIL, "", regex=True)
    if time_col is not None and not date_str.str.contains(":", regex=False).any():
        time_str = (
            raw[time_col]
            .astype(str)
            .str.strip()
            .str.replace(_BOGUS_DATE_HEAD, "", regex=True)
        )
        combined = (date_str + " " + time_str).str.strip()
    else:
        combined = date_str

    # Interpret naive datetimes as UTC wall-clock (matching the LI-7810 local
    # DATE/TIME timeline and the local-time notes). The day/month/year order is
    # inferred from the values so ISO and European dates both land correctly.
    dayfirst = _infer_dayfirst(date_str)
    when = pd.to_datetime(combined, utc=True, dayfirst=dayfirst, errors="coerce")
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
    if out.empty:
        sample = combined.iloc[0] if len(combined) else "∅"
        raise ValueError(
            f"Temperature file '{date_col}' column held no parseable dates "
            f"(sample: {sample!r})."
        )
    return out.sort_values("timestamp", ignore_index=True)
