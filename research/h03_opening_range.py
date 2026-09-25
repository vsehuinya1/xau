"""H03: do opening-range breakouts at the London open and after the 08:30 NY
data keep going?

Implements research/H03-opening-range.md as pre-registered (commit 2ce29f4).
  --check   print counts and sample breakouts up to the entry bar, no outcomes
  (default) run the study and write research/H03-results.md
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from xau.bars import load_m1  # noqa: E402
from xau.eventstudy import MIN, Bars, clustered_t, control_means, evaluate, prior_bin, series_at  # noqa: E402
from xau.features import m5_atr, m5_bars  # noqa: E402
from xau.report import md  # noqa: E402
from xau.sessions import NY, SESSIONS, session  # noqa: E402

# test: (clock, range start, window end), times as (hour, minute) on that clock
TESTS = {"London": ("Europe/London", (8, 0), (13, 0)), "New York": (NY, (8, 30), (12, 0))}
RANGE_MINUTES = 15
MIN_BARS = 10        # of the 15 range bars
HISTORY = 60         # previous ranges for the size filter
SIZE_PCT = (0.2, 0.8)
HORIZONS = (30, 60, 120)
PRIMARY = 60
MAX_WAIT = 5         # minutes; a later reference bar means the market was closed
COST_FIXED = 0.11    # $/oz per round trip: commission 0.09 + slippage 0.02
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri")


def load():
    m1 = load_m1("2018-01-01")  # the loader keeps the holdout locked
    m5 = m5_bars(m1)
    return dict(m1=m1, bars=Bars(m1), sess=session(m1.index), hour=m1.index.tz_convert(NY).hour.to_numpy(),
                atr=m5_atr(m1), m5=m5, m5_tc=(m5.index + pd.Timedelta(minutes=5)).as_unit("ns").asi8,
                m5_close=m5.close.to_numpy(float))


def ranges(d, clock, start, end):
    """One row per local date: the opening range, its size filter and times (ns)."""
    m1 = d["m1"]
    local = m1.index.tz_convert(clock)
    minute = local.hour * 60 + local.minute
    first = start[0] * 60 + start[1]
    inside = (minute >= first) & (minute < first + RANGE_MINUTES)
    date = local.tz_localize(None).normalize()[inside]
    g = m1[inside].groupby(date)
    r = pd.DataFrame({"high": g.high.max(), "low": g.low.min(), "bars": g.size()})
    r = r[r.bars >= MIN_BARS]
    r["height"] = r.high - r.low
    past = r.height.shift(1).rolling(HISTORY, min_periods=HISTORY)
    r["lo_pct"], r["hi_pct"] = past.quantile(SIZE_PCT[0]), past.quantile(SIZE_PCT[1])
    r["normal"] = (r.height >= r.lo_pct) & (r.height <= r.hi_pct)
    to_ns = lambda offset: (r.index + offset).tz_localize(clock).tz_convert("UTC").as_unit("ns").asi8  # noqa: E731
    r["range_end"] = to_ns(pd.Timedelta(minutes=first + RANGE_MINUTES))
    r["window_end"] = to_ns(pd.Timedelta(hours=end[0], minutes=end[1]))
    return r


def breakouts(d, r):
    """First M5 close beyond the range after it ends, per normal-size day."""
    bars, m5_tc, m5_close = d["bars"], d["m5_tc"], d["m5_close"]
    rows = []
    for date, x in r[r.normal].iterrows():
        a0 = np.searchsorted(m5_tc, int(x.range_end), side="right")   # closes after the range ends
        a1 = np.searchsorted(m5_tc, int(x.window_end), side="right")  # ... and no later than the window end
        side = np.sign((m5_close[a0:a1] > x.high).astype(int) - (m5_close[a0:a1] < x.low).astype(int))
        hit = np.flatnonzero(side != 0)
        if len(hit):
            rows.append((date, int(side[hit[0]]), int(m5_tc[a0 + hit[0]]), x.high, x.low, x.height))
    ev = pd.DataFrame(rows, columns=["day", "direction", "decided", "range_high", "range_low", "height"])
    k = bars.next_bar(ev.decided.to_numpy())
    ok = k < len(bars.t)
    k = np.clip(k, 0, len(bars.t) - 1)
    ok &= bars.t[k] <= ev.decided.to_numpy() + MAX_WAIT * MIN
    ev["ref"] = np.where(ok, k, -1)
    return ev


def measure(ev, d):
    """Forward moves from the reference bar's open, in the breakout direction."""
    bars = d["bars"]
    ev = ev[ev.ref >= 0].copy()
    k, dirn = ev.ref.to_numpy(), ev.direction.to_numpy()
    r, p_ref = bars.t[k], bars.open[k]
    a = series_at(d["atr"], r)
    ev["atr"], ev["time"] = a, pd.to_datetime(r, utc=True)
    ev["weekday"] = [WEEKDAYS[x.weekday()] for x in ev.day]
    ev["session"], ev["hour"] = d["sess"][k], d["hour"][k]
    ev["prior"] = dirn * (p_ref - bars.price_at(r - 15 * MIN)) / a
    ev["cost"] = bars.spread[k] + COST_FIXED
    for h in HORIZONS:
        ev[f"move{h}"] = dirn * (bars.price_at(r + h * MIN) - p_ref)
        ev[f"atr{h}"] = ev[f"move{h}"] / a
        ev[f"net{h}"] = ev[f"move{h}"] - ev.cost
    mfe, mae = bars.excursions(k, dirn, minutes=120)
    ev["mfe"], ev["mae"] = mfe / a, mae / a
    ev["mfe_range"], ev["mae_range"] = mfe / ev.height.to_numpy(), mae / ev.height.to_numpy()
    ev["bin"] = prior_bin(ev.prior.to_numpy())
    keep = np.isfinite(ev.prior.to_numpy()) & np.isfinite(a) & (r + 120 * MIN <= bars.tc[-1])
    return ev[keep]


