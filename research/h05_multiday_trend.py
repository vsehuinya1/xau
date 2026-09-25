"""H05: does gold's multi-day trend pay after swap and trading costs?

Implements research/H05-multiday-trend.md as pre-registered (commit f66ee9a).
  --check   print data-construction checks and position shares, no returns
  (default) run the study and write research/H05-results.md
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from xau.bars import load_m1  # noqa: E402
from xau.daily import daily_closes  # noqa: E402
from xau.rates import fed_funds  # noqa: E402
from xau.report import md  # noqa: E402
from xau.sessions import trading_day  # noqa: E402
from xau.stats import max_drawdown, newey_west_t  # noqa: E402

LOOKBACKS = (21, 63, 252)
START, LAST_DECISION = pd.Timestamp("1999-06-01"), pd.Timestamp("2025-09-29")
SPREAD, COST_FIXED = 0.40, 0.11           # $/oz per unit of position change
LONG_MARKUP, SHORT_MARKUP = 3.51, 1.18    # % a year above / below Fed funds
NW_LAGS = 10
CURRENT_REGIME = pd.Timestamp("2022-03-17")
ERAS = [("1999-2007", "1999-01-01", "2008-01-01"), ("2008-2016", "2008-01-01", "2017-01-01"),
        ("2017-Sep25", "2017-01-01", "2025-10-01")]
DAYS_PER_YEAR = 252


def load():
    closes = daily_closes()
    ff = fed_funds().reindex(closes.index, method="ffill")  # latest value on or before each day
    return closes, ff


def signal(closes, lookbacks):
    """Average sign of the log returns over the lookbacks; NaN until all exist."""
    logc = np.log(closes)
    return sum(np.sign(logc - logc.shift(n)) for n in lookbacks) / len(lookbacks)


def run(closes, ff, position):
    """Daily net returns (fraction of notional), dated by the day they're realised."""
    in_window = (position.index >= START) & (position.index <= LAST_DECISION)
    w = position.where(in_window, 0).fillna(0)
    nxt = closes.shift(-1) / closes - 1
    cost = w.diff().abs().fillna(w.abs()) * (SPREAD + COST_FIXED) / closes
    nights = pd.Series(np.where(closes.index.dayofweek == 2, 3, 1), index=closes.index)
    swap = (-w.clip(lower=0) * (ff + LONG_MARKUP) + (-w).clip(lower=0) * (ff - SHORT_MARKUP)) / 100 * nights / 365
    net = (w * nxt - cost + swap)[in_window]
    parts = pd.DataFrame({"gross": (w * nxt)[in_window], "cost": cost[in_window], "swap": swap[in_window],
                          "position": w[in_window]})
    realised = closes.index[closes.index.get_indexer(net.index) + 1]
    net.index = parts.index = realised
    return net, parts


def annual(x):
    return x.mean() * DAYS_PER_YEAR * 100  # % of notional a year


def check():
    bars = load_m1()
    raw = bars.close.groupby(trading_day(bars.index)).last()
    print(f"trading days with bars: {len(raw)}; weekend-labelled days dropped: {int((raw.index.dayofweek >= 5).sum())}")
    closes, ff = load()
    print(f"daily closes: {len(closes)} from {closes.index[0]:%Y-%m-%d} to {closes.index[-1]:%Y-%m-%d}")
    print("per year:", dict(closes.groupby(closes.index.year).size()))
    window = (closes.index >= START) & (closes.index <= LAST_DECISION)
    print(f"Fed funds missing in the test window: {int(ff[window].isna().sum())}")
    for price, rate in ((4280, 3.88),):
        long_night = (rate + LONG_MARKUP) / 100 / 365 * price
        short_night = (rate - SHORT_MARKUP) / 100 / 365 * price
        print(f"modelled swap at ${price} and Fed funds {rate}%: long -${long_night:.3f}/oz/night "
              f"(quote -$0.866), short +${short_night:.3f} (quote +$0.317)")
    pos = signal(closes, LOOKBACKS)[window]
    print(f"first decision {pos.index[0]:%Y-%m-%d}, NaN positions in window: {int(pos.isna().sum())}")
    print("position shares:", pos.value_counts(normalize=True).sort_index().round(3).to_dict())


