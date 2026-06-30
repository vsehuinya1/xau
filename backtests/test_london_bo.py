"""
London Breakout — Walk-Forward Backtest
========================================
Research Direction 1: Time-of-day + volatility expansion.

Methodology
-----------
* 5-window blocked walk-forward (same structure as test5_smc.py).
* Per window: IS = first 80% of days, OOS = last 20%.
* Hard filters (same as Phase-1 SMC): IS ≥ 300 trades, all OOS windows
  PF ≥ 1.0, each OOS window ≥ 30 trades.
* Random parameter sampling (Latin Hypercube-style) over PARAM_GRID.

Session feature precompute
--------------------------
  compute_session_features() runs once per unique (asian_start_hour,
  asian_end_hour, range_pct_lookback) key.  Children inherit the cache
  via fork copy-on-write with zero overhead.

Usage
-----
  python backtests/test_london_bo.py [--samples N] [--seed S]
                                      [--start YYYY] [--end YYYY]
                                      [--workers W]
"""
from __future__ import annotations

import sys
from pathlib import Path
# Ensure the repo root is on sys.path regardless of working directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
import multiprocessing as mp
import time as _time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from smc.loader import load, DataStore
from smc.confluence import ExecutionParams, Trade
from strategy.sessions import SessionFeatures, compute_session_features
from strategy.london_breakout import LBParams, run_simulation


# ── Hard filter thresholds ────────────────────────────────────────────────────

WF_WINDOWS      = 5
OOS_FRACTION    = 0.2
IS_MIN_TRADES   = 300   # across full IS set
OOS_MIN_TRADES  = 30    # per OOS window
IS_MAX_DD       = 0.35  # max intra-sample drawdown

EXEC_PARAMS = ExecutionParams(
    account_size    = 10_000,
    risk_pct        = 1.0,
    base_spread_pts = 20.0,
    spread_jitter   = 10.0,
    max_slippage_pts= 10.0,
    missed_fill_prob= 0.05,
)


# ── Parameter grid ────────────────────────────────────────────────────────────

PARAM_GRID: Dict[str, list] = {
    # Entry conditions — hypothesis test
    "require_compressed":    [True, False],
    "range_pct_threshold":   [10.0, 25.0, 40.0],
    "require_atr_expansion": [True, False],
    "atr_expansion_ratio":   [1.1, 1.3, 1.5],
    "breakout_confirm_bars": [1, 5, 15],
    # Exit
    "sl_buffer_atr":         [0.0, 0.1, 0.2],
    "rr_ratio":              [1.5, 2.0, 3.0],
    "max_bars_in_trade":     [60, 120, 180, 240],
    "max_scan_bars":         [60, 120, 180],
    # Quality
    "min_range_atr":         [0.0, 0.2, 0.4],
    "range_pct_lookback":    [10, 20, 40],
    # Volatility regime
    "min_atr_pct":           [10.0, 20.0, 30.0],
    "max_atr_pct":           [75.0, 85.0, 95.0],
}

DEFAULTS: Dict = {
    "require_compressed":    True,
    "range_pct_threshold":   25.0,
    "require_atr_expansion": True,
    "atr_expansion_ratio":   1.2,
    "breakout_confirm_bars": 5,
    "sl_buffer_atr":         0.1,
    "rr_ratio":              2.0,
    "max_bars_in_trade":     180,
    "max_scan_bars":         120,
    "min_range_atr":         0.2,
    "range_pct_lookback":    20,
    "min_atr_pct":           20.0,
    "max_atr_pct":           85.0,
}

FIXED_PARAMS: Dict = {
    "asian_start_hour": 0,
    "asian_end_hour":   7,
}


# ── Global caches (populated in main process, inherited by workers) ───────────

_session_cache: Dict[Tuple, SessionFeatures]   = {}
_atr_pct_cache: Dict[Tuple, np.ndarray]        = {}   # per-day M15 atr_pct

