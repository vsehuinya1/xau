"""
Test 4: Real-yield / USD lead-lag.

Gold is mechanically tied to USD. But contemporaneous co-movement is NOT an edge
(you can't trade a move that already happened). The hypothesis only pays if PAST
USD moves PREDICT FUTURE gold moves -- i.e. gold genuinely *lags* USD by minutes.

So the decisive statistic is the lead-lag information coefficient:
    IC(k,h) = corr( USD-strength return over the past k bars ,
                    gold return over the NEXT h bars )
with a strictly lagged, no-lookahead backtest on top (enter the bar AFTER the USD
move is known). We also compute the REVERSE IC (does gold lead USD instead?) to
locate causality, and a contemporaneous corr as a data/sign sanity check.

USD strength proxy (5-min returns, equal weight): -EURUSD, +USDJPY, -GBPUSD
(~83% of DXY weight). All series use the same histdata EST->UTC pipeline as gold,
so alignment is exact.

Hardened gates (same bar as Test 3b): walk-forward config selection, per-year
concentration, random-sign control, cost sensitivity, bootstrap CI.

Note: intraday *real yields* are not freely available; USD is the dominant and
cleanly-testable intraday channel. A daily real-yield check is a separate follow-up.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"

RESAMPLE = "5min"
# pair -> sign for USD strength (USD up = +)
USD_LEGS = {"EURUSD": -1, "USDJPY": +1, "GBPUSD": -1}

K_GRID = [1, 3, 6]          # lookback bars (5,15,30 min)
H_GRID = [3, 6, 12]         # forward hold bars (15,30,60 min)
THR_GRID = [0.0, 1.5]       # z-score threshold on the USD move (0 = trade every bar)
Z_LOOKBACK = 2000
TEST_YEARS = [2020, 2021, 2022, 2023, 2024, 2025]
MIN_TRAIN_TRADES = 100


@dataclass
class Trade:
    entry_ts: object
    year: int
    direction: int
    net_pnl: float
    gross_pnl: float


def _read_m1(pair: str, years: range) -> pd.DataFrame:
    frames = []
    for year in years:
        path = DATA_DIR / f"DAT_ASCII_{pair.upper()}_M1_{year}.csv"
        if not path.exists():
            raise FileNotFoundError(f"missing {path}")
        df = pd.read_csv(path, sep=";", header=None,
                         names=["dt_str", "open", "high", "low", "close", "volume"])
        naive = pd.to_datetime(df["dt_str"], format="%Y%m%d %H%M%S")
        df["ts"] = naive.dt.tz_localize("Etc/GMT+5").dt.tz_convert("UTC")
        frames.append(df[["ts", "open", "high", "low", "close"]])
    m1 = pd.concat(frames, ignore_index=True).sort_values("ts").drop_duplicates("ts")
    return m1.set_index("ts")


def close_5min(pair: str, years: range) -> pd.Series:
    c = _read_m1(pair, years)["close"].resample(RESAMPLE).last().dropna()
    c.name = pair.upper()
    return c


def gold_5min(years: range) -> pd.DataFrame:
    m1 = _read_m1("XAUUSD", years)
    o = m1["open"].resample(RESAMPLE).first()
    c = m1["close"].resample(RESAMPLE).last()
    return pd.DataFrame({"g_open": o, "g_close": c}).dropna()


def build_panel(years: range) -> pd.DataFrame:
    gold = gold_5min(years)
    usd_ret = None
    for pair, sign in USD_LEGS.items():
        r = close_5min(pair, years).pct_change() * sign
        usd_ret = r if usd_ret is None else usd_ret.add(r, fill_value=np.nan)
    usd_ret = usd_ret / len(USD_LEGS)
    usd_ret.name = "usd_ret"

    panel = gold.join(usd_ret, how="inner").dropna()
    panel["g_ret"] = panel["g_close"].pct_change()
    panel = panel.dropna()
    return panel


def summarize(trades: list[Trade]) -> dict:
    if not trades:
        return {"n": 0, "net": 0.0, "avg": 0.0, "win_pct": 0.0, "t": 0.0}
    nets = np.array([t.net_pnl for t in trades], dtype=float)
    sd = nets.std(ddof=1) if len(nets) > 1 else 0.0
    t = float(nets.mean() / (sd / np.sqrt(len(nets)))) if sd > 0 else 0.0
    return {"n": len(trades), "net": float(nets.sum()), "avg": float(nets.mean()),
            "win_pct": 100.0 * float((nets > 0).mean()), "t": t}


def per_year(trades: list[Trade]) -> dict[int, float]:
    out: dict[int, float] = {}
    for t in trades:
        out[t.year] = out.get(t.year, 0.0) + t.net_pnl
    return dict(sorted(out.items()))


def top_n_removed_positive(trades: list[Trade], n: int = 5) -> bool:
    if len(trades) <= n:
        return False
    rem = sorted(trades, key=lambda t: t.net_pnl, reverse=True)[n:]
    return sum(t.net_pnl for t in rem) > 0


def bootstrap_ci(trades: list[Trade], iters: int = 5000, seed: int = 7):
    nets = np.array([t.net_pnl for t in trades], dtype=float)
    if len(nets) < 2:
        return (0.0, 0.0, 1.0)
    rng = np.random.default_rng(seed)
    n = len(nets)
    means = np.array([nets[rng.integers(0, n, n)].mean() for _ in range(iters)])
    lo, hi = np.percentile(means, [2.5, 97.5])
    return (float(lo), float(hi), float(np.mean(means <= 0)))


def simulate(panel: pd.DataFrame, k: int, h: int, thr: float, cost_rt: float,
             random_sign: bool = False, seed: int = 0) -> list[Trade]:
    g_open = panel["g_open"].to_numpy(float)
    g_close = panel["g_close"].to_numpy(float)
    usd_k = panel["usd_ret"].rolling(k).sum().to_numpy(float)
    if thr > 0:
        z = panel["usd_ret"].rolling(k).sum()
        z = (z / z.rolling(Z_LOOKBACK).std()).to_numpy(float)
    else:
        z = None
    years = panel.index.year.to_numpy()
    ts = panel.index
    n = len(panel)
    rng = np.random.default_rng(seed)

    trades: list[Trade] = []
    warmup = max(k, Z_LOOKBACK if thr > 0 else k) + 1
    i = warmup
    while i < n - h - 1:
        s = usd_k[i]
        if np.isnan(s) or s == 0:
            i += 1
            continue
        if thr > 0:
            if np.isnan(z[i]) or abs(z[i]) < thr:
                i += 1
                continue
        # gold lags USD: USD up over past k -> gold down next -> short gold
        direction = -int(np.sign(s))
        if random_sign:
            direction = int(rng.choice([-1, 1]))
        entry_i = i + 1
        exit_i = entry_i + h
        if exit_i >= n:
            break
        gross = direction * (g_close[exit_i] - g_open[entry_i])
        trades.append(Trade(ts[entry_i], int(years[entry_i]), direction, gross - cost_rt, gross))
        i = exit_i + 1
    return trades


def ic_table(panel: pd.DataFrame) -> list[str]:
    out: list[str] = []
    usd = panel["usd_ret"]
    g = panel["g_ret"]

    contemp = float(np.corrcoef(g.to_numpy(), usd.to_numpy())[0, 1])
    out.append(f"Contemporaneous corr(gold_ret, usd_strength_ret) = {contemp:+.4f}   "
               f"(expect strongly negative; sanity that data/sign are correct)")
    out.append("")
    out.append("Lead-lag IC = corr(past-k USD strength, next-h gold return).")
    out.append("If gold lags USD, FORWARD IC should be NEGATIVE and clearly beat REVERSE.")
    out.append(f"{'k':>3} {'h':>3} {'fwd_IC(USD->gold)':>18} {'rev_IC(gold->USD)':>18} {'fwd_IC sign by yr':>22}")
    for k in K_GRID:
        usd_k = usd.rolling(k).sum()
        g_k = g.rolling(k).sum()
        for h in H_GRID:
            g_fwd = g.shift(-h).rolling(h).sum()      # next-h gold return (approx; leads via shift)
            usd_fwd = usd.shift(-h).rolling(h).sum()
            d = pd.DataFrame({"uk": usd_k, "gf": g_fwd, "gk": g_k, "uf": usd_fwd}).dropna()
            fwd = float(np.corrcoef(d["uk"], d["gf"])[0, 1])
            rev = float(np.corrcoef(d["gk"], d["uf"])[0, 1])
            # per-year sign consistency of forward IC
            signs = []
            for y, grp in d.assign(yr=d.index.year).groupby("yr"):
                if len(grp) > 100:
                    r = np.corrcoef(grp["uk"], grp["gf"])[0, 1]
                    signs.append("-" if r < 0 else "+")
            out.append(f"{k:>3} {h:>3} {fwd:>18.4f} {rev:>18.4f} {''.join(signs):>22}")
    return out


def run(cost_multiplier: float = 2.0, base_spread: float = 0.40) -> str:
    cost_rt = base_spread * cost_multiplier
    panel = build_panel(range(2018, 2026))

    L: list[str] = []
    L.append("=" * 82)
    L.append("TEST 4: USD LEAD-LAG (does past USD move predict future gold move?)")
    L.append("=" * 82)
    L.append(f"5-min bars (aligned): {len(panel):,}  range {panel.index.min()} -> {panel.index.max()}")
    L.append(f"USD proxy legs: {USD_LEGS}")
    L.append(f"Cost RT @ {cost_multiplier}x spread: {cost_rt:.2f} pts")
    L.append("")
    L.append("--- LEAD-LAG INFORMATION COEFFICIENTS ---")
    L.extend(ic_table(panel))
    L.append("")

    # full-sample grid
    grid = [(k, h, thr) for k in K_GRID for h in H_GRID for thr in THR_GRID]
    all_trades: dict[tuple, list[Trade]] = {}
    L.append("--- GRID BACKTEST (lagged, no-lookahead; net after cost) ---")
    L.append(f"{'k':>3} {'h':>3} {'thr':>4} {'n':>6} {'net':>9} {'avg':>8} {'win%':>6} {'t':>6}")
    for cfg in grid:
        k, h, thr = cfg
        tr = simulate(panel, k, h, thr, cost_rt)
        all_trades[cfg] = tr
        s = summarize(tr)
        L.append(f"{k:>3} {h:>3} {thr:>4.1f} {s['n']:>6} {s['net']:>9.1f} {s['avg']:>8.4f} {s['win_pct']:>6.1f} {s['t']:>6.2f}")
    L.append("")

    # walk-forward selection
    L.append("--- WALK-FORWARD (select k,h,thr on years<Y by train avg, trade year Y) ---")
    L.append(f"{'year':>5} {'picked (k,h,thr)':>18} {'n':>5} {'net':>9} {'avg':>8} {'train_avg':>9}")
    wf: list[Trade] = []
    for Y in TEST_YEARS:
        best_cfg, best_a = None, -1e18
        for cfg in grid:
            train = [t for t in all_trades[cfg] if t.year < Y]
            if len(train) < MIN_TRAIN_TRADES:
                continue
            a = summarize(train)["avg"]
            if a > best_a:
                best_a, best_cfg = a, cfg
        if best_cfg is None:
            continue
        test = [t for t in all_trades[best_cfg] if t.year == Y]
        wf.extend(test)
        s = summarize(test)
        L.append(f"{Y:>5} {str(best_cfg):>18} {s['n']:>5} {s['net']:>9.1f} {s['avg']:>8.4f} {best_a:>9.4f}")

    swf = summarize(wf)
    wf_year = per_year(wf)
    lo, hi, p_le0 = bootstrap_ci(wf)
    pos_years = sum(1 for v in wf_year.values() if v > 0)
    best_year = max(wf_year.items(), key=lambda kv: kv[1]) if wf_year else (None, 0.0)
    share = (best_year[1] / swf["net"]) if swf["net"] > 0 else float("inf")
    wf_ex = summarize([t for t in wf if t.year != best_year[0]])
    top5 = top_n_removed_positive(wf, 5)

    L.append("")
    L.append("--- WALK-FORWARD EQUITY (true OOS 2020-2025) ---")
    L.append(f"trades={swf['n']} net={swf['net']:.1f} avg={swf['avg']:.4f} win%={swf['win_pct']:.1f} t={swf['t']:.2f}")
    L.append(f"bootstrap 95% CI mean net: [{lo:.4f}, {hi:.4f}]  p(mean<=0)={p_le0:.3f}")
    L.append("per-year: " + " ".join(f"{y}={v:+.0f}" for y, v in wf_year.items()))
    L.append(f"positive years {pos_years}/{len(wf_year)}; best year {best_year[0]}={best_year[1]:+.0f} ({share*100:.0f}% of net)")
    L.append(f"net excl. best year: {wf_ex['net']:+.1f}; top-5 removed positive: {top5}")

    # cost sensitivity + random control on best full-sample config
    best_full = max(grid, key=lambda c: summarize(all_trades[c])["net"])
    L.append("")
    L.append(f"--- COST SENSITIVITY (best full-sample config {best_full}) ---")
    for mult in (0.0, 1.0, 2.0, 3.0):
        c = base_spread * mult
        s = summarize(simulate(panel, *best_full, c))
        L.append(f"{mult:>3.0f}x (RT={c:.2f}): net={s['net']:9.1f} avg={s['avg']:8.4f}")
    rc = summarize(simulate(panel, *best_full, cost_rt, random_sign=True, seed=3))
    sc = summarize(all_trades[best_full])
    L.append(f"random-sign control: net={rc['net']:9.1f} avg={rc['avg']:8.4f}  (signal avg={sc['avg']:.4f})")

    # verdict
    kills: list[str] = []
    if swf["net"] <= 0:
        kills.append("walk-forward net <= 0")
    if swf["avg"] <= 0:
        kills.append("walk-forward avg/trade <= 0")
    if swf["t"] < 1.0:
        kills.append(f"walk-forward t-stat {swf['t']:.2f} < 1.0")
    if share > 0.5:
        kills.append(f"one year ({best_year[0]}) = {share*100:.0f}% of WF net")
    if wf_ex["net"] <= 0:
        kills.append("removing best year flips WF net <= 0")
    if pos_years < len(wf_year) / 2:
        kills.append(f"only {pos_years}/{len(wf_year)} WF years positive")
    if not top5:
        kills.append("removing top-5 WF trades flips net <= 0")
    if rc["avg"] >= sc["avg"]:
        kills.append("random-sign control matches/beats the USD signal")

    L.append("")
    L.append("=" * 82)
    if kills:
        L.append("VERDICT: FAIL")
        for k_ in kills:
            L.append(f"  - {k_}")
    else:
        L.append("VERDICT: PASS (provisional — exploitable USD->gold lag)")
    L.append("=" * 82)
    L.append("")
    L.append("Reminder: a strong contemporaneous corr with a near-zero lead-lag IC means")
    L.append("gold and USD move TOGETHER, leaving no lag to trade -- the efficient-market null.")

    report = "\n".join(L)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / "test4_usd_leadlag.txt"
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
