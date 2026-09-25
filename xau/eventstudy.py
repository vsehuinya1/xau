"""Event-study helpers on M1 bars: prices at times, excursions, matched
controls and clustered t-statistics. Times are int64 nanoseconds (UTC)."""
import numpy as np
import pandas as pd

from xau.sessions import SESSIONS

MIN = 60_000_000_000  # one minute in nanoseconds
BIN_EDGES = [-2, -1, -0.5, -0.25, 0, 0.25, 0.5, 1, 2]  # prior move, in ATR
# Pre-registered in research/H01-level-pokes.md and reused by later hypotheses.
SUBPERIODS = [("2018-20", "2018-01-01", "2021-01-01"),
              ("2021-22", "2021-01-01", "2023-01-01"),
              ("2023-Sep25", "2023-01-01", "2025-10-01")]
RECENT = ("2024-01-01", "2025-10-01")


class Bars:
    """M1 bars as arrays; t is each bar's open time and tc its close time."""

    def __init__(self, m1):
        self.t = m1.index.as_unit("ns").asi8
        self.tc = self.t + MIN
        self.open, self.high, self.low, self.close = (
            m1[c].to_numpy(float) for c in ("open", "high", "low", "close"))
        self.spread = m1["spread"].to_numpy(float) * 0.01  # points -> $

    def price_at(self, times):
        """Last M1 close at or before each time; NaN if there is none."""
        pos = np.searchsorted(self.tc, times, side="right") - 1
        return np.where(pos >= 0, self.close[np.clip(pos, 0, None)], np.nan)

    def next_bar(self, times):
        """Index of the first bar opening at or after each time (len if none)."""
        return np.searchsorted(self.t, times, side="left")

    def excursions(self, idx, direction, minutes=60):
        """Largest favourable and adverse move from each bar's open, over bars
        opening in [t[idx], t[idx] + minutes)."""
        end = np.searchsorted(self.t, self.t[idx] + minutes * MIN, side="left")
        mfe, mae = np.empty(len(idx)), np.empty(len(idx))
        for n, (i, j, d) in enumerate(zip(idx, end, direction)):
            hi, lo = self.high[i:j].max(), self.low[i:j].min()
            mfe[n], mae[n] = (hi - self.open[i], self.open[i] - lo) if d > 0 else (self.open[i] - lo, hi - self.open[i])
        return mfe, mae


def measure(ev, bars, atr, sessions, hours, days, horizons, excursion_minutes, cost_fixed=0.11):
    """Forward moves of events from their reference bar's open, signed by trade direction.

    ev needs columns `ref` (M1 bar index; -1 drops the event) and `direction`.
    ATR (a time-indexed series) is taken as of the reference bar's open. Adds
    time, day, session, hour, weekday, prior (15-minute move, in ATR), cost,
    move/atr/net per horizon, mfe/mae (in ATR) and the prior-move bin. Drops
    events without a full forward window.
    """
    ev = ev[ev.ref >= 0].copy()
    k, dirn = ev.ref.to_numpy(), ev.direction.to_numpy()
    r, p_ref = bars.t[k], bars.open[k]
    a = series_at(atr, r)
    ev["atr"], ev["time"], ev["day"] = a, pd.to_datetime(r, utc=True), days[k]
    ev["session"], ev["hour"] = sessions[k], hours[k]
    ev["weekday"] = pd.DatetimeIndex(ev.day).day_name().str[:3]
    ev["prior"] = dirn * (p_ref - bars.price_at(r - 15 * MIN)) / a
    ev["cost"] = bars.spread[k] + cost_fixed
    for h in horizons:
        ev[f"move{h}"] = dirn * (bars.price_at(r + h * MIN) - p_ref)
        ev[f"atr{h}"] = ev[f"move{h}"] / a
        ev[f"net{h}"] = ev[f"move{h}"] - ev.cost
    mfe, mae = bars.excursions(k, dirn, minutes=excursion_minutes)
    ev["mfe"], ev["mae"] = mfe / a, mae / a
    ev["bin"] = prior_bin(ev.prior.to_numpy())
    keep = np.isfinite(ev.prior.to_numpy()) & np.isfinite(a) & (r + max(horizons + (excursion_minutes,)) * MIN <= bars.tc[-1])
    return ev[keep]


