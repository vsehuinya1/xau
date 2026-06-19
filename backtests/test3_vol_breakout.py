"""
Test 3: Volatility Regime Breakout.

Hypothesis: gold trends when volatility EXPANDS after COMPRESSION. The edge is
not the breakout itself but the compression filter ("don't trade chop").

So the decisive control is filtered-vs-unfiltered: a Donchian breakout taken
only after a low-ATR-percentile regime, compared against the same breakout with
no vol filter. If the filter does not improve expectancy across a sensible
parameter grid, the hypothesis is dead even if breakouts themselves make money.

Falsification:
  KILL #1: filtered net <= 0 after cost in the majority of grid configs
  KILL #2: filter fails to improve avg/trade in >= half the configs (core claim)
  KILL #3: best config out-of-sample (2022-2025) avg <= 0
  KILL #4: best config top-5 trade removal flips PnL negative
  KILL #5: filtered signal does not beat a random-entry control
"""

from __future__ import annotations

import argparse
import random
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"

TIMEFRAMES = {"1h": 24, "4h": 12}      # timeframe -> fixed hold in bars
DONCHIAN = [20, 50]
THRESH = [0.25, 0.40]                   # ATR-percentile compression cutoff
ATR_PERIOD = {"1h": 24, "4h": 12}
PCTILE_LOOKBACK = {"1h": 240, "4h": 120}


@dataclass
class Trade:
    entry_ts: pd.Timestamp
    direction: int
    net_pnl: float
    gross_pnl: float


def load_m1(years: range) -> pd.DataFrame:
    frames = []
    for year in years:
        path = DATA_DIR / f"DAT_ASCII_XAUUSD_M1_{year}.csv"
        if not path.exists():
            raise FileNotFoundError(f"missing {path}")
        df = pd.read_csv(
            path, sep=";", header=None,
            names=["dt_str", "open", "high", "low", "close", "volume"],
        )
        naive = pd.to_datetime(df["dt_str"], format="%Y%m%d %H%M%S")
        df["ts"] = naive.dt.tz_localize("Etc/GMT+5").dt.tz_convert("UTC")
        frames.append(df[["ts", "open", "high", "low", "close"]])
    m1 = pd.concat(frames, ignore_index=True).sort_values("ts").drop_duplicates("ts")
    return m1.set_index("ts")


def resample(m1: pd.DataFrame, rule: str) -> pd.DataFrame:
    o = m1["open"].resample(rule).first()
    h = m1["high"].resample(rule).max()
    l = m1["low"].resample(rule).min()
    c = m1["close"].resample(rule).last()
    out = pd.DataFrame({"open": o, "high": h, "low": l, "close": c}).dropna()
    return out


