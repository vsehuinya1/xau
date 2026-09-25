"""H04: does gold rise in Asian hours and fall in New York hours?

Implements research/H04-time-of-day.md as pre-registered (commit 4707015).
  --check   print leg counts and sample leg times, no prices or returns
  (default) run the study and write research/H04-results.md
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from xau.bars import load_m1  # noqa: E402
from xau.eventstudy import MIN, RECENT, SUBPERIODS, Bars, clustered_t  # noqa: E402
from xau.report import md  # noqa: E402
from xau.sessions import NY, trading_day  # noqa: E402

# leg: (direction, start, end) in New York time; a start after the end means
# it begins on the previous calendar day (the trading day opens at 18:00).
LEGS = {"Asia": (1, (19, 0), (3, 0)), "New York": (-1, (8, 0), (16, 0))}
DIAGNOSTIC_LEGS = {"London (unsigned)": (1, (3, 0), (8, 0))}
MAX_WAIT = 5       # minutes after the target time a bar may open
COST_FIXED = 0.11  # $/oz per round trip: commission 0.09 + slippage 0.02
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri")


def ny_time(days, hm, previous_day=False):
    """UTC nanoseconds of New York time hm on each trading day (or the day before)."""
    local = days - pd.Timedelta(days=1 if previous_day else 0) + pd.Timedelta(hours=hm[0], minutes=hm[1])
    return local.tz_localize(NY).tz_convert("UTC").as_unit("ns").asi8


def bar_at(bars, times):
    """Index of the first bar opening within MAX_WAIT minutes of each time, else -1."""
    k = np.searchsorted(bars.t, times, side="left")
    ok = k < len(bars.t)
    k = np.clip(k, 0, len(bars.t) - 1)
    ok &= bars.t[k] <= times + MAX_WAIT * MIN
    return np.where(ok, k, -1)


def legs(bars, days, spec):
    """Per trading day: entry and exit bar of each leg (-1 if missing)."""
    out = {}
    for name, (direction, start, end) in spec.items():
        overnight = start > end
        out[name] = (direction, bar_at(bars, ny_time(days, start, previous_day=overnight)), bar_at(bars, ny_time(days, end)))
    return out


def leg_returns(bars, direction, k_in, k_out):
    """Signed log return and cost, in basis points; NaN where a bar is missing."""
    ok = (k_in >= 0) & (k_out >= 0)
    p_in, p_out = bars.open[np.clip(k_in, 0, None)], bars.open[np.clip(k_out, 0, None)]
    ret = np.where(ok, direction * np.log(p_out / p_in) * 1e4, np.nan)
    cost = np.where(ok, (bars.spread[np.clip(k_in, 0, None)] + COST_FIXED) / p_in * 1e4, np.nan)
    usd = np.where(ok, direction * (p_out - p_in), np.nan)
    return ret, cost, usd


def load():
    m1 = load_m1("2018-01-01")  # the loader keeps the holdout locked
    days = pd.DatetimeIndex(np.unique(trading_day(m1.index)))
    days = days[days.dayofweek < 5]  # trading days are labelled Mon-Fri
    return Bars(m1), days


def check(bars, days):
    spec = legs(bars, days, {**LEGS, **DIAGNOSTIC_LEGS})
    print(f"{len(days)} trading days")
    for name, (_, k_in, k_out) in spec.items():
        print(f"  {name}: entry bar found {np.mean(k_in >= 0):.1%}, exit bar found {np.mean(k_out >= 0):.1%}")
    for day in ("2024-01-10", "2024-07-10", "2018-01-10"):  # winter, summer, the 2017/18 anomaly winter
        i = days.get_loc(pd.Timestamp(day))
        print(f"\ntrading day {day}:")
        for name, (_, k_in, k_out) in spec.items():
            show = lambda k: f"{pd.Timestamp(bars.t[k], tz='UTC'):%a %H:%M} UTC = {pd.Timestamp(bars.t[k], tz='UTC').tz_convert(NY):%a %H:%M} NY" if k >= 0 else "missing"  # noqa: E731
            print(f"  {name}: in {show(k_in[i])}, out {show(k_out[i])}")


def summarize(frame, col, days_col="week"):
    return pd.Series({"days": frame[col].notna().sum(), "mean (bp)": frame[col].mean(),
                      "t": clustered_t(frame[col].dropna(), frame.loc[frame[col].notna(), days_col])})


def main():
    bars, days = load()
    if "--check" in sys.argv:
        return check(bars, days)
    d = pd.DataFrame(index=days.rename("day"))
    d["weekday"] = [WEEKDAYS[x.dayofweek] for x in days]
    iso = days.isocalendar()
    d["week"] = (iso.year.astype(str) + "-" + iso.week.astype(str).str.zfill(2)).to_numpy()
    for name, (direction, k_in, k_out) in legs(bars, days, {**LEGS, **DIAGNOSTIC_LEGS}).items():
        d[f"{name} bp"], d[f"{name} cost"], d[f"{name} $"] = leg_returns(bars, direction, k_in, k_out)
    d["S"] = d["Asia bp"] + d["New York bp"]
    d["net"] = d.S - d["Asia cost"] - d["New York cost"]
    d["S $"] = d["Asia $"] + d["New York $"]
    s = d.dropna(subset=["S"]).reset_index()

    def between(f, a, b):
        return f[(f.day >= pd.Timestamp(a)) & (f.day < pd.Timestamp(b))]

    recent = between(s, *RECENT)
    t = clustered_t(s.S, s.week)
    subs = {name: between(s, a, b).S.mean() for name, a, b in SUBPERIODS}
    drops = {w: clustered_t(s[s.weekday != w].S, s[s.weekday != w].week) for w in WEEKDAYS}
    worst = min(drops, key=lambda w: drops[w])
    trimmed = recent[recent.net < recent.net.quantile(0.99)].net.mean()
    crit = [t >= 3, recent.net.mean() > 0, all(v > 0 for v in subs.values()), drops[worst] >= 2, trimmed > 0]
    verdict = pd.DataFrame({"S (Asia long + NY short)": {
        "days": len(s), "mean S (bp)": s.S.mean(), "t": t, **{f"C{n + 1}": bool(c) for n, c in enumerate(crit)},
        "PASS": all(crit)}}).T
    details = pd.Series({
        "2024-25 days": len(recent), "2024-25 mean S (bp)": recent.S.mean(),
        "2024-25 cost, both legs (bp)": (recent["Asia cost"] + recent["New York cost"]).mean(),
        "2024-25 mean net (bp)": recent.net.mean(), "2024-25 mean S ($/oz)": recent["S $"].mean(),
        **{f"mean S {n} (bp)": v for n, v in subs.items()},
        "t without best weekday": drops[worst], "best weekday": worst, "2024-25 net, top 1% cut (bp)": trimmed})

    out = [f"# H04 results\n\nRun {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC on M1 bars "
           f"2018-01-01 to 2025-09-30, as pre-registered in `H04-time-of-day.md` (commit 4707015).\n",
           "## Verdict\n", md(verdict.rename_axis("test")),
           "\nC1: mean S > 0 with t >= 3 (clustered by week). C2: mean S after both legs' costs > 0 in "
           "2024-Sep 2025. C3: mean S > 0 in all three sub-periods. C4: t >= 2 without the best weekday. "
           "C5: C2 holds without the top 1% of days.\n",
           "## The test in full\n", md(details.to_frame("S").rename_axis("")), "\n## Each leg by year (diagnostic)\n",
           "Returns are signed as traded: Asia long, New York short. London is unsigned (long).\n"]
    s["year"] = s.day.dt.year
    rows = {}
    for leg in ("Asia bp", "New York bp", "London (unsigned) bp", "S"):
        for year, g in s.groupby("year"):
            rows[(leg, year)] = summarize(g, leg)
        rows[(leg, "all")] = summarize(s, leg)
    out.append(md(pd.DataFrame(rows).T))
    (ROOT / "research" / "H04-results.md").write_text("\n".join(out) + "\n")
    print(md(verdict.rename_axis("test")))


if __name__ == "__main__":
    main()
