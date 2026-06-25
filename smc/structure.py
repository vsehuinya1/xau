"""
Market Structure Detection
==========================
Detects swing highs/lows, Break of Structure (BOS) and Change of Character
(CHoCH) with two mandatory ATR-based displacement gates on every break:

    Gate 1 — close distance:  close beyond swing  >  min_break_atr  × ATR[i]
    Gate 2 — candle range:    high[i] - low[i]    >  min_displacement × ATR[i]

Both gates MUST pass for any structure event to be recorded.

Look-ahead policy (causal)
--------------------------
A swing at bar j requires n bars on each side.  It is confirmed at bar j+n.
In the simulation loop, at bar i the latest usable confirmed swing is at
index ≤ i − swing_n.  The sequential loop below respects this exactly:
it only "sees" the swing at bar (i − swing_n) when iterating bar i.

Leg direction encoding
----------------------
+1  =  bullish leg  (price making Higher Highs / Higher Lows)
-1  =  bearish leg  (price making Lower Highs / Lower Lows)
 0  =  uninitialized (not enough data yet)

CHoCH  =  break AGAINST the current leg direction  (first sign of reversal)
BOS    =  break IN the direction of the current leg (continuation)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np

try:
    from scipy.ndimage import maximum_filter1d, minimum_filter1d
    _HAVE_SCIPY = True
except ImportError:
    _HAVE_SCIPY = False


# ── Return type ───────────────────────────────────────────────────────────────

@dataclass
class StructureArrays:
    """Pre-computed structure labels for one timeframe / one parameter combo."""
    is_swing_high:    np.ndarray   # bool (N,)  — raw swing pivot
    is_swing_low:     np.ndarray   # bool (N,)
    is_bull_choch:    np.ndarray   # bool (N,)  — bullish CHoCH at bar i
    is_bear_choch:    np.ndarray   # bool (N,)  — bearish CHoCH at bar i
    is_bull_bos:      np.ndarray   # bool (N,)
    is_bear_bos:      np.ndarray   # bool (N,)
    # Price level of the swing that was broken (for reference / diagnostics)
    broken_level:     np.ndarray   # float64 (N,)  — NaN where no event


# ── Swing detection ───────────────────────────────────────────────────────────

def _swings_scipy(high: np.ndarray, low: np.ndarray,
                  n: int) -> Tuple[np.ndarray, np.ndarray]:
    size     = 2 * n + 1
    roll_max = maximum_filter1d(high, size=size, mode="nearest")
    roll_min = minimum_filter1d(low,  size=size, mode="nearest")
    sh = (high == roll_max)
    sl = (low  == roll_min)
    # Zero out edges where the full n-bar window is not available
    sh[:n] = sh[-n:] = False
    sl[:n] = sl[-n:] = False
    return sh, sl


def _swings_numpy(high: np.ndarray, low: np.ndarray,
                  n: int) -> Tuple[np.ndarray, np.ndarray]:
    N  = len(high)
    sh = np.zeros(N, dtype=bool)
    sl = np.zeros(N, dtype=bool)
    for i in range(n, N - n):
        w_h = high[i - n: i + n + 1]
        w_l = low[i  - n: i + n + 1]
        if high[i] >= w_h.max():
            sh[i] = True
        if low[i]  <= w_l.min():
            sl[i] = True
    return sh, sl


def detect_swings(high: np.ndarray, low: np.ndarray,
                  n: int) -> Tuple[np.ndarray, np.ndarray]:
    """
    Return ``(is_swing_high, is_swing_low)`` boolean arrays.

    Swing at bar j is confirmed at bar j+n (look-ahead-free from j+n onward).
    Uses scipy for speed when available; falls back to pure numpy.
    """
    if _HAVE_SCIPY:
        return _swings_scipy(high, low, n)
    return _swings_numpy(high, low, n)


# ── Structure classification ──────────────────────────────────────────────────

def compute_structure(
    high:             np.ndarray,
    low:              np.ndarray,
    close:            np.ndarray,
    atr:              np.ndarray,
    swing_n:          int,
    min_break_atr:    float,
    min_displacement: float,
) -> StructureArrays:
    """
    Classify each bar as a BOS or CHoCH event (or neither).

    Parameters
    ----------
    high, low, close  : price arrays of the target timeframe
    atr               : Wilder ATR array (same length)
    swing_n           : bars on each side required for a swing pivot
    min_break_atr     : minimum close-beyond-swing in ATR multiples
    min_displacement  : minimum breaking-candle range in ATR multiples

    Returns
    -------
    StructureArrays   : per-bar boolean event labels + broken price level
    """
    N = len(close)

    is_sh, is_sl = detect_swings(high, low, swing_n)

    bull_choch   = np.zeros(N, dtype=bool)
    bear_choch   = np.zeros(N, dtype=bool)
    bull_bos     = np.zeros(N, dtype=bool)
    bear_bos     = np.zeros(N, dtype=bool)
    broken_level = np.full(N, np.nan, dtype=np.float64)

    # ── Pre-compute displacement gate (vectorised) ────────────────────────
    # Only bars where the candle range > min_displacement × ATR can ever
    # produce a structure event.  Building an index of candidates reduces
    # the sequential loop by ~60-70 % on typical M1 data.
    candle_ranges = high - low
    disp_mask = (
        ~np.isnan(atr) &
        (candle_ranges > min_displacement * np.where(np.isnan(atr), np.inf, atr))
    )

    # Leg-tracking state (sequential, cannot be vectorised)
    leg     = 0
    last_sh = np.nan
    last_sl = np.nan

    # We still need to update confirmed swings for EVERY bar (not just
    # candidates), because swing state is global.  Walk all bars but only
    # do the break-check on candidate bars.
    for i in range(swing_n, N):
        # Update confirmed swings
        conf_bar = i - swing_n
        if is_sh[conf_bar]:
            last_sh = high[conf_bar]
        if is_sl[conf_bar]:
            last_sl = low[conf_bar]

        # Fast path: skip if displacement gate not met or no swing refs yet
        if not disp_mask[i] or np.isnan(last_sh) or np.isnan(last_sl):
            continue

        # ── Bullish break of last swing high ─────────────────────────────
        if close[i] > last_sh:
            break_dist = close[i] - last_sh
            if break_dist > min_break_atr * atr[i]:
                broken_level[i] = last_sh
                if leg == -1:
                    bull_choch[i] = True
                else:
                    bull_bos[i]   = True
                leg     = 1
                last_sh = close[i]

        # ── Bearish break of last swing low ──────────────────────────────
        elif close[i] < last_sl:
            break_dist = last_sl - close[i]
            if break_dist > min_break_atr * atr[i]:
                broken_level[i] = last_sl
                if leg == 1:
                    bear_choch[i] = True
                else:
                    bear_bos[i]   = True
                leg     = -1
                last_sl = close[i]

    return StructureArrays(
        is_swing_high = is_sh,
        is_swing_low  = is_sl,
        is_bull_choch = bull_choch,
        is_bear_choch = bear_choch,
        is_bull_bos   = bull_bos,
        is_bear_bos   = bear_bos,
        broken_level  = broken_level,
    )
