"""D03 — Previous Day Range as Forward Predictor"""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.stats import kruskal
from research.diagnostics.registry import register_diagnostic
from research.diagnostics.base import BaseDiagnostic, DiagnosticConfig
from research.utils import bootstrap_ci, cohen_d, permutation_test
from research.reports.effect_report import build_effect_report, EffectReport


@register_diagnostic
class D03PrevDayRange(BaseDiagnostic):
    id        = "d03"
    tags      = ["daily", "range", "regime", "sessions"]
    hypothesis = (
        "Previous day range (PDR) quintile predicts today's London session "
        "directional efficiency and range expansion / contraction."
    )

    def _compute_core(self, data, config: DiagnosticConfig, mask: np.ndarray) -> dict:
        m1       = data.ds.m1
        daily    = data.daily_df.copy()
        daily    = daily.dropna(subset=["pdr_pct", "pdr"])

        if len(daily) < 50:
            return _empty()

        # Quintile labels
        daily["pdr_q"] = pd.qcut(daily["pdr_pct"], q=5, labels=False, duplicates="drop")

        # Today's London DE: compute from daily_df columns
        # Proxy: true_range / pdr_pct proxy — use daily true_range ratio
        daily["range_ratio"]  = daily["true_range"] / (daily["pdr"].shift(1) + 1e-9)

        # London continuation: asian_close_pos > 0.6 → bullish day
        daily["london_bull"]  = (daily["asian_close_pos"] > 0.6).astype(float)
        daily["london_bear"]  = (daily["asian_close_pos"] < 0.4).astype(float)
        daily["london_direc"] = (daily["asian_close_pos"] > 0.6).astype(float) - \
                                (daily["asian_close_pos"] < 0.4).astype(float)

        # Filter to mask date range
        _ts = pd.DatetimeIndex(m1.ts[mask])
        if _ts.tz is not None: _ts = _ts.tz_convert("UTC").tz_localize(None)
        m1_dates = _ts.normalize()
        valid_dates = set(m1_dates.unique())
        daily_f = daily[daily["date"].isin(valid_dates)].dropna(subset=["pdr_q", "range_ratio"])
        n_obs = len(daily_f)

        if n_obs < 30:
            return _empty()

        # ── KW test across quintiles
        quintile_groups = [
            daily_f.loc[daily_f["pdr_q"] == q, "range_ratio"].dropna().values
            for q in range(5) if (daily_f["pdr_q"] == q).sum() >= 10
        ]
        kw_stat, kw_p = kruskal(*quintile_groups) if len(quintile_groups) >= 2 else (0.0, 1.0)

        effect_sizes: dict[str, float] = {}
        cis:          dict[str, tuple] = {}
        p_raw:        dict[str, float] = {"kruskal_range_ratio": float(kw_p)}
        p_perm:       dict[str, float] = {}
        effect_reports: list[EffectReport] = []

        # ── Q1 (compressed) vs Q5 (wide)
        q1 = daily_f.loc[daily_f["pdr_q"] == 0, "range_ratio"].dropna().values
        q5 = daily_f.loc[daily_f["pdr_q"] == 4, "range_ratio"].dropna().values

        if len(q1) >= 20 and len(q5) >= 20:
            _, lo1, hi1 = bootstrap_ci(q1, np.mean, n=config.n_bootstrap)
            _, lo5, hi5 = bootstrap_ci(q5, np.mean, n=config.n_bootstrap)
            pr = permutation_test(q1, q5, np.mean,
                                  n_permutations=min(config.n_permutations, 5_000))

            effect_sizes["range_ratio_q1"] = float(np.nanmean(q1))
            effect_sizes["range_ratio_q5"] = float(np.nanmean(q5))
            cis["range_ratio_q1"] = (lo1, hi1)
            cis["range_ratio_q5"] = (lo5, hi5)
            p_perm["q1_vs_q5_range_ratio"] = pr.p_value

            er = build_effect_report(
                finding      = "Today range / PDR: compressed (Q1) vs wide (Q5) prior",
                condition    = "PDR quintile 1 (most compressed)",
                baseline     = float(np.nanmean(q5)),
                effect_value = float(np.nanmean(q1)),
                effect_unit  = "probability_difference",
                ci           = (lo1, hi1),
                p_perm       = pr.p_value,
                p_adj        = pr.p_value,
                effect_d     = cohen_d(q1, q5),
                stability    = 0.0,
                n_obs        = len(q1),
                n_obs_baseline = len(q5),
            )
            effect_reports.append(er)

        # ── London bull rate by quintile
        for q in range(5):
            qsub = daily_f[daily_f["pdr_q"] == q]
            if len(qsub) < 20:
                continue
            bull_r = qsub["london_bull"].mean()
            _, lo, hi = bootstrap_ci(qsub["london_bull"].values, np.mean,
                                     n=config.n_bootstrap)
            key = f"london_bull_q{q}"
            effect_sizes[key] = float(bull_r)
            cis[key]          = (lo, hi)

        return {
            "n_obs": n_obs, "effect_sizes": effect_sizes, "ci": cis,
            "p_values_raw": p_raw, "p_values_perm": p_perm,
            "raw_events": daily_f.reset_index(drop=True),
            "effect_reports": effect_reports, "feature_df": None,
            "summary_stats": {
                "pdr_q1_range_ratio": effect_sizes.get("range_ratio_q1"),
                "pdr_q5_range_ratio": effect_sizes.get("range_ratio_q5"),
                "kw_p": float(kw_p),
            },
        }

def _empty() -> dict:
    return {"n_obs": 0, "effect_sizes": {}, "ci": {}, "p_values_raw": {},
            "p_values_perm": {}, "raw_events": pd.DataFrame(),
            "effect_reports": [], "feature_df": None, "summary_stats": {}}
