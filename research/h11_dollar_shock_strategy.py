"""H11: the dollar-shock momentum strategy, with trade rules and costs.

Implements research/H11-dollar-shock-strategy.md as pre-registered (commit eb426bc).
  (default)         evaluate both variants on 2018 to Sep 2025; write research/H11-results.md
  --holdout H       run variant H (15 or 30) once on the holdout; ONLY with the user's approval
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from xau.bars import load_m1  # noqa: E402
from xau.dollar_shock import shocks, simulate  # noqa: E402
from xau.eventstudy import clustered_t  # noqa: E402
from xau.holdout import HOLDOUT_START  # noqa: E402
from xau.report import md  # noqa: E402
from xau.sessions import session, trading_day  # noqa: E402
from xau.stats import max_drawdown  # noqa: E402

K = 3.0
HOLDS = (15, 30)
ERAS = [("2018-20", "2018-01-01", "2021-01-01"), ("2021-22", "2021-01-01", "2023-01-01"),
        ("2023-Sep25", "2023-01-01", "2025-10-01")]


def trades_for(gold, eurusd, usdjpy, hold, start=None):
    sig = shocks(eurusd, usdjpy, K)
    if start is not None:
        sig = sig[sig.time >= pd.Timestamp(start).value]
    t = simulate(sig, gold, hold)
    t["day"] = trading_day(pd.DatetimeIndex(t.entry_time))
    t["session"] = session(pd.DatetimeIndex(t.entry_time))
    return t


def summary(t, years):
    per_year = len(t) / years
    s = {"trades": len(t), "trades/yr": per_year, "mean net $/oz": t.net.mean(), "t (by day)": clustered_t(t.net, t.day),
         "win rate %": (t.net > 0).mean() * 100, "total net $/oz": t.net.sum(), "mean cost $/oz": t.cost.mean(),
         "Sharpe (annualised)": t.net.mean() / t.net.std() * np.sqrt(per_year), "max drawdown $/oz": max_drawdown(t.net)}
    for name, a, b in ERAS:
        e = t[(t.entry_time >= pd.Timestamp(a, tz="UTC")) & (t.entry_time < pd.Timestamp(b, tz="UTC"))]
        s[f"mean net {name}"] = e.net.mean()
    s.update({"NEWS-HEAVY mean net $/oz": t.net_news_heavy.mean(), "NEWS-HEAVY t (by day)": clustered_t(t.net_news_heavy, t.day),
              "NEWS-HEAVY total $/oz": t.net_news_heavy.sum(),
              "NEWS-HEAVY Sharpe": t.net_news_heavy.mean() / t.net_news_heavy.std() * np.sqrt(per_year),
              "NEWS-HEAVY max drawdown $/oz": max_drawdown(t.net_news_heavy),
              "share of trades in 08:30-08:45 NY": np.mean(
                  (lambda ny: (ny.hour * 60 + ny.minute >= 510) & (ny.hour * 60 + ny.minute < 525))(
                      pd.DatetimeIndex(t.entry_time).tz_convert("America/New_York")))})
    for name, a, b in ERAS:
        e = t[(t.entry_time >= pd.Timestamp(a, tz="UTC")) & (t.entry_time < pd.Timestamp(b, tz="UTC"))]
        s[f"NEWS-HEAVY mean net {name}"] = e.net_news_heavy.mean()
    return s


def main():
    if "--holdout" in sys.argv:
        hold = int(sys.argv[sys.argv.index("--holdout") + 1])
        warm = (HOLDOUT_START - pd.Timedelta(days=30)).strftime("%Y-%m-%d")
        data = [load_m1(warm, None, symbol=s, allow_holdout=True) for s in ("XAUUSD", "EURUSD", "USDJPY")]
        t = trades_for(*data, hold, start=HOLDOUT_START)
        span = (t.entry_time.max() - HOLDOUT_START).days / 365.25
        s = pd.Series(summary(t, span)).to_frame(f"holdout, H={hold}")
        s.loc["PASS (NEWS-HEAVY mean net > 0)"] = bool(t.net_news_heavy.mean() > 0)
        by_month = t.groupby(t.entry_time.dt.strftime("%Y-%m")).net.agg(["size", "sum"]).rename(columns={"size": "trades", "sum": "net $/oz"})
        out = [f"# H11 holdout\n\nRun {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC, once, on {HOLDOUT_START:%Y-%m-%d} "
               f"to {t.exit_time.max():%Y-%m-%d} with the variant chosen in `H11-results.md` (H = {hold}).\n",
               md(s.rename_axis("")), "\n## By month\n", md(by_month.rename_axis("month"))]
        (ROOT / "research" / "H11-holdout.md").write_text("\n".join(out) + "\n")
        print(md(s.rename_axis("")))
        return

    gold, eurusd, usdjpy = (load_m1("2018-01-01", symbol=s) for s in ("XAUUSD", "EURUSD", "USDJPY"))
    years = (HOLDOUT_START - pd.Timestamp("2018-01-01", tz="UTC")).days / 365.25
    runs = {h: trades_for(gold, eurusd, usdjpy, h) for h in HOLDS}
    table = pd.DataFrame({f"H={h}": summary(t, years) for h, t in runs.items()})
    ok = {h: all(table.loc[f"mean net {n}", f"H={h}"] > 0 for n, _, _ in ERAS) for h in HOLDS}
    best = max(HOLDS, key=lambda h: table.loc["mean net $/oz", f"H={h}"])
    choice = best if ok[best] else next((h for h in HOLDS if ok[h]), None)
    table.loc["net > 0 in every era"] = [ok[h] for h in HOLDS]
    by_year = pd.DataFrame({f"H={h} net $/oz": t.groupby(t.entry_time.dt.year).net.sum() for h, t in runs.items()} |
                           {f"H={h} trades": t.groupby(t.entry_time.dt.year).size() for h, t in runs.items()}).rename_axis("year")
    by_session = pd.DataFrame({f"H={h} mean net": t.groupby("session").net.mean() for h, t in runs.items()} |
                              {f"H={h} trades": t.groupby("session").size() for h, t in runs.items()}).rename_axis("session")
    verdict = (f"**Chosen for the holdout: H = {choice}.**" if choice is not None
               else "**Neither variant is net positive in every era, so the strategy stops here (no holdout).**")
    out = [f"# H11 results\n\nRun {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC on Pepperstone M1 bars 2018-01-01 to "
           f"2025-09-30, as pre-registered in `H11-dollar-shock-strategy.md` (commit eb426bc). Net is per trade in $/oz "
           "after spread + $0.11.\n", md(table.rename_axis("")), f"\n{verdict}\n", "## By year\n", md(by_year),
           "\n## By session\n", md(by_session)]
    (ROOT / "research" / "H11-results.md").write_text("\n".join(out) + "\n")
    print(md(table.rename_axis("")))
    print(verdict)


if __name__ == "__main__":
    main()
