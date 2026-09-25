"""Statistics for strategy return series."""
import numpy as np


def newey_west_t(x, lags=10):
    """t-statistic of the mean of x, with Newey-West (Bartlett) standard errors."""
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 2:
        return np.nan
    d = x - x.mean()
    var = d @ d / n
    for lag in range(1, min(lags, n - 1) + 1):
        var += 2 * (1 - lag / (lags + 1)) * (d[lag:] @ d[:-lag]) / n
    return x.mean() / np.sqrt(var / n) if var > 0 else np.nan


def max_drawdown(returns):
    """Largest peak-to-trough fall of the cumulative sum of returns."""
    equity = np.cumsum(np.asarray(returns, float))
    return float(np.max(np.maximum.accumulate(np.r_[0, equity])[1:] - equity, initial=0))
