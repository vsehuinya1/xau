"""
SMC Phase 1 Backtester
======================
Runs a random search over the strategy parameter grid, validates results
through 5 rolling walk-forward windows, applies a 3-step selection procedure
(hard filters → rank by average OOS PF + variance penalty → choose simplest
survivor), and finally runs a post-optimisation kill test under stressed
execution assumptions.

Usage
-----
    python backtests/test5_smc.py [--samples N] [--seed S] [--years 2018 2025]

Outputs (written to results/)
------------------------------
    smc_trades_<run_id>.csv    — every trade from the winning param set
    smc_params_<run_id>.csv    — full param-search results table
    smc_kill_test_<run_id>.csv — kill-test scenario table
    (equity curve plot as PNG if matplotlib is available)

Kill switch
-----------
If the best param set produces fewer than TRADE_COUNT_MIN trades over the
full in-sample period, the script exits with code 1 immediately.

Walk-forward windows (5 × 3-year train / 1-year test)
------------------------------------------------------
WF1: train 2018-2020  |  test 2021
WF2: train 2019-2021  |  test 2022
WF3: train 2020-2022  |  test 2023
WF4: train 2021-2023  |  test 2024
WF5: train 2022-2024  |  test 2025

Parameter selection procedure (3 steps, no discretion)
------------------------------------------------------
Step 1 — Hard filters (any failure → discard):
    IS  trade count  ≥ 500
    OOS trade count  ≥ 100  (summed across all 5 windows)
    Every OOS window PF  ≥ 1.0  (not just the average)
    IS  max drawdown ≤ 25 %

Step 2 — Rank survivors:
    Primary:   mean OOS PF              (descending)
    Secondary: std  OOS PF              (ascending  — penalise variance)
    Tertiary:  total OOS trade count    (descending)

Step 3 — Choose simplest from top-10 survivors:
    Count non-default parameters in each set.
    Fewest non-defaults wins.  Tie-break: highest mean OOS PF.

Kill test (post-selection, full 2018-2025 sample)
-------------------------------------------------
Scenario      spread   slippage   rr_ratio
Base          × 1.0    × 1.0      × 1.0
Stress-A      × 1.5    × 1.0      × 1.0      (spread 50 % wider)
Stress-B      × 1.0    × 1.5      × 1.0      (slippage 50 % worse)
Stress-C      × 1.0    × 1.0      × 0.9      (TP 10 % closer)
Stress-ALL    × 1.5    × 1.5      × 0.9      (all combined)

Kill if:  any single stress scenario PF < 1.0
          OR  Stress-ALL expectancy < 0
"""
from __future__ import annotations

import argparse
import csv
import json
import multiprocessing as _mp
import os
import random
import sys
import time as _time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# ── Project imports ───────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from smc.loader    import load, DataStore, BarData
from smc.structure import compute_structure, StructureArrays
from smc.fvg       import compute_fvgs, FVGArrays
from smc.regime    import compute_regime, RegimeArrays, RegimeParams
from smc.confluence import (
    run_simulation, StrategyParams, ExecutionParams, Trade,
)

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# ── Multiprocessing worker globals ────────────────────────────────────────────
# These must live at module level so Windows 'spawn' can import them cleanly.
_W_DS:     object = None   # DataStore — set by _mp_init, never pickled per-task
_W_EXEC_P: object = None   # ExecutionParams


def _mp_init(ds, exec_p) -> None:
    """Pool initializer: store shared objects in each worker's global namespace."""
    global _W_DS, _W_EXEC_P
    _W_DS     = ds
    _W_EXEC_P = exec_p


def _mp_eval(p_dict: dict) -> object:
    """Evaluate one param set inside a worker process."""
    p = StrategyParams(**p_dict)
    return _evaluate_params(_W_DS, p, _W_EXEC_P)

# ── Walk-forward windows ──────────────────────────────────────────────────────
WF_WINDOWS: List[Tuple[int, int, int]] = [
    (2018, 2020, 2021),
    (2019, 2021, 2022),
    (2020, 2022, 2023),
    (2021, 2023, 2024),
    (2022, 2024, 2025),
]

# ── Kill switch ───────────────────────────────────────────────────────────────
TRADE_COUNT_MIN    = 500
TRADE_COUNT_TARGET = 1000

# ── Selection thresholds ──────────────────────────────────────────────────────
IS_MIN_PF          = 1.5
IS_MIN_TRADES      = 500
OOS_MIN_TRADES     = 100
OOS_MIN_PF_WINDOW  = 1.0    # every individual window must meet this
OOS_MEAN_PF        = 1.3    # mean across windows
IS_MAX_DD          = 0.25