# DataStore stored as a global so fork-based workers inherit it via CoW
# (zero serialisation overhead) instead of pickling it per job.
_ds: Optional[DataStore] = None


def _get_session_features(p: LBParams) -> SessionFeatures:
    key = (p.asian_start_hour, p.asian_end_hour, p.range_pct_lookback)
    if key not in _session_cache:
        _session_cache[key] = compute_session_features(
            _ds.m1,
            asian_start_hour   = p.asian_start_hour,
            asian_end_hour     = p.asian_end_hour,
            range_pct_lookback = p.range_pct_lookback,
        )
    return _session_cache[key]


def _get_london_atr_pct(p: LBParams) -> np.ndarray:
    """
    Per-day M15 ATR-pct value at each day's London-open bar.
    Depends on range_pct_lookback (via session features).
    """
    sf_key = (p.asian_start_hour, p.asian_end_hour, p.range_pct_lookback)
    if sf_key in _atr_pct_cache:
        return _atr_pct_cache[sf_key]

    sf = _get_session_features(p)
    m1_to_m15 = np.searchsorted(_ds.m15.ts, _ds.m1.ts, side="right") - 1
    m1_to_m15 = np.clip(m1_to_m15, 0, len(_ds.m15.atr_pct) - 1)

    atr_pct_per_day = np.full(sf.n_days, np.nan)
    for di in range(sf.n_days):
        bstart = sf.london_bar_start[di]
        if bstart >= 0:
            atr_pct_per_day[di] = _ds.m15.atr_pct[m1_to_m15[bstart]]

    _atr_pct_cache[sf_key] = atr_pct_per_day
    return atr_pct_per_day


def _precompute_all_caches(params_list: List[LBParams]) -> None:
    """
    Warm all caches before spawning workers.
    With fork-based multiprocessing the children inherit all arrays
    copy-on-write — zero serialisation overhead.
    """
    sf_keys = {(p.asian_start_hour, p.asian_end_hour, p.range_pct_lookback)
               for p in params_list}

    print(f"  Precomputing {len(sf_keys)} session-feature variant(s) …", flush=True)
    t0 = _time.time()
    for k in sf_keys:
        dummy = LBParams(
            asian_start_hour   = k[0],
            asian_end_hour     = k[1],
            range_pct_lookback = k[2],
        )
        _get_session_features(dummy)
        _get_london_atr_pct(dummy)
    print(f"    done  {_time.time() - t0:.0f}s", flush=True)


# ── Metrics ───────────────────────────────────────────────────────────────────

@dataclass
class SimMetrics:
    n_trades:   int
    pf:         float
    win_rate:   float
    net_pnl:    float
    max_dd:     float


def _calc_metrics(trades: List[Trade], account_size: float) -> SimMetrics:
    if not trades:
        return SimMetrics(0, 0.0, 0.0, 0.0, 0.0)
    pnls   = [t.net_pnl for t in trades]
    wins   = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    gp     = sum(wins)
    gl     = abs(sum(losses))
    pf     = gp / gl if gl > 0 else float("inf")

    # Equity drawdown
    equity = account_size
    peak   = equity
    max_dd = 0.0
    for p in pnls:
        equity += p
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak
        if dd > max_dd:
            max_dd = dd

    return SimMetrics(
        n_trades = len(trades),
        pf       = pf,
        win_rate = len(wins) / len(pnls) if pnls else 0.0,
        net_pnl  = sum(pnls),
        max_dd   = max_dd,
    )


# ── WF worker ─────────────────────────────────────────────────────────────────

