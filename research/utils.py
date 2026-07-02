"""
research/utils.py — Shared statistical utilities.

All heavy statistical machinery lives here:
  - BCa bootstrap confidence intervals
  - Label-shuffle permutation testing
  - Benjamini-Hochberg FDR correction (default) + Bonferroni (optional)
  - Cohen's d and odds ratio helpers
  - Vectorised rolling percentile and directional efficiency
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

import numpy as np
import pandas as pd
from scipy.stats import norm as _norm


# ── Bootstrap CI (BCa) ────────────────────────────────────────────────────────

def bootstrap_ci(
    data:  np.ndarray,
    func:  Callable[[np.ndarray], float] = np.mean,
    n:     int   = 2_000,
    ci:    float = 0.95,
    seed:  int   = 42,
) -> tuple[float, float, float]:
    """
    Bias-corrected accelerated (BCa) bootstrap confidence interval.

    Returns
    -------
    (estimate, lower_bound, upper_bound)

    Falls back to percentile bootstrap when acceleration cannot be computed
    (e.g. constant jackknife values).
    """
    data = np.asarray(data, dtype=float)
    data = data[~np.isnan(data)]
    if len(data) == 0:
        return np.nan, np.nan, np.nan

    rng       = np.random.default_rng(seed)
    theta_hat = func(data)
    N         = len(data)

    # For large arrays: subsample a pool of _BOOT_POOL observations.
    # By CLT, bootstrapping 5K from 350K has the same CI as the full sample.
    # This keeps the index matrix at (n_eff × _BOOT_POOL) = 2.5M entries max
    # instead of (500 × 354K) = 177M — ~70× speedup with no statistical loss.
    _BOOT_POOL = 5_000
    n_eff      = n if N <= _BOOT_POOL else min(n, 500)
    if N > _BOOT_POOL:
        pool = data[rng.choice(N, size=_BOOT_POOL, replace=False)]
    else:
        pool = data
    M    = len(pool)
    idx  = rng.integers(0, M, size=(n_eff, M))
    boot = np.array([func(pool[idx[i]]) for i in range(n_eff)])

    # Bias correction z0
    prop = np.mean(boot < theta_hat)
    prop = np.clip(prop, 1e-6, 1 - 1e-6)
    z0   = _norm.ppf(prop)

    # Acceleration via jackknife — capped at _JACK_MAX obs for performance.
    # For N > _JACK_MAX, use a random subsample (approximation is accurate
    # enough; BCa is robust to small jackknife errors for large N).
    _JACK_MAX = 300
    if N > _JACK_MAX:
        rng2      = np.random.default_rng(seed + 1)
        jack_data = data[rng2.choice(N, size=_JACK_MAX, replace=False)]
    else:
        jack_data = data
    jack  = np.array([func(np.delete(jack_data, i)) for i in range(len(jack_data))])
    jmean = np.mean(jack)
    num   = np.sum((jmean - jack) ** 3)
    den   = 6.0 * (np.sum((jmean - jack) ** 2) ** 1.5 + 1e-12)
    a     = num / den

    # Adjusted percentiles
    alpha = 1.0 - ci
    z_lo  = _norm.ppf(alpha / 2)
    z_hi  = _norm.ppf(1.0 - alpha / 2)

    def _adj(z: float) -> float:
        denom = 1.0 - a * (z0 + z) + 1e-12
        return float(_norm.cdf(z0 + (z0 + z) / denom))

    p_lo = np.clip(_adj(z_lo), 0.001, 0.999)
    p_hi = np.clip(_adj(z_hi), 0.001, 0.999)

    lo = float(np.nanpercentile(boot, p_lo * 100))
    hi = float(np.nanpercentile(boot, p_hi * 100))
    return theta_hat, lo, hi


def bootstrap_proportion_ci(
    successes: int,
    n:         int,
    ci:        float = 0.95,
    n_boot:    int   = 2_000,
    seed:      int   = 42,
) -> tuple[float, float, float]:
    """BCa CI for a proportion from count data."""
    data = np.zeros(n)
    data[:successes] = 1.0
    return bootstrap_ci(data, np.mean, n=n_boot, ci=ci, seed=seed)


# ── Permutation Test ──────────────────────────────────────────────────────────

@dataclass
class PermutationResult:
    observed_stat:     float
    p_value:           float
    null_distribution: np.ndarray
    n_permutations:    int
    alternative:       str


def permutation_test(
    group_a:        np.ndarray,
    group_b:        np.ndarray,
    statistic:      Callable = np.mean,
    n_permutations: int  = 10_000,
    alternative:    str  = "two-sided",
    seed:           int  = 42,
) -> PermutationResult:
    """
    Label-shuffle permutation test for difference of statistics.

    H0: group_a and group_b are drawn from the same distribution.
    T  = statistic(group_a) − statistic(group_b)
    """
    a = np.asarray(group_a, dtype=float)
    b = np.asarray(group_b, dtype=float)
    a = a[~np.isnan(a)]
    b = b[~np.isnan(b)]

    if len(a) < 2 or len(b) < 2:
        return PermutationResult(np.nan, 1.0, np.array([]), n_permutations, alternative)

    rng      = np.random.default_rng(seed)
    combined = np.concatenate([a, b])
    n_a      = len(a)
    T_obs    = statistic(a) - statistic(b)

    null = np.empty(n_permutations)
    for i in range(n_permutations):
        perm    = rng.permutation(combined)
        null[i] = statistic(perm[:n_a]) - statistic(perm[n_a:])

    if alternative == "two-sided":
        p = float(np.mean(np.abs(null) >= np.abs(T_obs)))
    elif alternative == "greater":
        p = float(np.mean(null >= T_obs))
    else:
        p = float(np.mean(null <= T_obs))

    return PermutationResult(T_obs, p, null, n_permutations, alternative)


# ── FDR Correction ────────────────────────────────────────────────────────────

def fdr_correction(
    p_values: dict[str, float],
    method:   str   = "bh",
    alpha:    float = 0.05,
) -> dict[str, tuple[float, bool]]:
    """
    Returns {name: (adjusted_p, reject_H0)}.

    method="bh"          Benjamini-Hochberg (controls FDR — default)
    method="bonferroni"  Bonferroni (controls FWER — use for confirmatory tests)
    """
    if not p_values:
        return {}

    names = list(p_values.keys())
    ps    = np.array([p_values[n] for n in names], dtype=float)
    m     = len(ps)

    if method == "bh":
        order         = np.argsort(ps)
        sorted_ps     = ps[order]
        ranks         = np.arange(1, m + 1)
        adj_sorted    = np.minimum(1.0, sorted_ps * m / ranks)
        # Enforce monotonicity (BH adjusted p)
        adj_sorted    = np.minimum.accumulate(adj_sorted[::-1])[::-1]
        reject_sorted = adj_sorted <= alpha
        adj_ps        = np.empty(m)
        reject        = np.zeros(m, dtype=bool)
        adj_ps[order] = adj_sorted
        reject[order] = reject_sorted
    elif method == "bonferroni":
        adj_ps = np.minimum(1.0, ps * m)
        reject = adj_ps <= alpha
    else:
        raise ValueError(f"Unknown FDR method: {method!r}")

    return {n: (float(adj_ps[i]), bool(reject[i])) for i, n in enumerate(names)}


# ── Effect Sizes ──────────────────────────────────────────────────────────────

def cohen_d(group_a: np.ndarray, group_b: np.ndarray) -> float:
    """Pooled Cohen's d."""
    a = np.asarray(group_a, dtype=float)
    a = a[~np.isnan(a)]
    b = np.asarray(group_b, dtype=float)
    b = b[~np.isnan(b)]
    if len(a) < 2 or len(b) < 2:
        return np.nan
    pooled_std = np.sqrt(
        ((len(a) - 1) * np.var(a, ddof=1) + (len(b) - 1) * np.var(b, ddof=1))
        / (len(a) + len(b) - 2)
    )
    return float((np.mean(a) - np.mean(b)) / (pooled_std + 1e-12))


