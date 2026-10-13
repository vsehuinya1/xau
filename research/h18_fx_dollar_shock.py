"""H18: do forex pairs also follow broad dollar shocks?

Implements research/H18-fx-dollar-shock.md as pre-registered.
Writes research/H18-results.md.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from xau.bars import load_m1  # noqa: E402
from xau.dollar_shock import MAX_WAIT, shocks  # noqa: E402
from xau.eventstudy import MIN, Bars, clustered_t  # noqa: E402
from xau.histdata import load_histdata  # noqa: E402
from xau.report import md  # noqa: E402
from xau.sessions import trading_day  # noqa: E402

PAIRS = {"EURUSD": -1, "GBPUSD": -1, "AUDUSD": -1, "USDJPY": 1, "USDCAD": 1, "USDCHF": 1}  # pair move per dollar-up
PIP = {p: (0.01 if p.endswith("JPY") else 0.0001) for p in PAIRS}
POINT = {p: PIP[p] / 10 for p in PAIRS}  # 5-digit / 3-digit quotes
HOLD = 30


def news_extra_pips(entry_times):
    ny = pd.DatetimeIndex(entry_times).tz_convert("America/New_York")
    minute = ny.hour * 60 + ny.minute
    return np.where((minute >= 510) & (minute < 525), 2.0, 0.2)


def trade_pair(sig, m1, pair, flat_cost):
    b = Bars(m1)
    spread_pips = m1["spread"].to_numpy(float) * POINT[pair] / PIP[pair]
    rows, busy = [], None
    for s in sig.itertuples():
        k = int(np.searchsorted(b.t, s.time, side="left"))
        if k >= len(b.t) or b.t[k] > s.time + MAX_WAIT * MIN or (busy is not None and b.t[k] < busy):
            continue
        exit_t = b.t[k] + HOLD * MIN
        if exit_t > b.tc[-1]:
            break
        d = -s.direction * PAIRS[pair]  # gold direction is against the dollar: dollar-up = -gold
        gross = d * (b.price_at(np.array([exit_t]))[0] - b.open[k]) / PIP[pair]
        cost = flat_cost if flat_cost is not None else spread_pips[k] + 0.8
        rows.append((pd.Timestamp(b.t[k], tz="UTC"), d, gross, cost))
        busy = exit_t
    tr = pd.DataFrame(rows, columns=["entry_time", "side", "gross", "cost"])
    tr["net"] = tr.gross - tr.cost
    tr["net_harsh"] = tr.net - news_extra_pips(tr.entry_time)
    return tr


def stats(tr):
    day = trading_day(pd.DatetimeIndex(tr.entry_time))
    return {"trades": len(tr), "gross pips": tr.gross.mean(), "t gross": clustered_t(tr.gross, day),
            "net pips (harsh)": tr.net_harsh.mean(), "t (harsh)": clustered_t(tr.net_harsh, day),
            "net pips (base)": tr.net.mean(), "win rate % (harsh)": (tr.net_harsh > 0).mean() * 100}


def main():
    yrs = range(2009, 2018)
    hist = {p: load_histdata(p.lower(), yrs) for p in PAIRS}
    pep = {p: load_m1("2018-01-01", symbol=p) for p in PAIRS}
    samples = {"histdata 2009-2017": (hist, 1.0), "Pepperstone 2018-Sep 2025": (pep, None)}
    table, verdict = {}, {}
    for name, (d, flat) in samples.items():
        sig = shocks(d["EURUSD"], d["USDJPY"], 3.0)
        for p in PAIRS:
            table[(p, name)] = stats(trade_pair(sig, d[p], p, flat))
    for p in PAIRS:
        verdict[p] = all(table[(p, n)]["net pips (harsh)"] > 0 and table[(p, n)]["t (harsh)"] >= 2 for n in samples)
    out = [f"# H18 results\n\nRun {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC, as pre-registered in "
           "`H18-fx-dollar-shock.md`. Pips per trade, 30-minute hold, trade in the dollar's direction.\n",
           "## Verdict (both samples: harsh net > 0 with t >= 2)\n",
           md(pd.DataFrame({p: {"PASS": v} for p, v in verdict.items()}).T.rename_axis("pair")),
           "\n## Results\n", md(pd.DataFrame(table).T.rename_axis(["pair", "sample"]))]
    (ROOT / "research" / "H18-results.md").write_text("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