# ── Parameter grid ────────────────────────────────────────────────────────────
PARAM_GRID: Dict[str, list] = {
    "swing_n":            [3, 5, 7],
    "min_break_atr":      [0.2, 0.3, 0.5],
    "min_displacement":   [0.8, 1.0, 1.5],
    "min_fvg_atr":        [0.15, 0.2, 0.3],
    "bias_tf":            ["m5", "m15"],
    "bias_expiry_bars":   [8, 16, 24],
    "bias_use_bos":       [True, False],
    "entry_timeout_bars": [20, 60, 120, 240],
    "sl_buffer_atr":      [0.1, 0.2],
    "rr_ratio":           [1.5, 2.0, 3.0],
    "close_on_bias_flip": [True, False],
    "min_atr_pct":        [10.0, 20.0, 30.0],
    "max_atr_pct":        [75.0, 85.0, 95.0],
    "slope_filter":       [True, False],
    "slope_lookback":     [2, 4, 8],
    "session_filter":     [True, False],
    # ── H4 ADX regime gate (Branch C)
    "adx_filter":         [True, False],
    "adx_threshold":      [20.0, 25.0, 30.0],
}

# Default values for "simplicity" counting in Step 3
DEFAULTS: Dict[str, object] = {
    "swing_n":            5,
    "min_break_atr":      0.3,
    "min_displacement":   1.0,
    "min_fvg_atr":        0.2,
    "bias_tf":            "m15",
    "bias_expiry_bars":   8,
    "bias_use_bos":       False,
    "entry_timeout_bars": 20,
    "sl_buffer_atr":      0.1,
    "rr_ratio":           2.0,
    "close_on_bias_flip": False,
    "min_atr_pct":        20.0,
    "max_atr_pct":        85.0,
    "slope_filter":       True,
    "slope_lookback":     4,
    "session_filter":     True,
    "adx_filter":         False,
    "adx_threshold":      25.0,
}

# Fixed params (not in grid)
FIXED_MIN_FVG_DOLLARS: float = 0.50
FIXED_MAX_FVG_BARS:    int   = 60
FIXED_MAX_ATR_PCT:     float = 85.0
FIXED_SLOPE_LOOKBACK:  int   = 4


# ── Metrics ───────────────────────────────────────────────────────────────────

@dataclass
class SimMetrics:
    n_trades:      int   = 0
    n_wins:        int   = 0
    n_losses:      int   = 0
    win_rate:      float = 0.0
    gross_pnl:     float = 0.0
    net_pnl:       float = 0.0
    profit_factor: float = 0.0
    expectancy:    float = 0.0    # per trade, net USD
    max_drawdown:  float = 0.0    # fraction  (0.05 = 5 %)
    cagr:          float = 0.0
    mar_ratio:     float = 0.0    # CAGR / max_drawdown


def _calc_metrics(
    trades: List[Trade],
    start_account: float,
    n_years: float,
) -> SimMetrics:
    if not trades:
        return SimMetrics()

    pnls   = np.array([t.net_pnl for t in trades])
    n      = len(pnls)
    wins   = pnls[pnls > 0]
    losses = pnls[pnls <= 0]

    gross_win  = float(wins.sum())  if wins.size   > 0 else 0.0
    gross_loss = float(np.abs(losses.sum())) if losses.size > 0 else 0.0

    pf = gross_win / gross_loss if gross_loss > 0 else (float("inf") if gross_win > 0 else 0.0)

    # Max drawdown from equity curve
    equity = np.empty(n + 1)
    equity[0] = start_account
    for k, t in enumerate(trades):
        equity[k + 1] = equity[k] + t.net_pnl
    peak     = np.maximum.accumulate(equity)
    dd_arr   = (peak - equity) / peak
    max_dd   = float(dd_arr.max())

    net_total = float(pnls.sum())
    final_eq  = start_account + net_total
    cagr = (
        (final_eq / start_account) ** (1.0 / n_years) - 1.0
        if n_years > 0 and final_eq > 0 else 0.0
    )
    mar = cagr / max_dd if max_dd > 0 else float("inf")

    return SimMetrics(
        n_trades      = n,
        n_wins        = int(wins.size),
        n_losses      = int(losses.size),
        win_rate      = wins.size / n,
        gross_pnl     = float(np.array([t.gross_pnl for t in trades]).sum()),
        net_pnl       = net_total,
        profit_factor = pf,
        expectancy    = net_total / n,
        max_drawdown  = max_dd,
        cagr          = cagr,
        mar_ratio     = mar,
    )


