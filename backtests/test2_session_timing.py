"""
Test 2: Session / Time-of-Day Behavior
Falsification suite for recurring liquidity-window edges on XAUUSD.
"""

from __future__ import annotations

import argparse
import random
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

UTC = ZoneInfo("UTC")
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"

# Key session anchors (UTC). Histdata timestamps are GMT/UTC.
SESSION_ANCHORS = {
    "asia_open": time(0, 0),
    "london_open": time(7, 0),
    "london_fix_am": time(10, 30),
    "ny_open": time(13, 30),
    "us_data_window": time(12, 30),
    "london_fix_pm": time(15, 0),
    "ny_close": time(21, 0),
}

# Prior-session lookback windows used for range definition (hours before anchor).
PRIOR_WINDOWS_H = {
    "asia_open": 7,       # 17:00 prev day -> 00:00 (approx prior NY)
    "london_open": 7,     # 00:00 -> 07:00 Asia
    "london_fix_am": 3,   # 07:30 -> 10:30
    "ny_open": 6,         # 07:30 -> 13:30 London morning
    "us_data_window": 4,  # 08:30 -> 12:30
    "london_fix_pm": 2,   # 13:00 -> 15:00
    "ny_close": 8,        # 13:00 -> 21:00 NY session
}

HOLD_MINUTES = [30, 60, 120]
ORB_MINUTES = 30
FAIL_REVERT_MINUTES = 15


@dataclass
class Trade:
    strategy: str
    session: str
    entry_ts: datetime
    exit_ts: datetime
    direction: int
    gross_pnl: float
    net_pnl: float
    hold_min: int


def load_bars(years: range) -> pd.DataFrame:
    frames = []
    for year in years:
        path = DATA_DIR / f"DAT_ASCII_XAUUSD_M1_{year}.csv"
        if not path.exists():
            raise FileNotFoundError(f"missing {path}")
        df = pd.read_csv(
            path, sep=";", header=None,
            names=["dt_str", "open", "high", "low", "close", "volume"],
        )
        df["ts"] = pd.to_datetime(df["dt_str"], format="%Y%m%d %H%M%S", utc=True)
        frames.append(df[["ts", "open", "high", "low", "close"]])
    bars = pd.concat(frames, ignore_index=True).sort_values("ts")
    return bars.drop_duplicates("ts").set_index("ts")


def slice_window(bars: pd.DataFrame, start: datetime, end: datetime) -> pd.DataFrame:
    return bars[(bars.index >= start) & (bars.index < end)]


def range_hi_lo(win: pd.DataFrame) -> tuple[float, float] | None:
    if win.empty:
        return None
    return float(win["high"].max()), float(win["low"].min())


def price_at(bars: pd.DataFrame, ts: datetime, col: str = "open") -> float | None:
    idx = bars.index.searchsorted(ts)
    if idx >= len(bars):
        return None
    return float(bars.iloc[idx][col])


def make_trade(
    strategy: str,
    session: str,
    entry_ts: datetime,
    direction: int,
    entry_px: float,
    exit_px: float,
    hold_min: int,
    cost_rt: float,
) -> Trade:
    gross = direction * (exit_px - entry_px)
    return Trade(
        strategy=strategy,
        session=session,
        entry_ts=entry_ts,
        exit_ts=entry_ts + timedelta(minutes=hold_min),
        direction=direction,
        gross_pnl=gross,
        net_pnl=gross - cost_rt,
        hold_min=hold_min,
    )


def session_breakout(
    bars: pd.DataFrame,
    day: datetime,
    session: str,
    anchor: time,
    lookback_h: int,
    hold_min: int,
    cost_rt: float,
) -> Trade | None:
    anchor_ts = datetime.combine(day.date(), anchor, tzinfo=UTC)
    prior_start = anchor_ts - timedelta(hours=lookback_h)
    prior = slice_window(bars, prior_start, anchor_ts)
    rng = range_hi_lo(prior)
    if rng is None:
        return None
    hi, lo = rng

    post = slice_window(bars, anchor_ts, anchor_ts + timedelta(minutes=30))
    if post.empty:
        return None

    direction = 0
    entry_ts = None
    for ts, row in post.iterrows():
        if row["close"] > hi:
            direction = 1
            entry_ts = ts
            break
        if row["close"] < lo:
            direction = -1
            entry_ts = ts
            break
    if direction == 0 or entry_ts is None:
        return None

    entry_px = float(post.loc[entry_ts, "close"])
    exit_ts = entry_ts + timedelta(minutes=hold_min)
    exit_px = price_at(bars, exit_ts, "close")
    if exit_px is None:
        return None
    return make_trade("session_breakout", session, entry_ts, direction, entry_px, exit_px, hold_min, cost_rt)


