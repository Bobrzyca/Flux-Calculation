"""LI-7810 concentration-log parser (pure; no HTTP).

The LI-7810 exports a tab-delimited text file with a **multi-line metadata
preamble** (model, serial, timezone, …), then a column-name header row carrying
``SECONDS``, ``CO2`` (ppm), ``CH4`` (ppb) plus many extras, then the 1 Hz data
rows. LI-COR firmware may prefix rows with ``DATAH`` (header) / ``DATAU`` (units)
/ ``DATA`` (data) markers, and the number of preamble lines varies between
instruments and firmware — so we **locate the header row by its column names**
rather than assuming a fixed offset. ``nan`` marks the laser warm-up and dropouts;
we keep those as ``nan`` here — dropping (and reporting) them is the
matching/fitting step's job.

**Encoding + format tolerance.** Real exports come off Windows machines and are
often saved in a legacy code page (cp1250 in Poland) or UTF-16, not UTF-8 — and
the preamble may carry non-ASCII bytes (``°C`` units, a Polish site name) before
the header. Reading strictly as UTF-8 raised ``UnicodeDecodeError`` and the file
was wrongly rejected, so text reads try several encodings. Researchers also open
the ``.txt`` in Excel and hand us the ``.xlsx`` "Save As" — so ``.xlsx``/``.xlsm``
workbooks with the same LI-7810 layout are accepted too.
"""

from collections.abc import Iterable
from pathlib import Path

import pandas as pd

from app.parsing.encoding import detect_encoding
from app.parsing.tabular import to_float_series

# The columns the downstream pipeline relies on.
REQUIRED_COLUMNS = frozenset({"SECONDS", "CO2", "CH4"})

# CO₂ readings outside this (ppm) range are treated as invalid sensor spikes and
# dropped (set to nan) before fitting. This is the DEFAULT upper bound; it is
# **configurable** (``settings.max_valid_co2_ppm`` / env ``MAX_VALID_CO2_PPM``,
# threaded in as ``parse_li7810(max_co2_ppm=…)``) because high-flux substrates
# (manure, very active soils) can genuinely exceed it over a closure. The R
# method-of-record used 1500; the default was raised to 5000. Negative CO₂ is
# physically impossible (ambient never drops below ~350 ppm), so anything < 0 is
# an instrument artefact — common on "noisy" DIAG-flagged rows we now keep.
MAX_VALID_CO2_PPM = 5000.0
MIN_VALID_CO2_PPM = 0.0

# CH₄ plausibility range (ppb). Ambient is ~1900–2000; a real chamber rise on a
# wetland campaign peaks in the tens of thousands (2026-07-02 Kampinos max:
# ~43k). Laser mode-hop artefacts cluster from ~130k into the millions, so the
# bound sits an order of magnitude above real rises and well below the garbage.
# Negative CH₄ is physically impossible.
MAX_VALID_CH4_PPB = 100_000.0
MIN_VALID_CH4_PPB = 0.0

# LI-COR status codes (manual Table 2-2) are additive bit flags. Bits 1|2|4|8|16
# ("yellow": frequency/laser-temperature adjustment, incomplete scan, start-up)
# mean "measurements may be noisy" but VALID — dropping them wiped out whole
# spots on real campaigns. Bits ≥ 32 ("red": spectral fit residual too high,
# unregulated pressures/temperatures, inlet clogged, not ready) mean
# "measurements are invalid" — only those rows lose both gases.
_DIAG_INVALID_MASK = ~0b11111

# How many lines/rows to scan for the header before giving up. Real preambles are
# a handful of lines; this bound keeps us from reading a whole huge non-LI file.
_MAX_HEADER_SCAN = 200

# Workbook formats we can read (openpyxl). Legacy .xls needs xlrd, which isn't a
# dependency, so it is not accepted.
_EXCEL_SUFFIXES = frozenset({".xlsx", ".xlsm"})
# Magic bytes: .xlsx/.xlsm are ZIP archives ("PK\x03\x04").
_ZIP_MAGIC = b"PK\x03\x04"


def _header_cells(values: str | Iterable[object]) -> set[str]:
    """Upper-cased, stripped set of cell names from a header line or row.

    Accepts a raw tab-delimited line (``str``) or an iterable of cell values
    (an Excel row), so the same required-column check serves both formats.
    """
    cells: Iterable[object] = (
        values.rstrip("\n").split("\t") if isinstance(values, str) else values
    )
    return {str(cell).strip().upper() for cell in cells}


