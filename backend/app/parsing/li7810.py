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
"""

from pathlib import Path

import pandas as pd

# The columns the downstream pipeline relies on.
REQUIRED_COLUMNS = frozenset({"SECONDS", "CO2", "CH4"})

# CO₂ readings outside this (ppm) range are treated as invalid sensor spikes and
# dropped (set to nan) before fitting. The upper bound mirrors the R
# method-of-record's ``subset(fx, CO2 < 1500)`` step; ambient is ~400–500 ppm and a
# chamber rise stays well under 1500, so values ≥ 1500 are spurious. The lower bound
# catches gross negative faults / error sentinels (real CO₂ is always positive).
MAX_VALID_CO2_PPM = 1500.0
MIN_VALID_CO2_PPM = -1500.0

# How many lines to scan for the header before giving up. Real preambles are a
# handful of lines; this bound keeps us from reading a whole huge non-LI file.
_MAX_HEADER_SCAN = 200


def _header_cells(line: str) -> set[str]:
    """Tab-split a line into upper-cased, stripped cell names."""
    return {cell.strip().upper() for cell in line.rstrip("\n").split("\t")}


def _find_header_index(path: str | Path) -> int | None:
    """0-based index of the header row (carrying SECONDS/CO2/CH4), or None.

    Scans past the metadata preamble; returns None for binary files (e.g. an
    xlsx), a differently-delimited file, or one missing the required columns.
    """
    try:
        with open(path, encoding="utf-8") as f:
            for index in range(_MAX_HEADER_SCAN):
                line = f.readline()
                if line == "":
                    break  # EOF
                if REQUIRED_COLUMNS <= _header_cells(line):
                    return index
    # Separate clauses on purpose: this ruff-format version rewrites a tuple
    # `except (A, B):` into the fragile 2-style `except A, B:`, so we avoid it.
    except OSError:
        return None
    except UnicodeDecodeError:
        return None
    return None


def looks_like_li7810(path: str | Path) -> bool:
    """True if a SECONDS/CO2/CH4 header row is found anywhere in the preamble.

    Used by the upload endpoint to reject non-LI-7810 files with a clear message.
    """
    return _find_header_index(path) is not None


def parse_li7810(path: str | Path) -> pd.DataFrame:
    """Parse a LI-7810 log into columns ``timestamp``, ``co2_ppm``, ``ch4_ppb``.

    Timestamps are unix seconds (float). Concentrations keep ``nan`` as-is. Rows
    without a usable timestamp (a LI-COR units row after the header, blank lines)
    are dropped; column matching is case-insensitive.
    """
    header_index = _find_header_index(path)
    if header_index is None:
        raise ValueError(
            "No LI-7810 header found — expected columns SECONDS, CO2, CH4."
        )

    raw = pd.read_csv(path, sep="\t", skiprows=header_index)
    raw.columns = [str(c).strip() for c in raw.columns]
    # Case-insensitive lookup so SECONDS/Seconds/seconds all resolve.
    by_upper = {c.upper(): c for c in raw.columns}
    co2, ch4 = by_upper["CO2"], by_upper["CH4"]

    df = pd.DataFrame(
        {
            "timestamp": _timeline(raw, by_upper),
            "co2_ppm": pd.to_numeric(raw[co2], errors="coerce").astype(float),
            "ch4_ppb": pd.to_numeric(raw[ch4], errors="coerce").astype(float),
        }
    )
    # Drop spurious CO₂ spikes (sensor errors) outside the valid range so they
    # can't distort a fit: high (≥ 1500 ppm) and gross-negative (< -1500 ppm).
    df.loc[
        (df["co2_ppm"] >= MAX_VALID_CO2_PPM) | (df["co2_ppm"] < MIN_VALID_CO2_PPM),
        "co2_ppm",
    ] = float("nan")
    # Drop rows with no usable timestamp (units row / blank trailing lines); keep
    # nan concentrations (warm-up and dropouts) for the matching step to handle.
    return df.dropna(subset=["timestamp"]).reset_index(drop=True)


def _timeline(raw: pd.DataFrame, by_upper: dict[str, str]) -> pd.Series:
    """Build the unix-seconds timeline for matching.

    Prefer the instrument's **local** ``DATE`` + ``TIME`` columns (read as naive
    UTC wall-clock) so the timeline lines up with the local-time field notes and
    temperature log. The ``SECONDS`` column is *true* unix (a different timezone
    on real exports), so using it directly would misalign matching by the UTC
    offset. Fall back to ``SECONDS`` only when DATE/TIME aren't present.
    """
    if "DATE" in by_upper and "TIME" in by_upper:
        combined = (
            raw[by_upper["DATE"]].astype(str).str.strip()
            + " "
            + raw[by_upper["TIME"]].astype(str).str.strip()
        )
        when = pd.to_datetime(combined, utc=True, errors="coerce")
        epoch = pd.Timestamp("1970-01-01", tz="UTC")
        return (when - epoch) / pd.Timedelta(seconds=1)
    return pd.to_numeric(raw[by_upper["SECONDS"]], errors="coerce").astype(float)
