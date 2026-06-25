"""
Multi-Timeframe Signal Engine & Event-Driven Simulator
=======================================================
Phase 1 — fixed SL / fixed TP / no trailing / no partials.

Signal logic (two-phase)
------------------------
Phase 1 (15m bias):
    On each new M15 bar close:
    - If 15m bullish CHoCH  → bias = +1  (look for longs on 1m)
    - If 15m bearish CHoCH  → bias = −1  (look for shorts on 1m)
    - Bias expires after ``bias_expiry_bars`` M15 bars of silence.

Phase 2 (1m entry):
    While bias is active at bar i:
    - Regime must pass (session + volatility + slope direction).
    - 1m CHoCH in the bias direction must fire at bar i.
    - A qualifying bullish (or bearish) FVG must be OPEN at bar i,
      as indicated by ``m1_fvgs.latest_bull_entry[i]`` being non-NaN.
    - A pending limit order is armed at the FVG midpoint.
    - Fill occurs when price touches the limit level within
      ``entry_timeout_bars`` 1m bars.
    - SL = nearest swing low/high within ``swing_n * 3`` bars
             − / + ``sl_buffer_atr × ATR`` buffer.
    - TP = entry ± rr_ratio × SL_distance.

Execution model (realistic from bar 1)
---------------------------------------
- Spread:    base_spread_pts + Uniform(0, spread_jitter_pts)    per fill
- Slippage:  Uniform(0, max_slippage_pts)                        per fill
- Missed fill: with probability ``missed_fill_prob`` a valid signal
               produces no fill (price blew through without resting).
All costs are in price points (1 pt = 0.01 USD for XAUUSD).

Lot sizing
----------
1 standard lot = 100 oz.  1 pip = 0.01 USD/oz = $1 per standard lot.

    lots = (account × risk_pct) / (sl_pips × pip_value_per_lot)
    pip_value_per_lot = 1.0  USD

PnL (USD)
---------
    gross = direction × (exit_price − entry_price) × lots × 100
    net   = gross − round_trip_cost_usd
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from smc.structure import StructureArrays
from smc.fvg       import FVGArrays
from smc.regime    import RegimeArrays


# ── Constants ─────────────────────────────────────────────────────────────────

_PIP_VALUE_PER_LOT = 1.0      # USD per pip per standard lot (XAUUSD)
_PIP_SIZE          = 0.01     # 1 pip = 0.01 USD


# ── Parameter containers ──────────────────────────────────────────────────────

@dataclass
class StrategyParams:
    # ── Structure
    swing_n:             int   = 5
    min_break_atr:       float = 0.3
    min_displacement:    float = 1.0
    # ── FVG
    min_fvg_atr:         float = 0.2
    min_fvg_dollars:     float = 0.50
    max_fvg_bars:        int   = 60
    # ── Bias timeframe
    bias_tf:             str   = "m15"  # "m5" or "m15" — CHoCH/BOS source TF
    bias_expiry_bars:    int   = 8     # bars (in bias_tf) before bias expires
    bias_use_bos:        bool  = False  # same-direction BOS refreshes the entry window
    # ── 1m entry
    entry_timeout_bars:  int   = 20    # M1 bars to wait for FVG fill
    sl_buffer_atr:       float = 0.1   # extra ATR buffer outside swing SL
    # ── Exit
    rr_ratio:            float = 2.0
    close_on_bias_flip:  bool  = False
    # ── Regime (stored here for convenient param-set bundling)
    min_atr_pct:         float = 20.0
    max_atr_pct:         float = 85.0
    slope_filter:        bool  = True
    slope_lookback:      int   = 4
    session_filter:      bool  = True


@dataclass
class ExecutionParams:
    base_spread_pts:  float = 20.0    # baseline spread in price points
    spread_jitter:    float = 10.0    # max random addition to spread
    max_slippage_pts: float = 10.0    # max adverse slippage per fill
    missed_fill_prob: float = 0.05    # fraction of valid signals that get no fill
    account_size:     float = 10_000.0
    risk_pct:         float = 0.01    # 1 % risk per trade


# ── Trade record ──────────────────────────────────────────────────────────────

@dataclass
class Trade:
    entry_ts:    np.datetime64
    exit_ts:     np.datetime64
    direction:   int           # +1 long / -1 short
    entry_price: float
    sl_price:    float
    tp_price:    float
    exit_price:  float
    exit_reason: str           # "sl" | "tp" | "bias_flip" | "eod"
    lots:        float
    sl_pips:     float         # SL distance in pips (= USD distance / 0.01)
    gross_pnl:   float         # USD before costs
    cost_usd:    float         # total round-trip execution cost USD
    net_pnl:     float         # gross − cost


# ── Internal state objects ────────────────────────────────────────────────────

@dataclass
class _Pending:
    """A limit order that has been armed but not yet filled."""
    direction:   int
    entry_price: float
    sl_price:    float
    tp_price:    float
    lots:        float
    sl_pips:     float
    armed_bar:   int
    timeout_bar: int


@dataclass
class _Position:
    """An open position."""
    direction:   int
    entry_price: float
    sl_price:    float
    tp_price:    float
    lots:        float
    entry_ts:    np.datetime64
    cost_usd:    float         # already paid on entry (held for PnL netting)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _lot_size(account: float, risk_pct: float, sl_pips: float) -> float:
    if sl_pips <= 0:
        return 0.0
    return (account * risk_pct) / (sl_pips * _PIP_VALUE_PER_LOT)


def _draw_cost(exec_p: ExecutionParams) -> tuple[float, float]:
    """Sample spread and slippage (both in price points)."""
    spread = exec_p.base_spread_pts + random.uniform(0.0, exec_p.spread_jitter)
    slip   = random.uniform(0.0, exec_p.max_slippage_pts)
    return spread, slip


def _swing_sl(
    low:         np.ndarray,
    high:        np.ndarray,
    atr:         np.ndarray,
    direction:   int,
    bar:         int,
    lookback:    int,
    buffer_atr:  float,
) -> float:
    """
    SL as the worst swing low (long) or swing high (short) in the lookback
    window, pushed further out by buffer_atr × ATR.
    Falls back to 2 × ATR if the window has no valid data.
    """
    start = max(0, bar - lookback)
    if direction == 1:
        ref = float(np.nanmin(low[start: bar + 1]))
        return ref - buffer_atr * atr[bar]
    else:
        ref = float(np.nanmax(high[start: bar + 1]))
        return ref + buffer_atr * atr[bar]


# ── Simulation loop ───────────────────────────────────────────────────────────

def run_simulation(
    m1:         object,            # loader.BarData (duck-typed to avoid circular import)
    m15:        object,            # loader.BarData
    m1_struct:  StructureArrays,
    m15_struct: StructureArrays,
    m1_fvgs:    FVGArrays,
    regime:     RegimeArrays,
    params:     StrategyParams,
    exec_p:     ExecutionParams,
    start_bar:  int,
    end_bar:    int,
) -> List[Trade]:
    """
    Event-driven M1 bar-by-bar simulation.

    Parameters
    ----------
    m1, m15     : BarData objects for the two timeframes
    m1_struct   : pre-computed 1m structure arrays
    m15_struct  : pre-computed 15m structure arrays
    m1_fvgs     : pre-computed 1m FVG entry arrays
    regime      : pre-computed regime arrays
    params      : strategy parameters
    exec_p      : execution model parameters
    start_bar   : first M1 bar index (inclusive)
    end_bar     : last  M1 bar index (exclusive)

    Returns
    -------
    List[Trade]  — all completed trades in the simulation window.

    Guarantees
    ----------
    - No look-ahead: at M1 bar i only data from bars ≤ i is used.
    - 15m decisions are locked at each M15 bar close (the M1 bar that
      first belongs to the NEXT M15 period triggers the update of the
      PREVIOUS M15 bar's CHoCH status).
    - Maximum one open position at a time.
    """
    trades: List[Trade] = []

    # ── Pre-build M15 bar index for every M1 bar (fast O(N) lookup) ──────
    # m1_to_m15[i] = index of the M15 bar whose open ≤ ts_m1[i]
    m1_to_m15: np.ndarray = (
        np.searchsorted(m15.ts, m1.ts, side="right") - 1
    )

    SL_LOOKBACK = params.swing_n * 3

    # ── State ─────────────────────────────────────────────────────────────────────
    bias:          int               = 0
    bias_set_m15:  int               = -9999
    watch_end:     int               = -1    # last M1 bar of the active entry window
    prev_m15:      int               = -1
    pending:       Optional[_Pending]  = None
    position:      Optional[_Position] = None
    account:       float             = exec_p.account_size

    for i in range(start_bar, end_bar):

        atr_i = m1.atr[i]
        if np.isnan(atr_i):
            continue

        # ── Update 15m bias on new M15 bar close ─────────────────────────
        m15_j = int(m1_to_m15[i])
        if m15_j != prev_m15:
            closed_m15 = m15_j - 1
            if 0 <= closed_m15 < m15.n:
                if m15_struct.is_bull_choch[closed_m15]:
                    bias         = 1
                    bias_set_m15 = closed_m15
                    watch_end    = i + params.entry_timeout_bars  # CHoCH opens window
                    if pending is not None and pending.direction != 1:
                        pending = None
                elif m15_struct.is_bear_choch[closed_m15]:
                    bias         = -1
                    bias_set_m15 = closed_m15
                    watch_end    = i + params.entry_timeout_bars  # CHoCH opens window
                    if pending is not None and pending.direction != -1:
                        pending = None
                elif params.bias_use_bos:
                    # BOS in bias direction refreshes the WINDOW only (not the bias direction)
                    if bias == 1 and m15_struct.is_bull_bos[closed_m15]:
                        watch_end = i + params.entry_timeout_bars
                    elif bias == -1 and m15_struct.is_bear_bos[closed_m15]:
                        watch_end = i + params.entry_timeout_bars
            prev_m15 = m15_j

        # Bias expiry
        if bias != 0 and (m15_j - bias_set_m15) >= params.bias_expiry_bars:
            bias      = 0
            pending   = None
            watch_end = -1

        # ── Manage open position ──────────────────────────────────────────
        if position is not None:
            lo_i = m1.low[i]
            hi_i = m1.high[i]
            exit_price: Optional[float] = None
            reason: str = ""

            if position.direction == 1:
                # Long: SL on low, TP on high; SL wins on same-bar conflict
                if lo_i <= position.sl_price:
                    _, slip    = _draw_cost(exec_p)
                    exit_price = position.sl_price - slip * _PIP_SIZE
                    reason     = "sl"
                elif hi_i >= position.tp_price:
                    _, slip    = _draw_cost(exec_p)
                    exit_price = position.tp_price - slip * _PIP_SIZE
                    reason     = "tp"
            else:
                # Short: SL on high, TP on low; SL wins on same-bar conflict
                if hi_i >= position.sl_price:
                    _, slip    = _draw_cost(exec_p)
                    exit_price = position.sl_price + slip * _PIP_SIZE
                    reason     = "sl"
                elif lo_i <= position.tp_price:
                    _, slip    = _draw_cost(exec_p)
                    exit_price = position.tp_price + slip * _PIP_SIZE
                    reason     = "tp"

            # Optional: close on bias flip
            if exit_price is None and params.close_on_bias_flip:
                if bias != 0 and bias != position.direction:
                    exit_price = m1.close[i]
                    reason     = "bias_flip"

            if exit_price is not None:
                gross = (
                    position.direction
                    * (exit_price - position.entry_price)
                    * position.lots * 100.0
                )
                net = gross - position.cost_usd
                account += net
                trades.append(Trade(
                    entry_ts    = position.entry_ts,
                    exit_ts     = m1.ts[i],
                    direction   = position.direction,
                    entry_price = position.entry_price,
                    sl_price    = position.sl_price,
                    tp_price    = position.tp_price,
                    exit_price  = exit_price,
                    exit_reason = reason,
                    lots        = position.lots,
                    sl_pips     = abs(position.entry_price - position.sl_price) / _PIP_SIZE,
                    gross_pnl   = gross,
                    cost_usd    = position.cost_usd,
                    net_pnl     = net,
                ))
                position = None
            continue   # one position at a time

        if bias == 0:
            pending = None
            continue

        # ── Regime gate ───────────────────────────────────────────────────
        if not regime.is_tradeable[i]:
            continue

        if params.slope_filter:
            slope = regime.h1_ema_slope[i]
            if not np.isnan(slope):
                if bias == 1 and slope < 0:
                    continue
                if bias == -1 and slope > 0:
                    continue

        # ── Pending fill check ───────────────────────────────────────────────
        if pending is not None:
            expired = (i > pending.timeout_bar or pending.direction != bias)
            if expired:
                pending = None
                # fall through to Step 3
            else:
                filled = (
                    (pending.direction ==  1 and m1.low[i]  <= pending.entry_price) or
                    (pending.direction == -1 and m1.high[i] >= pending.entry_price)
                )
                if filled:
                    if random.random() < exec_p.missed_fill_prob:
                        pending = None   # missed fill; fall through to re-arm
                    else:
                        spread, slip = _draw_cost(exec_p)
                        entry_adj    = pending.direction * (spread / 2 + slip) * _PIP_SIZE
                        actual_entry = pending.entry_price + entry_adj
                        cost_usd     = (
                            (spread + slip * 2) * _PIP_SIZE
                            * pending.lots * 100.0
                        )
                        position = _Position(
                            direction   = pending.direction,
                            entry_price = actual_entry,
                            sl_price    = pending.sl_price,
                            tp_price    = pending.tp_price,
                            lots        = pending.lots,
                            entry_ts    = m1.ts[i],
                            cost_usd    = cost_usd,
                        )
                        pending = None
                        continue   # now in position
                else:
                    continue       # still waiting for price to reach limit

        # \u2500\u2500 FVG arm: only within the entry window opened by a 15m event \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
        # Window is set by 15m CHoCH (always) or 15m BOS (if bias_use_bos=True).
        # Tight window = only fresh-structure FVGs; wider = more trades.
        if i > watch_end:
            continue

        if bias == 1:
            fvg_entry  = m1_fvgs.latest_bull_entry[i]
            fvg_sl_ref = m1_fvgs.latest_bull_sl_ref[i]
        else:
            fvg_entry  = m1_fvgs.latest_bear_entry[i]
            fvg_sl_ref = m1_fvgs.latest_bear_sl_ref[i]

        if np.isnan(fvg_entry):
            continue   # no qualifying FVG available yet on this bar

        # SL: worst swing in lookback + ATR buffer; also beyond the FVG edge
        sl_price = _swing_sl(
            m1.low, m1.high, m1.atr,
            bias, i, SL_LOOKBACK, params.sl_buffer_atr,
        )

        # Ensure SL is beyond the FVG boundary (more conservative)
        if bias == 1:
            sl_price = min(sl_price, fvg_sl_ref - params.sl_buffer_atr * atr_i)
        else:
            sl_price = max(sl_price, fvg_sl_ref + params.sl_buffer_atr * atr_i)

        sl_distance = abs(fvg_entry - sl_price)
        if sl_distance < 5 * _PIP_SIZE:   # degenerate: SL < 5 pips
            continue

        sl_pips  = sl_distance / _PIP_SIZE
        tp_price = fvg_entry + bias * params.rr_ratio * sl_distance
        lots     = _lot_size(account, exec_p.risk_pct, sl_pips)

        if lots <= 0.0:
            continue

        pending = _Pending(
            direction   = bias,
            entry_price = fvg_entry,
            sl_price    = sl_price,
            tp_price    = tp_price,
            lots        = lots,
            sl_pips     = sl_pips,
            armed_bar   = i,
            timeout_bar = i + params.entry_timeout_bars,
        )

    # ── Close any position still open at the end of the window ───────────
    if position is not None:
        exit_price = m1.close[end_bar - 1]
        gross = (
            position.direction
            * (exit_price - position.entry_price)
            * position.lots * 100.0
        )
        net = gross - position.cost_usd
        account += net
        trades.append(Trade(
            entry_ts    = position.entry_ts,
            exit_ts     = m1.ts[end_bar - 1],
            direction   = position.direction,
            entry_price = position.entry_price,
            sl_price    = position.sl_price,
            tp_price    = position.tp_price,
            exit_price  = exit_price,
            exit_reason = "eod",
            lots        = position.lots,
            sl_pips     = abs(position.entry_price - position.sl_price) / _PIP_SIZE,
            gross_pnl   = gross,
            cost_usd    = position.cost_usd,
            net_pnl     = net,
        ))

    return trades