# ── Pre-computation cache ─────────────────────────────────────────────────────

_struct_cache: Dict[tuple, tuple[StructureArrays, StructureArrays]] = {}
_fvg_cache:   Dict[tuple, FVGArrays]  = {}
_regime_cache: Dict[tuple, RegimeArrays] = {}


def _get_structure(ds: DataStore, p: StrategyParams) -> Tuple[StructureArrays, StructureArrays]:
    """Bias-TF structure + M1 structure, keyed by (swing_n, min_break_atr, min_displacement)."""
    key = (p.bias_tf, p.swing_n, p.min_break_atr, p.min_displacement)
    if key not in _struct_cache:
        bias_data = ds.m5 if p.bias_tf == "m5" else ds.m15
        bias_s = compute_structure(
            bias_data.high, bias_data.low, bias_data.close, bias_data.atr,
            p.swing_n, p.min_break_atr, p.min_displacement,
        )
        m1_s  = compute_structure(
            ds.m1.high, ds.m1.low, ds.m1.close, ds.m1.atr,
            p.swing_n, p.min_break_atr, p.min_displacement,
        )
        _struct_cache[key] = (bias_s, m1_s)
    return _struct_cache[key]


def _get_fvgs(ds: DataStore, p: StrategyParams) -> FVGArrays:
    key = (p.min_fvg_atr, p.min_fvg_dollars, p.max_fvg_bars)
    if key not in _fvg_cache:
        _fvg_cache[key] = compute_fvgs(
            ds.m1.high, ds.m1.low, ds.m1.close, ds.m1.atr,
            p.min_fvg_atr, p.min_fvg_dollars, p.max_fvg_bars,
        )
    return _fvg_cache[key]


def _get_regime(ds: DataStore, p: StrategyParams) -> RegimeArrays:
    key = (p.min_atr_pct, p.max_atr_pct, p.slope_filter,
           p.slope_lookback, p.session_filter)
    if key not in _regime_cache:
        rp = RegimeParams(
            min_atr_pct    = p.min_atr_pct,
            max_atr_pct    = p.max_atr_pct,
            slope_filter   = p.slope_filter,
            slope_lookback = p.slope_lookback,
            session_filter = p.session_filter,
        )
        _regime_cache[key] = compute_regime(
            ds.m1.ts, ds.m15.ts, ds.m15.atr_pct,
            ds.h1.ts, ds.h1.ema_slow,
            ds.h4.ts, ds.h4.high, ds.h4.low, ds.h4.close,
            rp,
        )
    return _regime_cache[key]


def _precompute_all_caches(ds: DataStore, params_list: List[StrategyParams]) -> None:
    """
    Populate _struct_cache / _fvg_cache / _regime_cache for every unique
    key that appears in params_list.  Call this in the MAIN process before
    spawning workers so that fork-based children inherit the caches for free
    (copy-on-write — zero data copying until a worker writes to a new key).
    """
    struct_keys  = {(p.bias_tf, p.swing_n, p.min_break_atr, p.min_displacement) for p in params_list}
    fvg_keys     = {(p.min_fvg_atr, p.min_fvg_dollars, p.max_fvg_bars) for p in params_list}
    regime_keys  = {(p.min_atr_pct, p.max_atr_pct, p.slope_filter,
                     p.slope_lookback, p.session_filter) for p in params_list}

    print(f"  Precomputing {len(struct_keys)} struct / "
          f"{len(fvg_keys)} FVG / {len(regime_keys)} regime combos …",
          flush=True)
    t0 = _time.time()

    for k in struct_keys:
        _get_structure(ds, StrategyParams(bias_tf=k[0], swing_n=k[1], min_break_atr=k[2], min_displacement=k[3]))
    print(f"    struct done  {_time.time()-t0:.0f}s", flush=True)

    for k in fvg_keys:
        _get_fvgs(ds, StrategyParams(min_fvg_atr=k[0], min_fvg_dollars=k[1], max_fvg_bars=k[2]))
    print(f"    FVG done     {_time.time()-t0:.0f}s", flush=True)

    for k in regime_keys:
        _get_regime(ds, StrategyParams(
            min_atr_pct=k[0], max_atr_pct=k[1],
            slope_filter=k[2], slope_lookback=k[3], session_filter=k[4],
        ))
    print(f"    regime done  {_time.time()-t0:.0f}s", flush=True)