def opening_range_breakout(
    bars: pd.DataFrame,
    day: datetime,
    session: str,
    anchor: time,
    hold_min: int,
    cost_rt: float,
) -> Trade | None:
    anchor_ts = datetime.combine(day.date(), anchor, tzinfo=UTC)
    orb_end = anchor_ts + timedelta(minutes=ORB_MINUTES)
    orb = slice_window(bars, anchor_ts, orb_end)
    if len(orb) < 10:
        return None
    hi, lo = float(orb["high"].max()), float(orb["low"].min())
    if hi <= lo:
        return None

    post = slice_window(bars, orb_end, orb_end + timedelta(minutes=60))
    direction = 0
    entry_ts = None
    for ts, row in post.iterrows():
        if row["close"] > hi:
            direction = 1
            entry_ts = ts
            break
        if row["close"] < lo:
            direction = -1
            entry_ts = ts
            break
    if direction == 0 or entry_ts is None:
        return None

    entry_px = float(post.loc[entry_ts, "close"])
    exit_px = price_at(bars, entry_ts + timedelta(minutes=hold_min), "close")
    if exit_px is None:
        return None
    return make_trade("orb", session, entry_ts, direction, entry_px, exit_px, hold_min, cost_rt)


def failed_breakout_revert(
    bars: pd.DataFrame,
    day: datetime,
    session: str,
    anchor: time,
    lookback_h: int,
    hold_min: int,
    cost_rt: float,
) -> Trade | None:
    anchor_ts = datetime.combine(day.date(), anchor, tzinfo=UTC)
    prior_start = anchor_ts - timedelta(hours=lookback_h)
    prior = slice_window(bars, prior_start, anchor_ts)
    rng = range_hi_lo(prior)
    if rng is None:
        return None
    hi, lo = rng

    watch = slice_window(bars, anchor_ts, anchor_ts + timedelta(minutes=FAIL_REVERT_MINUTES + 30))
    if watch.empty:
        return None

    failed_dir = 0
    entry_ts = None
    pierced_up = False
    pierced_dn = False

    for ts, row in watch.iterrows():
        if row["high"] > hi:
            pierced_up = True
        if row["low"] < lo:
            pierced_dn = True
        if pierced_up and row["close"] < hi:
            failed_dir = -1
            entry_ts = ts
            break
        if pierced_dn and row["close"] > lo:
            failed_dir = 1
            entry_ts = ts
            break
        if ts >= anchor_ts + timedelta(minutes=FAIL_REVERT_MINUTES):
            break

    if failed_dir == 0 or entry_ts is None:
        return None

    entry_px = float(watch.loc[entry_ts, "close"])
    exit_px = price_at(bars, entry_ts + timedelta(minutes=hold_min), "close")
    if exit_px is None:
        return None
    return make_trade("failed_breakout_fade", session, entry_ts, failed_dir, entry_px, exit_px, hold_min, cost_rt)


def trading_days(bars: pd.DataFrame) -> list[datetime]:
    days = pd.Series(bars.index.date).unique()
    return [datetime.combine(d, time(0, 0), tzinfo=UTC) for d in sorted(days)]


def random_control_trade(
    bars: pd.DataFrame,
    day: datetime,
    strategy: str,
    hold_min: int,
    cost_rt: float,
    seed: int,
) -> Trade | None:
    rng = random.Random(seed)
    fake_anchor = time(rng.randint(8, 19), rng.choice([0, 15, 30, 45]))
    session = "random"
    if strategy == "session_breakout":
        return session_breakout(bars, day, session, fake_anchor, 4, hold_min, cost_rt)
    if strategy == "orb":
        return opening_range_breakout(bars, day, session, fake_anchor, hold_min, cost_rt)
    return failed_breakout_revert(bars, day, session, fake_anchor, 4, hold_min, cost_rt)


def summarize(trades: list[Trade]) -> dict:
    if not trades:
        return {"n": 0, "gross": 0.0, "net": 0.0, "avg": 0.0, "win_pct": 0.0}
    nets = [t.net_pnl for t in trades]
    return {
        "n": len(trades),
        "gross": sum(t.gross_pnl for t in trades),
        "net": sum(nets),
        "avg": float(np.mean(nets)),
        "win_pct": 100.0 * sum(1 for n in nets if n > 0) / len(nets),
    }


