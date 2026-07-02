"""D02 — Impulse-Pullback Structure"""
from __future__ import annotations
import numpy as np
import pandas as pd
from research.diagnostics.registry import register_diagnostic
from research.diagnostics.base import BaseDiagnostic, DiagnosticConfig
from research.utils import bootstrap_ci, cohen_d, permutation_test
from research.reports.effect_report import build_effect_report, EffectReport
from research.data.cache import disk_cached

_N_BARS_DEFAULT   = 5
_ATR_MULT_DEFAULT = 1.5
_SCAN_WINDOW      = 60   # M1 bars to measure post-impulse behaviour


@disk_cached(fmt="feather")
def _detect_impulses(
    m5_high, m5_low, m5_close, m5_atr, m5_ts,
    n_bars: int,
    atr_mult: float,
    data_fp: str = "",
) -> pd.DataFrame:
    """Detect all N-bar impulses on M5 bars. Cached on disk."""
    N = len(m5_close)
    records = []
    i = n_bars
    while i < N:
        # Check for a bullish run of n_bars consecutive up closes
        window = m5_close[i - n_bars: i]
        prev   = m5_close[i - n_bars - 1: i - 1]
        moves  = window - prev
        atr_ref = m5_atr[i - 1] if not np.isnan(m5_atr[i - 1]) else 1.0
        cum_move = np.sum(moves)
        all_bull = np.all(moves > 0)
        all_bear = np.all(moves < 0)
        if (all_bull and cum_move > atr_mult * atr_ref) or \
           (all_bear and abs(cum_move) > atr_mult * atr_ref):
            direction  = 1 if all_bull else -1
            records.append({
                "m5_end_idx":  i - 1,
                "ts":          m5_ts[i - 1],
                "direction":   direction,
                "magnitude":   abs(cum_move),
                "atr_ref":     atr_ref,
                "atr_mult":    abs(cum_move) / (atr_ref + 1e-9),
                "impulse_high": np.max(m5_high[i - n_bars: i]),
                "impulse_low":  np.min(m5_low[i - n_bars: i]),
            })
            i += n_bars   # skip past this impulse
        else:
            i += 1
    return pd.DataFrame(records)


