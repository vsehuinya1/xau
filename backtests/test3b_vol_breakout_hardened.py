"""
Test 3b: Hardened volatility-regime breakout.

Test 3 "passed" but on two fragile legs: (a) the best config was chosen
in-sample, and (b) ~93% of its net came from 2025. This script answers the only
question that matters for deployment: *could you have actually traded this?*

Hardening layers:
  1. WALK-FORWARD: for each test year Y (2020..2025), pick the best config using
     ONLY data from years < Y, then trade that config in year Y. Concatenate the
     out-of-sample years into one honest equity curve. A no-filter option is in
     the grid, so the walk-forward is free to reject the compression filter.
  2. CONCENTRATION GATE: kill if one calendar year supplies >50% of WF net, or if
     removing the single best year flips WF net <= 0.
  3. FILTER CONTRIBUTION: filtered vs unfiltered, head-to-head, on net/avg/t and
     per-year consistency — does the "regime" claim actually add anything?
  4. EQUITY METRICS: max drawdown (pts), edge ratio (avg/std), positive-year rate,
     top-5 trade removal, bootstrap CI on WF mean.

Falsification (hardened):
  KILL if WF net <= 0
  KILL if WF avg/trade <= 0 or WF t-stat < 1.0
  KILL if one year > 50% of WF net (concentration)
  KILL if removing best WF year flips net <= 0
  KILL if WF positive years < half
  KILL if removing top-5 WF trades flips net <= 0
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtests.test3_vol_breakout import load_m1, resample, atr

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"

TF_HOLD = {"1h": 24, "4h": 12}
ATR_PERIOD = {"1h": 24, "4h": 12}
PCTILE_LB = {"1h": 240, "4h": 120}
DONCHIAN = [20, 50]
THRESH = [0.25, 0.40, None]   # None == unfiltered (walk-forward may pick this)

TEST_YEARS = [2020, 2021, 2022, 2023, 2024, 2025]
MIN_TRAIN_TRADES = 40


@dataclass
class Trade:
    entry_ts: object
    year: int
    direction: int
    gross_pnl: float
    net_pnl: float


def atr_percentile_fast(atr_series, lookback: int) -> np.ndarray:
    """Fraction of the trailing `lookback` ATR values <= the current ATR."""
    vals = atr_series.to_numpy(dtype=float)
    n = len(vals)
    out = np.full(n, np.nan)
    if n < lookback:
        return out
    sw = np.lib.stride_tricks.sliding_window_view(vals, lookback)  # (n-lb+1, lb)
    cur = sw[:, -1]
    valid = ~np.isnan(sw).any(axis=1)
    frac = (sw <= cur[:, None]).mean(axis=1)
    out[lookback - 1:] = np.where(valid, frac, np.nan)
    return out


@dataclass
class TFData:
    open_: np.ndarray
    close: np.ndarray
    ts: object
    years: np.ndarray
    pct: np.ndarray
    donchian: dict   # don -> (upper, lower)


def build_tf(m1, tf: str) -> TFData:
    df = resample(m1, tf)
    pct = atr_percentile_fast(atr(df, ATR_PERIOD[tf]), PCTILE_LB[tf])
    donch = {}
    for don in DONCHIAN:
        upper = df["high"].rolling(don).max().shift(1).to_numpy(float)
        lower = df["low"].rolling(don).min().shift(1).to_numpy(float)
        donch[don] = (upper, lower)
    return TFData(
        open_=df["open"].to_numpy(float),
        close=df["close"].to_numpy(float),
        ts=df.index,
        years=df.index.year.to_numpy(),
        pct=pct,
        donchian=donch,
    )


def simulate(tfd: TFData, don: int, thr, hold: int, cost_rt: float) -> list[Trade]:
    upper, lower = tfd.donchian[don]
    close, open_, pct, ts, years = tfd.close, tfd.open_, tfd.pct, tfd.ts, tfd.years
    n = len(close)
    trades: list[Trade] = []
    warmup = max(don, PCTILE_LB["4h"], 0) + 1
    i = warmup
    while i < n - 1:
        u, l = upper[i], lower[i]
        if np.isnan(u) or np.isnan(l):
            i += 1
            continue
        direction = 1 if close[i] > u else (-1 if close[i] < l else 0)
        if direction == 0:
            i += 1
            continue
        if thr is not None:
            p = pct[i - 1]
            if np.isnan(p) or p >= thr:
                i += 1
                continue
        entry_i = i + 1
        exit_i = entry_i + hold
        if exit_i >= n:
            break
        gross = direction * (close[exit_i] - open_[entry_i])
        trades.append(Trade(ts[entry_i], int(years[entry_i]), direction, gross, gross - cost_rt))
        i = exit_i + 1
    return trades


def summarize(trades: list[Trade]) -> dict:
    if not trades:
        return {"n": 0, "net": 0.0, "avg": 0.0, "win_pct": 0.0, "t": 0.0, "edge": 0.0}
    nets = np.array([t.net_pnl for t in trades], dtype=float)
    sd = nets.std(ddof=1) if len(nets) > 1 else 0.0
    t = float(nets.mean() / (sd / np.sqrt(len(nets)))) if sd > 0 else 0.0
    edge = float(nets.mean() / sd) if sd > 0 else 0.0
    return {
        "n": len(trades),
        "net": float(nets.sum()),
        "avg": float(nets.mean()),
        "win_pct": 100.0 * float((nets > 0).mean()),
        "t": t,
        "edge": edge,
    }


def per_year(trades: list[Trade]) -> dict[int, float]:
    out: dict[int, float] = {}
    for t in trades:
        out[t.year] = out.get(t.year, 0.0) + t.net_pnl
    return dict(sorted(out.items()))


def max_drawdown(trades: list[Trade]) -> float:
    eq = peak = mdd = 0.0
    for t in sorted(trades, key=lambda x: x.entry_ts):
        eq += t.net_pnl
        peak = max(peak, eq)
        mdd = max(mdd, peak - eq)
    return mdd


def bootstrap_ci(trades: list[Trade], iters: int = 10000, seed: int = 7):
    nets = np.array([t.net_pnl for t in trades], dtype=float)
    if len(nets) < 2:
        return (0.0, 0.0, 1.0)
    rng = np.random.default_rng(seed)
    n = len(nets)
    means = np.array([nets[rng.integers(0, n, n)].mean() for _ in range(iters)])
    lo, hi = np.percentile(means, [2.5, 97.5])
    return (float(lo), float(hi), float(np.mean(means <= 0)))


def top_n_removed_positive(trades: list[Trade], n: int = 5) -> bool:
    if len(trades) <= n:
        return False
    rem = sorted(trades, key=lambda t: t.net_pnl, reverse=True)[n:]
    return sum(t.net_pnl for t in rem) > 0


def run(cost_multiplier: float = 2.0, base_spread: float = 0.40) -> str:
    cost_rt = base_spread * cost_multiplier
    m1 = load_m1(range(2018, 2026))
    tfdata = {tf: build_tf(m1, tf) for tf in TF_HOLD}

    grid = [(tf, don, thr) for tf in TF_HOLD for don in DONCHIAN for thr in THRESH]
    all_trades: dict[tuple, list[Trade]] = {}
    for (tf, don, thr) in grid:
        all_trades[(tf, don, thr)] = simulate(tfdata[tf], don, thr, TF_HOLD[tf], cost_rt)

    L: list[str] = []
    L.append("=" * 80)
    L.append("TEST 3b: HARDENED VOLATILITY-REGIME BREAKOUT (walk-forward)")
    L.append("=" * 80)
    L.append(f"M1 bars: {len(m1):,}  range {m1.index.min()} -> {m1.index.max()}")
    L.append(f"Cost RT @ {cost_multiplier}x spread: {cost_rt:.2f} pts")
    L.append(f"Grid: {len(grid)} configs (incl. unfiltered)  | select by train avg/trade, min {MIN_TRAIN_TRADES} trades")
    L.append("")

    # ---------- WALK-FORWARD ----------
    L.append("--- WALK-FORWARD (config chosen on years < Y, traded in year Y) ---")
    L.append(f"{'year':>5} {'picked config':>22} {'n':>4} {'net':>8} {'avg':>7} {'train_avg':>9}")
    wf_trades: list[Trade] = []
    picks: list[tuple] = []
    for Y in TEST_YEARS:
        best_cfg = None
        best_train_avg = -1e18
        for cfg in grid:
            train = [t for t in all_trades[cfg] if t.year < Y]
            if len(train) < MIN_TRAIN_TRADES:
                continue
            a = summarize(train)["avg"]
            if a > best_train_avg:
                best_train_avg = a
                best_cfg = cfg
        if best_cfg is None:
            continue
        test = [t for t in all_trades[best_cfg] if t.year == Y]
        wf_trades.extend(test)
        picks.append(best_cfg)
        s = summarize(test)
        tf, don, thr = best_cfg
        cfg_str = f"{tf} don{don} thr{thr if thr is not None else 'OFF'}"
        L.append(f"{Y:>5} {cfg_str:>22} {s['n']:>4} {s['net']:>8.1f} {s['avg']:>7.3f} {best_train_avg:>9.3f}")

    wf = summarize(wf_trades)
    wf_year = per_year(wf_trades)
    mdd = max_drawdown(wf_trades)
    lo, hi, p_le0 = bootstrap_ci(wf_trades)
    n_filter_picks = sum(1 for c in picks if c[2] is not None)

    L.append("")
    L.append("--- WALK-FORWARD EQUITY (true out-of-sample, 2020-2025) ---")
    L.append(f"trades={wf['n']}  net={wf['net']:.1f}  avg={wf['avg']:.3f}  win%={wf['win_pct']:.1f}  "
             f"t={wf['t']:.2f}  edge(avg/std)={wf['edge']:.3f}  maxDD={mdd:.1f}")
    L.append(f"bootstrap 95% CI on mean net: [{lo:.3f}, {hi:.3f}]  p(mean<=0)={p_le0:.3f}")
    L.append(f"per-year net: " + " ".join(f"{y}={v:+.0f}" for y, v in wf_year.items()))
    L.append(f"filter selected in {n_filter_picks}/{len(picks)} walk-forward years")

    # concentration
    pos_years = sum(1 for v in wf_year.values() if v > 0)
    best_year = max(wf_year.items(), key=lambda kv: kv[1]) if wf_year else (None, 0.0)
    best_year_share = (best_year[1] / wf["net"]) if wf["net"] > 0 else float("inf")
    wf_ex_best = [t for t in wf_trades if t.year != best_year[0]]
    s_ex = summarize(wf_ex_best)
    top5 = top_n_removed_positive(wf_trades, 5)

    L.append("")
    L.append("--- CONCENTRATION ---")
    L.append(f"positive years: {pos_years}/{len(wf_year)}")
    L.append(f"best year {best_year[0]} = {best_year[1]:+.1f}  ({best_year_share*100:.0f}% of WF net)")
    L.append(f"WF net excluding best year: {s_ex['net']:+.1f} (n={s_ex['n']}, avg={s_ex['avg']:.3f})")
    L.append(f"top-5 trades removed still positive: {top5}")

    # ---------- FILTER CONTRIBUTION ----------
    L.append("")
    L.append("--- FILTER CONTRIBUTION (full sample, matched configs) ---")
    L.append(f"{'tf':>3} {'don':>4} | {'filt thr':>8} {'f_net':>8} {'f_avg':>7} {'f_t':>5} | "
             f"{'unf_net':>8} {'unf_avg':>7} | {'help?':>5}")
    filter_helps = 0
    filter_pairs = 0
    for tf in TF_HOLD:
        for don in DONCHIAN:
            unf = summarize(all_trades[(tf, don, None)])
            for thr in (0.25, 0.40):
                f = summarize(all_trades[(tf, don, thr)])
                helped = f["avg"] > unf["avg"]
                filter_pairs += 1
                filter_helps += int(helped)
                L.append(f"{tf:>3} {don:>4} | {thr:>8.2f} {f['net']:>8.1f} {f['avg']:>7.3f} {f['t']:>5.2f} | "
                         f"{unf['net']:>8.1f} {unf['avg']:>7.3f} | {'yes' if helped else 'no':>5}")
    L.append(f"filter improves avg/trade in {filter_helps}/{filter_pairs} matched pairs")

    # ---------- VERDICT ----------
    kills: list[str] = []
    if wf["net"] <= 0:
        kills.append("walk-forward net <= 0")
    if wf["avg"] <= 0:
        kills.append("walk-forward avg/trade <= 0")
    if wf["t"] < 1.0:
        kills.append(f"walk-forward t-stat {wf['t']:.2f} < 1.0 (not distinguishable from 0)")
    if best_year_share > 0.5:
        kills.append(f"one year ({best_year[0]}) = {best_year_share*100:.0f}% of WF net (>50%)")
    if s_ex["net"] <= 0:
        kills.append("removing best year flips WF net <= 0")
    if pos_years < len(wf_year) / 2:
        kills.append(f"only {pos_years}/{len(wf_year)} WF years positive")
    if not top5:
        kills.append("removing top-5 WF trades flips net <= 0")

    L.append("")
    L.append("=" * 80)
    if kills:
        L.append("VERDICT: FAIL (does not survive walk-forward / concentration)")
        for k in kills:
            L.append(f"  - {k}")
    else:
        L.append("VERDICT: PASS — survives walk-forward and concentration gates")
    L.append("=" * 80)

    # honest note on the hypothesis vs the residual edge
    L.append("")
    if filter_helps <= filter_pairs / 2:
        L.append("NOTE: compression filter does NOT robustly help — residual edge (if any) is")
        L.append("plain breakout momentum, not the volatility-regime hypothesis as stated.")

    report = "\n".join(L)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / "test3b_vol_breakout_hardened.txt"
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
