"""
Fair Value Gap Detection
========================
Identifies price imbalances (FVGs) and pre-computes per-bar entry arrays
for fast O(1) lookup during the simulation hot loop.

Definitions
-----------
Bullish FVG at bar i:
    gap = low[i] - high[i-2]  >  max(min_fvg_atr * ATR[i], min_fvg_dollars)
    Zone: bottom = high[i-2],  top = low[i]

Bearish FVG at bar i:
    gap = low[i-2] - high[i]  >  max(min_fvg_atr * ATR[i], min_fvg_dollars)
    Zone: bottom = high[i],   top = low[i-2]

FVG state machine (per gap)
---------------------------
OPEN      — not yet retested
MITIGATED — price touched the 50 % midpoint from outside
             → this fires the entry-level array at that bar
FILLED    — close trades fully through the gap (invalidated)
EXPIRED   — survived max_fvg_bars without mitigation (discarded)

Entry arrays returned
---------------------
``latest_bull_entry[i]``   — 50 % mid of the most-recently-formed bullish FVG
                             that is still OPEN at bar i, else NaN.
``latest_bull_sl_ref[i]``  — bottom of that FVG (SL reference for longs).
``latest_bear_entry[i]``   — same for bearish FVGs (for shorts).
``latest_bear_sl_ref[i]``  — top of that FVG (SL reference for shorts).

Look-ahead note
---------------
To determine whether a FVG is still OPEN at bar k (the CHoCH bar), we pre-
compute for each FVG the first bar where it is mitigated.  Mitigation is
determined by scanning forward from the formation bar — which uses future
price data relative to the FVG formation, but is 100 % causal from the
perspective of bar k (a real trader at bar k can see whether the FVG was
retested in bars j+1..k).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np


OPEN      = 0
MITIGATED = 1
FILLED    = 2
EXPIRED   = 3


# ── FVG record ────────────────────────────────────────────────────────────────

@dataclass
class FVG:
    kind:            int              # +1 bullish / -1 bearish
    form_bar:        int              # bar index where the FVG was detected
    top:             float
    bottom:          float
    mid:             float            # 50 % entry level
    state:           int = OPEN
    mitigation_bar:  Optional[int] = None


# ── Return type ───────────────────────────────────────────────────────────────

@dataclass
class FVGArrays:
    """Per-M1-bar entry arrays consumed by the simulation loop."""
    # Entry price for a valid, open bullish FVG at bar i (NaN if none)
    latest_bull_entry:  np.ndarray   # float64 (N,)
    # SL reference (FVG bottom) for the above
    latest_bull_sl_ref: np.ndarray   # float64 (N,)
    # Entry price for a valid, open bearish FVG at bar i (NaN if none)
    latest_bear_entry:  np.ndarray   # float64 (N,)
    # SL reference (FVG top) for the above
    latest_bear_sl_ref: np.ndarray   # float64 (N,)
    # Diagnostics: all detected FVG objects
    bull_fvgs: List[FVG] = field(default_factory=list)
    bear_fvgs: List[FVG] = field(default_factory=list)


# ── Main function ─────────────────────────────────────────────────────────────

def compute_fvgs(
    high:            np.ndarray,
    low:             np.ndarray,
    close:           np.ndarray,
    atr:             np.ndarray,
    min_fvg_atr:     float,
    min_fvg_dollars: float,
    max_fvg_bars:    int,
) -> FVGArrays:
    """
    Detect all valid FVGs and build per-bar entry arrays.

    An FVG at bar i is included in ``latest_bull_entry[k]`` for all bars k in
    the half-open interval  [i+1, mitigation_bar)  — i.e. bars where the FVG
    is formed but NOT YET mitigated.  Later FVGs overwrite earlier ones so
    ``latest_bull_entry[k]`` always holds the most recently formed open FVG.

    Parameters
    ----------
    high, low, close  : M1 price arrays
    atr               : Wilder ATR array
    min_fvg_atr       : gap must be ≥ this multiple of ATR
    min_fvg_dollars   : gap must be ≥ this USD amount (hard floor)
    max_fvg_bars      : bars after formation before the FVG is considered stale
    """
    N = len(close)

    latest_bull_entry  = np.full(N, np.nan, dtype=np.float64)
    latest_bull_sl_ref = np.full(N, np.nan, dtype=np.float64)
    latest_bear_entry  = np.full(N, np.nan, dtype=np.float64)
    latest_bear_sl_ref = np.full(N, np.nan, dtype=np.float64)

    bull_fvgs: List[FVG] = []
    bear_fvgs: List[FVG] = []

    for i in range(2, N):
        if np.isnan(atr[i]):
            continue

        min_gap = max(min_fvg_atr * atr[i], min_fvg_dollars)

        # ── Detect bullish FVG ────────────────────────────────────────────
        gap_bull = low[i] - high[i - 2]
        if gap_bull > min_gap:
            fvg = FVG(
                kind    = 1,
                form_bar= i,
                top     = low[i],
                bottom  = high[i - 2],
                mid     = high[i - 2] + gap_bull * 0.5,
            )
            # Find first mitigation bar (vectorized scan)
            scan_end  = min(i + max_fvg_bars, N)
            scan_lows = low[i + 1 : scan_end]
            # Mitigated when price retraces down to mid (low ≤ mid)
            hits = np.where(scan_lows <= fvg.mid)[0]
            if hits.size > 0:
                fvg.state          = MITIGATED
                fvg.mitigation_bar = i + 1 + int(hits[0])
            # FVG is valid (open) from bar i+1 to just before mitigation / expiry
            valid_end = fvg.mitigation_bar if fvg.mitigation_bar else scan_end
            valid_end = min(valid_end, N)
            if valid_end > i + 1:
                latest_bull_entry [i + 1 : valid_end] = fvg.mid
                latest_bull_sl_ref[i + 1 : valid_end] = fvg.bottom
            bull_fvgs.append(fvg)

        # ── Detect bearish FVG ────────────────────────────────────────────
        gap_bear = low[i - 2] - high[i]
        if gap_bear > min_gap:
            fvg = FVG(
                kind    = -1,
                form_bar= i,
                top     = low[i - 2],
                bottom  = high[i],
                mid     = high[i] + gap_bear * 0.5,
            )
            scan_end   = min(i + max_fvg_bars, N)
            scan_highs = high[i + 1 : scan_end]
            # Mitigated when price rallies back up to mid (high ≥ mid)
            hits = np.where(scan_highs >= fvg.mid)[0]
            if hits.size > 0:
                fvg.state          = MITIGATED
                fvg.mitigation_bar = i + 1 + int(hits[0])
            valid_end = fvg.mitigation_bar if fvg.mitigation_bar else scan_end
            valid_end = min(valid_end, N)
            if valid_end > i + 1:
                latest_bear_entry [i + 1 : valid_end] = fvg.mid
                latest_bear_sl_ref[i + 1 : valid_end] = fvg.top
            bear_fvgs.append(fvg)

    return FVGArrays(
        latest_bull_entry  = latest_bull_entry,
        latest_bull_sl_ref = latest_bull_sl_ref,
        latest_bear_entry  = latest_bear_entry,
        latest_bear_sl_ref = latest_bear_sl_ref,
        bull_fvgs          = bull_fvgs,
        bear_fvgs          = bear_fvgs,
    )