@register_diagnostic
class D02ImpulsePullback(BaseDiagnostic):
    id        = "d02"
    tags      = ["impulse", "pullback", "structure"]
    hypothesis = (
        "After an N-bar M5 impulse exceeding Y×ATR, pullback depth and "
        "continuation probability are non-uniform and measurable by session/context."
    )

    def _compute_core(self, data, config: DiagnosticConfig, mask: np.ndarray) -> dict:
        m1  = data.ds.m1
        m5  = data.ds.m5
        n   = config.params.get("n_bars",   _N_BARS_DEFAULT)
        atr = config.params.get("atr_mult", _ATR_MULT_DEFAULT)

        # Detect impulses (cached)
        imp_df = _detect_impulses(
            m5.high, m5.low, m5.close, m5.atr, m5.ts,
            n_bars=n, atr_mult=atr, data_fp=data.data_fp
        )
        if imp_df.empty:
            return _empty_core()

        # Filter impulses to those within the date mask (match M5 ts to M1 ts range)
        m1_ts_min = m1.ts[mask][0]  if mask.sum() > 0 else m1.ts[0]
        m1_ts_max = m1.ts[mask][-1] if mask.sum() > 0 else m1.ts[-1]
        imp_df = imp_df[(imp_df["ts"] >= m1_ts_min) & (imp_df["ts"] <= m1_ts_max)]

        if len(imp_df) < 10:
            return _empty_core()

        # Map each M5 impulse end to the nearest M1 bar
        m5_to_m1 = np.searchsorted(m1.ts, imp_df["ts"].values, side="right") - 1
        m5_to_m1 = np.clip(m5_to_m1, 0, len(m1.ts) - 1)

        records = []
        for k, (_, imp) in enumerate(imp_df.iterrows()):
            m1_start  = int(m5_to_m1[k])
            direction = int(imp["direction"])
            imp_extreme = float(imp["impulse_high"] if direction == 1 else imp["impulse_low"])
            imp_mag   = float(imp["magnitude"])
            sess      = int(data.session[m1_start]) if m1_start < len(data.session) else -1

            # Scan SCAN_WINDOW M1 bars for pullback and continuation
            scan_end  = min(m1_start + _SCAN_WINDOW, len(m1.ts))
            max_pb    = 0.0   # max retracement fraction
            pb_time   = -1    # bars to max retracement
            continues = False

            entry_close = m1.close[m1_start]
            for j in range(m1_start, scan_end):
                if direction == 1:
                    pb = (entry_close - m1.low[j]) / (imp_mag + 1e-9)
                    if pb > max_pb:
                        max_pb, pb_time = pb, j - m1_start
                    if m1.close[j] > imp_extreme:
                        continues = True
                else:
                    pb = (m1.high[j] - entry_close) / (imp_mag + 1e-9)
                    if pb > max_pb:
                        max_pb, pb_time = pb, j - m1_start
                    if m1.close[j] < imp_extreme:
                        continues = True

            records.append({
                "bar_idx":       m1_start,
                "direction":     direction,
                "magnitude_atr": float(imp["atr_mult"]),
                "session":       sess,
                "pullback_pct":  float(np.clip(max_pb, 0, 1)),
                "pb_time_bars":  pb_time,
                "continues":     int(continues),
                "full_fill":     int(max_pb >= 1.0),
            })

        df = pd.DataFrame(records)
        n_obs = len(df)

        # ── Statistics
        bull = df[df["direction"] ==  1]
        bear = df[df["direction"] == -1]

        effect_sizes: dict[str, float] = {}
        cis:          dict[str, tuple] = {}
        p_raw:        dict[str, float] = {}
        p_perm:       dict[str, float] = {}
        effect_reports: list[EffectReport] = []

        # Global pullback depth
        pb_all  = df["pullback_pct"].values
        _, lo, hi = bootstrap_ci(pb_all, np.mean, n=config.n_bootstrap)
        effect_sizes["pullback_mean"]   = float(np.nanmean(pb_all))
        cis["pullback_mean"]            = (lo, hi)
        effect_sizes["continuation_rate"] = float(df["continues"].mean())
        _, lo2, hi2 = bootstrap_ci(df["continues"].values, np.mean, n=config.n_bootstrap)
        cis["continuation_rate"]        = (lo2, hi2)

        # Session breakdown
        for sess_id, sname in {0: "Asian", 1: "London", 2: "NY"}.items():
            sub = df[df["session"] == sess_id]
            if len(sub) < 20:
                continue
            pb_s = sub["pullback_pct"].values
            cr_s = sub["continues"].values
            pb_all_excl = df[df["session"] != sess_id]["pullback_pct"].values

            _, lo_pb, hi_pb = bootstrap_ci(pb_s, np.mean, n=config.n_bootstrap)
            _, lo_cr, hi_cr = bootstrap_ci(cr_s, np.mean, n=config.n_bootstrap)
            pr = permutation_test(pb_s, pb_all_excl, np.mean,
                                  n_permutations=min(config.n_permutations, 3_000))

            k_pb = f"pullback_{sname}"
            k_cr = f"continuation_{sname}"
            effect_sizes[k_pb] = float(np.nanmean(pb_s))
            effect_sizes[k_cr] = float(np.nanmean(cr_s))
            cis[k_pb]          = (lo_pb, hi_pb)
            cis[k_cr]          = (lo_cr, hi_cr)
            p_perm[k_pb]       = pr.p_value

            er = build_effect_report(
                finding      = f"Pullback depth after {sname} impulse",
                condition    = f"session={sname}, N={n}, ≥{atr}×ATR",
                baseline     = float(np.nanmean(df["pullback_pct"])),
                effect_value = float(np.nanmean(pb_s)),
                effect_unit  = "probability_difference",
                ci           = (lo_pb, hi_pb),
                p_perm       = pr.p_value,
                p_adj        = pr.p_value,
                effect_d     = cohen_d(pb_s, pb_all_excl),
                stability    = 0.0,
                n_obs        = len(sub),
                n_obs_baseline = n_obs,
            )
            effect_reports.append(er)

        # Feature contributions
        ft = df[["bar_idx", "pullback_pct"]].rename(columns={"pullback_pct": "pullback_depth"})

        return {
            "n_obs": n_obs, "effect_sizes": effect_sizes,
            "ci": cis, "p_values_raw": p_raw, "p_values_perm": p_perm,
            "raw_events": df, "effect_reports": effect_reports,
            "feature_df": ft,
            "summary_stats": {
                "n_impulses": n_obs,
                "pullback_mean": float(np.nanmean(pb_all)),
                "continuation_rate": float(df["continues"].mean()),
                "full_fill_rate": float(df["full_fill"].mean()),
            },
        }


def _empty_core() -> dict:
    return {"n_obs": 0, "effect_sizes": {}, "ci": {}, "p_values_raw": {},
            "p_values_perm": {}, "raw_events": pd.DataFrame(),
            "effect_reports": [], "feature_df": None, "summary_stats": {}}
