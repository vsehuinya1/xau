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

        # ── Vectorised per-session-per-day OHLC (replaces double Python loop) ──
        bar_df = pd.DataFrame({
            "date":    dates[mask],
            "session": session[mask].astype(np.int8),
            "open":    m1.open[mask],
            "high":    m1.high[mask],
            "low":     m1.low[mask],
            "close":   m1.close[mask],
        })
        grp = bar_df.groupby(["date", "session"])
        df = grp.agg(
            open  = ("open",  "first"),
            high  = ("high",  "max"),
            low   = ("low",   "min"),
            close = ("close", "last"),
            n     = ("close", "count"),
        ).reset_index()
        df = df[df["n"] >= 5].copy()
        df["range"] = df["high"] - df["low"]
        df["de"]    = np.where(
            df["range"] > 0,
            (df["close"] - df["open"]).abs() / df["range"],
            np.nan,
        )
        df["dir"] = np.sign(df["close"] - df["open"]).astype(int)

        if len(df) < 10:
            return _empty_core()

        # ── Vectorised continuation table (replaces second Python loop) ─────────
        # Pivot to wide per-day, then align prior vs current sessions
        pivot_dir = df.pivot(index="date", columns="session", values="dir")
        pivot_de  = df.pivot(index="date", columns="session", values="de")
        continuation_rows = []
        for prior_s, curr_s in _SESSION_PAIRS:
            if prior_s not in pivot_dir.columns or curr_s not in pivot_dir.columns:
                continue
            combined = pd.DataFrame({
                "prior_dir": pivot_dir[prior_s],
                "curr_dir":  pivot_dir[curr_s],
                "prior_de":  pivot_de[prior_s],
            }).dropna()
            combined = combined[(combined["prior_dir"] != 0) & (combined["curr_dir"] != 0)]
            combined["continuation"]  = (combined["prior_dir"] == combined["curr_dir"]).astype(int)
            combined["prior_session"] = prior_s
            combined["curr_session"]  = curr_s
            continuation_rows.append(combined.reset_index())
        cont_df = pd.concat(continuation_rows, ignore_index=True) if continuation_rows else pd.DataFrame()

        bar_indices = np.where(mask)[0]


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