def _is_excel(path: str | Path) -> bool:
    """True if the file is an Excel workbook (by suffix or ZIP magic bytes)."""
    if Path(path).suffix.lower() in _EXCEL_SUFFIXES:
        return True
    try:
        with open(path, "rb") as f:
            return f.read(4) == _ZIP_MAGIC
    except OSError:
        return False


def _find_header_index_text(path: str | Path, encoding: str) -> int | None:
    """0-based line index of the header row in a text export, or None."""
    try:
        with open(path, encoding=encoding) as f:
            for index in range(_MAX_HEADER_SCAN):
                line = f.readline()
                if line == "":
                    break  # EOF
                if REQUIRED_COLUMNS <= _header_cells(line):
                    return index
    except OSError:
        return None
    return None


def _find_header_index_excel(frame: pd.DataFrame) -> int | None:
    """0-based row index of the header within a header-less Excel frame, or None."""
    for index in range(min(len(frame), _MAX_HEADER_SCAN)):
        if REQUIRED_COLUMNS <= _header_cells(frame.iloc[index].tolist()):
            return index
    return None


def _read_excel_raw(path: str | Path) -> pd.DataFrame | None:
    """Read a LI-7810 Excel export into a frame with proper column names, or None.

    The workbook mirrors the text layout: a preamble, then a header row, then a
    ``DATAU`` units row and the data. We read it header-less (all cells as
    strings so a stray Excel date-cast can't hide a header), find the header row
    by its column names, and re-key the data below it.
    """
    # Stacked clauses on purpose: this ruff-format version rewrites a tuple
    # `except (A, B):` into the fragile 2-style `except A, B:` (a syntax error),
    # so we list each cause separately instead.
    try:
        frame = pd.read_excel(path, header=None, dtype=str, engine="openpyxl")
    except ValueError:
        return None  # unreadable / not a real workbook
    except OSError:
        return None
    except KeyError:
        return None
    header_index = _find_header_index_excel(frame)
    if header_index is None:
        return None
    header = [str(c).strip() for c in frame.iloc[header_index].tolist()]
    raw = frame.iloc[header_index + 1 :].copy()
    raw.columns = header
    return raw.reset_index(drop=True)


def _read_text_raw(path: str | Path) -> pd.DataFrame | None:
    """Read a LI-7810 text export into a frame with proper column names, or None."""
    encoding = detect_encoding(path)
    if encoding is None:
        return None
    header_index = _find_header_index_text(path, encoding)
    if header_index is None:
        return None
    raw = pd.read_csv(path, sep="\t", skiprows=header_index, encoding=encoding)
    raw.columns = [str(c).strip() for c in raw.columns]
    return raw


def _read_raw(path: str | Path) -> pd.DataFrame | None:
    """Read any accepted LI-7810 export (text or Excel) into a named-column frame."""
    if _is_excel(path):
        return _read_excel_raw(path)
    return _read_text_raw(path)


def looks_like_li7810(path: str | Path) -> bool:
    """True if a SECONDS/CO2/CH4 header is found (text or Excel export).

    Used by the upload endpoint to reject non-LI-7810 files with a clear message.
    """
    return _read_raw(path) is not None


