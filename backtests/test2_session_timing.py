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

SESSION_ANCHORS = {
    "asia_open": time(0, 0),
    "london_open": time(7, 0),
    "london_fix_am": time(10, 30),
    "ny_open": time(13, 30),
    "us_data_window": time(12, 30),
    "london_fix_pm": time(15, 0),
    "ny_close": time(21, 0),
}

PRIOR_WINDOWS_H = {
    "asia_open": 7,
    "london_open": 7,
    "london_fix_am": 3,
    "ny_open": 6,
    "us_data_window": 4,
    "london_fix_pm": 2,
    "ny_close": 8,
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


@dataclass
class BarStore:
    ts: np.ndarray
    open_: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray

    @property
    def n(self) -> int:
        return len(self.ts)

    def idx_at(self, t: np.datetime64) -> int:
        return int(np.searchsorted(self.ts, t, side="left"))

    def idx_before(self, t: np.datetime64) -> int:
        return int(np.searchsorted(self.ts, t, side="right")) - 1

    def window_hi_lo(self, i0: int, i1: int) -> tuple[float, float] | None:
        if i0 >= i1:
            return None
        hi = float(np.max(self.high[i0:i1]))
        lo = float(np.min(self.low[i0:i1]))
        return hi, lo


def load_bars(years: range) -> BarStore:
    frames = []
    for year in years:
        path = DATA_DIR / f"DAT_ASCII_XAUUSD_M1_{year}.csv"
        if not path.exists():
            raise FileNotFoundError(f"missing {path}")
        df = pd.read_csv(
            path, sep=";", header=None,
            names=["dt_str", "open", "high", "low", "close", "volume"],
        )
        # histdata.com ASCII timestamps are EST (UTC-5, no DST). Convert to true
        # UTC so session anchors below refer to real UTC session boundaries.
        naive = pd.to_datetime(df["dt_str"], format="%Y%m%d %H%M%S")
        df["ts"] = naive.dt.tz_localize("Etc/GMT+5").dt.tz_convert("UTC")
        frames.append(df[["ts", "open", "high", "low", "close"]])
    bars = pd.concat(frames, ignore_index=True).sort_values("ts").drop_duplicates("ts")
    return BarStore(
        ts=bars["ts"].values.astype("datetime64[ns]"),
        open_=bars["open"].to_numpy(dtype=float),
        high=bars["high"].to_numpy(dtype=float),
        low=bars["low"].to_numpy(dtype=float),
        close=bars["close"].to_numpy(dtype=float),
    )


def to_ns(day: datetime, t: time) -> np.datetime64:
    return np.datetime64(datetime.combine(day.date(), t, tzinfo=UTC).replace(tzinfo=None))


def make_trade(
    strategy: str,
    session: str,
    entry_i: int,
    store: BarStore,
    direction: int,
    hold_min: int,
    cost_rt: float,
) -> Trade | None:
    exit_i = store.idx_at(store.ts[entry_i] + np.timedelta64(hold_min, "m"))
    if exit_i >= store.n:
        return None
    entry_px = store.close[entry_i]
    exit_px = store.close[exit_i]
    gross = direction * (exit_px - entry_px)
    return Trade(
        strategy=strategy,
        session=session,
        entry_ts=pd.Timestamp(store.ts[entry_i]).to_pydatetime().replace(tzinfo=UTC),
        exit_ts=pd.Timestamp(store.ts[exit_i]).to_pydatetime().replace(tzinfo=UTC),
        direction=direction,
        gross_pnl=gross,
        net_pnl=gross - cost_rt,
        hold_min=hold_min,
    )


def session_breakout(
    store: BarStore, day: datetime, session: str, anchor: time,
    lookback_h: int, hold_min: int, cost_rt: float,
) -> Trade | None:
    anchor_ns = to_ns(day, anchor)
    i0 = store.idx_at(anchor_ns - np.timedelta64(lookback_h, "h"))
    i1 = store.idx_at(anchor_ns)
    rng = store.window_hi_lo(i0, i1)
    if rng is None:
        return None
    hi, lo = rng
    i2 = store.idx_at(anchor_ns + np.timedelta64(30, "m"))
    for i in range(i1, min(i2, store.n)):
        c = store.close[i]
        if c > hi:
            return make_trade("session_breakout", session, i, store, 1, hold_min, cost_rt)
        if c < lo:
            return make_trade("session_breakout", session, i, store, -1, hold_min, cost_rt)
    return None


def opening_range_breakout(
    store: BarStore, day: datetime, session: str, anchor: time,
    hold_min: int, cost_rt: float,
) -> Trade | None:
    anchor_ns = to_ns(day, anchor)
    i0 = store.idx_at(anchor_ns)
    i1 = store.idx_at(anchor_ns + np.timedelta64(ORB_MINUTES, "m"))
    if i1 - i0 < 10:
        return None
    hi, lo = store.window_hi_lo(i0, i1) or (0.0, 0.0)
    if hi <= lo:
        return None
    i2 = store.idx_at(anchor_ns + np.timedelta64(ORB_MINUTES + 60, "m"))
    for i in range(i1, min(i2, store.n)):
        c = store.close[i]
        if c > hi:
            return make_trade("orb", session, i, store, 1, hold_min, cost_rt)
        if c < lo:
            return make_trade("orb", session, i, store, -1, hold_min, cost_rt)
    return None


def failed_breakout_revert(
    store: BarStore, day: datetime, session: str, anchor: time,
    lookback_h: int, hold_min: int, cost_rt: float,
) -> Trade | None:
    anchor_ns = to_ns(day, anchor)
    i0 = store.idx_at(anchor_ns - np.timedelta64(lookback_h, "h"))
    i1 = store.idx_at(anchor_ns)
    rng = store.window_hi_lo(i0, i1)
    if rng is None:
        return None
    hi, lo = rng
    i2 = store.idx_at(anchor_ns + np.timedelta64(FAIL_REVERT_MINUTES + 30, "m"))
    pierced_up = pierced_dn = False
    for i in range(i1, min(i2, store.n)):
        if store.high[i] > hi:
            pierced_up = True
        if store.low[i] < lo:
            pierced_dn = True
        c = store.close[i]
        if pierced_up and c < hi:
            return make_trade("failed_breakout_fade", session, i, store, -1, hold_min, cost_rt)
        if pierced_dn and c > lo:
            return make_trade("failed_breakout_fade", session, i, store, 1, hold_min, cost_rt)
        if store.ts[i] >= anchor_ns + np.timedelta64(FAIL_REVERT_MINUTES, "m"):
            break
    return None


def trading_days(store: BarStore) -> list[datetime]:
    days = pd.to_datetime(store.ts).date
    unique = sorted(set(days))
    return [datetime.combine(d, time(0, 0), tzinfo=UTC) for d in unique]


def random_control_trade(
    store: BarStore, day: datetime, strategy: str,
    hold_min: int, cost_rt: float, seed: int,
) -> Trade | None:
    rng = random.Random(seed)
    fake_anchor = time(rng.randint(8, 19), rng.choice([0, 15, 30, 45]))
    session = "random"
    if strategy == "session_breakout":
        return session_breakout(store, day, session, fake_anchor, 4, hold_min, cost_rt)
    if strategy == "orb":
        return opening_range_breakout(store, day, session, fake_anchor, hold_min, cost_rt)
    return failed_breakout_revert(store, day, session, fake_anchor, 4, hold_min, cost_rt)


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
    return {s: summarize([t for t in trades if t.session == s]) for s in SESSION_ANCHORS}


def by_year(trades: list[Trade]) -> dict[int, float]:
    out: dict[int, float] = {}
    for t in trades:
        out[t.entry_ts.year] = out.get(t.entry_ts.year, 0.0) + t.net_pnl
    return dict(sorted(out.items()))


def top_n_removed_positive(trades: list[Trade], n: int = 5) -> bool:
    if len(trades) <= n:
        return False
    rem = sorted(trades, key=lambda t: t.net_pnl, reverse=True)[n:]
    return sum(t.net_pnl for t in rem) > 0


def run_test(cost_multiplier: float = 2.0, base_spread: float = 0.40) -> str:
    cost_rt = base_spread * cost_multiplier
    store = load_bars(range(2018, 2026))
    days = trading_days(store)

    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("TEST 2: SESSION / TIME-OF-DAY BEHAVIOR")
    lines.append("=" * 60)
    lines.append(f"Data range: {pd.Timestamp(store.ts[0])} -> {pd.Timestamp(store.ts[-1])}")
    lines.append(f"Bars: {store.n:,}")
    lines.append(f"Trading days: {len(days):,}")
    lines.append(f"Cost RT @ {cost_multiplier}x spread: {cost_rt:.2f} pts")
    lines.append("")

    strategies = ("session_breakout", "orb", "failed_breakout_fade")
    all_trades: dict[str, dict[int, list[Trade]]] = {s: {} for s in strategies}
    controls: dict[str, dict[int, list[Trade]]] = {s: {} for s in strategies}

    for strat in strategies:
        for hold in HOLD_MINUTES:
            trades: list[Trade] = []
            ctrl: list[Trade] = []
            for i, day in enumerate(days):
                for session, anchor in SESSION_ANCHORS.items():
                    lookback = PRIOR_WINDOWS_H[session]
                    if strat == "session_breakout":
                        t = session_breakout(store, day, session, anchor, lookback, hold, cost_rt)
                    elif strat == "orb":
                        t = opening_range_breakout(store, day, session, anchor, hold, cost_rt)
                    else:
                        t = failed_breakout_revert(store, day, session, anchor, lookback, hold, cost_rt)
                    if t:
                        trades.append(t)
                for j in range(2):
                    ct = random_control_trade(store, day, strat, hold, cost_rt, seed=i * 10 + j)
                    if ct:
                        ctrl.append(ct)
            all_trades[strat][hold] = trades
            controls[strat][hold] = ctrl

    lines.append("--- STRATEGY x HOLD RESULTS (60m) ---")
    for strat in strategies:
        s = summarize(all_trades[strat][60])
        c = summarize(controls[strat][60])
        lines.append(
            f"{strat:22s} n={s['n']:5d} net={s['net']:9.1f} avg={s['avg']:7.4f} "
            f"win%={s['win_pct']:5.1f} | control_avg={c['avg']:7.4f}"
        )

    lines.append("")
    lines.append("--- SESSION BREAKDOWN (session_breakout 60m) ---")
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

    if sum(1 for s in strategies if summarize(all_trades[s][60])["net"] > 0) == 0:
        kills.append("KILL #1: all strategies negative after costs at 60m hold")

    sb = summarize(sb60)
    sb_ctrl = summarize(controls["session_breakout"][60])
    if sb_ctrl["avg"] >= sb["avg"]:
        kills.append("KILL #2: random-time control matches/beats session signals")

    if sum(1 for s in by_session(sb60).values() if s["net"] > 0) < 2:
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
