"""H19: trade silver on dollar shocks, with a volatility gate.

Implements research/H19-silver.md as pre-registered.
Writes research/H19-results.md.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from xau.bars import load_m1  # noqa: E402
from xau.dollar_shock import GATE_BETA, news_heavy_extra, shocks, simulate  # noqa: E402
from xau.eventstudy import SUBPERIODS, clustered_t, series_at  # noqa: E402
from xau.features import m5_atr  # noqa: E402
from xau.histdata import load_histdata  # noqa: E402
from xau.report import md  # noqa: E402
from xau.sessions import trading_day  # noqa: E402
from xau.stats import max_drawdown  # noqa: E402

HOLD = 30
SLIP, NEWS, OTHER, NEWS_STRESS = 0.3e-4, 4e-4, 1e-4, 16e-4  # fractions of entry price
HOLDOUT = ("2025-10-01", "2026-10-01")


def is_news(entry_times):
    ny = pd.DatetimeIndex(entry_times).tz_convert("America/New_York")
    minute = ny.hour * 60 + ny.minute
    return (minute >= 510) & (minute < 525)


def with_atr(tr, sig, m1):
    """ATR of the traded metal at the shock behind each trade."""
    t_entry = tr.entry_time.astype("int64").to_numpy()
    shock_t = sig.time.to_numpy()[np.searchsorted(sig.time.to_numpy(), t_entry, side="right") - 1]
    tr["atr"] = series_at(m5_atr(m1), shock_t)
    return tr


def silver_trades(silver, eur, jpy, point=0.001):
    sig = shocks(eur, jpy, 3.0)
    # Bars converts the spread field at gold's $0.01 per point; silver's point is $0.001
    tr = with_atr(simulate(sig, silver.assign(spread=silver.spread * point / 0.01), HOLD, cost_fixed=0.0), sig, silver)
    tr["spread"] = tr.cost
    tr["gross"] = tr.net + tr.cost
    news = is_news(tr.entry_time)
    tr["cost_real"] = tr.spread + tr.entry * (SLIP + np.where(news, NEWS, OTHER))
    tr["net_real"] = tr.gross - tr.cost_real
    tr["net_2x"] = tr.net_real - tr.spread
    tr["net_stress"] = tr.gross - tr.spread - tr.entry * (SLIP + np.where(news, NEWS_STRESS, OTHER))
    for c in ("gross", "net_real", "net_2x", "net_stress"):
        tr[c + "_bp"] = tr[c] / tr.entry * 1e4
    return tr


def gold_gated(gold, eur, jpy):
    """Gold's live strategy (H11 + H17 gate) on the same shocks, for the overlap diagnostics."""
    sig = shocks(eur, jpy, 3.0)
    tr = with_atr(simulate(sig, gold, HOLD), sig, gold)
    tr = tr[GATE_BETA * tr.atr >= tr.cost + news_heavy_extra(tr.entry_time)]
    tr["net_bp"] = tr.net_news_heavy / tr.entry * 1e4
    return tr


def between(tr, a, b):
    return tr[(tr.entry_time >= pd.Timestamp(a, tz="UTC")) & (tr.entry_time < pd.Timestamp(b, tz="UTC"))]


def stats(tr, years):
    day = trading_day(pd.DatetimeIndex(tr.entry_time))
    trimmed = tr[tr.net_real_bp < tr.net_real_bp.quantile(0.99)]
    return {"trades": len(tr), "trades/yr": len(tr) / years,
            "gross bp": tr.gross_bp.mean(), "t gross": clustered_t(tr.gross_bp, day),
            "net bp (realistic)": tr.net_real_bp.mean(), "t net": clustered_t(tr.net_real_bp, day),
            "net bp (2x spread)": tr.net_2x_bp.mean(), "net bp (stress)": tr.net_stress_bp.mean(),
            "net bp w/o top 1%": trimmed.net_real_bp.mean(), "total bp": tr.net_real_bp.sum(),
            "max drawdown bp": max_drawdown(tr.net_real_bp), "cost bp": (tr.cost_real / tr.entry * 1e4).mean()}