def _evaluate_params(
    args: Tuple[LBParams, int],
) -> Optional[Dict]:
    p, sample_idx = args

    sf      = _get_session_features(p)
    atr_pct = _get_london_atr_pct(p)
    n_days  = sf.n_days

    win_size = n_days // WF_WINDOWS

    all_is_trades: List[Trade] = []
    wf_oos_pf:     List[float] = []
    wf_oos_n:      List[int]   = []

    for w in range(WF_WINDOWS):
        wf_start = w * win_size
        wf_end   = (wf_start + win_size) if w < WF_WINDOWS - 1 else n_days
        is_end   = int(wf_start + (wf_end - wf_start) * (1.0 - OOS_FRACTION))
        oos_start = is_end

        is_trades  = run_simulation(_ds.m1, sf, atr_pct, p, EXEC_PARAMS,
                                    wf_start, is_end)
        oos_trades = run_simulation(_ds.m1, sf, atr_pct, p, EXEC_PARAMS,
                                    oos_start, wf_end)

        all_is_trades.extend(is_trades)

        oos_m = _calc_metrics(oos_trades, EXEC_PARAMS.account_size)
        wf_oos_pf.append(oos_m.pf)
        wf_oos_n.append(oos_m.n_trades)

    is_m = _calc_metrics(all_is_trades, EXEC_PARAMS.account_size)

    # ── Count non-default params (simplicity proxy)
    non_defaults = sum(
        1 for k, v in DEFAULTS.items()
        if getattr(p, k, None) != v
    )

    return {
        "is_n_trades":  is_m.n_trades,
        "is_pf":        is_m.pf,
        "is_win_rate":  is_m.win_rate,
        "is_net_pnl":   is_m.net_pnl,
        "is_max_dd":    is_m.max_dd,
        "mean_oos_pf":  float(np.nanmean([x for x in wf_oos_pf if np.isfinite(x)])),
        "std_oos_pf":   float(np.nanstd( [x for x in wf_oos_pf if np.isfinite(x)])),
        "total_oos_n":  sum(wf_oos_n),
        "non_defaults": non_defaults,
        **{f"wf{w+1}_oos_pf": wf_oos_pf[w] for w in range(WF_WINDOWS)},
        **{f"wf{w+1}_oos_n":  wf_oos_n[w]  for w in range(WF_WINDOWS)},
        # strategy params
        "require_compressed":    p.require_compressed,
        "range_pct_threshold":   p.range_pct_threshold,
        "require_atr_expansion": p.require_atr_expansion,
        "atr_expansion_ratio":   p.atr_expansion_ratio,
        "breakout_confirm_bars": p.breakout_confirm_bars,
        "sl_buffer_atr":         p.sl_buffer_atr,
        "rr_ratio":              p.rr_ratio,
        "max_bars_in_trade":     p.max_bars_in_trade,
        "max_scan_bars":         p.max_scan_bars,
        "min_range_atr":         p.min_range_atr,
        "range_pct_lookback":    p.range_pct_lookback,
        "min_atr_pct":           p.min_atr_pct,
        "max_atr_pct":           p.max_atr_pct,
        "asian_start_hour":      p.asian_start_hour,
        "asian_end_hour":        p.asian_end_hour,
    }


def _passes_hard_filters(row: Dict, wf_windows: int) -> bool:
    if row["is_n_trades"] < IS_MIN_TRADES:
        return False
    if row["is_max_dd"] > IS_MAX_DD:
        return False
    for w in range(1, wf_windows + 1):
        if row[f"wf{w}_oos_n"] < OOS_MIN_TRADES:
            return False
        pf = row[f"wf{w}_oos_pf"]
        if not np.isfinite(pf) or pf < 1.0:
            return False
    return True


# ── Random parameter sampling ─────────────────────────────────────────────────

