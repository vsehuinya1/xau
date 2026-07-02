"""D09 — Asian Range as Directional Predictor"""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency
from research.diagnostics.registry import register_diagnostic
from research.diagnostics.base import BaseDiagnostic, DiagnosticConfig
from research.utils import bootstrap_ci, cohen_d, permutation_test
from research.reports.effect_report import build_effect_report, EffectReport


@register_diagnostic
class D09AsianRangePredictor(BaseDiagnostic):
    id        = "d09"
    tags      = ["sessions", "asian", "direction", "daily"]
    hypothesis = (
        "The Asian session close position [0,1] within the Asian range predicts "
        "London session direction with P materially different from 0.50."
    )

    def _compute_core(self, data, config: DiagnosticConfig, mask: np.ndarray) -> dict:
        m1    = data.ds.m1
        daily = data.daily_df.copy()

        # Filter daily to mask date range
        def _tznv(v):
            t = pd.Timestamp(v)
            return t.tz_convert("UTC").tz_localize(None) if t.tzinfo else t
        m1_ts_min = _tznv(m1.ts[mask][0]  if mask.sum() > 0 else m1.ts[0])
        m1_ts_max = _tznv(m1.ts[mask][-1] if mask.sum() > 0 else m1.ts[-1])
        daily = daily[(daily["date"] >= m1_ts_min) & (daily["date"] <= m1_ts_max)]
        daily = daily.dropna(subset=["asian_close_pos", "asian_range"])

        if len(daily) < 50:
            return _empty()

        # Classify Asian close position
        daily["asian_class"] = "neutral"
        daily.loc[daily["asian_close_pos"] > 0.6, "asian_class"] = "bull"
        daily.loc[daily["asian_close_pos"] < 0.4, "asian_class"] = "bear"

        # London direction proxy: close > open for that day
        daily["day_bull"]  = (daily["close"] > daily["open"]).astype(int)

        # London break of Asian high/low proxy: range ratio
        daily["london_expansive"] = (
            daily["true_range"] > daily["asian_range"] * 1.5
        ).astype(int)

        n_obs = len(daily)
        bull_days = daily[daily["asian_class"] == "bull"]
        bear_days = daily[daily["asian_class"] == "bear"]
        neut_days = daily[daily["asian_class"] == "neutral"]
        baseline  = float(daily["day_bull"].mean())

        effect_sizes: dict[str, float] = {}
        cis:          dict[str, tuple] = {}
        p_raw:        dict[str, float] = {}
        p_perm:       dict[str, float] = {}
        effect_reports: list[EffectReport] = []

        for cls_name, cls_df in [("bull", bull_days), ("bear", bear_days)]:
            if len(cls_df) < 20:
                continue

            rate = float(cls_df["day_bull"].mean())
            _, lo, hi = bootstrap_ci(cls_df["day_bull"].values, np.mean,
                                     n=config.n_bootstrap)
            other = daily[daily["asian_class"] != cls_name]
            pr = permutation_test(
                cls_df["day_bull"].values, other["day_bull"].values,
                np.mean, n_permutations=min(config.n_permutations, 3_000)
            )
            # Chi2 vs baseline
            ct = pd.crosstab(daily["asian_class"], daily["day_bull"])
            _, chi2_p, _, _ = chi2_contingency(ct)

            key = f"day_bull_{cls_name}_asian"
            effect_sizes[key] = rate
            cis[key]          = (lo, hi)
            p_raw[key]        = float(chi2_p)
            p_perm[key]       = pr.p_value

            er = build_effect_report(
                finding      = f"Day bullish rate (Asian {cls_name} close)",
                condition    = f"Asian close position {'> 0.6' if cls_name == 'bull' else '< 0.4'}",
                baseline     = baseline,
                effect_value = rate,
                effect_unit  = "probability_difference",
                ci           = (lo, hi),
                p_perm       = pr.p_value,
                p_adj        = pr.p_value,
                effect_d     = cohen_d(cls_df["day_bull"].values, other["day_bull"].values),
                stability    = 0.0,
                n_obs        = len(cls_df),
                n_obs_baseline = n_obs,
            )
            effect_reports.append(er)

        # Asian range compression as predictor
        daily["asian_compressed"] = daily["asian_range_pct"] < 25
        comp_days = daily[daily["asian_compressed"]]
        wide_days = daily[~daily["asian_compressed"]]
        if len(comp_days) >= 20 and len(wide_days) >= 20:
            rate_c = float(comp_days["london_expansive"].mean())
            rate_w = float(wide_days["london_expansive"].mean())
            _, lo_c, hi_c = bootstrap_ci(comp_days["london_expansive"].values,
                                         np.mean, n=config.n_bootstrap)
            pr2 = permutation_test(
                comp_days["london_expansive"].values,
                wide_days["london_expansive"].values,
                np.mean, n_permutations=min(config.n_permutations, 3_000)
            )
            effect_sizes["london_expansion_compressed"] = rate_c
            effect_sizes["london_expansion_wide"]       = rate_w
            cis["london_expansion_compressed"] = (lo_c, hi_c)
            p_perm["london_expansion_comp_vs_wide"] = pr2.p_value

            er2 = build_effect_report(
                finding      = "London expansive day rate (Asian compressed)",
                condition    = "Asian range < 25th percentile",
                baseline     = rate_w,
                effect_value = rate_c,
                effect_unit  = "probability_difference",
                ci           = (lo_c, hi_c),
                p_perm       = pr2.p_value,
                p_adj        = pr2.p_value,
                effect_d     = cohen_d(comp_days["london_expansive"].values,
                                       wide_days["london_expansive"].values),
                stability    = 0.0,
                n_obs        = len(comp_days),
                n_obs_baseline = len(wide_days),
            )
            effect_reports.append(er2)

        return {
            "n_obs": n_obs, "effect_sizes": effect_sizes, "ci": cis,
            "p_values_raw": p_raw, "p_values_perm": p_perm,
            "raw_events": daily.reset_index(drop=True),
            "effect_reports": effect_reports, "feature_df": None,
            "summary_stats": {
                "bull_asian_day_rate": effect_sizes.get("day_bull_bull_asian"),
                "bear_asian_day_rate": effect_sizes.get("day_bull_bear_asian"),
                "baseline_day_bull":   baseline,
            },
        }

def _empty() -> dict:
    return {"n_obs": 0, "effect_sizes": {}, "ci": {}, "p_values_raw": {},
            "p_values_perm": {}, "raw_events": pd.DataFrame(),
            "effect_reports": [], "feature_df": None, "summary_stats": {}}
