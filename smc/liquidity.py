"""
Liquidity Sweep Detection
=========================
Identifies clusters of equal highs / equal lows (EQH / EQL) and detects
when price sweeps through them and reverses — a high-conviction entry signal.

What we're measuring
---------------------
Retail traders cluster stops at obvious levels: prior swing highs and lows.
Institutional flow is frequently driven by sweeping those clusters, absorbing
the stop-triggered orders, then reversing direction.

Equal High cluster (EQH)
------------------------
Two or more confirmed swing highs within ``eq_tolerance × ATR`` of each other.
The cluster level = the highest of the group.

Equal Low cluster (EQL)
------------------------
Two or more confirmed swing lows within ``eq_tolerance × ATR`` of each other.
The cluster level = the lowest of the group.

Sweep definition
----------------
A bullish sweep of EQL occurs when:
    low[i]  < cluster_level
    close[i] > cluster_level    — closes BACK above (pin bar / wick through)
    The sweep is valid for ``sweep_expiry_bars`` bars after the wick bar.

A bearish sweep of EQH occurs when:
    high[i] > cluster_level
    close[i] < cluster_level

Per-bar output arrays
---------------------
``bull_sweep_active[i]``  — True if bar i is within a valid bullish sweep window
``bull_sweep_level[i]``   — price level of the swept EQL cluster
``bear_sweep_active[i]``  — True if bar i is within a valid bearish sweep window
``bear_sweep_level[i]``   — price level of the swept EQH cluster
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

import numpy as np

from smc.structure import StructureArrays


@dataclass
class LiqArrays:
    bull_sweep_active: np.ndarray   # bool (N,)
    bull_sweep_level:  np.ndarray   # float64 (N,)  NaN where inactive
    bear_sweep_active: np.ndarray   # bool (N,)
    bear_sweep_level:  np.ndarray   # float64 (N,)


def compute_liquidity(
    high:              np.ndarray,
    low:               np.ndarray,
    close:             np.ndarray,
    atr:               np.ndarray,
    struct:            StructureArrays,
    eq_tolerance:      float,
    sweep_expiry_bars: int,
    min_cluster_size:  int,
) -> LiqArrays:
    """
    Detect EQH / EQL clusters and produce per-bar sweep-active arrays.

    Parameters
    ----------
    high, low, close   : price arrays
    atr                : Wilder ATR
    struct             : StructureArrays (for confirmed swing locations)
    eq_tolerance       : max distance between swing highs/lows to form a cluster (× ATR)
    sweep_expiry_bars  : bars after the sweep wick that the signal remains valid
    min_cluster_size   : minimum swing high/low members to form a valid cluster
    """
    N = len(close)

    bull_active = np.zeros(N, dtype=bool)
    bull_level  = np.full(N, np.nan)
    bear_active = np.zeros(N, dtype=bool)
    bear_level  = np.full(N, np.nan)

    # Collect all confirmed swing locations
    sh_bars = np.where(struct.is_swing_high)[0]
    sl_bars = np.where(struct.is_swing_low)[0]

    # ── Build EQH clusters (within a rolling max_lookback window) ─────────
    eqh_clusters: List[Tuple[int, float]] = []    # (bar_index, cluster_level)
    if sh_bars.size >= min_cluster_size:
        sh_prices = high[sh_bars]
        for i, bi in enumerate(sh_bars):
            if np.isnan(atr[bi]):
                continue
            tol = eq_tolerance * atr[bi]
            # Find other swing highs within tolerance of this one
            diffs = np.abs(sh_prices - sh_prices[i])
            members = np.where(diffs <= tol)[0]
            if len(members) >= min_cluster_size:
                cluster_level = float(sh_prices[members].max())
                eqh_clusters.append((int(bi), cluster_level))

    # ── Build EQL clusters ────────────────────────────────────────────────
    eql_clusters: List[Tuple[int, float]] = []
    if sl_bars.size >= min_cluster_size:
        sl_prices = low[sl_bars]
        for i, bi in enumerate(sl_bars):
            if np.isnan(atr[bi]):
                continue
            tol = eq_tolerance * atr[bi]
            diffs = np.abs(sl_prices - sl_prices[i])
            members = np.where(diffs <= tol)[0]
            if len(members) >= min_cluster_size:
                cluster_level = float(sl_prices[members].min())
                eql_clusters.append((int(bi), cluster_level))

    # ── Detect sweeps ─────────────────────────────────────────────────────

    # Bullish sweep of EQL: price wicks below, closes above
    for cluster_bar, level in eql_clusters:
        # Search for sweep candle after the cluster forms
        for i in range(cluster_bar + 1, min(cluster_bar + 200, N)):
            if low[i] < level and close[i] > level:
                # Sweep confirmed at bar i
                end = min(i + sweep_expiry_bars, N)
                bull_active[i + 1 : end] = True
                bull_level [i + 1 : end] = level
                break

    # Bearish sweep of EQH: price wicks above, closes below
    for cluster_bar, level in eqh_clusters:
        for i in range(cluster_bar + 1, min(cluster_bar + 200, N)):
            if high[i] > level and close[i] < level:
                end = min(i + sweep_expiry_bars, N)
                bear_active[i + 1 : end] = True
                bear_level [i + 1 : end] = level
                break

    return LiqArrays(
        bull_sweep_active = bull_active,
        bull_sweep_level  = bull_level,
        bear_sweep_active = bear_active,
        bear_sweep_level  = bear_level,
    )