def by_session(trades: list[Trade]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for s in SESSION_ANCHORS:
        out[s] = summarize([t for t in trades if t.session == s])
    return out


def by_year(trades: list[Trade]) -> dict[int, float]:
    out: dict[int, float] = {}
    for t in trades:
        y = t.entry_ts.year
        out[y] = out.get(y, 0.0) + t.net_pnl
    return dict(sorted(out.items()))


def top_n_removed_positive(trades: list[Trade], n: int = 5) -> bool:
    if len(trades) <= n:
        return False
    rem = sorted(trades, key=lambda t: t.net_pnl, reverse=True)[n:]
    return sum(t.net_pnl for t in rem) > 0


def run_test(cost_multiplier: float = 2.0, base_spread: float = 0.40) -> str:
    cost_rt = base_spread * cost_multiplier
    bars = load_bars(range(2018, 2026))
    days = trading_days(bars)

    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("TEST 2: SESSION / TIME-OF-DAY BEHAVIOR")
    lines.append("=" * 60)
    lines.append(f"Data range: {bars.index.min()} -> {bars.index.max()}")
    lines.append(f"Bars: {len(bars):,}")
    lines.append(f"Trading days: {len(days):,}")
    lines.append(f"Cost RT @ {cost_multiplier}x spread: {cost_rt:.2f} pts")
    lines.append("")

    strategies = {
        "session_breakout": session_breakout,
        "orb": opening_range_breakout,
        "failed_breakout_fade": failed_breakout_revert,
    }

    all_trades: dict[str, dict[int, list[Trade]]] = {}
    controls: dict[str, dict[int, list[Trade]]] = {}

    for strat_name, strat_fn in strategies.items():
        all_trades[strat_name] = {}
        controls[strat_name] = {}
        for hold in HOLD_MINUTES:
            trades: list[Trade] = []
            ctrl: list[Trade] = []
            for i, day in enumerate(days):
                for session, anchor in SESSION_ANCHORS.items():
                    lookback = PRIOR_WINDOWS_H[session]
                    if strat_name == "session_breakout":
                        t = strat_fn(bars, day, session, anchor, lookback, hold, cost_rt)
                    elif strat_name == "orb":
                        t = strat_fn(bars, day, session, anchor, hold, cost_rt)
                    else:
                        t = strat_fn(bars, day, session, anchor, lookback, hold, cost_rt)
                    if t:
                        trades.append(t)
                for j in range(2):
                    ct = random_control_trade(bars, day, strat_name, hold, cost_rt, seed=i * 10 + j)
                    if ct:
                        ctrl.append(ct)
            all_trades[strat_name][hold] = trades
            controls[strat_name][hold] = ctrl

    lines.append("--- STRATEGY x HOLD RESULTS (60m) ---")
    best_combo = None
    best_net = -1e18
    for strat_name in strategies:
        s = summarize(all_trades[strat_name][60])
        c = summarize(controls[strat_name][60])
        lines.append(
            f"{strat_name:22s} n={s['n']:5d} net={s['net']:9.1f} avg={s['avg']:7.4f} "
            f"win%={s['win_pct']:5.1f} | control_avg={c['avg']:7.4f}"
        )
        if s["net"] > best_net:
            best_net = s["net"]
            best_combo = (strat_name, 60)

    lines.append("")
    lines.append("--- SESSION BREAKDOWN (best: session_breakout 60m) ---")
    sb60 = all_trades["session_breakout"][60]
    for session, s in by_session(sb60).items():
        if s["n"] > 0:
            lines.append(f"{session:16s} n={s['n']:4d} net={s['net']:8.1f} avg={s['avg']:7.4f}")

    lines.append("")
    lines.append("--- YEAR-BY-YEAR NET (session_breakout 60m) ---")
    yearly = by_year(sb60)
    lines.append(" ".join(f"{y}={v:+.0f}" for y, v in yearly.items()))

    lines.append("")
    lines.append("--- FALSIFICATION CHECKS ---")
    kills: list[str] = []

    positive_strats = sum(
        1 for s in strategies if summarize(all_trades[s][60])["net"] > 0
    )
    if positive_strats == 0:
        kills.append("KILL #1: all strategies negative after costs at 60m hold")

    sb = summarize(sb60)
    sb_ctrl = summarize(controls["session_breakout"][60])
    if sb_ctrl["avg"] >= sb["avg"]:
        kills.append("KILL #2: random-time control matches/beats session signals")

    profitable_sessions = sum(1 for s in by_session(sb60).values() if s["net"] > 0)
    if profitable_sessions < 2:
        kills.append("KILL #3: edge concentrated in <2 session buckets")

    y18_21 = sum(yearly.get(y, 0) for y in range(2018, 2022))
    y22_25 = sum(yearly.get(y, 0) for y in range(2022, 2026))
    if y18_21 > 0 and y22_25 < 0:
        kills.append("KILL #4: 2022-2025 negative while 2018-2021 positive")

    top5_ok = top_n_removed_positive(sb60, 5)
    lines.append(f"Top-5-removed still positive (session_breakout 60m): {top5_ok}")
    if not top5_ok and sb["net"] > 0:
        kills.append("KILL #5: removing top 5 trades flips PnL negative")

    lines.append("")
    if kills:
        lines.append("VERDICT: FAIL")
        for k in kills:
            lines.append(f"  - {k}")
    else:
        lines.append("VERDICT: PASS (provisional — paper trade Monday)")

    report = "\n".join(lines)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / "test2_session_timing.txt"
    out.write_text(report)
    print(report)
    print(f"\nWrote {out}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spread", type=float, default=0.40)
    parser.add_argument("--cost-mult", type=float, default=2.0)
    args = parser.parse_args()
    run_test(cost_multiplier=args.cost_mult, base_spread=args.spread)


if __name__ == "__main__":
    main()
