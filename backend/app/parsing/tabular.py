"""Shared tabular-file helpers for the logger/pressure parsers (pure; no HTTP).

Real field exports vary wildly — Windows code pages, ``;``/``,``/tab/space
delimiters, **comma decimal separators** (``13,35``), a date and time in one
column or two, ISO vs European day-first order. These helpers centralise the
tolerant reading so the temperature and pressure parsers stay small and behave
identically. If a file can't be read, or no date/time column can be found, a
clear ``ValueError`` is raised (the API turns it into a 422, not a 500).
"""

import re
from pathlib import Path

import pandas as pd

from app.parsing.encoding import detect_encoding

# Substring keywords used to classify the temporal columns (lower-cased headers).
# 'date' words name the calendar date (or a combined datetime); 'time' words name
# a clock-time column. Polish 'czas' is a time/timestamp word; when a separate
# date column exists it is the time-of-day, otherwise it carries the full stamp.
_DATE_KEYS = ("date", "data", "datum", "fecha", "dzień", "dzien", "day")
_TIME_KEYS = ("time", "godzina", "godz", "hour", "czas")

# Leading date triple A<sep>B<sep>C with . / or - separators (year last, or first
# for ISO). Used only to infer the day/month/year order.
_DATE_LEAD = re.compile(r"(\d{1,4})\s*[./\-]\s*(\d{1,2})\s*[./\-]\s*(\d{1,4})")

# An Excel date-only cell round-trips to "YYYY-MM-DD 00:00:00"; a time-only cell
# may round-trip with a bogus 1899/1900 date. Strip both so a separate date and
# time column recombine cleanly.
_MIDNIGHT_TAIL = re.compile(r"[ T]00:00:00(\.0+)?$")
_BOGUS_DATE_HEAD = re.compile(r"^18\d\d-\d\d-\d\d[ T]|^19\d\d-\d\d-\d\d[ T]")


def to_float_series(series: pd.Series) -> pd.Series:
    """Coerce a column to float, tolerating European number formats.

    Dot-decimal values (``13.35``) parse directly. Values that fail — because
    they use a **comma decimal** (``13,35``) or a **thousands comma**
    (``1,013.25``) — are retried: a comma with no dot is a decimal separator
    (``,`` → ``.``); a comma alongside a dot is a thousands separator (dropped).
    A genuinely unparseable cell stays ``NaN``. This never changes a value that
    already parsed, so dot-decimal files are unaffected.
    """
    numeric = pd.to_numeric(series, errors="coerce")
    mask = numeric.isna() & series.notna()
    if mask.any():
        text = series[mask].astype(str).str.strip()
        has_dot = text.str.contains(".", regex=False)
        has_comma = text.str.contains(",", regex=False)
        fixed = text.copy()
        both = has_dot & has_comma
        comma_only = has_comma & ~has_dot
        fixed[both] = text[both].str.replace(",", "", regex=False)
        fixed[comma_only] = text[comma_only].str.replace(",", ".", regex=False)
        numeric = numeric.copy()
        numeric.loc[mask] = pd.to_numeric(fixed, errors="coerce")
    return numeric.astype(float)


def read_table(path: str | Path) -> pd.DataFrame:
    """Read an xlsx/csv/txt into a DataFrame, tolerant of a wrong extension,
    Windows encodings, and tab/``;``/``,``/2+-space delimiters.

    Legacy ``.xls`` needs ``xlrd`` (not a dependency) and is rejected with a
    clear message rather than a cryptic openpyxl error.
    """
    suffix = Path(path).suffix.lower()
    if suffix == ".xls":
        raise ValueError(
            "Legacy .xls is not supported — save the file as .xlsx or export it to CSV."
        )
    # Prefer the reader matching the extension, but fall back to the other so a
    # mislabelled file (a CSV saved as .xlsx, or vice versa) still parses.
    readers = (_read_csv, _read_excel) if suffix == ".csv" else (_read_excel, _read_csv)
    last_error: Exception | None = None
    for reader in readers:
        try:
            return reader(path)
        except Exception as exc:  # noqa: BLE001 - deliberately try the next reader
            last_error = exc
    raise ValueError(
        f"Could not read the file as a spreadsheet or delimited text ({last_error})."
    )


def _read_excel(path: str | Path) -> pd.DataFrame:
    return pd.read_excel(path, engine="openpyxl")


