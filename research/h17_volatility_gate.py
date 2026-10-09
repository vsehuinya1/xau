"""H17: a volatility gate for dollar-shock momentum.

Implements research/H17-volatility-gate.md as pre-registered.
Writes research/H17-results.md.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from xau.bars import load_m1  # noqa: E402
from xau.dollar_shock import news_heavy_extra, shocks, simulate  # noqa: E402
from xau.eventstudy import Bars, clustered_t, series_at  # noqa: E402
from xau.features import m5_atr  # noqa: E402
from xau.histdata import load_histdata  # noqa: E402
from xau.report import md  # noqa: E402
from xau.sessions import trading_day  # noqa: E402
from xau.stats import max_drawdown  # noqa: E402

HOLD = 30


def trades_with_atr(gold, eur, jpy, cost_fixed):
    sig = shocks(eur, jpy, 3.0)
    tr = simulate(sig, gold, HOLD, cost_fixed=cost_fixed)
    sig_time = sig.set_index("time")
    # the shock time behind each trade: the latest shock at or before entry
    t_entry = tr.entry_time.astype("int64").to_numpy()
    shock_t = sig.time.to_numpy()[np.searchsorted(sig.time.to_numpy(), t_entry, side="right") - 1]
    tr["atr"] = series_at(m5_atr(gold), shock_t)
    tr["gross"] = tr.net + tr.cost
    tr["cost_heavy"] = tr.cost + news_heavy_extra(tr.entry_time)
    return tr


def stats(tr, years):
    day = trading_day(pd.DatetimeIndex(tr.entry_time))
    return {"trades": len(tr), "trades/yr": len(tr) / years, "mean net (news-heavy) $/oz": tr.net_news_heavy.mean(),
            "t": clustered_t(tr.net_news_heavy, day), "total (news-heavy) $/oz": tr.net_news_heavy.sum(),
            "max drawdown $/oz": max_drawdown(tr.net_news_heavy), "mean ATR $": tr.atr.mean()}


def main():
    yrs = range(2009, 2018)
    cal = trades_with_atr(load_histdata("xauusd", yrs), load_histdata("eurusd", yrs), load_histdata("usdjpy", yrs), 0.51)
    ok = np.isfinite(cal.atr)
    beta = float((cal.gross[ok] * cal.atr[ok]).sum() / (cal.atr[ok] ** 2).sum())

    def gate(tr):
        return tr[beta * tr.atr >= tr.cost_heavy]

    pep = trades_with_atr(*(load_m1("2018-01-01", symbol=s) for s in ("XAUUSD", "EURUSD", "USDJPY")), 0.11)
    rec_all = trades_with_atr(*(load_m1("2025-08-01", None, symbol=s, allow_holdout=True) for s in ("XAUUSD", "EURUSD", "USDJPY")), 0.11)
    rec = rec_all[rec_all.entry_time >= pd.Timestamp("2025-10-01", tz="UTC")]
    table = {("ungated", "2018-Sep 2025"): stats(pep, 7.75), ("gated", "2018-Sep 2025"): stats(gate(pep), 7.75),
             ("ungated", "Oct 2025-Sep 2026 (diag.)"): stats(rec, 1.0), ("gated", "Oct 2025-Sep 2026 (diag.)"): stats(gate(rec), 1.0),
             ("ungated", "calibration 2009-2017"): stats(cal, 9.0)}
    T = pd.DataFrame(table).T
    g, u = T.loc[("gated", "2018-Sep 2025")], T.loc[("ungated", "2018-Sep 2025")]
    crit = {"1 gated net > 0, t >= 2": g["mean net (news-heavy) $/oz"] > 0 and g["t"] >= 2,
            "2 gated per-trade > ungated": g["mean net (news-heavy) $/oz"] > u["mean net (news-heavy) $/oz"],
            "3 gated total >= 90% of ungated": g["total (news-heavy) $/oz"] >= 0.9 * u["total (news-heavy) $/oz"]}
    gp = gate(pep)
    by_year = pd.DataFrame({"ungated trades": pep.groupby(pep.entry_time.dt.year).size(),
                            "gated trades": gp.groupby(gp.entry_time.dt.year).size(),
                            "ungated net": pep.groupby(pep.entry_time.dt.year).net_news_heavy.sum(),
                            "gated net": gp.groupby(gp.entry_time.dt.year).net_news_heavy.sum()}).fillna(0).rename_axis("year")
    out = [f"# H17 results\n\nRun {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC, as pre-registered in `H17-volatility-gate.md`.\n",
           f"Calibrated on histdata 2009-2017: **beta = {beta:.3f}** (gross $/oz per trade per $ of gold M5 ATR). "
           f"Gate: trade only if {beta:.3f} x ATR >= the trade's news-heavy cost.\n", "## Criteria (2018-Sep 2025)\n",
           md(pd.DataFrame({k: {"PASS": bool(v)} for k, v in crit.items()}).T.rename_axis("criterion")),
           f"\n**Overall: {'PASS' if all(crit.values()) else 'FAIL'}**\n", "## Results\n", md(T.rename_axis(["strategy", "sample"])),
           "\n## By year, 2018-2025 (news-heavy net $/oz)\n", md(by_year)]
    (ROOT / "research" / "H17-results.md").write_text("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
