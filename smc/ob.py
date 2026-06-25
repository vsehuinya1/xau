"""
Order Block Detection
=====================
An Order Block (OB) is the last OPPOSING candle before a BOS/CHoCH
displacement move.  The institutional interpretation: that candle represents
the last point where opposing orders were placed before price was swept.

Definition used here
---------------------
Bullish OB:
    - Bearish candle at bar j  (close < open)
    - Followed by a bullish BOS or CHoCH between bars j+1 and j + max_ob_bars
    - Body size  (open[j] - close[j])  ≥  body_atr_min × ATR[j]
    - No close below OB bottom (low[j]) before the BOS — gap must be clean

Bearish OB:
    - Bullish candle at bar j  (close > open)
    - Followed by a bearish BOS or CHoCH
    - Body size  (close[j] - open[j])  ≥  body_atr_min × ATR[j]

OB zone
-------
    Bullish OB:  bottom = low[j],  top = high[j]   (full candle range)
    Bearish OB:  bottom = low[j],  top = high[j]
    Entry level:  top   of bullish OB  (price retraces back into the OB from above)
                  bottom of bearish OB (price retraces back into the OB from below)
    Mid-level:   average of top and bottom (50 % retracement into OB)

Invalidation
------------
A bullish OB is invalidated (removed from the active list) when price closes
BELOW its bottom.  A bearish OB is invalidated when price closes ABOVE its top.

Per-bar output arrays
---------------------
``latest_bull_ob_top[i]``   — top   of the most recent ACTIVE bullish OB at bar i
``latest_bull_ob_bot[i]``   — bottom  …
``latest_bull_ob_mid[i]``   — midpoint  …  (entry level for retest longs)
``latest_bear_ob_top[i]``   — top    of the most recent ACTIVE bearish OB
``latest_bear_ob_bot[i]``   — bottom …
``latest_bear_ob_mid[i]``   — midpoint  …  (entry level for retest shorts)

All arrays are NaN when no active OB of that type exists at bar i.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from smc.structure import StructureArrays


# ── OB record ─────────────────────────────────────────────────────────────────

@dataclass
class OB:
    kind:      int           # +1 bullish / -1 bearish
    form_bar:  int
    top:       float
    bottom:    float
    mid:       float
    active:    bool = True
    invalidated_bar: Optional[int] = None


# ── Return type ───────────────────────────────────────────────────────────────

@dataclass
class OBArrays:
    latest_bull_ob_top: np.ndarray   # float64 (N,)
    latest_bull_ob_bot: np.ndarray   # float64 (N,)
    latest_bull_ob_mid: np.ndarray   # float64 (N,)
    latest_bear_ob_top: np.ndarray   # float64 (N,)
    latest_bear_ob_bot: np.ndarray   # float64 (N,)
    latest_bear_ob_mid: np.ndarray   # float64 (N,)
    bull_obs: List[OB] = field(default_factory=list)
    bear_obs: List[OB] = field(default_factory=list)


# ── Main function ─────────────────────────────────────────────────────────────

def compute_obs(
    open_:           np.ndarray,
    high:            np.ndarray,
    low:             np.ndarray,
    close:           np.ndarray,
    atr:             np.ndarray,
    struct:          StructureArrays,
    body_atr_min:    float,
    ob_proximity_bars: int,
) -> OBArrays:
    """
    Detect institutional Order Blocks and produce per-bar active-OB arrays.

    Parameters
    ----------
    open_, high, low, close : M1 price arrays
    atr                     : Wilder ATR (same length)
    struct                  : pre-computed StructureArrays for this TF
    body_atr_min            : OB candle body must be ≥ this × ATR
    ob_proximity_bars       : max bars between OB candle and the displacement
                              move (user mandate: 1–5; default 3)
    """
    N = len(close)

    bull_ob_top = np.full(N, np.nan)
    bull_ob_bot = np.full(N, np.nan)
    bull_ob_mid = np.full(N, np.nan)
    bear_ob_top = np.full(N, np.nan)
    bear_ob_bot = np.full(N, np.nan)
    bear_ob_mid = np.full(N, np.nan)

    bull_obs: List[OB] = []
    bear_obs: List[OB] = []

    # ── Pre-scan: for each structure event, find the preceding opposing candle ─
    bull_events = np.where(struct.is_bull_choch | struct.is_bull_bos)[0]
    bear_events = np.where(struct.is_bear_choch | struct.is_bear_bos)[0]

    for ev in bull_events:
        if np.isnan(atr[ev]):
            continue
        # Search backward ob_proximity_bars bars for the last BEARISH candle.
        # The OB must DIRECTLY precede the displacement — not be 12 bars away.
        search_start = max(0, ev - ob_proximity_bars)
        ob_bar: Optional[int] = None
        for j in range(ev - 1, search_start - 1, -1):
            if close[j] < open_[j]:           # bearish candle
                body = open_[j] - close[j]
                if not np.isnan(atr[j]) and body >= body_atr_min * atr[j]:
                    ob_bar = j
                    break

        if ob_bar is None:
            continue

        ob = OB(
            kind     = 1,
            form_bar = ob_bar,
            top      = high[ob_bar],
            bottom   = low[ob_bar],
            mid      = (high[ob_bar] + low[ob_bar]) * 0.5,
        )

        # Valid from ev+1 onward; find first bar where close < bottom (invalidation)
        for k in range(ev + 1, min(ev + max_ob_bars * 3, N)):
            if close[k] < ob.bottom:
                ob.invalidated_bar = k
                ob.active          = False
                break

        valid_end = ob.invalidated_bar if ob.invalidated_bar else N
        bull_ob_top[ev + 1 : valid_end] = ob.top
        bull_ob_bot[ev + 1 : valid_end] = ob.bottom
        bull_ob_mid[ev + 1 : valid_end] = ob.mid
        bull_obs.append(ob)

    for ev in bear_events:
        if np.isnan(atr[ev]):
            continue
        search_start = max(0, ev - ob_proximity_bars)
        ob_bar = None
        for j in range(ev - 1, search_start - 1, -1):
            if close[j] > open_[j]:           # bullish candle
                body = close[j] - open_[j]
                if not np.isnan(atr[j]) and body >= body_atr_min * atr[j]:
                    ob_bar = j
                    break

        if ob_bar is None:
            continue

        ob = OB(
            kind     = -1,
            form_bar = ob_bar,
            top      = high[ob_bar],
            bottom   = low[ob_bar],
            mid      = (high[ob_bar] + low[ob_bar]) * 0.5,
        )

        for k in range(ev + 1, min(ev + max_ob_bars * 3, N)):
            if close[k] > ob.top:
                ob.invalidated_bar = k
                ob.active          = False
                break

        valid_end = ob.invalidated_bar if ob.invalidated_bar else N
        bear_ob_top[ev + 1 : valid_end] = ob.top
        bear_ob_bot[ev + 1 : valid_end] = ob.bottom
        bear_ob_mid[ev + 1 : valid_end] = ob.mid
        bear_obs.append(ob)

    return OBArrays(
        latest_bull_ob_top = bull_ob_top,
        latest_bull_ob_bot = bull_ob_bot,
        latest_bull_ob_mid = bull_ob_mid,
        latest_bear_ob_top = bear_ob_top,
        latest_bear_ob_bot = bear_ob_bot,
        latest_bear_ob_mid = bear_ob_mid,
        bull_obs           = bull_obs,
        bear_obs           = bear_obs,
    )