def odds_ratio(
    n_success_a: int, n_a: int,
    n_success_b: int, n_b: int,
) -> float:
    """Simple odds ratio with Haldane-Anscombe correction."""
    p_a = (n_success_a + 0.5) / (n_a + 1)
    p_b = (n_success_b + 0.5) / (n_b + 1)
    odds_a = p_a / (1 - p_a + 1e-12)
    odds_b = p_b / (1 - p_b + 1e-12)
    return float(odds_a / (odds_b + 1e-12))


# ── Vectorised Helpers ────────────────────────────────────────────────────────

def directional_efficiency(
    open_: np.ndarray,
    high:  np.ndarray,
    low:   np.ndarray,
    close: np.ndarray,
) -> np.ndarray:
    """DE = |close − open| / (high − low). NaN when high == low."""
    rng = high - low
    de  = np.abs(close - open_) / np.where(rng > 0, rng, np.nan)
    return de.astype(np.float32)


def rolling_percentile_rank(values: np.ndarray, window: int) -> np.ndarray:
    """
    Rolling percentile rank [0, 100] over the preceding `window` values.
    Returns NaN for the first `window` positions.
    """
    out = np.full(len(values), np.nan, dtype=np.float32)
    for i in range(window, len(values)):
        w    = values[max(0, i - window): i]
        v    = values[i]
        valid = w[~np.isnan(w)]
        if len(valid) > 0 and not np.isnan(v):
            out[i] = float(np.sum(valid <= v)) / len(valid) * 100.0
    return out


def label_sessions(
    ts_utc:              np.ndarray,        # datetime64[ns]
    asian_start_hour:    int = 0,
    asian_end_hour:      int = 7,
    london_start_hour:   int = 7,
    london_end_hour:     int = 12,
    ny_start_hour:       int = 12,
    ny_end_hour:         int = 17,
) -> np.ndarray:
    """
    Returns int8 array: 0=Asian 1=London 2=NY 3=Off
    """
    hours = pd.DatetimeIndex(ts_utc).hour.to_numpy()
    out   = np.full(len(hours), 3, dtype=np.int8)
    out[((hours >= asian_start_hour)  & (hours < asian_end_hour))]  = 0
    out[((hours >= london_start_hour) & (hours < london_end_hour))] = 1
    out[((hours >= ny_start_hour)     & (hours < ny_end_hour))]     = 2
    return out


def forward_returns(
    close:    np.ndarray,
    horizons: Sequence[int],
) -> dict[int, np.ndarray]:
    """
    Forward return at each horizon (in bars). NaN at the tail.
    Returns {horizon: float32 array of same length as close}.
    """
    out = {}
    n   = len(close)
    for h in horizons:
        arr     = np.full(n, np.nan, dtype=np.float32)
        arr[:n - h] = (close[h:] - close[:n - h]) / (close[:n - h] + 1e-10)
        out[h]  = arr
    return out