# ── Bar-range helpers ─────────────────────────────────────────────────────────

def _year_start_bar(ts: np.ndarray, year: int) -> int:
    target = np.datetime64(f"{year}-01-01T00:00:00", "ns")
    return int(np.searchsorted(ts, target, side="left"))


def _year_end_bar(ts: np.ndarray, year: int) -> int:
    target = np.datetime64(f"{year + 1}-01-01T00:00:00", "ns")
    return int(np.searchsorted(ts, target, side="left"))


# ── Single simulation wrapper ─────────────────────────────────────────────────

def _simulate(
    ds:         DataStore,
    p:          StrategyParams,
    exec_p:     ExecutionParams,
    start_bar:  int,
    end_bar:    int,
    n_years:    float,
) -> Tuple[SimMetrics, Optional[List[Trade]]]:
    bias_struct, m1_struct = _get_structure(ds, p)
    bias_data = ds.m5 if p.bias_tf == "m5" else ds.m15
    fvgs   = _get_fvgs(ds, p)
    regime = _get_regime(ds, p)
    trades = run_simulation(
        ds.m1, bias_data,
        m1_struct, bias_struct,
        fvgs, regime, p, exec_p,
        start_bar, end_bar,
    )
    return _calc_metrics(trades, exec_p.account_size, n_years), trades


# ── Random parameter sampling ─────────────────────────────────────────────────

def _random_params() -> StrategyParams:
    p = StrategyParams()
    for name, choices in PARAM_GRID.items():
        setattr(p, name, random.choice(choices))
    # Fixed params
    p.min_fvg_dollars = FIXED_MIN_FVG_DOLLARS
    p.max_fvg_bars    = FIXED_MAX_FVG_BARS
    p.max_atr_pct     = FIXED_MAX_ATR_PCT
    p.slope_lookback  = FIXED_SLOPE_LOOKBACK
    return p


def _non_default_count(p: StrategyParams) -> int:
    count = 0
    for name, default in DEFAULTS.items():
        if getattr(p, name) != default:
            count += 1
    return count


# ── Walk-forward evaluation ───────────────────────────────────────────────────

@dataclass
class WFResult:
    wf_idx:        int
    train_years:   str
    test_year:     int
    is_metrics:    SimMetrics
    oos_metrics:   SimMetrics


@dataclass
class ParamResult:
    params:         StrategyParams
    wf_results:     List[WFResult]
    is_trades_all:  List[Trade]         # full IS trades (2018-2022 window)
    mean_oos_pf:    float = 0.0
    std_oos_pf:     float = 0.0
    total_oos_n:    int   = 0
    is_max_dd:      float = 0.0
    is_n_trades:    int   = 0
    non_defaults:   int   = 0
    pass_hard:      bool  = False


