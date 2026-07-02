"""D08 — Intraday High/Low Timing"""
from __future__ import annotations
import numpy as np
import pandas as pd
from research.diagnostics.registry import register_diagnostic
from research.diagnostics.base import BaseDiagnostic, DiagnosticConfig
from research.utils import bootstrap_proportion_ci
from research.reports.effect_report import build_effect_report, EffectReport


@register_diagnostic
class D08IntradayTiming(BaseDiagnostic):
    id        = "d08"
    tags      = ["sessions", "intraday", "timing", "daily"]
    hypothesis = (
        "The daily high and low form at non-uniform UTC hours. P(daily extreme "
        "not yet formed | current hour) gives a session-based reversal probability "
        "surface that is actionable for timing entries."
    )

    def _compute_core(self, data, config: DiagnosticConfig, mask: np.ndarray) -> dict:
        m1    = data.ds.m1
        ts_pd = pd.DatetimeIndex(m1.ts)
        if ts_pd.tz is not None: ts_pd = ts_pd.tz_convert("UTC").tz_localize(None)
        dates = ts_pd.normalize().values

        bar_indices = np.where(mask)[0]
        unique_dates = np.unique(dates[mask])

        rows = []
        for date in unique_dates:
            day_mask_full = dates == date
            day_bars_m1   = np.where(day_mask_full & mask)[0]
            if len(day_bars_m1) < 60:   # need a full trading day
                continue

            highs = m1.high[day_bars_m1]
            lows  = m1.low[day_bars_m1]
            hours = ts_pd.hour[day_bars_m1].to_numpy()

            day_high_idx = int(np.argmax(highs))
            day_low_idx  = int(np.argmin(lows))
            day_high_hour = int(hours[day_high_idx])
            day_low_hour  = int(hours[day_low_idx])

            rows.append({
                "date":           date,
                "weekday":        int(ts_pd.dayofweek[day_bars_m1[0]]),
                "day_high_hour":  day_high_hour,
                "day_low_hour":   day_low_hour,
                "high_before_low": int(day_high_idx < day_low_idx),
                "day_range":      float(np.max(highs) - np.min(lows)),
            })

        df = pd.DataFrame(rows)
        n_obs = len(df)
        if n_obs < 30:
            return _empty()

        # ── Distribution of high/low formation hour
        high_hour_dist = df["day_high_hour"].value_counts().sort_index()
        low_hour_dist  = df["day_low_hour"].value_counts().sort_index()

        # ── Survival curve: P(day_high not yet formed | current hour h)
        # = fraction of days where day_high_hour > h
        survival_high = {}
        survival_low  = {}
        for h in range(24):
            survival_high[h] = float((df["day_high_hour"] > h).mean())
            survival_low[h]  = float((df["day_low_hour"]  > h).mean())

        # ── Effect: does London window (7-12) contain most daily highs/lows?
        london_high = float((df["day_high_hour"].between(7, 11)).mean())
        london_low  = float((df["day_low_hour"].between(7, 11)).mean())
        ny_high     = float((df["day_high_hour"].between(12, 16)).mean())
        ny_low      = float((df["day_low_hour"].between(12, 16)).mean())
        asian_high  = float((df["day_high_hour"].between(0, 6)).mean())
        asian_low   = float((df["day_low_hour"].between(0, 6)).mean())
        baseline    = 5.0 / 24.0   # uniform: 5-hr window / 24hr

        effect_sizes = {
            "london_high_rate": london_high,
            "london_low_rate":  london_low,
            "ny_high_rate":     ny_high,
            "ny_low_rate":      ny_low,
            "asian_high_rate":  asian_high,
        }
        cis: dict[str, tuple] = {}
        for k in ["london_high_rate", "london_low_rate", "ny_high_rate"]:
            n_ok = int(round(effect_sizes[k] * n_obs))
            _, lo, hi = bootstrap_proportion_ci(n_ok, n_obs, n_boot=config.n_bootstrap)
            cis[k] = (lo, hi)

        effect_reports: list[EffectReport] = []
        for k, label, cond in [
            ("london_high_rate", "Day high forms in London session", "07:00-12:00 UTC"),
            ("london_low_rate",  "Day low forms in London session",  "07:00-12:00 UTC"),
            ("ny_high_rate",     "Day high forms in NY session",     "12:00-17:00 UTC"),
        ]:
            n_ok = int(round(effect_sizes[k] * n_obs))
            _, lo, hi = bootstrap_proportion_ci(n_ok, n_obs, n_boot=config.n_bootstrap)
            er = build_effect_report(
                finding      = label,
                condition    = cond,
                baseline     = baseline,
                effect_value = effect_sizes[k],
                effect_unit  = "probability_difference",
                ci           = (lo, hi),
                p_perm       = 1.0,   # simple proportion test
                p_adj        = 1.0,
                effect_d     = (effect_sizes[k] - baseline) / (baseline * (1 - baseline) + 1e-9) ** 0.5,
                stability    = 0.0,
                n_obs        = n_ok,
                n_obs_baseline = n_obs,
            )
            effect_reports.append(er)

        return {
            "n_obs": n_obs, "effect_sizes": effect_sizes, "ci": cis,
            "p_values_raw": {}, "p_values_perm": {},
            "raw_events": df, "effect_reports": effect_reports,
            "feature_df": None,
            "summary_stats": {
                "london_high_rate": london_high,
                "london_low_rate":  london_low,
                "high_before_low_rate": float(df["high_before_low"].mean()),
                "survival_high_at_7":  survival_high.get(7, np.nan),
                "survival_high_at_12": survival_high.get(12, np.nan),
                "survival_low_at_7":   survival_low.get(7, np.nan),
            },
        }

def _empty() -> dict:
    return {"n_obs": 0, "effect_sizes": {}, "ci": {}, "p_values_raw": {},
            "p_values_perm": {}, "raw_events": pd.DataFrame(),
            "effect_reports": [], "feature_df": None, "summary_stats": {}}
