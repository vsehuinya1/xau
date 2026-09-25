"""H01: what happens when gold pushes through an obvious level?

Implements research/H01-level-pokes.md as pre-registered (commit ab8ba89).
  --check   print event counts and sample events with their bars, no outcomes
  (default) run the study and write research/H01-results.md
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from xau.bars import load_m1  # noqa: E402
from xau.eventstudy import MIN, Bars, clustered_t, control_means, prior_bin, series_at  # noqa: E402
from xau.features import m5_atr, m5_bars  # noqa: E402
from xau.levels import daily_levels  # noqa: E402
from xau.sessions import NY, SESSIONS, session, trading_day  # noqa: E402

HORIZONS = (15, 30, 60)
WINDOW = 10           # minutes after the push to decide reclaim vs acceptance
ACCEPT_ATR = 0.1      # acceptance: an M5 close this many ATR beyond the level
MAX_WAIT = 5          # minutes; a later reference bar means the market was closed
ROUND = 50.0          # round-number spacing, $
COST_FIXED = 0.11     # $/oz per round trip: commission 0.09 + slippage 0.02
NEAR_LEVEL_ATR = 0.5  # controls must be at least this far from any level
SUBPERIODS = [("2018-20", "2018-01-01", "2021-01-01"),
              ("2021-22", "2021-01-01", "2023-01-01"),
              ("2023-Sep25", "2023-01-01", "2025-10-01")]
RECENT = ("2024-01-01", "2025-10-01")
NEVER = np.iinfo(np.int64).max


def utc(s):
    return pd.Timestamp(s, tz="UTC")


def load():
    m1 = load_m1("2018-01-01")  # the loader keeps the holdout locked
    day = trading_day(m1.index).to_numpy()
    sess = session(m1.index)
    lv = daily_levels(m1).reindex(pd.DatetimeIndex(day))
    asia_known = np.isin(sess, ["London", "NY am", "NY pm"])
    levels = {"pdh": lv.pdh.to_numpy(), "pdl": lv.pdl.to_numpy(),
              "asia_hi": np.where(asia_known, lv.asia_hi.to_numpy(), np.nan),
              "asia_lo": np.where(asia_known, lv.asia_lo.to_numpy(), np.nan)}
    return dict(m1=m1, bars=Bars(m1), day=day, sess=sess, hour=m1.index.tz_convert(NY).hour.to_numpy(),
                levels=levels, atr=m5_atr(m1), m5=m5_bars(m1))


def find_pushes(d):
    """First bar per trading day, level and side whose high (low) trades
    through a level that was above (below) the previous bar's close."""
    bars, levels = d["bars"], d["levels"]
    prev = np.r_[np.nan, bars.close[:-1]]
    found = []

    def add(level, kind):
        with np.errstate(invalid="ignore"):
            up = (level > prev) & (bars.high > level)
            down = (level < prev) & (bars.low < level)
        for side, mask in ((1, up), (-1, down)):
            i = np.flatnonzero(mask)
            found.append(pd.DataFrame({"i": i, "kind": kind, "level": level[i], "side": side}))

    add(levels["pdh"], "prior-day")
    add(levels["pdl"], "prior-day")
    add(levels["asia_hi"], "Asia")
    add(levels["asia_lo"], "Asia")
    with np.errstate(invalid="ignore"):
        above = (np.floor(prev / ROUND) + 1) * ROUND
        below = (np.ceil(prev / ROUND) - 1) * ROUND
    for k in range(3):  # a fast bar can cross more than one $50 level
        add(above + k * ROUND, "round")
        add(below - k * ROUND, "round")
    ev = pd.concat(found, ignore_index=True)
    ev["day"] = d["day"][ev.i]
    ev = ev.sort_values("i", kind="stable").drop_duplicates(["day", "kind", "level", "side"])
    return ev.reset_index(drop=True)


