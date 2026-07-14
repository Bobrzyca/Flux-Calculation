"""Linear regression of concentration vs. time (pure).

Thin wrapper over ``scipy.stats.linregress`` returning just what the flux math
and the per-spot plot need. ``nan`` rows must already be removed by the caller
(the pipeline reports how many it dropped).
"""

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
from scipy import stats


@dataclass
class FitResult:
    slope: float
    intercept: float
    r2: float
    n_points: int


def fit_slope(times_s: npt.ArrayLike, values: npt.ArrayLike) -> FitResult:
    """Fit ``values`` against ``times_s`` (seconds). Needs ≥ 2 points."""
    x = np.asarray(times_s, dtype=float)
    y = np.asarray(values, dtype=float)
    if x.size < 2:
        raise ValueError("Need at least two points to fit a slope")
    result = stats.linregress(x, y)
    return FitResult(
        slope=float(result.slope),
        intercept=float(result.intercept),
        r2=float(result.rvalue) ** 2,
        n_points=int(x.size),
    )