def _read_csv(path: str | Path) -> pd.DataFrame:
    # Sniff the encoding first (Windows exports are often cp1250/UTF-16), then the
    # delimiter: tab / ; / , / runs of 2+ spaces (which keep the single space
    # inside a "YYYY-MM-DD HH:MM:SS" datetime intact).
    encoding = detect_encoding(path)
    for sep in ("\t", ";", ","):
        try:
            frame = pd.read_csv(path, sep=sep, encoding=encoding)
        except ValueError:  # pandas ParserError subclasses ValueError
            continue
        if frame.shape[1] > 1:
            return frame
    try:
        frame = pd.read_csv(path, sep=r"\s{2,}", engine="python", encoding=encoding)
        if frame.shape[1] > 1:
            return frame
    except ValueError:
        pass
    # Last resort: let pandas sniff the delimiter itself.
    return pd.read_csv(path, sep=None, engine="python", encoding=encoding)


def _find_by_keys(
    columns: list[str], keys: tuple[str, ...], exclude: tuple[str, ...] = ()
) -> str | None:
    """First column whose lower-cased header contains a key and no excluded word."""
    for col in columns:
        low = col.strip().lower()
        if any(k in low for k in keys) and not any(e in low for e in exclude):
            return col
    return None


def _first_datetime_like_column(
    frame: pd.DataFrame, exclude: tuple[str, ...]
) -> str | None:
    """The non-excluded column whose values parse as the most datetimes (or None)."""
    best_col: str | None = None
    best_ok = 0
    for col in frame.columns:
        if col in exclude:
            continue
        parsed = pd.to_datetime(frame[col].astype(str), errors="coerce", dayfirst=True)
        ok = int(parsed.notna().sum())
        if ok > best_ok:
            best_col, best_ok = col, ok
    return best_col if best_ok else None


def resolve_temporal_columns(
    columns: list[str], frame: pd.DataFrame, exclude: tuple[str, ...] = ()
) -> tuple[str, str | None]:
    """Return ``(date_col, time_col_or_None)``.

    ``date_col`` may itself hold a full datetime (or unix seconds). A separate
    ``time_col`` is returned only when a distinct clock-time column exists
    alongside a date column. Falls back to the column that parses as the most
    datetimes when the headers are unfamiliar. Raises ``ValueError`` if none.
    """
    candidates = [c for c in columns if c not in exclude]
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
        date_col = _first_datetime_like_column(frame, exclude)
    if date_col is None:
        raise ValueError(f"No recognisable date/time column; found {list(columns)}.")
    return date_col, time_col


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


def to_unix_seconds(
    frame: pd.DataFrame, date_col: str, time_col: str | None
) -> pd.Series:
    """Build a unix-seconds Series from a resolved date (+ optional time) column.

    Supports: a numeric **unix-seconds** column; a single combined datetime
    column; and **two separate** date + time columns (recombined). The
    day/month/year order is inferred from the values. Naive datetimes are read
    as UTC wall-clock (matching the LI-7810 local timeline and the local notes).
    Unparseable rows become ``NaN`` (the caller drops them).
    """
    # A pure unix-seconds column (only when there's no separate time column, and
    # the column isn't already datetime-typed — an Excel datetime cell would
    # otherwise coerce to nanoseconds and masquerade as a huge unix stamp).
    if time_col is None and not pd.api.types.is_datetime64_any_dtype(frame[date_col]):
        numeric = pd.to_numeric(frame[date_col], errors="coerce")
        if numeric.notna().all():
            return numeric.astype(float)

    date_str = (
        frame[date_col]
        .astype(str)
        .str.strip()
        .str.replace(_MIDNIGHT_TAIL, "", regex=True)
    )
    if time_col is not None and not date_str.str.contains(":", regex=False).any():
        time_str = (
            frame[time_col]
            .astype(str)
            .str.strip()
            .str.replace(_BOGUS_DATE_HEAD, "", regex=True)
        )
        combined = (date_str + " " + time_str).str.strip()
    else:
        combined = date_str

    dayfirst = _infer_dayfirst(date_str)
    when = pd.to_datetime(combined, utc=True, dayfirst=dayfirst, errors="coerce")
    epoch = pd.Timestamp("1970-01-01", tz="UTC")
    return (when - epoch) / pd.Timedelta(seconds=1)