def classify(ev, d):
    """Reclaim or acceptance, whichever comes first within WINDOW minutes, and
    the reference bar that a trade would enter on."""
    bars, m5 = d["bars"], d["m5"]
    m5_tc = (m5.index + pd.Timedelta(minutes=5)).as_unit("ns").asi8
    m5_close = m5.close.to_numpy(float)
    atr = series_at(d["atr"], bars.t[ev.i.to_numpy()])  # M5 bars closed by the push bar's open
    paths, decided = [], []
    for i, level, side, a in zip(ev.i.to_numpy(), ev.level.to_numpy(), ev.side.to_numpy(), atr):
        p = bars.tc[i]
        end = np.searchsorted(bars.tc, p + WINDOW * MIN, side="right")
        rec = np.flatnonzero(side * (bars.close[i:end] - level) < 0)
        t_rec = bars.tc[i + rec[0]] if len(rec) else NEVER
        t_acc = NEVER
        if np.isfinite(a):
            a0 = np.searchsorted(m5_tc, p, side="left")
            a1 = np.searchsorted(m5_tc, p + WINDOW * MIN, side="right")
            acc = np.flatnonzero(side * (m5_close[a0:a1] - level) >= ACCEPT_ATR * a)
            t_acc = m5_tc[a0 + acc[0]] if len(acc) else NEVER
        if t_rec == t_acc:  # neither happened (both NEVER); they can't tie otherwise
            paths.append("neither")
            decided.append(0)
        else:
            paths.append("reclaim" if t_rec < t_acc else "acceptance")
            decided.append(min(t_rec, t_acc))
    ev = ev.assign(atr=atr, path=paths, decided=np.array(decided, dtype=np.int64))
    ev["direction"] = np.where(ev.path == "reclaim", -ev.side, ev.side)
    k = bars.next_bar(ev.decided.to_numpy())
    ok = (ev.path != "neither").to_numpy() & (k < len(bars.t))
    k = np.clip(k, 0, len(bars.t) - 1)
    ok &= bars.t[k] <= ev.decided.to_numpy() + MAX_WAIT * MIN
    ev["ref"] = np.where(ok, k, -1)
    return ev


def measure(ev, d):
    """Forward moves from the reference bar's open, signed by trade direction."""
    bars = d["bars"]
    ev = ev[ev.ref >= 0].copy()
    k, dirn, a = ev.ref.to_numpy(), ev.direction.to_numpy(), ev.atr.to_numpy()
    r, p_ref = bars.t[k], bars.open[k]
    ev["time"] = pd.to_datetime(r, utc=True)
    ev["session"], ev["hour"] = d["sess"][k], d["hour"][k]
    ev["prior"] = dirn * (p_ref - bars.price_at(r - 15 * MIN)) / a
    for h in HORIZONS:
        ev[f"move{h}"] = dirn * (bars.price_at(r + h * MIN) - p_ref)
        ev[f"atr{h}"] = ev[f"move{h}"] / a
    ev["cost"] = bars.spread[k] + COST_FIXED
    ev["net30"] = ev.move30 - ev.cost
    mfe, mae = bars.excursions(k, dirn)
    ev["mfe"], ev["mae"] = mfe / a, mae / a
    ev["bin"] = prior_bin(ev.prior.to_numpy())
    keep = np.isfinite(ev.prior.to_numpy()) & np.isfinite(a) & (r + 60 * MIN <= bars.tc[-1])
    return ev[keep]


def controls(d):
    bars, levels = d["bars"], d["levels"]
    atr = series_at(d["atr"], bars.t)
    p = bars.open
    dist = np.fmin.reduce(np.vstack([np.abs(p - levels[x]) for x in ("pdh", "pdl", "asia_hi", "asia_lo")]), axis=0)
    frac = np.mod(p, ROUND)
    dist = np.fmin(dist, np.minimum(frac, ROUND - frac))
    keep = (np.isin(d["sess"], SESSIONS) & np.isfinite(atr) & (dist >= NEAR_LEVEL_ATR * atr)
            & (bars.t + 60 * MIN <= bars.tc[-1]))
    return control_means(bars, atr, d["sess"], d["hour"], keep, HORIZONS)


def add_excess(ev, cm):
    key = pd.MultiIndex.from_arrays([ev.session, ev.hour, ev.bin])
    for h in HORIZONS:
        ev[f"exc{h}"] = ev[f"atr{h}"].to_numpy() - cm[h].reindex(key).to_numpy()
    return ev[np.isfinite(ev.exc30.to_numpy())]


def evaluate(cell):
    between = lambda f, a, b: f[(f.time >= utc(a)) & (f.time < utc(b))]  # noqa: E731
    recent = between(cell, *RECENT)
    t30 = clustered_t(cell.exc30, cell.day)
    subs = {name: between(cell, a, b).exc30.mean() for name, a, b in SUBPERIODS}
    drops = {s: clustered_t(cell[cell.session != s].exc30, cell[cell.session != s].day) for s in SESSIONS}
    worst = min(drops, key=lambda s: drops[s])
    trimmed = recent[recent.net30 < recent.net30.quantile(0.99)].net30.mean()
    crit = [t30 >= 3, recent.net30.mean() > 0, all(v > 0 for v in subs.values()), drops[worst] >= 2, trimmed > 0]
    row = {"events": len(cell), "days": cell.day.nunique()}
    for h in HORIZONS:
        row[f"excess {h}m (ATR)"] = cell[f"exc{h}"].mean()
        row[f"t {h}m"] = clustered_t(cell[f"exc{h}"], cell.day)
    row.update({"move 30m (ATR)": cell.atr30.mean(), "2024-25 events": len(recent),
                "2024-25 move 30m $": recent.move30.mean(), "2024-25 cost $": recent.cost.mean(),
                "2024-25 net 30m $": recent.net30.mean()})
    row.update({f"excess {n}": v for n, v in subs.items()})
    row.update({"t without best session": drops[worst], "best session": worst, "2024-25 net, top 1% cut": trimmed})
    row.update({f"C{n + 1}": bool(c) for n, c in enumerate(crit)})
    row["PASS"] = all(crit)
    return row