def _evaluate_params(
    ds:     DataStore,
    p:      StrategyParams,
    exec_p: ExecutionParams,
) -> ParamResult:
    """
    Run ONE simulation over the full data period and slice trades by year
    to compute IS / OOS metrics for each walk-forward window.

    This is ~6 × faster than running 10 separate simulations (5 IS + 5 OOS),
    because the pre-computed structure / FVG / regime arrays are reused across
    all windows and the simulation loop runs once over the full dataset.

    Minor caveat: account equity carries forward from IS to OOS periods,
    slightly affecting position sizing on % risk.  At 1 % risk the effect is
    negligible — a 20 % IS gain shifts lot sizes by ≤ 20 %.
    """
    import pandas as _pd

    # ── Full-period simulation ────────────────────────────────────────────
    _, all_trades = _simulate(
        ds, p, exec_p,
        start_bar = 0,
        end_bar   = ds.m1.n,
        n_years   = 8.0,
    )

    if not all_trades:
        return ParamResult(
            params=p, wf_results=[], is_trades_all=[],
            mean_oos_pf=0.0, std_oos_pf=0.0, total_oos_n=0,
            is_max_dd=1.0, is_n_trades=0,
            non_defaults=_non_default_count(p), pass_hard=False,
        )

    # ── Group trades by entry year ────────────────────────────────────────
    trades_by_year: Dict[int, List[Trade]] = {}
    for t in all_trades:
        yr = int(_pd.Timestamp(t.entry_ts).year)
        trades_by_year.setdefault(yr, []).append(t)

    # ── Compute per-window IS / OOS metrics ───────────────────────────────
    wf_results: List[WFResult] = []
    for idx, (train_start, train_end, test_year) in enumerate(WF_WINDOWS):
        is_trades  = []
        for yr in range(train_start, train_end + 1):
            is_trades.extend(trades_by_year.get(yr, []))
        oos_trades = trades_by_year.get(test_year, [])

        n_is = float(train_end - train_start + 1)
        is_m  = _calc_metrics(is_trades,  exec_p.account_size, n_is)
        oos_m = _calc_metrics(oos_trades, exec_p.account_size, 1.0)

        wf_results.append(WFResult(
            wf_idx      = idx + 1,
            train_years = f"{train_start}–{train_end}",
            test_year   = test_year,
            is_metrics  = is_m,
            oos_metrics = oos_m,
        ))

    # ── Aggregate statistics ──────────────────────────────────────────────
    oos_pfs = np.array([
        min(r.oos_metrics.profit_factor, 3.0)
        if not np.isinf(r.oos_metrics.profit_factor)
        else 3.0
        for r in wf_results
    ])

    total_oos_n = sum(r.oos_metrics.n_trades for r in wf_results)
    is_max_dd   = max((r.is_metrics.max_drawdown for r in wf_results), default=1.0)

    # IS trade count = trades in 2018–2022 (the earliest shared IS window)
    is_n_trades = sum(
        len(trades_by_year.get(yr, []))
        for yr in range(2018, 2023)
    )

    oos_all_above = all(
        r.oos_metrics.profit_factor >= OOS_MIN_PF_WINDOW
        for r in wf_results
    )
    pass_hard = (
        is_n_trades >= IS_MIN_TRADES  and
        total_oos_n >= OOS_MIN_TRADES  and
        oos_all_above                  and
        is_max_dd   <= IS_MAX_DD
    )

    return ParamResult(
        params         = p,
        wf_results     = wf_results,
        is_trades_all  = all_trades,
        mean_oos_pf    = float(oos_pfs.mean()),
        std_oos_pf     = float(oos_pfs.std()),
        total_oos_n    = total_oos_n,
        is_max_dd      = is_max_dd,
        is_n_trades    = is_n_trades,
        non_defaults   = _non_default_count(p),
        pass_hard      = pass_hard,
    )



# ── Step 3: select simplest from top-10 survivors ────────────────────────────

def _select_winner(survivors: List[ParamResult]) -> ParamResult:
    if not survivors:
        raise RuntimeError("No survivors passed the hard filters.")

    # Rank survivors: primary = mean OOS PF ↓, secondary = std OOS PF ↑
    ranked = sorted(
        survivors,
        key=lambda r: (-r.mean_oos_pf, r.std_oos_pf, -r.total_oos_n),
    )
    top10 = ranked[:10]

    # From top-10, choose simplest (fewest non-default params)
    winner = min(top10, key=lambda r: (r.non_defaults, -r.mean_oos_pf))
    return winner


# ── Kill test ─────────────────────────────────────────────────────────────────

@dataclass
class KillScenario:
    name:          str
    spread_mult:   float
    slip_mult:     float
    rr_mult:       float
    n_trades:      int   = 0
    profit_factor: float = 0.0
    expectancy:    float = 0.0
    passed:        bool  = True


def _run_kill_test(
    ds:       DataStore,
    p:        StrategyParams,
    base_exec: ExecutionParams,
    start_year: int,
    end_year:   int,
) -> List[KillScenario]:
    scenarios = [
        KillScenario("Base",       1.0, 1.0, 1.0),
        KillScenario("Stress-A",   1.5, 1.0, 1.0),
        KillScenario("Stress-B",   1.0, 1.5, 1.0),
        KillScenario("Stress-C",   1.0, 1.0, 0.9),
        KillScenario("Stress-ALL", 1.5, 1.5, 0.9),
    ]
    sb = _year_start_bar(ds.m1.ts, start_year)
    eb = _year_end_bar(ds.m1.ts, end_year)
    n_years = float(end_year - start_year + 1)

    for sc in scenarios:
        stressed_exec = ExecutionParams(
            base_spread_pts  = base_exec.base_spread_pts  * sc.spread_mult,
            spread_jitter    = base_exec.spread_jitter    * sc.spread_mult,
            max_slippage_pts = base_exec.max_slippage_pts * sc.slip_mult,
            missed_fill_prob = base_exec.missed_fill_prob,
            account_size     = base_exec.account_size,
            risk_pct         = base_exec.risk_pct,
        )
        stressed_p = StrategyParams(**asdict(p))
        stressed_p.rr_ratio *= sc.rr_mult

        m, _ = _simulate(ds, stressed_p, stressed_exec, sb, eb, n_years)

        sc.n_trades      = m.n_trades
        sc.profit_factor = m.profit_factor
        sc.expectancy    = m.expectancy

        # Kill conditions
        if sc.name in ("Stress-A", "Stress-B", "Stress-C"):
            sc.passed = m.profit_factor >= 1.0
        elif sc.name == "Stress-ALL":
            sc.passed = m.expectancy >= 0.0

    return scenarios