def main():
    if "--check" in sys.argv:
        return check()
    closes, ff = load()
    net, parts = run(closes, ff, signal(closes, LOOKBACKS))
    singles = {n: run(closes, ff, signal(closes, (n,)))[0] for n in LOOKBACKS}
    hold, hold_parts = run(closes, ff, pd.Series(1.0, index=closes.index))

    t = newey_west_t(net, NW_LAGS)
    current = net[net.index >= CURRENT_REGIME]
    eras = {n: net[(net.index >= a) & (net.index < b)] for n, a, b in ERAS}
    yearly = net.groupby(net.index.year).sum()
    best = int(yearly.idxmax())
    rest = net[net.index.year != best]
    t_rest = newey_west_t(rest, NW_LAGS)
    crit = [net.mean() > 0 and t >= 2, current.mean() > 0, all(e.mean() > 0 for e in eras.values()),
            all(s.mean() > 0 for s in singles.values()), rest.mean() > 0 and t_rest >= 1.5]
    verdict = pd.DataFrame({"trend (1/3/12-month)": {
        "days": len(net), "net %/yr": annual(net), "t (NW)": t, **{f"C{n + 1}": bool(c) for n, c in enumerate(crit)},
        "PASS": all(crit)}}).T.rename_axis("test")

    beta = np.polyfit(hold_parts.gross, net, 1)[0]
    alpha = net - beta * hold_parts.gross
    sharpe = lambda x: x.mean() / x.std() * np.sqrt(DAYS_PER_YEAR)  # noqa: E731
    details = pd.DataFrame({
        "trend": {"net %/yr": annual(net), "gross %/yr": annual(parts.gross), "costs %/yr": -annual(parts.cost),
                  "swap %/yr": annual(parts.swap), "Sharpe": sharpe(net), "t (NW)": t,
                  "max drawdown %": max_drawdown(net) * 100, "position changes/yr": parts.position.diff().abs().sum() / (len(net) / DAYS_PER_YEAR),
                  "time long %": (parts.position > 0).mean() * 100, "time short %": (parts.position < 0).mean() * 100,
                  f"net %/yr since {CURRENT_REGIME:%Y-%m-%d}": annual(current),
                  **{f"net %/yr {n}": annual(e) for n, e in eras.items()},
                  **{f"net %/yr, {n}-day only": annual(s) for n, s in singles.items()},
                  f"net %/yr without {best} (best year)": annual(rest), f"t without {best}": t_rest,
                  "alpha over buy-and-hold %/yr": annual(alpha), "beta to buy-and-hold": beta,
                  "t of alpha (NW)": newey_west_t(alpha, NW_LAGS)},
        "buy-and-hold": {"net %/yr": annual(hold), "gross %/yr": annual(hold_parts.gross),
                         "costs %/yr": -annual(hold_parts.cost), "swap %/yr": annual(hold_parts.swap),
                         "Sharpe": sharpe(hold), "t (NW)": newey_west_t(hold, NW_LAGS),
                         "max drawdown %": max_drawdown(hold) * 100}})
    by_year = pd.DataFrame({"trend net %": yearly * 100, "buy-and-hold net %": hold.groupby(hold.index.year).sum() * 100,
                            "mean position": parts.position.groupby(parts.index.year).mean()}).rename_axis("year")

    out = [f"# H05 results\n\nRun {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC on Pepperstone daily closes "
           f"1998-2025-09-30, as pre-registered in `H05-multiday-trend.md` (commit f66ee9a).\n",
           "## Verdict\n", md(verdict),
           "\nC1: mean > 0 with t >= 2 (Newey-West, 10 lags). C2: mean > 0 since 2022-03-17. C3: mean > 0 in each era. "
           "C4: each lookback alone has mean > 0. C5: without the best year, mean > 0 and t >= 1.5.\n",
           "## Details\n", md(details.rename_axis("")), "\nReturns are % of notional per year (daily mean x 252), "
           "at a fixed notional (no compounding).\n", "## By year\n", md(by_year)]
    (ROOT / "research" / "H05-results.md").write_text("\n".join(out) + "\n")
    print(md(verdict))


if __name__ == "__main__":
    main()