def _random_params(rng: np.random.Generator, n: int) -> List[LBParams]:
    params = []
    for _ in range(n):
        kw = {k: rng.choice(v) for k, v in PARAM_GRID.items()}
        kw.update(FIXED_PARAMS)
        params.append(LBParams(**kw))
    return params


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="London Breakout WF Backtest")
    ap.add_argument("--samples", type=int, default=200)
    ap.add_argument("--seed",    type=int, default=42)
    ap.add_argument("--start",   type=int, default=2018)
    ap.add_argument("--end",     type=int, default=2025)
    ap.add_argument("--workers", type=int, default=max(1, mp.cpu_count() - 1))
    args = ap.parse_args()

    run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    print("=" * 60)
    print(f"  London Breakout Backtest  |  run {run_id}")
    print("=" * 60)
    print(f"  samples={args.samples}  seed={args.seed}  "
          f"risk={EXEC_PARAMS.risk_pct:.1f}%  "
          f"account=${EXEC_PARAMS.account_size:,.0f}")

    # ── Load data
    print("\nLoading data …")
    ds = load(args.start, args.end)

    # ── Build param list
    rng    = np.random.default_rng(args.seed)
    params = _random_params(rng, args.samples)

    # ── Precompute caches (before forking)
    # Set _ds global so fork-based workers inherit it via CoW (zero pickle cost)
    global _ds
    _ds = ds
    print("\nPrecomputing session features …")
    _precompute_all_caches(params)

    # ── Run grid search
    print(f"\nRunning {args.samples} random parameter sets …  "
          f"(workers={args.workers})")

    results:   List[Dict] = []
    survivors: int        = 0
    t0 = _time.time()

    ctx  = mp.get_context("fork")
    pool = ctx.Pool(processes=args.workers)

    job_args = [(p, i) for i, p in enumerate(params)]

    for done, result in enumerate(
        pool.imap_unordered(_evaluate_params, job_args), start=1
    ):
        if result is not None:
            passes = _passes_hard_filters(result, WF_WINDOWS)
            result["pass_hard"] = passes
            results.append(result)
            if passes:
                survivors += 1

        elapsed = _time.time() - t0
        eta     = elapsed / done * (args.samples - done)
        print(f"  {done:>4}/{args.samples}  survivors={survivors}"
              f"  elapsed={elapsed:.0f}s  ETA={eta:.0f}s",
              flush=True)

    pool.close()
    pool.join()

    # ── Sort and save
    df = pd.DataFrame(results).sort_values("mean_oos_pf", ascending=False)
    out_dir = Path(__file__).resolve().parent.parent / "results"
    out_dir.mkdir(exist_ok=True)
    csv_path = out_dir / f"lb_params_{run_id}.csv"
    df.to_csv(csv_path, index=False)

    # ── Console summary
    total = _time.time() - t0
    print(f"\n  Search complete in {total:.0f} s")
    print(f"  Candidates : {len(results)}")
    print(f"  Survivors  : {survivors}")

    if survivors > 0:
        print(f"\n  ✓ PASS — {survivors} parameter set(s) passed all hard filters.")
        best = df[df["pass_hard"]].iloc[0]
        print(f"  Best: IS={best['is_n_trades']:.0f} trades  "
              f"OOS_PF={best['mean_oos_pf']:.3f}  DD={best['is_max_dd']:.1%}")
        print(f"  WF: " + "  ".join(
            f"{best[f'wf{w}_oos_pf']:.2f}" for w in range(1, WF_WINDOWS + 1)
        ))
    else:
        best_row = df.iloc[0]
        print(f"\n  KILL — No parameter set passed all hard filters.")
        print(f"  Best IS trade count: {df['is_n_trades'].max():.0f}"
              f"  (minimum required: {IS_MIN_TRADES})")
        print(f"  Best mean OOS PF:   {df['mean_oos_pf'].max():.3f}")
        print(f"  Best WF windows:    " + "  ".join(
            f"{best_row[f'wf{w}_oos_pf']:.2f}" for w in range(1, WF_WINDOWS + 1)
        ))

    print(f"\n  Compressed (True) vs any breakout (False):")
    for comp in [True, False]:
        sub = df[df["require_compressed"] == comp]
        print(f"    require_compressed={comp}: n={len(sub)}"
              f"  max_OOS_PF={sub['mean_oos_pf'].max():.3f}"
              f"  IS>300={(sub['is_n_trades'] >= 300).sum()}")

    print(f"  params  → {csv_path}")


if __name__ == "__main__":
    main()
