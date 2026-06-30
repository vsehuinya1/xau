"""
London Breakout Strategy
========================
Research direction 1: Time-of-day + volatility expansion.

Hypothesis
----------
If the Asian session produced a compressed range (< N-th percentile) AND
London opens with ATR expanding relative to the Asian session, a breakout
of the Asian range (first K consecutive M1 closes beyond high or low)
tends to continue with momentum.

The parameter `require_compressed=False` turns off the compression filter,
allowing the grid to test whether the compression matters at all.

Strategy rules (per day)
------------------------
1.  Compute Asian range extremes (00:00–07:00 UTC default).
2.  At London open (07:00 UTC), check entry conditions.
3.  Scan London bars for the first confirmed breakout direction.
4.  Fill on the next M1 bar open with spread + slippage.
5.  SL  = opposite side of Asian range − buffer × ATR.
6.  TP  = entry + RR × |entry − SL|.
7.  Exit on SL, TP, or after max_bars_in_trade minutes (timeout).

One trade per day maximum.  No position re-entry after exit.

This module is fully independent of all SMC modules.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np

from smc.loader import BarData
from smc.confluence import Trade, ExecutionParams  # reuse Trade + cost model
from strategy.sessions import SessionFeatures


# ── Constants (XAUUSD) ───────────────────────────────────────────────────────

_PIP_SIZE          = 0.01    # 1 pip = $0.01
_PIP_VALUE_PER_LOT = 1.0     # $1 per pip per standard lot


# ── Parameter container ───────────────────────────────────────────────────────

@dataclass
class LBParams:
    """All tunable parameters for the London Breakout strategy."""

    # ── Session definition (must match precomputed SessionFeatures)
    asian_start_hour:       int   = 0      # UTC (inclusive)
    asian_end_hour:         int   = 7      # UTC (exclusive)
    range_pct_lookback:     int   = 20     # days for rolling percentile

    # ── Entry conditions
    require_compressed:     bool  = True   # True → only trade compressed days
    range_pct_threshold:    float = 25.0   # compressed if range_pct < this
    require_atr_expansion:  bool  = True   # True → require ATR expansion at London open
    atr_expansion_ratio:    float = 1.2    # london_open_atr / asian_mean_atr > ratio
    breakout_confirm_bars:  int   = 5      # consecutive M1 bars beyond range to confirm

    # ── Exit
    sl_buffer_atr:          float = 0.1    # ATR added beyond range for SL
    rr_ratio:               float = 2.0    # reward : risk
    max_bars_in_trade:      int   = 180    # M1 bars from entry before timeout

    # ── Quality filters
    min_range_atr:          float = 0.2    # skip day if Asian range < this × ATR
    max_scan_bars:          int   = 120    # M1 bars after London open to look for breakout

    # ── Volatility regime gate
    min_atr_pct:            float = 20.0   # M15 ATR percentile lower bound
    max_atr_pct:            float = 85.0   # M15 ATR percentile upper bound


# ── Simulation ────────────────────────────────────────────────────────────────

def run_simulation(
    m1:                 BarData,
    sf:                 SessionFeatures,
    london_m15_atr_pct: np.ndarray,      # per-day M15 ATR pct at London open
    params:             LBParams,
    exec_p:             ExecutionParams,
    start_day:          int,             # inclusive day index in sf.dates
    end_day:            int,             # exclusive
) -> List[Trade]:
    """
    Simulate the London Breakout over [start_day, end_day).

    Loops over days (not M1 bars) for speed.  Each qualifying day may
    produce at most one Trade (first confirmed breakout direction).

    Returns
    -------
    List[Trade]  — one entry per filled trade.
    """
    trades: List[Trade] = []
    rng = np.random.default_rng(42)   # deterministic cost simulation

    N = len(m1.ts)

    for di in range(start_day, end_day):
        bstart = int(sf.london_bar_start[di])
        bend   = int(sf.london_bar_end[di])
        if bstart < 0 or bend < 0 or bstart >= N:
            continue   # no London data this day

        asian_h = sf.asian_high[di]
        asian_l = sf.asian_low[di]
        asian_r = sf.asian_range[di]

        if asian_r <= 0 or np.isnan(asian_r):
            continue

        a_atr = sf.asian_mean_atr[di]
        l_atr = sf.london_open_atr[di]

        # ── Volatility regime gate (M15 ATR percentile at London open)
        atr_pct_d = london_m15_atr_pct[di]
        if not np.isnan(atr_pct_d):
            if not (params.min_atr_pct <= atr_pct_d <= params.max_atr_pct):
                continue

        # ── Minimum range quality filter
        ref_atr = a_atr if (not np.isnan(a_atr) and a_atr > 0) else l_atr
        if ref_atr > 0 and asian_r < params.min_range_atr * ref_atr:
            continue

        # ── Asian range compression filter
        if params.require_compressed:
            rpct = sf.asian_range_pct[di]
            if np.isnan(rpct) or rpct >= params.range_pct_threshold:
                continue

        # ── ATR expansion filter
        if params.require_atr_expansion:
            if (np.isnan(a_atr) or a_atr <= 0 or l_atr <= 0
                    or l_atr / a_atr < params.atr_expansion_ratio):
                continue

        # ── Scan London bars for confirmed breakout
        scan_end = min(bend, bstart + params.max_scan_bars)
        direction  = 0
        entry_bar  = -1
        above_cnt  = 0
        below_cnt  = 0

        for i in range(bstart, scan_end):
            c = m1.close[i]
            if c > asian_h:
                above_cnt += 1
                below_cnt  = 0
                if above_cnt >= params.breakout_confirm_bars:
                    direction = 1
                    entry_bar = i
                    break
            elif c < asian_l:
                below_cnt += 1
                above_cnt  = 0
                if below_cnt >= params.breakout_confirm_bars:
                    direction = -1
                    entry_bar = i
                    break
            else:
                above_cnt = below_cnt = 0

        if direction == 0 or entry_bar < 0:
            continue   # no confirmed breakout this day

        # ── Fill on next bar open + realistic costs
        fill_bar = entry_bar + 1
        if fill_bar >= N:
            continue

        spread_pts = exec_p.base_spread_pts + rng.uniform(0.0, exec_p.spread_jitter)
        slip_pts   = rng.uniform(0.0, exec_p.max_slippage_pts)
        cost_pts   = spread_pts + slip_pts

        fill_price = m1.open[fill_bar]
        if direction == 1:
            entry_price = fill_price + cost_pts * _PIP_SIZE
            sl_price    = asian_l - params.sl_buffer_atr * l_atr
        else:
            entry_price = fill_price - cost_pts * _PIP_SIZE
            sl_price    = asian_h + params.sl_buffer_atr * l_atr

        sl_dist = abs(entry_price - sl_price)
        if sl_dist < _PIP_SIZE:
            continue   # degenerate SL

        tp_price = entry_price + direction * params.rr_ratio * sl_dist

        # ── Position sizing (1% risk)
        risk_usd = exec_p.account_size * exec_p.risk_pct / 100.0
        sl_pips  = sl_dist / _PIP_SIZE
        lot_size = risk_usd / (sl_pips * _PIP_VALUE_PER_LOT)

        # ── Bar-by-bar trade management
        timeout_bar = fill_bar + params.max_bars_in_trade
        exit_price  = m1.close[min(timeout_bar - 1, N - 1)]
        exit_reason = "timeout"
        exit_bar    = min(timeout_bar - 1, N - 1)

        for j in range(fill_bar, min(timeout_bar, N)):
            if direction == 1:
                if m1.low[j] <= sl_price:
                    exit_price  = sl_price
                    exit_reason = "sl"
                    exit_bar    = j
                    break
                if m1.high[j] >= tp_price:
                    exit_price  = tp_price
                    exit_reason = "tp"
                    exit_bar    = j
                    break
            else:
                if m1.high[j] >= sl_price:
                    exit_price  = sl_price
                    exit_reason = "sl"
                    exit_bar    = j
                    break
                if m1.low[j] <= tp_price:
                    exit_price  = tp_price
                    exit_reason = "tp"
                    exit_bar    = j
                    break

        # ── P&L
        move_pips = direction * (exit_price - entry_price) / _PIP_SIZE
        raw_pnl   = move_pips * _PIP_VALUE_PER_LOT * lot_size
        cost_usd  = cost_pts  * _PIP_VALUE_PER_LOT * lot_size
        net_pnl   = raw_pnl - cost_usd

        trades.append(Trade(
            entry_ts    = m1.ts[fill_bar],
            exit_ts     = m1.ts[exit_bar],
            direction   = direction,
            entry_price = entry_price,
            sl_price    = sl_price,
            tp_price    = tp_price,
            exit_price  = exit_price,
            exit_reason = exit_reason,
            lots        = lot_size,
            sl_pips     = sl_pips,
            gross_pnl   = move_pips * _PIP_VALUE_PER_LOT * lot_size,
            cost_usd    = cost_pts  * _PIP_VALUE_PER_LOT * lot_size,
            net_pnl     = net_pnl,
        ))

    return trades
