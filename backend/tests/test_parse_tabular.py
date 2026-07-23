"""Shared tabular helpers: European-number coercion and the tolerant reader."""

from pathlib import Path

import pandas as pd

from app.parsing.tabular import read_table, to_float_series


def test_to_float_series_dot_decimal() -> None:
    out = to_float_series(pd.Series(["13.35", "1013.2", "0.0"]))
    assert out.tolist() == [13.35, 1013.2, 0.0]


def test_to_float_series_comma_decimal() -> None:
    # European decimal comma: "13,35" must become 13.35, not NaN.
    out = to_float_series(pd.Series(["13,35", "1013,2"]))
    assert out.tolist() == [13.35, 1013.2]


def test_to_float_series_comma_thousands() -> None:
    # "1,013.25" is a US thousands separator + dot decimal -> 1013.25.
    out = to_float_series(pd.Series(["1,013.25"]))
    assert out.tolist() == [1013.25]


def test_to_float_series_already_numeric_and_blanks() -> None:
    out = to_float_series(pd.Series([13.35, None, 20.0]))
    assert out.iloc[0] == 13.35
    assert pd.isna(out.iloc[1])
    assert out.iloc[2] == 20.0


def test_read_table_rejects_legacy_xls(tmp_path: Path) -> None:
    # A legacy .xls needs xlrd (not a dependency); we reject it with a clear
    # message rather than a cryptic openpyxl "not a zip" error.
    fake = tmp_path / "old.xls"
    fake.write_bytes(b"\xd0\xcf\x11\xe0not really xls")
    try:
        read_table(fake)
    except ValueError as exc:
        assert ".xls" in str(exc)
    else:
        raise AssertionError("expected ValueError for legacy .xls")