# ── Output helpers ────────────────────────────────────────────────────────────

def _save_trades(trades: List[Trade], run_id: str) -> None:
    path = RESULTS_DIR / f"smc_trades_{run_id}.csv"
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "entry_ts", "exit_ts", "direction", "entry_price", "sl_price",
            "tp_price", "exit_price", "exit_reason", "lots", "sl_pips",
            "gross_pnl", "cost_usd", "net_pnl",
        ])
        for t in trades:
            w.writerow([
                t.entry_ts, t.exit_ts, t.direction, round(t.entry_price, 3),
                round(t.sl_price, 3), round(t.tp_price, 3),
                round(t.exit_price, 3), t.exit_reason,
                round(t.lots, 4), round(t.sl_pips, 1),
                round(t.gross_pnl, 2), round(t.cost_usd, 2), round(t.net_pnl, 2),
            ])
    print(f"  trades  → {path}")


def _save_params(results: List[ParamResult], run_id: str) -> None:
    path = RESULTS_DIR / f"smc_params_{run_id}.csv"
    rows = []
    for r in results:
        row: Dict = {
            "pass_hard":      r.pass_hard,
            "mean_oos_pf":    round(r.mean_oos_pf, 4),
            "std_oos_pf":     round(r.std_oos_pf, 4),
            "total_oos_n":    r.total_oos_n,
            "is_n_trades":    r.is_n_trades,
            "is_max_dd":      round(r.is_max_dd, 4),
            "non_defaults":   r.non_defaults,
        }
        for wf in r.wf_results:
            row[f"wf{wf.wf_idx}_oos_pf"] = round(wf.oos_metrics.profit_factor, 4)
            row[f"wf{wf.wf_idx}_oos_n"]  = wf.oos_metrics.n_trades
        for name in PARAM_GRID:
            row[name] = getattr(r.params, name)
        rows.append(row)
    df = pd.DataFrame(rows).sort_values("mean_oos_pf", ascending=False)
    df.to_csv(path, index=False)
    print(f"  params  → {path}")


def _save_kill_test(scenarios: List[KillScenario], run_id: str) -> None:
    path = RESULTS_DIR / f"smc_kill_test_{run_id}.csv"
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["scenario", "spread_mult", "slip_mult", "rr_mult",
                    "n_trades", "profit_factor", "expectancy", "passed"])
        for sc in scenarios:
            w.writerow([
                sc.name, sc.spread_mult, sc.slip_mult, sc.rr_mult,
                sc.n_trades, round(sc.profit_factor, 4),
                round(sc.expectancy, 2), sc.passed,
            ])
    print(f"  kill    → {path}")


def _print_summary(winner: ParamResult, kill: List[KillScenario]) -> None:
    print("\n" + "═" * 60)
    print("  WINNING PARAMETER SET")
    print("═" * 60)
    p = winner.params
    for name in PARAM_GRID:
        mark = "" if getattr(p, name) == DEFAULTS[name] else "  ← non-default"
        print(f"  {name:<24} {getattr(p, name)}{mark}")
    print(f"\n  Non-default params : {winner.non_defaults}")
    print(f"  IS trades (WF1)    : {winner.wf_results[0].is_metrics.n_trades}")
    print(f"  IS PF    (WF1)     : {winner.wf_results[0].is_metrics.profit_factor:.3f}")
    print(f"  IS max DD (WF1)    : {winner.wf_results[0].is_metrics.max_drawdown:.2%}")
    print()
    print(f"  {'Window':<12} {'OOS PF':>9}  {'OOS trades':>11}")
    print(f"  {'──────':<12} {'──────':>9}  {'──────────':>11}")
    for wf in winner.wf_results:
        print(f"  WF{wf.wf_idx} ({wf.test_year})  "
              f"{wf.oos_metrics.profit_factor:9.3f}  "
              f"{wf.oos_metrics.n_trades:11d}")
    print(f"\n  Mean OOS PF : {winner.mean_oos_pf:.3f}")
    print(f"  Std  OOS PF : {winner.std_oos_pf:.3f}")
    print(f"  Total OOS N : {winner.total_oos_n}")

    print("\n" + "═" * 60)
    print("  KILL TEST")
    print("═" * 60)
    all_passed = True
    for sc in kill:
        status = "✓ PASS" if sc.passed else "✗ FAIL"
        print(f"  {sc.name:<12}  PF={sc.profit_factor:.3f}  "
              f"E={sc.expectancy:+.2f}  N={sc.n_trades}  {status}")
        if not sc.passed:
            all_passed = False
    print()
    if all_passed:
        print("  ✓ Kill test PASSED — edge survives stressed execution.")
    else:
        print("  ✗ Kill test FAILED — edge too thin for live trading.")
    print("═" * 60)