def check(d):
    bars = d["bars"]
    for name, (clock, start, end) in TESTS.items():
        r = ranges(d, clock, start, end)
        ev = breakouts(d, r)
        print(f"\n== {name}: {len(r)} days with a range, {int(r.lo_pct.notna().sum())} with 60 days of history, "
              f"{int(r.normal.sum())} normal-size, {len(ev)} breakouts, {int((ev.ref >= 0).sum())} with a reference bar")
        for _, e in ev[ev.ref >= 0].sample(2, random_state=3).iterrows():
            x = r.loc[e.day]
            k = int(e.ref)
            print(f"\n{e.day:%Y-%m-%d} {'long' if e.direction > 0 else 'short'}: range {x.low:.2f}-{x.high:.2f} "
                  f"(height {x.height:.2f}, normal band {x.lo_pct:.2f}-{x.hi_pct:.2f}), range ends "
                  f"{pd.Timestamp(int(x.range_end), tz='UTC'):%H:%M} UTC")
            a0 = np.searchsorted(d["m5_tc"], x.range_end, side="right")
            a1 = np.searchsorted(d["m5_tc"], e.decided, side="right")
            for t5, c5 in zip(d["m5_tc"][a0:a1], d["m5_close"][a0:a1]):
                print(f"  M5 close {pd.Timestamp(int(t5), tz='UTC'):%H:%M} UTC: {c5:.2f}")
            print(f"  ref {pd.Timestamp(bars.t[k], tz='UTC'):%H:%M} UTC, entry at open {bars.open[k]:.2f}")


def main():
    d = load()
    if "--check" in sys.argv:
        return check(d)
    bars = d["bars"]
    atr = series_at(d["atr"], bars.t)
    keep = np.isin(d["sess"], SESSIONS) & np.isfinite(atr) & (bars.t + 120 * MIN <= bars.tc[-1])
    cm, n_controls = control_means(bars, atr, d["sess"], d["hour"], keep, HORIZONS)
    tests, counts = {}, {}
    for name, (clock, start, end) in TESTS.items():
        r = ranges(d, clock, start, end)
        ev = measure(breakouts(d, r), d)
        key = pd.MultiIndex.from_arrays([ev.session, ev.hour, ev.bin])
        for h in HORIZONS:
            ev[f"exc{h}"] = ev[f"atr{h}"].to_numpy() - cm[h].reindex(key).to_numpy()
        tests[name] = ev[np.isfinite(ev[f"exc{PRIMARY}"].to_numpy())]
        counts[name] = {"days with a range": len(r), "normal-size": int(r.normal.sum()), "events": len(tests[name])}
    cells = pd.DataFrame({n: evaluate(ev, HORIZONS, PRIMARY, split="weekday", groups=WEEKDAYS)
                          for n, ev in tests.items()}).T
    cells.index.name = "test"
    cols = ["events", f"t {PRIMARY}m", "C1", "C2", "C3", "C4", "C5", "PASS"]

    out = [f"# H03 results\n\nRun {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC on M1 bars "
           f"2018-01-01 to 2025-09-30, as pre-registered in `H03-opening-range.md` (commit 2ce29f4).\n",
           "## Verdict\n", md(cells[cols]),
           f"\nC1: t >= 3 against the matched control at {PRIMARY}m. C2: after-cost {PRIMARY}m move > 0 in "
           "2024-Sep 2025. C3: positive excess in all three sub-periods. C4: t >= 2 without the best weekday. "
           "C5: C2 holds without the top 1% of events.\n",
           "## Ranges\n", md(pd.DataFrame(counts).T.rename_axis("test")),
           f"\nControls: {n_controls:,} M1 moments, each used long and short.\n",
           "## Each test in full\n", md(cells.drop(columns=["C1", "C2", "C3", "C4", "C5", "PASS"]).T)]
    both = pd.concat(tests, names=["test"]).reset_index(level=0)
    both["year"] = both.time.dt.year
    for name, col in (("side", "direction"), ("weekday", "weekday"), ("year", "year")):
        by = both.groupby(["test", col])
        out.append(f"\n## By {name} (diagnostic)\n")
        out.append(md(pd.DataFrame({"events": by.size(), f"excess {PRIMARY}m (ATR)": by[f"exc{PRIMARY}"].mean(),
                                    f"t {PRIMARY}m": by.apply(lambda g: clustered_t(g[f"exc{PRIMARY}"], g.day))})))
    by = both.groupby("test")
    out.append("\n## Excursions within 120 minutes (diagnostic)\n")
    out.append(md(pd.DataFrame({"MFE median (ATR)": by.mfe.median(), "MAE median (ATR)": by.mae.median(),
                                "MFE median (x range)": by.mfe_range.median(), "MAE median (x range)": by.mae_range.median(),
                                "MFE p75 (x range)": by.mfe_range.quantile(0.75)})))
    (ROOT / "research" / "H03-results.md").write_text("\n".join(out) + "\n")
    print(md(cells[cols]))


if __name__ == "__main__":
    main()
