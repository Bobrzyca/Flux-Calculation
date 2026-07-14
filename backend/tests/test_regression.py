"""Regression fit: exact on a clean line, sane on noisy data."""

import numpy as np
import pytest

from app.flux.regression import fit_slope


def test_perfect_line_is_exact() -> None:
    times = list(range(100))
    values = [3.0 + 0.5 * t for t in times]
    fit = fit_slope(times, values)
    assert fit.slope == pytest.approx(0.5)
    assert fit.intercept == pytest.approx(3.0)
    assert fit.r2 == pytest.approx(1.0)
    assert fit.n_points == 100


def test_noisy_data_has_sane_r2() -> None:
    rng = np.random.default_rng(0)
    times = np.arange(300, dtype=float)
    values = 400.0 + 0.03 * times + rng.normal(0, 0.05, size=times.size)
    fit = fit_slope(times, values)
    assert 0.9 < fit.r2 <= 1.0
    assert fit.slope == pytest.approx(0.03, abs=1e-3)


def test_too_few_points_raises() -> None:
    with pytest.raises(ValueError):
        fit_slope([1.0], [2.0])
