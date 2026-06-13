"""
Test 1: US Macro Shock Momentum
Falsification suite for XAUUSD post-release continuation.
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

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from events.calendar import MacroEvent, load_calendar

UTC = ZoneInfo("UTC")
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
HOLD_MINUTES = [15, 30, 60, 120]
IMPULSE_MINUTES = 5
ENTRY_OFFSET_MINUTES = 5


@dataclass
class Trade:
    event: str
    event_type: str
    entry_ts: datetime
    exit_ts: datetime
    direction: int
    entry_px: float
    exit_px: float
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
    bars = bars.drop_duplicates("ts").set_index("ts")
    return bars


def bar_at_or_after(bars: pd.DataFrame, ts: datetime) -> pd.Series | None:
    idx = bars.index.searchsorted(ts)
    if idx >= len(bars):
        return None
    return bars.iloc[idx]


def bar_at_or_before(bars: pd.DataFrame, ts: datetime) -> pd.Series | None:
    idx = bars.index.searchsorted(ts, side="right") - 1
    if idx < 0:
        return None
    return bars.iloc[idx]


def price_at(bars: pd.DataFrame, ts: datetime, col: str = "open") -> float | None:
    row = bar_at_or_after(bars, ts)
    return None if row is None else float(row[col])


def impulse_direction(bars: pd.DataFrame, release_ts: datetime) -> int | None:
    start = release_ts
    end = release_ts + timedelta(minutes=IMPULSE_MINUTES)
    o = price_at(bars, start, "open")
    c_row = bar_at_or_before(bars, end)
    if o is None or c_row is None:
        return None
    c = float(c_row["close"])
    diff = c - o
    if abs(diff) < 1e-9:
        return None
    return 1 if diff > 0 else -1


def simulate_event_trade(
    bars: pd.DataFrame,
    event: MacroEvent,
    hold_min: int,
    cost_rt: float,
    label: str | None = None,
) -> Trade | None:
    direction = impulse_direction(bars, event.ts_utc)
    if direction is None:
        return None

    entry_ts = event.ts_utc + timedelta(minutes=ENTRY_OFFSET_MINUTES)
    exit_ts = entry_ts + timedelta(minutes=hold_min)
    entry_px = price_at(bars, entry_ts, "open")
    exit_px = price_at(bars, exit_ts, "close")
    if entry_px is None or exit_px is None:
        return None

    gross = direction * (exit_px - entry_px)
    net = gross - cost_rt
    return Trade(
        event=label or event.name,
        event_type=event.name,
        entry_ts=entry_ts,
        exit_ts=exit_ts,
        direction=direction,
        entry_px=entry_px,
        exit_px=exit_px,
        gross_pnl=gross,
        net_pnl=net,
        hold_min=hold_min,
    )


def random_control_trades(
    bars: pd.DataFrame,
    event_days: set,
    events: list[MacroEvent],
    hold_min: int,
    cost_rt: float,
    seed: int = 42,
) -> list[Trade]:
    rng = random.Random(seed)
    trades: list[Trade] = []
    event_ts_set = {e.ts_utc for e in events}

    for day in sorted(event_days):
        day_start = datetime.combine(day, time(8, 0), tzinfo=UTC)
        day_end = datetime.combine(day, time(20, 0), tzinfo=UTC)
        for _ in range(3):
            offset_min = rng.randint(0, int((day_end - day_start).total_seconds() // 60))
            fake_ts = day_start + timedelta(minutes=offset_min)
            # exclude ±30 min around real events
            if any(abs((fake_ts - et).total_seconds()) < 1800 for et in event_ts_set):
                continue
            fake = MacroEvent("RANDOM", fake_ts)
            direction = impulse_direction(bars, fake_ts)
            if direction is None:
                continue
            t = simulate_event_trade(bars, fake, hold_min, cost_rt, label="RANDOM")
            if t:
                trades.append(t)
    return trades


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


def by_type(trades: list[Trade]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for name in ("CPI", "NFP", "FOMC"):
        subset = [t for t in trades if t.event_type == name]
        out[name] = summarize(subset)
    return out


def by_year(trades: list[Trade]) -> dict[int, float]:
    out: dict[int, float] = {}
    for t in trades:
        y = t.entry_ts.year
        out[y] = out.get(y, 0.0) + t.net_pnl
    return dict(sorted(out.items()))


def top_n_removed_still_positive(trades: list[Trade], n: int = 5) -> bool:
    if len(trades) <= n:
        return False
    remaining = sorted(trades, key=lambda t: t.net_pnl, reverse=True)[n:]
    return sum(t.net_pnl for t in remaining) > 0


def run_test(cost_multiplier: float = 2.0, base_spread: float = 0.40) -> str:
    cost_rt = base_spread * cost_multiplier
    years = range(2018, 2026)
    bars = load_bars(years)
    events = [e for e in load_calendar(2018, 2025) if e.name in ("CPI", "NFP", "FOMC")]
    events = [e for e in events if bars.index.min() <= e.ts_utc <= bars.index.max()]

    event_days = {e.date for e in events}
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("TEST 1: US MACRO SHOCK MOMENTUM")
    lines.append("=" * 60)
    lines.append(f"Data range: {bars.index.min()} -> {bars.index.max()}")
    lines.append(f"Bars: {len(bars):,}")
    lines.append(f"Events: {len(events)} (CPI/NFP/FOMC)")
    lines.append(f"Cost RT @ {cost_multiplier}x spread: {cost_rt:.2f} pts")
    lines.append("")

    all_results: dict[int, list[Trade]] = {}
    control_results: dict[int, list[Trade]] = {}
    for hold in HOLD_MINUTES:
        trades = []
        for ev in events:
            t = simulate_event_trade(bars, ev, hold, cost_rt)
            if t:
                trades.append(t)
        all_results[hold] = trades
        control_results[hold] = random_control_trades(
            bars, event_days, events, hold, cost_rt
        )

    lines.append("--- HOLD PERIOD RESULTS ---")
    positive_holds = 0
    for hold in HOLD_MINUTES:
        s = summarize(all_results[hold])
        c = summarize(control_results[hold])
        lines.append(
            f"Hold {hold:3d}m: n={s['n']:3d}  gross={s['gross']:8.1f}  net={s['net']:8.1f}  "
            f"avg={s['avg']:6.3f}  win%={s['win_pct']:5.1f}  |  control_avg={c['avg']:6.3f}"
        )
        if s["net"] > 0:
            positive_holds += 1

    lines.append("")
    lines.append("--- BY EVENT TYPE (60m hold) ---")
    hold60 = all_results[60]
    for name, s in by_type(hold60).items():
        lines.append(f"{name:5s}: n={s['n']:3d}  net={s['net']:8.1f}  avg={s['avg']:6.3f}")

    lines.append("")
    lines.append("--- YEAR-BY-YEAR NET (60m hold) ---")
    yearly = by_year(hold60)
    lines.append(" ".join(f"{y}={v:+.0f}" for y, v in yearly.items()))

    lines.append("")
    lines.append("--- FALSIFICATION CHECKS ---")
    kills: list[str] = []

    if positive_holds == 0:
        kills.append("KILL #1: net <= 0 on all hold periods after costs")

    type_net = {k: v["net"] for k, v in by_type(hold60).items()}
    profitable_types = sum(1 for v in type_net.values() if v > 0)
    if profitable_types < 2:
        kills.append("KILL #2: profits concentrated in <2 event types")

    ctrl60 = summarize(control_results[60])
    ev60 = summarize(hold60)
    if ctrl60["avg"] >= ev60["avg"]:
        kills.append("KILL #3: random-time control matches/beats events")

    y18_21 = sum(yearly.get(y, 0) for y in range(2018, 2022))
    y22_25 = sum(yearly.get(y, 0) for y in range(2022, 2026))
    if y18_21 > 0 and y22_25 < 0:
        kills.append("KILL #4: 2022-2025 negative while 2018-2021 positive")

    top5_ok = top_n_removed_still_positive(hold60, 5)
    lines.append(f"Top-5-removed still positive (60m): {top5_ok}")
    if not top5_ok:
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
    out = RESULTS_DIR / "test1_macro_momentum.txt"
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