def add_excess(ev, cm, horizons, prefix="exc"):
    """Event move minus the mean control move in its session x hour x bin cell."""
    key = pd.MultiIndex.from_arrays([ev.session, ev.hour, ev.bin])
    for h in horizons:
        ev[f"{prefix}{h}"] = ev[f"atr{h}"].to_numpy() - cm[h].reindex(key).to_numpy()
    return ev


def series_at(series, times):
    """Value of a time-indexed series at or before each time (ns); NaN if none."""
    idx = series.index.as_unit("ns").asi8
    pos = np.searchsorted(idx, times, side="right") - 1
    return np.where(pos >= 0, series.to_numpy(float)[np.clip(pos, 0, None)], np.nan)


def prior_bin(prior):
    return np.digitize(prior, BIN_EDGES)


def control_means(bars, atr, sessions, hours, keep, horizons):
    """Mean forward move, in ATR, of every kept bar taken as a moment in both
    directions, per cell of session x hour x prior-move bin. The reference is
    each bar's open and the prior move is over the previous 15 minutes."""
    prior = (bars.open - bars.price_at(bars.t - 15 * MIN)) / atr
    fwd = {h: (bars.price_at(bars.t + h * MIN) - bars.open) / atr for h in horizons}
    ok = keep & np.isfinite(prior)
    for h in horizons:
        ok &= np.isfinite(fwd[h])
    frames = []
    for d in (1, -1):
        f = pd.DataFrame({"session": sessions[ok], "hour": hours[ok], "bin": prior_bin(d * prior[ok])})
        for h in horizons:
            f[h] = d * fwd[h][ok]
        frames.append(f)
    both = pd.concat(frames)
    return both.groupby(["session", "hour", "bin"])[list(horizons)].mean(), int(ok.sum())


def evaluate(cell, horizons, primary, split="session", groups=SESSIONS):
    """The five pre-registered pass criteria for one test, plus its details.

    cell needs columns time (UTC), day, cost, the `split` column, and per
    horizon h: move{h} ($), atr{h} and exc{h} (ATR), net{h} ($ after costs).
    Criterion 4 drops each of `groups` of the `split` column in turn.
    """
    def between(f, a, b):
        return f[(f.time >= pd.Timestamp(a, tz="UTC")) & (f.time < pd.Timestamp(b, tz="UTC"))]

    exc, net = f"exc{primary}", f"net{primary}"
    recent = between(cell, *RECENT)
    t = clustered_t(cell[exc], cell.day)
    subs = {name: between(cell, a, b)[exc].mean() for name, a, b in SUBPERIODS}
    drops = {s: clustered_t(cell[cell[split] != s][exc], cell[cell[split] != s].day) for s in groups}
    worst = min(drops, key=lambda s: drops[s])
    trimmed = recent[recent[net] < recent[net].quantile(0.99)][net].mean()
    crit = [t >= 3, recent[net].mean() > 0, all(v > 0 for v in subs.values()), drops[worst] >= 2, trimmed > 0]
    row = {"events": len(cell), "days": cell.day.nunique()}
    for h in horizons:
        row[f"excess {h}m (ATR)"] = cell[f"exc{h}"].mean()
        row[f"t {h}m"] = clustered_t(cell[f"exc{h}"], cell.day)
    row.update({f"move {primary}m (ATR)": cell[f"atr{primary}"].mean(), "2024-25 events": len(recent),
                f"2024-25 move {primary}m $": recent[f"move{primary}"].mean(), "2024-25 cost $": recent.cost.mean(),
                f"2024-25 net {primary}m $": recent[net].mean()})
    row.update({f"excess {n}": v for n, v in subs.items()})
    row.update({f"t without best {split}": drops[worst], f"best {split}": worst, "2024-25 net, top 1% cut": trimmed})
    row.update({f"C{n + 1}": bool(c) for n, c in enumerate(crit)})
    row["PASS"] = all(crit)
    return row


def clustered_t(x, groups):
    """t-statistic of the mean of x, with standard errors clustered by group."""
    x = np.asarray(x, float)
    if len(x) < 2:
        return np.nan
    dev = pd.Series(x - x.mean()).groupby(np.asarray(groups)).sum()
    g = len(dev)
    if g < 2:
        return np.nan
    se = np.sqrt(g / (g - 1) * (dev ** 2).sum()) / len(x)
    return x.mean() / se if se > 0 else np.nan