def _plot_equity(trades: List[Trade], run_id: str) -> None:
    try:
        import matplotlib.pyplot as plt
        if not trades:
            return
        eq = [10_000.0]
        for t in trades:
            eq.append(eq[-1] + t.net_pnl)
        fig, ax = plt.subplots(figsize=(14, 5))
        ax.plot(eq, linewidth=1.0, color="#2196F3")
        ax.fill_between(range(len(eq)), eq, eq[0], alpha=0.1, color="#2196F3")
        ax.set_title(f"SMC Phase 1 — Equity Curve  (run {run_id})")
        ax.set_xlabel("Trade #")
        ax.set_ylabel("Account USD")
        ax.grid(alpha=0.3)
        path = RESULTS_DIR / f"smc_equity_{run_id}.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"  equity  → {path}")
    except ImportError:
        pass


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="SMC Phase 1 backtester",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Runtime estimates (8 years of M1 data):\n"
            "  --samples 20  : ~10 min   (quick validation)\n"
            "  --samples 100 : ~60 min   (recommended first run)\n"
            "  --samples 500 : ~5 hours  (thorough search)\n"
        ),
    )
    parser.add_argument("--samples", type=int, default=100,
                        help="Random param sets to evaluate (default 100)")

    parser.add_argument("--seed",    type=int, default=42)
    parser.add_argument("--start",   type=int, default=2018,
                        help="First data year to load")
    parser.add_argument("--end",     type=int, default=2025,
                        help="Last data year to load")
    parser.add_argument("--risk",    type=float, default=0.01,
                        help="Risk per trade as a fraction (default 0.01 = 1%%)")
    parser.add_argument("--account", type=float, default=10_000.0,
                        help="Starting account size in USD")
    parser.add_argument("--workers", type=int,
                        default=max(1, (_mp.cpu_count() or 2) - 1),
                        help="Parallel worker processes (default: cpu_count-1)")
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    print(f"\n{'═'*60}")
    print(f"  SMC Phase 1 Backtest  |  run {run_id}")
    print(f"{'═'*60}")
    print(f"  samples={args.samples}  seed={args.seed}  "
          f"risk={args.risk:.1%}  account=${args.account:,.0f}\n")

    # ── Load data ─────────────────────────────────────────────────────────
    print("Loading data …")
    ds = load(args.start, args.end)

    base_exec = ExecutionParams(
        base_spread_pts  = 20.0,
        spread_jitter    = 10.0,
        max_slippage_pts = 10.0,
        missed_fill_prob = 0.05,
        account_size     = args.account,
        risk_pct         = args.risk,
    )

    # ── Random search ─────────────────────────────────────────────────────
    random.seed(args.seed)
    np.random.seed(args.seed)
    params_list = [_random_params() for _ in range(args.samples)]

    # ── Precompute shared caches before forking workers ──────────────────────
    # On Linux/Mac (fork), workers inherit these dicts for free.
    # On Windows (spawn), workers recompute from scratch — acceptable.
    if os.name != "nt":
        _precompute_all_caches(ds, params_list)

    print(f"\nRunning {args.samples} random parameter sets …"
          f"  (workers={args.workers})")
    t0 = _time.time()

    if args.workers > 1:
        # ── Parallel path ─────────────────────────────────────────────────
        # Spawn-safe: DataStore is pickled once per worker (not per task).
        # Windows requires the 'spawn' context; fork is faster on Linux/Mac.
        ctx    = _mp.get_context("fork") if os.name != "nt" else _mp.get_context("spawn")
        chunks = [asdict(p) for p in params_list]
        with ctx.Pool(
            processes   = args.workers,
            initializer = _mp_init,
            initargs    = (ds, base_exec),
        ) as pool:
            all_results: List[ParamResult] = []
            done = 0
            for res in pool.imap_unordered(_mp_eval, chunks, chunksize=max(1, args.samples // (args.workers * 4))):
                all_results.append(res)
                done += 1
                if done % 10 == 0:
                    elapsed = _time.time() - t0
                    eta     = elapsed / done * (args.samples - done)
                    surv    = sum(1 for r in all_results if r.pass_hard)
                    print(f"  {done:4d}/{args.samples}  survivors={surv}  "
                          f"elapsed={elapsed:.0f}s  ETA={eta:.0f}s")
        survivors = [r for r in all_results if r.pass_hard]

    else:
        # ── Serial path (original behaviour) ──────────────────────────────
        all_results = []
        survivors   = []
        for k, p in enumerate(params_list):
            res = _evaluate_params(ds, p, base_exec)
            all_results.append(res)
            if res.pass_hard:
                survivors.append(res)
            if (k + 1) % 10 == 0:
                elapsed = _time.time() - t0
                eta     = elapsed / (k + 1) * (args.samples - k - 1)
                print(f"  {k+1:4d}/{args.samples}  survivors={len(survivors)}  "
                      f"elapsed={elapsed:.0f}s  ETA={eta:.0f}s")

    print(f"\n  Search complete in {_time.time()-t0:.0f} s")
    print(f"  Candidates : {len(all_results)}")
    print(f"  Survivors  : {len(survivors)}")

    # ── Trade-count kill switch ───────────────────────────────────────────
    if not survivors:
        # Check best IS trade count to give a meaningful error
        best = max(all_results, key=lambda r: r.is_n_trades)
        print(f"\n  KILL — No parameter set passed all hard filters.")
        print(f"  Best IS trade count: {best.is_n_trades} "
              f"(minimum required: {IS_MIN_TRADES})")
        print("  Strategy is not viable at Phase 1. Development stopped.")
        _save_params(all_results, run_id)
        sys.exit(1)

    # Pick the winning param set
    winner = _select_winner(survivors)

    # Hard-check on total IS trades for the winner
    is_sb = _year_start_bar(ds.m1.ts, args.start)
    is_eb = _year_end_bar(ds.m1.ts, 2022)                 # IS up to 2022
    is_m, is_trades = _simulate(ds, winner.params, base_exec, is_sb, is_eb,
                                 2022 - args.start + 1)
    if is_trades and len(is_trades) < TRADE_COUNT_MIN:
        print(f"\n  KILL — Winner IS trade count = {len(is_trades)} "
              f"< {TRADE_COUNT_MIN}. Strategy not viable.")
        _save_params(all_results, run_id)
        sys.exit(1)
    if is_trades and len(is_trades) < TRADE_COUNT_TARGET:
        print(f"\n  WARNING — IS trade count = {len(is_trades)} "
              f"< {TRADE_COUNT_TARGET}. Results may be unreliable.")

    # ── Kill test ─────────────────────────────────────────────────────────
    print("\nRunning kill test …")
    kill_scenarios = _run_kill_test(
        ds, winner.params, base_exec, args.start, args.end
    )
    kill_failed = any(not sc.passed for sc in kill_scenarios)

    # ── Full-period trade log for winner ──────────────────────────────────
    full_sb = _year_start_bar(ds.m1.ts, args.start)
    full_eb = _year_end_bar(ds.m1.ts, args.end)
    _, full_trades = _simulate(ds, winner.params, base_exec, full_sb, full_eb,
                                args.end - args.start + 1)

    # ── Outputs ───────────────────────────────────────────────────────────
    print("\nSaving outputs …")
    _save_trades(full_trades or [], run_id)
    _save_params(all_results, run_id)
    _save_kill_test(kill_scenarios, run_id)
    _plot_equity(full_trades or [], run_id)
    _print_summary(winner, kill_scenarios)

    # Save winning params as JSON for reuse in live trader
    params_json = RESULTS_DIR / f"smc_winner_{run_id}.json"
    with open(params_json, "w") as f:
        json.dump(asdict(winner.params), f, indent=2)
    print(f"  winner  → {params_json}")

    if kill_failed:
        print("\n  ⚠  Kill test failed — review before live deployment.")
        sys.exit(2)
    else:
        print("\n  ✓  Phase 1 complete — proceed to Phase 2 evaluation.")


if __name__ == "__main__":
    main()