def atr(df: pd.DataFrame, period: int) -> pd.Series:
    pc = df["close"].shift(1)
    tr = pd.concat(
        [df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period).mean()


def atr_percentile(atr_series: pd.Series, lookback: int) -> np.ndarray:
    vals = atr_series.to_numpy(dtype=float)
    out = np.full(len(vals), np.nan)
    for i in range(len(vals)):
        if i + 1 < lookback or np.isnan(vals[i]):
            continue
        w = vals[i - lookback + 1 : i + 1]
        if np.isnan(w).any():
            continue
        out[i] = float((w <= vals[i]).mean())
    return out


def simulate(
    df: pd.DataFrame,
    don_n: int,
    thresh: float,
    hold: int,
    atr_p: int,
    pctile_lb: int,
    cost_rt: float,
    filtered: bool,
) -> list[Trade]:
    high = df["high"].to_numpy(float)
    low = df["low"].to_numpy(float)
    close = df["close"].to_numpy(float)
    open_ = df["open"].to_numpy(float)
    ts = df.index

    upper = df["high"].rolling(don_n).max().shift(1).to_numpy(float)
    lower = df["low"].rolling(don_n).min().shift(1).to_numpy(float)
    pct = atr_percentile(atr(df, atr_p), pctile_lb)

    trades: list[Trade] = []
    n = len(df)
    i = max(don_n, atr_p, pctile_lb) + 1
    while i < n - 1:
        if np.isnan(upper[i]) or np.isnan(lower[i]):
            i += 1
            continue

        direction = 0
        if close[i] > upper[i]:
            direction = 1
        elif close[i] < lower[i]:
            direction = -1
        if direction == 0:
            i += 1
            continue

        if filtered:
            if np.isnan(pct[i - 1]) or pct[i - 1] >= thresh:
                i += 1
                continue

        entry_i = i + 1
        exit_i = entry_i + hold
        if exit_i >= n:
            break
        entry_px = open_[entry_i]
        exit_px = close[exit_i]
        gross = direction * (exit_px - entry_px)
        trades.append(Trade(ts[entry_i], direction, gross - cost_rt, gross))
        i = exit_i + 1  # cooldown until exit
    return trades


def random_entry_control(
    df: pd.DataFrame, hold: int, cost_rt: float, n_trades: int, seed: int = 11
) -> list[Trade]:
    rng = random.Random(seed)
    open_ = df["open"].to_numpy(float)
    close = df["close"].to_numpy(float)
    ts = df.index
    n = len(df)
    trades: list[Trade] = []
    for _ in range(n_trades):
        entry_i = rng.randint(50, n - hold - 2)
        direction = rng.choice([1, -1])
        gross = direction * (close[entry_i + hold] - open_[entry_i])
        trades.append(Trade(ts[entry_i], direction, gross - cost_rt, gross))
    return trades


def summarize(trades: list[Trade]) -> dict:
    if not trades:
        return {"n": 0, "net": 0.0, "avg": 0.0, "win_pct": 0.0, "t": 0.0}
    nets = np.array([t.net_pnl for t in trades], dtype=float)
    t = 0.0
    if len(nets) > 1 and nets.std(ddof=1) > 0:
        t = float(nets.mean() / (nets.std(ddof=1) / np.sqrt(len(nets))))
    return {
        "n": len(trades),
        "net": float(nets.sum()),
        "avg": float(nets.mean()),
        "win_pct": 100.0 * float((nets > 0).mean()),
        "t": t,
    }


def oos_split(trades: list[Trade]) -> tuple[dict, dict]:
    tr = [t for t in trades if t.entry_ts.year <= 2021]
    te = [t for t in trades if t.entry_ts.year >= 2022]
    return summarize(tr), summarize(te)


def top_n_removed_positive(trades: list[Trade], n: int = 5) -> bool:
    if len(trades) <= n:
        return False
    rem = sorted(trades, key=lambda t: t.net_pnl, reverse=True)[n:]
    return sum(t.net_pnl for t in rem) > 0


def run(cost_multiplier: float = 2.0, base_spread: float = 0.40) -> str:
    cost_rt = base_spread * cost_multiplier
    m1 = load_m1(range(2018, 2026))

    L: list[str] = []
    L.append("=" * 78)
    L.append("TEST 3: VOLATILITY REGIME BREAKOUT (filtered vs unfiltered)")
    L.append("=" * 78)
    L.append(f"M1 bars: {len(m1):,}  range {m1.index.min()} -> {m1.index.max()}")
    L.append(f"Cost RT @ {cost_multiplier}x spread: {cost_rt:.2f} pts")
    L.append("")
    L.append(f"{'tf':>3} {'don':>4} {'thr':>5} {'hold':>4} | "
             f"{'filt_n':>6} {'filt_net':>9} {'filt_avg':>8} {'filt_t':>6} | "
             f"{'unf_n':>6} {'unf_net':>9} {'unf_avg':>8} | {'delta_avg':>9}")

    grid = []
    cache: dict[tuple, pd.DataFrame] = {}
    for tf, hold in TIMEFRAMES.items():
        if tf not in cache:
            cache[tf] = resample(m1, tf)
        df = cache[tf]
        for don in DONCHIAN:
            for thr in THRESH:
                filt = simulate(df, don, thr, hold, ATR_PERIOD[tf], PCTILE_LOOKBACK[tf], cost_rt, True)
                unf = simulate(df, don, thr, hold, ATR_PERIOD[tf], PCTILE_LOOKBACK[tf], cost_rt, False)
                sf, su = summarize(filt), summarize(unf)
                delta = sf["avg"] - su["avg"]
                grid.append({
                    "tf": tf, "don": don, "thr": thr, "hold": hold,
                    "filt": filt, "unf": unf, "sf": sf, "su": su, "delta": delta,
                })
                L.append(
                    f"{tf:>3} {don:>4} {thr:>5.2f} {hold:>4} | "
                    f"{sf['n']:>6} {sf['net']:>9.1f} {sf['avg']:>8.3f} {sf['t']:>6.2f} | "
                    f"{su['n']:>6} {su['net']:>9.1f} {su['avg']:>8.3f} | {delta:>9.3f}"
                )

    L.append("")
    # Aggregate the core claim: does the compression filter help?
    helps = sum(1 for g in grid if g["delta"] > 0)
    filt_pos = sum(1 for g in grid if g["sf"]["net"] > 0)
    L.append(f"Configs where filter improves avg/trade: {helps}/{len(grid)}")
    L.append(f"Configs where filtered net > 0 after cost: {filt_pos}/{len(grid)}")
    L.append("")

    best = max(grid, key=lambda g: g["sf"]["avg"])
    L.append(f"--- BEST FILTERED CONFIG: {best['tf']} don={best['don']} thr={best['thr']} hold={best['hold']} ---")
    sf = best["sf"]
    L.append(f"filtered:   n={sf['n']:4d} net={sf['net']:9.1f} avg={sf['avg']:7.3f} win%={sf['win_pct']:5.1f} t={sf['t']:.2f}")
    su = best["su"]
    L.append(f"unfiltered: n={su['n']:4d} net={su['net']:9.1f} avg={su['avg']:7.3f} win%={su['win_pct']:5.1f}")

    df_best = cache[best["tf"]]
    rc = random_entry_control(df_best, best["hold"], cost_rt, max(sf["n"], 200))
    src = summarize(rc)
    L.append(f"rand-entry: n={src['n']:4d} net={src['net']:9.1f} avg={src['avg']:7.3f} win%={src['win_pct']:5.1f}")

    s_tr, s_te = oos_split(best["filt"])
    L.append("")
    L.append("--- OOS SPLIT (best filtered config) ---")
    L.append(f"TRAIN 2018-2021: n={s_tr['n']:4d} net={s_tr['net']:9.1f} avg={s_tr['avg']:7.3f}")
    L.append(f"TEST  2022-2025: n={s_te['n']:4d} net={s_te['net']:9.1f} avg={s_te['avg']:7.3f}")

    yearly: dict[int, float] = {}
    for t in best["filt"]:
        yearly[t.entry_ts.year] = yearly.get(t.entry_ts.year, 0.0) + t.net_pnl
    L.append("")
    L.append("--- YEAR-BY-YEAR NET (best filtered config) ---")
    L.append(" ".join(f"{y}={v:+.0f}" for y, v in sorted(yearly.items())))

    top5 = top_n_removed_positive(best["filt"], 5)
    L.append("")
    L.append(f"Top-5-removed still positive (best filtered): {top5}")
    L.append("")

    kills: list[str] = []
    if filt_pos < len(grid) / 2:
        kills.append(f"filtered net <= 0 in majority of configs ({filt_pos}/{len(grid)} positive)")
    if helps < len(grid) / 2:
        kills.append(f"compression filter improves avg in only {helps}/{len(grid)} configs (core claim fails)")
    if s_te["avg"] <= 0:
        kills.append("best config out-of-sample (2022-2025) avg <= 0")
    if not top5:
        kills.append("best config: removing top 5 trades flips PnL negative")
    if src["avg"] >= sf["avg"]:
        kills.append("random-entry control matches/beats filtered signal")

    L.append("=" * 78)
    if kills:
        L.append("VERDICT: FAIL")
        for k in kills:
            L.append(f"  - {k}")
    else:
        L.append("VERDICT: PASS (provisional — compression filter adds robust edge)")
    L.append("=" * 78)

    report = "\n".join(L)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / "test3_vol_breakout.txt"
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