def parse_li7810(
    path: str | Path, *, max_co2_ppm: float = MAX_VALID_CO2_PPM
) -> pd.DataFrame:
    """Parse a LI-7810 log into columns ``timestamp``, ``co2_ppm``, ``ch4_ppb``.

    Accepts the tab-delimited text export (any common encoding) or the same
    layout saved as ``.xlsx``/``.xlsm``. Timestamps are unix seconds (float).
    Concentrations keep ``nan`` as-is. Rows without a usable timestamp (a LI-COR
    units row after the header, blank lines) are dropped; column matching is
    case-insensitive. ``max_co2_ppm`` is the upper CO₂ plausibility bound (the
    configurable ``settings.max_valid_co2_ppm``); readings at or above it are
    dropped as sensor artefacts.
    """
    raw = _read_raw(path)
    if raw is None:
        raise ValueError(
            "No LI-7810 header found — expected columns SECONDS, CO2, CH4."
        )

    # Case-insensitive lookup so SECONDS/Seconds/seconds all resolve.
    by_upper = {c.upper(): c for c in raw.columns}
    co2, ch4 = by_upper["CO2"], by_upper["CH4"]

    df = pd.DataFrame(
        {
            "timestamp": _timeline(raw, by_upper),
            "co2_ppm": to_float_series(raw[co2]),
            "ch4_ppb": to_float_series(raw[ch4]),
        }
    )
    # Drop both gases only on rows the instrument marks INVALID (a "red" DIAG
    # bit, ≥ 32). "Yellow" codes (1..16) mean noisy-but-valid — keep those and
    # let the per-gas range checks below and the fit step's despike handle the
    # noise. An unparsable DIAG cell keeps the reading.
    n_diag_invalid = 0
    if "DIAG" in by_upper:
        diag = pd.to_numeric(raw[by_upper["DIAG"]], errors="coerce")
        invalid = (diag.fillna(0).astype(int) & _DIAG_INVALID_MASK) != 0
        n_diag_invalid = int(invalid.sum())
        df.loc[invalid.to_numpy(), ["co2_ppm", "ch4_ppb"]] = float("nan")
    # Per-gas plausibility: drop values outside each gas's physical range so an
    # artefact in one gas (e.g. mode-hop CH4 in the 100k+ ppb range on a noisy
    # row) can't distort a fit — without discarding the other, good gas. Count the
    # drops (values that WERE present and now fall out of range) so the match step
    # can log them — they used to vanish silently.
    co2_bad = (df["co2_ppm"] >= max_co2_ppm) | (df["co2_ppm"] < MIN_VALID_CO2_PPM)
    ch4_bad = (df["ch4_ppb"] >= MAX_VALID_CH4_PPB) | (df["ch4_ppb"] < MIN_VALID_CH4_PPB)
    n_co2_out_of_range = int(co2_bad.sum())
    n_ch4_out_of_range = int(ch4_bad.sum())
    df.loc[co2_bad, "co2_ppm"] = float("nan")
    df.loc[ch4_bad, "ch4_ppb"] = float("nan")
    # Drop rows with no usable timestamp (units row / blank trailing lines); keep
    # nan concentrations (warm-up and dropouts) for the matching step to handle.
    out = df.dropna(subset=["timestamp"]).reset_index(drop=True)
    # Record how many readings were silently invalidated, per reason, so the
    # match endpoint can surface them in the processing log.
    out.attrs["n_diag_invalid"] = n_diag_invalid
    out.attrs["n_co2_out_of_range"] = n_co2_out_of_range
    out.attrs["n_ch4_out_of_range"] = n_ch4_out_of_range
    return out


def _timeline(raw: pd.DataFrame, by_upper: dict[str, str]) -> pd.Series:
    """Build the unix-seconds timeline for matching.

    Prefer the instrument's **local** ``DATE`` + ``TIME`` columns (read as naive
    UTC wall-clock) so the timeline lines up with the local-time field notes and
    temperature log. The ``SECONDS`` column is *true* unix (a different timezone
    on real exports), so using it directly would misalign matching by the UTC
    offset. Fall back to ``SECONDS`` only when DATE/TIME aren't present.

    The date format is chosen by separator: the European **dotted**
    ``DD.MM.YYYY`` (e.g. ``06.10.2025`` = 6 October) is parsed **day-first** to
    match the temperature loader — reading it month-first would land the whole
    record on the wrong day (June instead of October) and it would never line up
    with the temperature log. **Dashed** ISO ``YYYY-MM-DD`` is year-first and is
    parsed as-is (forcing ``dayfirst`` on ISO makes pandas flip it to June).
    """
    if "DATE" in by_upper and "TIME" in by_upper:
        date_str = raw[by_upper["DATE"]].astype(str).str.strip()
        combined = date_str + " " + raw[by_upper["TIME"]].astype(str).str.strip()
        # Dotted dates are European day-first (DD.MM.YYYY); dashed dates are ISO
        # (YYYY-MM-DD, year-first). One instrument uses one format per file.
        dayfirst = bool(date_str.str.contains(".", regex=False).any())
        when = pd.to_datetime(combined, utc=True, errors="coerce", dayfirst=dayfirst)
        # Only trust DATE/TIME if at least one row actually parsed. Excel can
        # re-cast those cells to its own date/time serials, which stringify to a
        # form to_datetime can't read; when every row fails, fall back to the
        # SECONDS column rather than silently dropping the whole file.
        if when.notna().any():
            epoch = pd.Timestamp("1970-01-01", tz="UTC")
            return (when - epoch) / pd.Timedelta(seconds=1)
    return pd.to_numeric(raw[by_upper["SECONDS"]], errors="coerce").astype(float)
