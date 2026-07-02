"""
D01 — Session Directional Persistence
=======================================
Hypothesis: Asian, London, and NY sessions have materially different
directional efficiency (DE) and continuation-vs-reversal rates. This is the
primary regime variable driving walk-forward instability in both prior
strategy families.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu, chi2_contingency

from research.diagnostics.registry import register_diagnostic
from research.diagnostics.base import BaseDiagnostic, DiagnosticConfig
from research.utils import bootstrap_ci, directional_efficiency, cohen_d, permutation_test
from research.reports.effect_report import build_effect_report, EffectReport

_SESSION_NAMES = {0: "Asian", 1: "London", 2: "NY"}
_SESSION_PAIRS = [(0, 1), (1, 2), (0, 2)]   # (prior, current) for continuation tests


@register_diagnostic
class D01SessionPersistence(BaseDiagnostic):
    id        = "d01"
    tags      = ["sessions", "direction", "regime"]
    hypothesis = (
        "Sessions have materially different directional efficiency and "
        "continuation rates; this is the primary driver of WF instability."
    )

    def _compute_core(self, data, config: DiagnosticConfig, mask: np.ndarray) -> dict:
        m1      = data.ds.m1
        session = data.session
        ts_pd   = pd.DatetimeIndex(m1.ts)
        if ts_pd.tz is not None: ts_pd = ts_pd.tz_convert("UTC").tz_localize(None)
        dates   = ts_pd.normalize().values

        bar_indices = np.where(mask)[0]
        unique_dates = np.unique(dates[mask])

        # ── Per-session-per-day statistics
        rows = []
        for date in unique_dates:
            day_mask = dates == date
            for sess_id in [0, 1, 2]:
                bmask = day_mask & (session == sess_id) & mask
                if bmask.sum() < 5:
                    continue
                o = m1.open[bmask][0]
                h = np.max(m1.high[bmask])
                l = np.min(m1.low[bmask])
                c = m1.close[bmask][-1]
                rng = h - l
                de  = abs(c - o) / rng if rng > 0 else np.nan
                rows.append({
                    "date":    date,
                    "session": sess_id,
                    "open":    o,
                    "high":    h,
                    "low":     l,
                    "close":   c,
                    "range":   rng,
                    "de":      de,
                    "dir":     int(np.sign(c - o)),
                })

        df = pd.DataFrame(rows)
        if len(df) < 10:
            return _empty_core()

        # ── Continuation table: prior session dir → current session direction
        continuation_rows = []
        for date in unique_dates:
            day = df[df["date"] == date].set_index("session")
            for prior_s, curr_s in _SESSION_PAIRS:
                if prior_s not in day.index or curr_s not in day.index:
                    continue
                prior_dir = day.loc[prior_s, "dir"]
                curr_dir  = day.loc[curr_s, "dir"]
                if prior_dir == 0 or curr_dir == 0:
                    continue
                continuation_rows.append({
                    "prior_session": prior_s,
                    "curr_session":  curr_s,
                    "prior_dir":     prior_dir,
                    "curr_dir":      curr_dir,
                    "continuation":  int(prior_dir == curr_dir),
                    "prior_de":      day.loc[prior_s, "de"],
                })
        cont_df = pd.DataFrame(continuation_rows)

        # ── Effect sizes: DE by session + continuation rates
        effect_sizes: dict[str, float] = {}
        cis:          dict[str, tuple] = {}
        p_raw:        dict[str, float] = {}
        p_perm:       dict[str, float] = {}

        london_de = df.loc[df["session"] == 1, "de"].dropna().values
        asian_de  = df.loc[df["session"] == 0, "de"].dropna().values
        ny_de     = df.loc[df["session"] == 2, "de"].dropna().values

        for sname, sde in [("asian", asian_de), ("london", london_de), ("ny", ny_de)]:
            if len(sde) < 10:
                continue
            _, lo, hi = bootstrap_ci(sde, np.mean, n=config.n_bootstrap)
            effect_sizes[f"de_{sname}_mean"] = float(np.nanmean(sde))
            cis[f"de_{sname}_mean"]          = (lo, hi)

        # Mann-Whitney: London DE vs Asian DE
        if len(london_de) > 10 and len(asian_de) > 10:
            stat, p = mannwhitneyu(london_de, asian_de, alternative="two-sided")
            p_raw["london_vs_asian_de"] = float(p)
            effect_sizes["london_vs_asian_d"] = cohen_d(london_de, asian_de)
            pr = permutation_test(london_de, asian_de, np.mean,
                                  n_permutations=min(config.n_permutations, 5_000))
            p_perm["london_vs_asian_de"] = pr.p_value

        # ── Continuation rates
        effect_reports: list[EffectReport] = []
        for prior_s, curr_s in _SESSION_PAIRS:
            sub = cont_df[(cont_df["prior_session"] == prior_s) &
                          (cont_df["curr_session"] == curr_s)]
            if len(sub) < 30:
                continue

            cont_rate = sub["continuation"].mean()
            baseline  = 0.50   # null hypothesis: coin flip
            _, lo, hi = bootstrap_ci(sub["continuation"].values, np.mean,
                                     n=config.n_bootstrap)

            # High-DE condition: prior session DE > 0.65
            hi_de = sub[sub["prior_de"] > 0.65]["continuation"]
            lo_de = sub[sub["prior_de"] <= 0.35]["continuation"]

            key = f"cont_{_SESSION_NAMES[prior_s]}_{_SESSION_NAMES[curr_s]}"
            effect_sizes[key] = cont_rate - baseline
            cis[key]          = (lo - baseline, hi - baseline)
            p_raw[key]        = float(chi2_contingency(
                pd.crosstab(sub["continuation"], sub["prior_dir"])
            )[1])

            er = build_effect_report(
                finding      = f"{_SESSION_NAMES[prior_s]}→{_SESSION_NAMES[curr_s]} continuation",
                condition    = f"all {_SESSION_NAMES[prior_s]} sessions",
                baseline     = baseline,
                effect_value = float(cont_rate),
                effect_unit  = "probability_difference",
                ci           = (lo, hi),
                p_perm       = p_raw[key],
                p_adj        = p_raw[key],
                effect_d     = cohen_d(sub["continuation"].values,
                                       np.full(len(sub), 0.5)),
                stability    = 0.0,
                n_obs        = len(sub),
                n_obs_baseline = len(sub),
            )
            effect_reports.append(er)

            # High DE conditional
            if len(hi_de) >= 30:
                _, lo2, hi2 = bootstrap_ci(hi_de.values, np.mean, n=config.n_bootstrap)
                er2 = build_effect_report(
                    finding      = f"{_SESSION_NAMES[prior_s]}→{_SESSION_NAMES[curr_s]} cont (high DE prior)",
                    condition    = f"{_SESSION_NAMES[prior_s]} DE > 0.65",
                    baseline     = float(cont_rate),
                    effect_value = float(hi_de.mean()),
                    effect_unit  = "probability_difference",
                    ci           = (lo2, hi2),
                    p_perm       = float(permutation_test(
                        hi_de.values, lo_de.values if len(lo_de) >= 10 else hi_de.values,
                        np.mean, n_permutations=min(config.n_permutations, 2_000)
                    ).p_value),
                    p_adj        = 1.0,
                    effect_d     = cohen_d(hi_de.values,
                                          lo_de.values if len(lo_de) >= 10 else hi_de.values),
                    stability    = 0.0,
                    n_obs        = len(hi_de),
                    n_obs_baseline = len(sub),
                )
                effect_reports.append(er2)

        # ── Feature table contributions
        ft_rows = []
        for i, bi in enumerate(bar_indices):
            si = int(data.session[bi])
            ft_rows.append({
                "bar_idx": int(bi),
                "session": si,
                "weekday": int(data.weekday[bi]),
                "hour_utc": int(data.hour_utc[bi]),
            })
        feature_df = pd.DataFrame(ft_rows)

        return {
            "n_obs":          len(df),
            "effect_sizes":   effect_sizes,
            "ci":             cis,
            "p_values_raw":   p_raw,
            "p_values_perm":  p_perm,
            "raw_events":     df,
            "effect_reports": effect_reports,
            "feature_df":     feature_df,
            "summary_stats": {
                "london_de_mean": float(np.nanmean(london_de)) if len(london_de) else np.nan,
                "asian_de_mean":  float(np.nanmean(asian_de))  if len(asian_de)  else np.nan,
                "ny_de_mean":     float(np.nanmean(ny_de))     if len(ny_de)     else np.nan,
            },
        }


def _empty_core() -> dict:
    return {
        "n_obs": 0, "effect_sizes": {}, "ci": {},
        "p_values_raw": {}, "p_values_perm": {},
        "raw_events": pd.DataFrame(), "effect_reports": [],
        "feature_df": None, "summary_stats": {},
    }
