"""
Test 1b: FOMC-only drill-down.

Test 1 showed blanket macro-momentum fails, but FOMC continuation cleared costs
at 60m. FOMC has only ~68 events in 2018-2025, so this script stresses that
sub-signal for small-sample robustness before any paper-trade decision:

  - full hold curve (5..120m)
  - t-stat + bootstrap 95% CI on mean net (is +EV distinguishable from 0?)
  - out-of-sample split (2018-2021 train vs 2022-2025 test)
  - directionality (long vs short legs)
  - cost sensitivity (1x / 2x / 3x spread)
  - random-time control on FOMC days
  - top-N trade removal
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from events.calendar import load_calendar
from backtests.test1_macro_momentum import (
    Trade,
    load_bars,
    simulate_event_trade,
    random_control_trades,
    summarize,
    by_year,
    top_n_removed_still_positive,
)

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
HOLDS = [5, 15, 30, 45, 60, 90, 120]


def fomc_trades(bars, events, hold: int, cost_rt: float) -> list[Trade]:
    out: list[Trade] = []
    for ev in events:
        t = simulate_event_trade(bars, ev, hold, cost_rt)
        if t:
            out.append(t)
    return out


def tstat(trades: list[Trade]) -> float:
    nets = np.array([t.net_pnl for t in trades], dtype=float)
    if len(nets) < 2 or nets.std(ddof=1) == 0:
        return 0.0
    return float(nets.mean() / (nets.std(ddof=1) / np.sqrt(len(nets))))


def bootstrap_ci(trades: list[Trade], iters: int = 10000, seed: int = 7) -> tuple[float, float, float]:
    """Return (lo95, hi95, p_mean_le_0) for mean net per trade."""
    nets = np.array([t.net_pnl for t in trades], dtype=float)
    if len(nets) < 2:
        return (0.0, 0.0, 1.0)
    rng = np.random.default_rng(seed)
    means = np.empty(iters)
    n = len(nets)
    for i in range(iters):
        means[i] = nets[rng.integers(0, n, n)].mean()
    lo, hi = np.percentile(means, [2.5, 97.5])
    p_le0 = float(np.mean(means <= 0))
    return (float(lo), float(hi), p_le0)


def leg_summary(trades: list[Trade], direction: int) -> dict:
    return summarize([t for t in trades if t.direction == direction])


def run(cost_multiplier: float = 2.0, base_spread: float = 0.40) -> str:
    cost_rt = base_spread * cost_multiplier
    bars = load_bars(range(2018, 2026))
    events = [e for e in load_calendar(2018, 2025) if e.name == "FOMC"]
    events = [e for e in events if bars.index.min() <= e.ts_utc <= bars.index.max()]
    fomc_days = {e.date for e in events}

    L: list[str] = []
    L.append("=" * 64)
    L.append("TEST 1b: FOMC-ONLY DRILL-DOWN")
    L.append("=" * 64)
    L.append(f"Data: {bars.index.min()} -> {bars.index.max()}")
    L.append(f"FOMC events: {len(events)}  (small sample — read CIs, not point estimates)")
    L.append(f"Cost RT @ {cost_multiplier}x spread: {cost_rt:.2f} pts")
    L.append("")

    L.append("--- HOLD CURVE (net per trade, after cost) ---")
    L.append(f"{'hold':>5} {'n':>4} {'gross':>8} {'net':>8} {'avg':>7} {'win%':>6} {'t':>6} {'boot95_lo':>10} {'boot95_hi':>10} {'p(<=0)':>7}")
    best = None
    per_hold: dict[int, list[Trade]] = {}
    for hold in HOLDS:
        tr = fomc_trades(bars, events, hold, cost_rt)
        per_hold[hold] = tr
        s = summarize(tr)
        t = tstat(tr)
        lo, hi, p = bootstrap_ci(tr)
        L.append(
            f"{hold:>5} {s['n']:>4} {s['gross']:>8.1f} {s['net']:>8.1f} {s['avg']:>7.3f} "
            f"{s['win_pct']:>6.1f} {t:>6.2f} {lo:>10.3f} {hi:>10.3f} {p:>7.3f}"
        )
        if best is None or s["avg"] > best[1]:
            best = (hold, s["avg"])

    best_hold = best[0]
    bt = per_hold[best_hold]
    L.append("")
    L.append(f"Best hold by avg net: {best_hold}m")
    L.append("")

    L.append(f"--- DIRECTIONALITY (best hold {best_hold}m) ---")
    longs = leg_summary(bt, 1)
    shorts = leg_summary(bt, -1)
    L.append(f"LONG : n={longs['n']:3d} net={longs['net']:8.1f} avg={longs['avg']:7.3f} win%={longs['win_pct']:5.1f}")
    L.append(f"SHORT: n={shorts['n']:3d} net={shorts['net']:8.1f} avg={shorts['avg']:7.3f} win%={shorts['win_pct']:5.1f}")
    L.append("")

    L.append(f"--- OUT-OF-SAMPLE SPLIT (best hold {best_hold}m) ---")
    train = [t for t in bt if t.entry_ts.year <= 2021]
    test = [t for t in bt if t.entry_ts.year >= 2022]
    s_tr, s_te = summarize(train), summarize(test)
    L.append(f"TRAIN 2018-2021: n={s_tr['n']:3d} net={s_tr['net']:8.1f} avg={s_tr['avg']:7.3f} win%={s_tr['win_pct']:5.1f}")
    L.append(f"TEST  2022-2025: n={s_te['n']:3d} net={s_te['net']:8.1f} avg={s_te['avg']:7.3f} win%={s_te['win_pct']:5.1f}")
    L.append("")

    L.append(f"--- YEAR-BY-YEAR NET (best hold {best_hold}m) ---")
    yearly = by_year(bt)
    L.append(" ".join(f"{y}={v:+.0f}" for y, v in yearly.items()))
    pos_years = sum(1 for v in yearly.values() if v > 0)
    L.append(f"Positive years: {pos_years}/{len(yearly)}")
    L.append("")

    L.append(f"--- COST SENSITIVITY (best hold {best_hold}m) ---")
    for mult in (0.0, 1.0, 2.0, 3.0):
        c = base_spread * mult
        tr = fomc_trades(bars, events, best_hold, c)
        s = summarize(tr)
        L.append(f"{mult:>3.0f}x spread (RT={c:.2f}): net={s['net']:8.1f} avg={s['avg']:7.3f}")
    L.append("")

    L.append(f"--- RANDOM-TIME CONTROL (FOMC days, best hold {best_hold}m) ---")
    ctrl = random_control_trades(bars, fomc_days, events, best_hold, cost_rt)
    sc = summarize(ctrl)
    L.append(f"control: n={sc['n']:3d} net={sc['net']:8.1f} avg={sc['avg']:7.3f}")
    L.append("")

    top5_ok = top_n_removed_still_positive(bt, 5)
    L.append(f"Top-5-removed still positive: {top5_ok}")
    L.append("")

    # ---- verdict ----
    s_best = summarize(bt)
    lo, hi, p = bootstrap_ci(bt)
    kills: list[str] = []
    if s_best["net"] <= 0:
        kills.append("net <= 0 at best hold after 2x cost")
    if lo <= 0:
        kills.append(f"bootstrap 95% CI lower bound <= 0 ({lo:.3f}) — mean not distinguishable from 0")
    if s_te["avg"] <= 0:
        kills.append("out-of-sample (2022-2025) avg <= 0")
    if sc["avg"] >= s_best["avg"]:
        kills.append("random-time control matches/beats FOMC signal")
    if not top5_ok:
        kills.append("removing top 5 trades flips PnL negative")
    if pos_years < len(yearly) / 2:
        kills.append(f"profitable in only {pos_years}/{len(yearly)} years")

    L.append("=" * 64)
    if kills:
        L.append("VERDICT: NOT ROBUST ENOUGH TO PAPER MONDAY")
        for k in kills:
            L.append(f"  - {k}")
    else:
        L.append("VERDICT: SURVIVES — candidate for Monday paper (small size)")
    L.append("=" * 64)

    report = "\n".join(L)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / "test1b_fomc_drill.txt"
    out.write_text(report)
    print(report)
    print(f"\nWrote {out}")
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spread", type=float, default=0.40)
    ap.add_argument("--cost-mult", type=float, default=2.0)
    args = ap.parse_args()
    run(cost_multiplier=args.cost_mult, base_spread=args.spread)


if __name__ == "__main__":
    main()
