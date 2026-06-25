"""
Advanced Exit Management
========================
Three exit modes, selectable per strategy parameter set:

Mode 1 — "fixed"  (Phase 1 baseline)
--------------------------------------
SL at fixed level, TP at entry ± rr_ratio × SL_distance.
No adjustment during the trade.

Mode 2 — "trail"  (trailing stop)
-----------------------------------
Phase 1:  SL at fixed level, TP at entry ± rr_ratio × SL_dist.
Activation: once floating PnL ≥ trail_activate_rr × SL_dist,
            the trailing phase begins.
Trail:      SL moves to the bar's most extreme close that is favourable,
            minus/plus trail_step_atr × ATR[i].
            The trail only moves in the favourable direction (ratchet).
TP:         removed once trailing starts (trade rides until SL is hit).

Mode 3 — "partial"  (scale out at 1R then trail the rest)
-----------------------------------------------------------
At partial_rr × SL_dist: close partial_fraction (default 50 %) of the
position and lock in a break-even SL on the remainder.
Remaining lot then trails as in Mode 2.

API
---
This module does NOT implement a simulation loop.  Instead it exposes
``manage_exit()``, a function called on every bar for an open position,
which returns an ``ExitDecision``.

The caller (smc/confluence2.py) is responsible for executing the decision.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

import numpy as np


class ExitMode(str, Enum):
    FIXED   = "fixed"
    TRAIL   = "trail"
    PARTIAL = "partial"


@dataclass
class ExitDecision:
    """Result of one call to manage_exit()."""
    should_close_full:    bool  = False   # close entire remaining position
    should_close_partial: bool  = False   # close partial_fraction at partial_price
    partial_price:        float = 0.0
    partial_fraction:     float = 0.5
    new_sl:               float = 0.0    # updated SL (nan = unchanged)
    exit_price:           float = 0.0    # price for full close
    exit_reason:          str   = ""


@dataclass
class ExitState:
    """Mutable state carried forward bar-to-bar for one open trade."""
    direction:          int
    entry_price:        float
    sl_price:           float
    tp_price:           float
    lots:               float
    sl_distance:        float      # original SL distance (pips)
    mode:               ExitMode

    # Trailing / partial state
    trailing_active:    bool  = False
    partial_done:       bool  = False
    best_excursion:     float = 0.0    # maximum favourable price seen so far
    trail_sl:           float = 0.0    # current trailing SL (0 = not yet active)

    # Params
    trail_activate_rr:  float = 1.0
    trail_step_atr:     float = 0.5
    partial_rr:         float = 1.0
    partial_fraction:   float = 0.5


def manage_exit(
    state:   ExitState,
    bar_high: float,
    bar_low:  float,
    bar_atr:  float,
) -> ExitDecision:
    """
    Evaluate exit conditions for the current bar.

    Parameters
    ----------
    state     : mutable ExitState updated in-place
    bar_high  : current bar's high
    bar_low   : current bar's low
    bar_atr   : current ATR (used for trail step)

    Returns
    -------
    ExitDecision — the caller applies the decision then updates state.

    Precedence rule
    ---------------
    SL hit always wins (same-bar tie-breaking is resolved before calling this).
    Partial > full TP.  Trail SL hit overrides TP-based full close.
    """
    d       = state.direction
    hi, lo  = bar_high, bar_low
    dec     = ExitDecision()

    # ── Fixed mode ────────────────────────────────────────────────────────
    if state.mode == ExitMode.FIXED:
        if d == 1:
            if lo <= state.sl_price:
                dec.should_close_full = True
                dec.exit_price        = state.sl_price
                dec.exit_reason       = "sl"
            elif hi >= state.tp_price:
                dec.should_close_full = True
                dec.exit_price        = state.tp_price
                dec.exit_reason       = "tp"
        else:
            if hi >= state.sl_price:
                dec.should_close_full = True
                dec.exit_price        = state.sl_price
                dec.exit_reason       = "sl"
            elif lo <= state.tp_price:
                dec.should_close_full = True
                dec.exit_price        = state.tp_price
                dec.exit_reason       = "tp"
        return dec

    # ── Shared: update best excursion ─────────────────────────────────────
    current_excursion = (hi - state.entry_price) if d == 1 else (state.entry_price - lo)
    if current_excursion > state.best_excursion:
        state.best_excursion = current_excursion

    # ── SL check (all non-fixed modes) ────────────────────────────────────
    active_sl = state.trail_sl if state.trailing_active else state.sl_price
    sl_hit = (d == 1 and lo <= active_sl) or (d == -1 and hi >= active_sl)
    if sl_hit:
        dec.should_close_full = True
        dec.exit_price        = active_sl
        dec.exit_reason       = "trail_sl" if state.trailing_active else "sl"
        return dec

    # ── Partial mode: first milestone ─────────────────────────────────────
    if state.mode == ExitMode.PARTIAL and not state.partial_done:
        partial_target = state.entry_price + d * state.partial_rr * state.sl_distance
        partial_hit    = (d == 1 and hi >= partial_target) or \
                         (d == -1 and lo <= partial_target)
        if partial_hit:
            state.partial_done = True
            # Lock SL to break-even
            state.sl_price       = state.entry_price
            state.trail_sl       = state.entry_price
            state.trailing_active = True
            dec.should_close_partial = True
            dec.partial_price        = partial_target
            dec.partial_fraction     = state.partial_fraction
            dec.new_sl               = state.entry_price
            return dec

    # ── Trail activation ──────────────────────────────────────────────────
    if not state.trailing_active:
        activate_dist = state.trail_activate_rr * state.sl_distance
        if state.best_excursion >= activate_dist:
            state.trailing_active = True
            # Set initial trail SL from current extreme
            if d == 1:
                state.trail_sl = hi - state.trail_step_atr * bar_atr
            else:
                state.trail_sl = lo + state.trail_step_atr * bar_atr

    # ── Ratchet the trail SL ──────────────────────────────────────────────
    if state.trailing_active:
        if d == 1:
            new_trail = hi - state.trail_step_atr * bar_atr
            if new_trail > state.trail_sl:
                state.trail_sl = new_trail
        else:
            new_trail = lo + state.trail_step_atr * bar_atr
            if new_trail < state.trail_sl:
                state.trail_sl = new_trail
        dec.new_sl = state.trail_sl

    return dec
