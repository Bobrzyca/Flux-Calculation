"""LI-7810 concentration-log parser (pure; no HTTP).

The LI-7810 exports a tab-delimited text file: one metadata header row, then a
column-name header row (``SECONDS``, ``CO2`` in ppm, ``CH4`` in ppb, plus extras),
then 1 Hz data rows. ``nan`` marks the laser warm-up and dropouts; we keep those
as ``nan`` here — dropping (and reporting) them is the matching/fitting step's job.
"""

from pathlib import Path

import pandas as pd

# The columns the downstream pipeline relies on.
REQUIRED_COLUMNS = frozenset({"SECONDS", "CO2", "CH4"})


def looks_like_li7810(path: str | Path) -> bool:
    """True if the file's column-name header carries SECONDS, CO2 and CH4.

    Used by the upload endpoint to reject non-LI-7810 files with a clear message.
    Returns False for binary files (e.g. an xlsx) or a differently-delimited file.
    """
    try:
        with open(path, encoding="utf-8") as f:
            f.readline()  # metadata row (skipped)
            header = f.readline()
    except OSError, UnicodeDecodeError:
        return False
    columns = {cell.strip().upper() for cell in header.rstrip("\n").split("\t")}
    return REQUIRED_COLUMNS <= columns


def parse_li7810(path: str | Path) -> pd.DataFrame:
    """Parse a LI-7810 log into columns ``timestamp``, ``co2_ppm``, ``ch4_ppb``.

    Timestamps are unix seconds (float). Concentrations keep ``nan`` as-is.
    """
    raw = pd.read_csv(path, sep="\t", skiprows=1)
    raw.columns = [str(c).strip() for c in raw.columns]
    return pd.DataFrame(
        {
            "timestamp": pd.to_numeric(raw["SECONDS"], errors="coerce").astype(float),
            "co2_ppm": pd.to_numeric(raw["CO2"], errors="coerce").astype(float),
            "ch4_ppb": pd.to_numeric(raw["CH4"], errors="coerce").astype(float),
        }
    )
