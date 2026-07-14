"""Time-shift correction: positive, negative and zero offsets."""

import pandas as pd

from app.matching.timeshift import apply_offset


def _readings() -> pd.DataFrame:
    return pd.DataFrame(
        {"timestamp": [100.0, 101.0, 102.0], "co2_ppm": [1.0, 2.0, 3.0]}
    )


def test_positive_offset() -> None:
    out = apply_offset(_readings(), 5)
    assert list(out["timestamp"]) == [105.0, 106.0, 107.0]


def test_negative_offset() -> None:
    out = apply_offset(_readings(), -10)
    assert list(out["timestamp"]) == [90.0, 91.0, 92.0]


def test_zero_offset_is_unchanged_copy() -> None:
    original = _readings()
    out = apply_offset(original, 0)
    assert list(out["timestamp"]) == [100.0, 101.0, 102.0]
    # A copy — mutating the result must not touch the input.
    out.loc[0, "timestamp"] = 999.0
    assert original.loc[0, "timestamp"] == 100.0
