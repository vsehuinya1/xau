"""D10 — Weekday Effects"""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.stats import kruskal
from research.diagnostics.registry import register_diagnostic
from research.diagnostics.base import BaseDiagnostic, DiagnosticConfig
from research.utils import bootstrap_ci, cohen_d
from research.reports.effect_report import build_effect_report, EffectReport

_WD_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri"]


@register_diagnostic
class D10WeekdayEffects(BaseDiagnostic):
    id        = "d10"
    tags      = ["daily", "weekday", "regime"]
    hypothesis = (
        "Day-of-week has measurable and stable effects on XAUUSD range, "
        "directional persistence, and session continuation rates."
    )

    def _compute_core(self, data, config: DiagnosticConfig, mask: np.ndarray) -> dict:
        m1    = data.ds.m1
        daily = data.daily_df.copy()

        def _tznv(v):
            t = pd.Timestamp(v)
            return t.tz_convert("UTC").tz_localize(None) if t.tzinfo else t
        m1_ts_min = _tznv(m1.ts[mask][0]  if mask.sum() > 0 else m1.ts[0])
        m1_ts_max = _tznv(m1.ts[mask][-1] if mask.sum() > 0 else m1.ts[-1])
        daily = daily[(daily["date"] >= m1_ts_min) & (daily["date"] <= m1_ts_max)]
        daily = daily.dropna(subset=["true_range", "weekday"])
        daily["close_return"] = (daily["close"] - daily["open"]) / (daily["open"] + 1e-9)

        n_obs = len(daily)
        if n_obs < 50:
            return _empty()

        # ── Kruskal-Wallis across weekdays for range and return
        wd_groups_range  = [daily.loc[daily["weekday"] == wd, "true_range"].dropna().values
                            for wd in range(5)]
        wd_groups_return = [daily.loc[daily["weekday"] == wd, "close_return"].dropna().values
                            for wd in range(5)]

        valid_range  = [g for g in wd_groups_range  if len(g) >= 10]
        valid_return = [g for g in wd_groups_return if len(g) >= 10]

        kw_range_p  = float(kruskal(*valid_range)[1])  if len(valid_range)  >= 2 else 1.0
        kw_return_p = float(kruskal(*valid_return)[1]) if len(valid_return) >= 2 else 1.0

        effect_sizes: dict[str, float] = {}
        cis:          dict[str, tuple] = {}
        p_raw:        dict[str, float] = {
            "kw_range_by_weekday":  kw_range_p,
            "kw_return_by_weekday": kw_return_p,
        }
        p_perm:       dict[str, float] = {}
        effect_reports: list[EffectReport] = []

        baseline_range  = float(daily["true_range"].mean())
        baseline_return = float(daily["close_return"].mean())

        for wd in range(5):
            sub = daily[daily["weekday"] == wd]
            if len(sub) < 20:
                continue
            wname = _WD_NAMES[wd]

            # Range
            rng_vals = sub["true_range"].values
            _, lo_r, hi_r = bootstrap_ci(rng_vals, np.mean, n=config.n_bootstrap)
            key_r = f"range_{wname}"
            effect_sizes[key_r] = float(np.nanmean(rng_vals))
            cis[key_r]          = (lo_r, hi_r)

            # Return (directional)
            ret_vals = sub["close_return"].values
            _, lo_ret, hi_ret = bootstrap_ci(ret_vals, np.mean, n=config.n_bootstrap)
            key_ret = f"return_{wname}"
            effect_sizes[key_ret] = float(np.nanmean(ret_vals))
            cis[key_ret]          = (lo_ret, hi_ret)

            # Trending day rate (|return| > 0.5 × mean_range / open)
            trend_rate = float((sub["true_range"] > baseline_range * 1.2).mean())
            effect_sizes[f"trend_rate_{wname}"] = trend_rate

            # Effect report for range (most stable)
            other = daily[daily["weekday"] != wd]
            er = build_effect_report(
                finding      = f"{wname} daily range",
                condition    = f"weekday={wname}",
                baseline     = baseline_range,
                effect_value = float(np.nanmean(rng_vals)),
                effect_unit  = "return_difference",
                ci           = (lo_r, hi_r),
                p_perm       = 1.0,
                p_adj        = kw_range_p,
                effect_d     = cohen_d(rng_vals, other["true_range"].dropna().values),
                stability    = 0.0,
                n_obs        = len(sub),
                n_obs_baseline = n_obs,
            )
            effect_reports.append(er)

        return {
            "n_obs": n_obs, "effect_sizes": effect_sizes, "ci": cis,
            "p_values_raw": p_raw, "p_values_perm": p_perm,
            "raw_events": daily.reset_index(drop=True),
            "effect_reports": effect_reports, "feature_df": None,
            "summary_stats": {
                "kw_range_p":  kw_range_p,
                "kw_return_p": kw_return_p,
                "best_range_day": _WD_NAMES[int(np.argmax(
                    [daily.loc[daily["weekday"]==wd, "true_range"].mean()
                     for wd in range(5)]
                ))],
            },
        }

def _empty() -> dict:
    return {"n_obs": 0, "effect_sizes": {}, "ci": {}, "p_values_raw": {},
            "p_values_perm": {}, "raw_events": pd.DataFrame(),
            "effect_reports": [], "feature_df": None, "summary_stats": {}}
