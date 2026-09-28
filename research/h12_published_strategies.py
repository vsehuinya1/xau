"""H12: do published gold strategies hold up on our data?

Implements research/H12-published-strategies.md as pre-registered (commit 55fe90c).
Writes research/H12-results.md.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

import h05_multiday_trend as h05  # noqa: E402  (daily closes, swap model, costs)
from xau.bars import load_m1  # noqa: E402
from xau.eventstudy import MIN, Bars  # noqa: E402
from xau.histdata import load_histdata  # noqa: E402
from xau.report import md  # noqa: E402
from xau.sessions import trading_day  # noqa: E402
from xau.stats import newey_west_t  # noqa: E402

MAX_WAIT = 5
FLAT_COST = 0.51  # $/oz per round trip where there are no spreads (histdata)
SPLIT = pd.Timestamp("2012-06-30")


def ns(day, hhmm, tz):
    return pd.Timestamp(f"{day:%Y-%m-%d} {hhmm}").tz_localize(tz).tz_convert("UTC").value


def trade(b, cost_of, day, direction, start, end, tz):
    """One trade from the first bar opening within MAX_WAIT of `start` to the last close at or before `end`."""
    t0, t1 = ns(day, start, tz), ns(day, end, tz)
    k = int(np.searchsorted(b.t, t0, side="left"))
    if k >= len(b.t) or b.t[k] > t0 + MAX_WAIT * MIN or t1 > b.tc[-1]:
        return None
    exit_ = b.price_at(np.array([t1]))[0]
    return {"day": day, "direction": direction, "gross": direction * (exit_ - b.open[k]), "cost": cost_of(k)}


def intraday_trades(m1, flat_cost):
    b = Bars(m1)
    cost_of = (lambda k: flat_cost) if flat_cost is not None else (lambda k: b.spread[k] + 0.11)
    days = pd.DatetimeIndex(np.unique(trading_day(m1.index)))
    days = days[days.dayofweek < 5]
    out = {"A": [], "B1": [], "B2": []}
    ny = "America/New_York"
    for prev, day in zip(days[:-1], days[1:]):
        ref, now = b.price_at(np.array([ns(prev, "13:30", ny), ns(day, "13:00", ny)]))
        s = int(np.sign(np.log(now / ref))) if np.isfinite(ref) and np.isfinite(now) else 0
        if s:
            out["A"].append(trade(b, cost_of, day, s, "13:00", "13:30", ny))
        out["B1"].append(trade(b, cost_of, day, -1, "09:30", "10:30", "Europe/London"))
        out["B2"].append(trade(b, cost_of, day, 1, "15:00", "16:00", "Europe/London"))
    frames = {}
    for name, rows in out.items():
        f = pd.DataFrame([r for r in rows if r is not None])
        f["net"] = f.gross - f.cost
        frames[name] = f
    return frames


def summarize(f):
    return {"trades": len(f), "mean net $/oz": f.net.mean(), "t (NW 5)": newey_west_t(f.net, 5),
            "mean gross $/oz": f.gross.mean(), "t gross": newey_west_t(f.gross, 5),
            "win rate %": (f.net > 0).mean() * 100, "total net $/oz": f.net.sum(), "mean cost $/oz": f.cost.mean()}


def daily_tests():
    closes, ff = h05.load()
    idx = closes.index
    # D: 200-day trend filter, long or flat
    d_net, d_parts = h05.run(closes, ff, (closes > closes.rolling(200).mean()).astype(float).where(closes.rolling(200).count() == 200))
    hold, _ = h05.run(closes, ff, pd.Series(1.0, index=idx))
    # C: long at the closes of month-days -2, -1 and +1 (so returns of days -1, +1, +2 are held)
    month = idx.to_period("M")
    pos_in_month = pd.Series(np.arange(len(idx)), index=idx).groupby(month).transform(lambda s: s - s.min())
    from_end = pd.Series(np.arange(len(idx)), index=idx).groupby(month).transform(lambda s: s.max() - s)
    c_pos = ((from_end <= 1) | (pos_in_month == 0)).astype(float)
    c_net, c_parts = h05.run(closes, ff, c_pos)
    # per turn-of-month episode: consecutive held days
    held = c_parts.position > 0
    episode = (held != held.shift()).cumsum()[held]
    per_trade = c_net[held].groupby(episode).sum()
    per_trade.index = c_net[held].groupby(episode).apply(lambda s: s.index[0])
    sharpe = lambda x: x.mean() / x.std() * np.sqrt(252)  # noqa: E731
    halves = lambda s: (s[s.index <= SPLIT], s[s.index > SPLIT])  # noqa: E731
    c1, c2 = halves(per_trade)
    d1, d2 = halves(d_net)
    h1, h2 = halves(hold)
    rows = {
        "C turn of month": {"trades": len(per_trade), "mean net % per trade": per_trade.mean() * 100,
                            "t": newey_west_t(per_trade, 1), "mean net 1st half %": c1.mean() * 100,
                            "mean net 2nd half %": c2.mean() * 100,
                            "PASS": bool(per_trade.mean() > 0 and newey_west_t(per_trade, 1) >= 2 and c1.mean() > 0 and c2.mean() > 0)},
        "D 200-day filter": {"net %/yr": d_net.mean() * 25200, "t (NW 10)": newey_west_t(d_net, 10),
                             "Sharpe 1st half": sharpe(d1), "buy-and-hold Sharpe 1st half": sharpe(h1),
                             "Sharpe 2nd half": sharpe(d2), "buy-and-hold Sharpe 2nd half": sharpe(h2),
                             "time long %": (d_parts.position > 0).mean() * 100,
                             "PASS": bool(d_net.mean() > 0 and newey_west_t(d_net, 10) >= 2 and sharpe(d1) > sharpe(h1) and sharpe(d2) > sharpe(h2))},
    }
    return rows, hold


def main():
    samples = {"histdata 2009-2017": (load_histdata("xauusd", range(2009, 2018)), FLAT_COST),
               "Pepperstone 2018-Sep 2025": (load_m1("2018-01-01"), None)}
    res = {name: intraday_trades(m1, cost) for name, (m1, cost) in samples.items()}
    holdout = intraday_trades(load_m1("2025-09-01", None, allow_holdout=True).loc["2025-10-01":], None)
    table, verdict = {}, {}
    for test in ("A", "B1", "B2"):
        for name in samples:
            table[(test, name)] = summarize(res[name][test])
        table[(test, "holdout Oct 2025-Sep 2026 (diagnostic)")] = summarize(holdout[test])
        verdict[test] = all(table[(test, n)]["mean net $/oz"] > 0 and table[(test, n)]["t (NW 5)"] >= 2 for n in samples)
    daily, hold = daily_tests()
    labels = {"A": "A intraday momentum 13:00-13:30 NY", "B1": "B1 short into AM fix", "B2": "B2 long after PM fix"}
    out = [f"# H12 results\n\nRun {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC, as pre-registered in "
           "`H12-published-strategies.md` (commit 55fe90c).\n", "## Verdict\n",
           md(pd.DataFrame({**{labels[k]: {"PASS": v} for k, v in verdict.items()},
                            **{k: {"PASS": v["PASS"]} for k, v in daily.items()}}).T.rename_axis("test")),
           "\n## Intraday tests (A, B): both samples must show net > 0 with t >= 2\n",
           md(pd.DataFrame(table).T.rename_axis(["test", "sample"])),
           "\n## Daily tests (C, D), June 1999 to Sep 2025, with H05's swap and cost model\n",
           md(pd.DataFrame(daily).T.rename_axis("test")),
           f"\nBuy-and-hold over the same period: {hold.mean() * 25200:.2f}%/yr net of swap.\n"]
    (ROOT / "research" / "H12-results.md").write_text("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
