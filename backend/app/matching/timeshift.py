"""Instrument-clock offset correction (pure).

The LI-7810 clock drifts from real time; the user supplies an offset (seconds,
possibly negative) that is added to every concentration timestamp before matching.
"""

import pandas as pd


def apply_offset(readings: pd.DataFrame, offset_seconds: float) -> pd.DataFrame:
    """Return a copy of ``readings`` with ``offset_seconds`` added to ``timestamp``.

    A zero (or falsy) offset is a no-op copy.
    """
    shifted = readings.copy()
    if offset_seconds:
        shifted["timestamp"] = shifted["timestamp"].astype(float) + float(
            offset_seconds
        )
    return shifted