def fmt(v):
    if isinstance(v, (bool, np.bool_)):
        return "yes" if v else "no"
    if isinstance(v, (float, np.floating)):
        return "" if np.isnan(v) else f"{v:.0f}" if float(v).is_integer() and abs(v) >= 10 else f"{v:.3f}"
    return str(v)


def md(df):
    """DataFrame as a markdown table; tuple labels are joined with ' / '."""
    label = lambda x: " / ".join(map(str, x)) if isinstance(x, (tuple, list)) else str(x)  # noqa: E731
    cols = [label(list(df.index.names) if df.index.nlevels > 1 else df.index.name or "")] + [label(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for idx, row in df.iterrows():
        lines.append("| " + " | ".join([label(idx)] + [fmt(v) for v in row]) + " |")
    return "\n".join(lines)


def check(d):
    ev = classify(find_pushes(d), d)
    print(pd.crosstab(ev.kind, ev.path, margins=True))
    bars = d["bars"]
    rng = np.random.default_rng(1)
    for (kind, path), g in ev[ev.path != "neither"].groupby(["kind", "path"]):
        for _, e in g.sample(2, random_state=rng.integers(1 << 31)).iterrows():
            i, k = int(e.i), int(e.ref)
            print(f"\n{kind} {path}: level {e.level:.2f} side {e.side:+d} atr {e.atr:.2f} "
                  f"push bar {pd.Timestamp(bars.t[i], tz='UTC')} decided {pd.Timestamp(int(e.decided), tz='UTC')} "
                  f"ref bar {pd.Timestamp(bars.t[k], tz='UTC') if k >= 0 else None} direction {e.direction:+d}")
            for j in range(i - 1, min(i + 12, len(bars.t))):
                mark = "<push" if j == i else ("<ref" if j == k else "")
                print(f"  {pd.Timestamp(bars.t[j], tz='UTC'):%m-%d %H:%M} o {bars.open[j]:.2f} h {bars.high[j]:.2f} "
                      f"l {bars.low[j]:.2f} c {bars.close[j]:.2f} {mark}")


def main():
    d = load()
    if "--check" in sys.argv:
        return check(d)
    pushes = classify(find_pushes(d), d)
    cm, n_controls = controls(d)
    ev = add_excess(measure(pushes, d), cm)
    cells = pd.DataFrame({key: evaluate(g) for key, g in ev.groupby(["kind", "path"])}).T
    cells.index.names = ["level", "path"]

    out = [f"# H01 results\n\nRun {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC on M1 bars "
           f"2018-01-01 to 2025-09-30, as pre-registered in `H01-level-pokes.md` (commit ab8ba89).\n",
           "## Verdict\n", md(cells[["events", "t 30m", "C1", "C2", "C3", "C4", "C5", "PASS"]]),
           "\nC1: t >= 3 against the matched control. C2: after-cost 30m move > 0 in 2024-Sep 2025. "
           "C3: positive excess in all three sub-periods. C4: t >= 2 without the best session. "
           "C5: C2 holds without the top 1% of events.\n",
           "## Pushes by level and path\n", md(pd.crosstab(pushes.kind, pushes.path, margins=True)),
           f"\nControls: {n_controls:,} M1 moments, each used long and short.\n",
           "## Each test in full\n", md(cells.drop(columns=["C1", "C2", "C3", "C4", "C5", "PASS"]).T),
           "\n## By session (diagnostic)\n"]
    by = ev.groupby(["kind", "path", "session"])
    out.append(md(pd.DataFrame({"events": by.size(), "excess 30m (ATR)": by.exc30.mean(),
                                "t 30m": by.apply(lambda g: clustered_t(g.exc30, g.day))})))
    out.append("\n## By side (diagnostic)\n")
    by = ev.groupby(["kind", "path", "side"])
    out.append(md(pd.DataFrame({"events": by.size(), "excess 30m (ATR)": by.exc30.mean(),
                                "t 30m": by.apply(lambda g: clustered_t(g.exc30, g.day))})))
    out.append("\n## Excursions within 60 minutes, in ATR (diagnostic)\n")
    by = ev.groupby(["kind", "path"])
    out.append(md(pd.DataFrame({"MFE median": by.mfe.median(), "MFE p75": by.mfe.quantile(0.75),
                                "MAE median": by.mae.median(), "MAE p75": by.mae.quantile(0.75)})))
    (ROOT / "research" / "H01-results.md").write_text("\n".join(out) + "\n")
    print(md(cells[["events", "t 30m", "C1", "C2", "C3", "C4", "C5", "PASS"]]))


if __name__ == "__main__":
    main()
