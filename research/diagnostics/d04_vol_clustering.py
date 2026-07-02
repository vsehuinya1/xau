"""D04 — Intraday Volatility Clustering"""
from __future__ import annotations
import numpy as np
import pandas as pd
from research.diagnostics.registry import register_diagnostic
from research.diagnostics.base import BaseDiagnostic, DiagnosticConfig
from research.utils import bootstrap_ci, permutation_test
from research.reports.effect_report import build_effect_report, EffectReport

_ACF_LAGS      = 60    # M1 bars (= 1 hour)
_SPIKE_MULT    = 2.0   # vol spike: bar_range > this × trailing 14-bar mean
_TRAILING_BARS = 14    # trailing window for vol mean


@register_diagnostic
class D04VolClustering(BaseDiagnostic):
    id        = "d04"
    tags      = ["volatility", "regime", "intraday"]
    hypothesis = (
        "M1 bar range exhibits strong positive autocorrelation up to 60 bars "
        "(1 hour); vol spikes persist for measurable periods. This enables "
        "vol-regime filtering for all downstream strategies."
    )

    def _compute_core(self, data, config: DiagnosticConfig, mask: np.ndarray) -> dict:
        m1      = data.ds.m1
        session = data.session[mask]
        hours   = data.hour_utc[mask]
        bar_range = (m1.high - m1.low)[mask].astype(np.float64)

        n_obs = int(mask.sum())
        if n_obs < 500:
            return _empty()

        # ── Trailing mean vol (14-bar rolling)
        trail_mean = pd.Series(bar_range).rolling(_TRAILING_BARS, min_periods=3).mean().values
        bar_range_z = (bar_range - trail_mean) / (trail_mean + 1e-9)
        vol_spike   = bar_range > _SPIKE_MULT * (trail_mean + 1e-9)

        # ── ACF at lags 1..ACF_LAGS
        valid = bar_range[~np.isnan(bar_range)]
        mu    = np.mean(valid)
        var   = np.var(valid)
        acf   = np.zeros(_ACF_LAGS)
        for lag in range(1, _ACF_LAGS + 1):
            cov      = np.mean((valid[lag:] - mu) * (valid[:-lag] - mu))
            acf[lag - 1] = cov / (var + 1e-12)

        # ── Per-hour mean bar_range
        hour_stats: dict[int, dict] = {}
        for h in range(24):
            hmask  = hours == h
            if hmask.sum() < 50:
                continue
            br_h   = bar_range[hmask]
            _, lo, hi = bootstrap_ci(br_h, np.mean, n=config.n_bootstrap)
            hour_stats[h] = {
                "mean": float(np.nanmean(br_h)),
                "p90":  float(np.nanpercentile(br_h, 90)),
                "ci_lo": lo, "ci_hi": hi,
                "n": int(hmask.sum()),
            }

        # ── Vol spike persistence: how many bars after a spike remain elevated?
        spike_decay = np.zeros(30)
        spike_count = 0
        bar_range_s = pd.Series(bar_range)
        for i in np.where(vol_spike)[0]:
            window_start = int(i) + 1
            window_end   = min(window_start + 30, n_obs)
            if window_start >= n_obs:
                continue
            window_br  = bar_range[window_start:window_end]
            ref        = bar_range[i]
            ratio      = window_br / (ref + 1e-9)
            pad_len    = 30 - len(ratio)
            spike_decay[:len(ratio)] += ratio
            spike_count += 1

        if spike_count > 0:
            spike_decay /= spike_count

        # ── ATR-pct tercile for feature table
        atr_pct   = data.ds.m15.atr_pct
        m1_to_m15 = np.clip(
            np.searchsorted(data.ds.m15.ts, data.ds.m1.ts[mask], side="right") - 1,
            0, len(atr_pct) - 1,
        )
        atr_pct_m1 = atr_pct[m1_to_m15]
        vol_regime = np.zeros(n_obs, dtype=np.int8)
        vol_regime[atr_pct_m1 > np.nanpercentile(atr_pct_m1, 66.7)] = 2
        vol_regime[(atr_pct_m1 > np.nanpercentile(atr_pct_m1, 33.3)) &
                   (atr_pct_m1 <= np.nanpercentile(atr_pct_m1, 66.7))] = 1

        # ── Effect: London open (7am UTC) vs off-hours
        london_hr = (hours >= 7) & (hours < 12)
        off_hr    = (hours < 7) | (hours >= 17)
        if london_hr.sum() > 50 and off_hr.sum() > 50:
            lon_br = bar_range[london_hr]
            off_br = bar_range[off_hr]
            pr = permutation_test(lon_br, off_br, np.mean,
                                  n_permutations=min(config.n_permutations, 3_000))
            _, lo, hi = bootstrap_ci(lon_br, np.mean, n=config.n_bootstrap)
            _, lo2,hi2= bootstrap_ci(off_br, np.mean, n=config.n_bootstrap)
        else:
            pr = type("P", (), {"p_value": 1.0})()
            lo, hi, lo2, hi2 = np.nan, np.nan, np.nan, np.nan
            lon_br, off_br = np.array([]), np.array([])

        effect_sizes = {
            "acf_lag1":              float(acf[0]),
            "acf_mean_1_10":         float(np.nanmean(acf[:10])),
            "london_vs_off_mean_br": float(np.nanmean(lon_br) - np.nanmean(off_br))
                                     if len(lon_br) and len(off_br) else np.nan,
            "spike_rate":            float(vol_spike.mean()),
        }
        cis = {
            "london_mean_br": (lo, hi),
            "off_mean_br":    (lo2, hi2),
            "acf_lag1":       (float(acf[0]) - 0.02, float(acf[0]) + 0.02),  # approx
        }
        effect_reports: list[EffectReport] = []
        if len(lon_br) > 50 and len(off_br) > 50:
            er = build_effect_report(
                finding      = "London open bar range vs off-hours",
                condition    = "session=London (07:00-12:00 UTC)",
                baseline     = float(np.nanmean(off_br)),
                effect_value = float(np.nanmean(lon_br)),
                effect_unit  = "return_difference",
                ci           = (lo, hi),
                p_perm       = pr.p_value,
                p_adj        = pr.p_value,
                effect_d     = float(
                    (np.nanmean(lon_br) - np.nanmean(off_br)) /
                    (np.nanstd(off_br) + 1e-9)
                ),
                stability    = 0.0,
                n_obs        = int(london_hr.sum()),
                n_obs_baseline = int(off_hr.sum()),
            )
            effect_reports.append(er)

        # Feature table
        bar_indices = np.where(mask)[0]
        ft = pd.DataFrame({
            "bar_idx":   bar_indices,
            "bar_range_z": bar_range_z.astype(np.float32),
            "vol_spike": vol_spike,
            "vol_regime": vol_regime,
            "atr_pct_m15": atr_pct_m1.astype(np.float32),
        })

        return {
            "n_obs": n_obs, "effect_sizes": effect_sizes, "ci": cis,
            "p_values_raw": {}, "p_values_perm": {"london_vs_off": float(pr.p_value)},
            "raw_events": pd.DataFrame({
                "acf_lag": list(range(1, _ACF_LAGS + 1)), "acf": acf.tolist()
            }),
            "effect_reports": effect_reports,
            "feature_df": ft,
            "summary_stats": {
                "acf_lag1": float(acf[0]),
                "acf_lag5": float(acf[4]),
                "spike_rate": float(vol_spike.mean()),
                "spike_decay_3bar": float(spike_decay[2]) if spike_count > 0 else np.nan,
                "hour_peak": int(max(hour_stats, key=lambda h: hour_stats[h]["mean"]))
                             if hour_stats else -1,
            },
        }

def _empty() -> dict:
    return {"n_obs": 0, "effect_sizes": {}, "ci": {}, "p_values_raw": {},
            "p_values_perm": {}, "raw_events": pd.DataFrame(),
            "effect_reports": [], "feature_df": None, "summary_stats": {}}