def main():
    yrs = range(2009, 2018)
    cal = silver_trades(load_histdata("xagusd", yrs), load_histdata("eurusd", yrs), load_histdata("usdjpy", yrs))
    ok = np.isfinite(cal.atr)
    beta = float((cal.gross[ok] * cal.atr[ok]).sum() / (cal.atr[ok] ** 2).sum())

    def gate(tr):
        return tr[beta * tr.atr >= tr.cost_real]

    syms = ("XAGUSD", "EURUSD", "USDJPY")
    m1 = {s: load_m1("2018-01-01", symbol=s) for s in syms + ("XAUUSD",)}
    pep = silver_trades(*(m1[s] for s in syms))
    gp = gate(pep)

    rep = cal.gross_bp.mean() > 0 and clustered_t(cal.gross_bp, trading_day(pd.DatetimeIndex(cal.entry_time))) >= 3
    g = stats(gp, 7.75)
    subs = {name: between(gp, a, b).net_real_bp.mean() for name, a, b in SUBPERIODS}
    crit = {"R  histdata 2009-17 gross > 0, t >= 3 (ungated)": rep,
            "1  gated realistic net > 0, t >= 2": g["net bp (realistic)"] > 0 and g["t net"] >= 2,
            "2  gated net at double spread > 0": g["net bp (2x spread)"] > 0,
            "3  gated net > 0 in every sub-period": all(v > 0 for v in subs.values()),
            "4  gated net > 0 without the top 1%": g["net bp w/o top 1%"] > 0}
    passed = all(bool(v) for v in crit.values())

    table = {("ungated", "histdata 2009-2017"): stats(cal, 9.0), ("ungated", "2018-Sep 2025"): stats(pep, 7.75),
             ("gated", "2018-Sep 2025"): g}
    if passed:  # the holdout is opened only if everything above passes
        hm = {s: load_m1("2025-08-01", None, symbol=s, allow_holdout=True) for s in syms}
        hold = gate(between(silver_trades(*(hm[s] for s in syms)), *HOLDOUT))
        table[("gated", "holdout Oct 2025-Sep 2026")] = stats(hold, 1.0)
        crit["H  holdout gated realistic net > 0"] = table[("gated", "holdout Oct 2025-Sep 2026")]["net bp (realistic)"] > 0

    # overlap with gold's live (gated) strategy, 2018-Sep 2025
    gold = gold_gated(m1["XAUUSD"], m1["EURUSD"], m1["USDJPY"])
    both = pd.merge_asof(gp.sort_values("entry_time"), gold[["entry_time", "net_bp"]].sort_values("entry_time"),
                         on="entry_time", direction="nearest", tolerance=pd.Timedelta(minutes=5))
    overlap = {"silver gated trades": len(gp), "gold gated trades": len(gold),
               "silver trades on shocks gold also traded": int(both.net_bp.notna().sum()),
               "silver trades where gold's gate skipped": int(both.net_bp.isna().sum()),
               "correlation of net bp on shared shocks": both[["net_real_bp", "net_bp"]].dropna().corr().iloc[0, 1],
               "silver net bp on shocks gold skipped": both[both.net_bp.isna()].net_real_bp.mean()}

    by_year = pd.DataFrame({"ungated trades": pep.groupby(pep.entry_time.dt.year).size(),
                            "gated trades": gp.groupby(gp.entry_time.dt.year).size(),
                            "ungated net bp": pep.groupby(pep.entry_time.dt.year).net_real_bp.sum(),
                            "gated net bp": gp.groupby(gp.entry_time.dt.year).net_real_bp.sum()}).fillna(0).rename_axis("year")
    news = is_news(gp.entry_time)
    out = [f"# H19 results\n\nRun {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC, as pre-registered in `H19-silver.md`. "
           "Per trade, in bp of silver's entry price; 30-minute hold.\n",
           f"Calibrated on histdata 2009-2017: **beta = {beta:.3f}** (gross $/oz per trade per $ of silver M5 ATR). "
           f"Gate: trade only if {beta:.3f} x ATR >= the trade's realistic cost.\n", "## Criteria\n",
           md(pd.DataFrame({k: {"PASS": bool(v)} for k, v in crit.items()}).T.rename_axis("criterion")),
           f"\n**Overall: {'PASS' if all(bool(v) for v in crit.values()) else 'FAIL'}**"
           f"{'' if passed else ' (holdout not opened)'}\n",
           "## Results\n", md(pd.DataFrame(table).T.rename_axis(["strategy", "sample"])),
           "\n## Gated net bp by sub-period\n", md(pd.DataFrame({"net bp": subs}).rename_axis("sub-period")),
           f"\nGated trades at 08:30-08:44 New York: {int(news.sum())} of {len(gp)}.\n",
           "\n## By year, 2018-2025 (realistic net, bp)\n", md(by_year),
           "\n## Overlap with gold's live strategy, 2018-Sep 2025\n", md(pd.DataFrame({"value": overlap}).rename_axis("measure"))]
    (ROOT / "research" / "H19-results.md").write_text("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
