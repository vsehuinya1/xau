"""
research/reports/stability.py — Stability score computation.

Measures how consistently a finding replicates across two sub-periods.

Score ∈ [0, 1]:
  0.30 × sign_agreement     both effects on same side of zero
  0.40 × ci_overlap         Jaccard overlap of the two 95% CIs
  0.30 × effect_similarity  1 − |d1−d2|/(|d1|+|d2|)
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def compute_stability_score(
    effect_a:    float,
    effect_b:    float,
    ci_a:        tuple[float, float],
    ci_b:        tuple[float, float],
    zero_effect: float = 0.0,
) -> float:
    """
    Composite stability score ∈ [0, 1].

    A score ≥ 0.60 → stable finding.
    A score < 0.40 → unreliable (flag SUBPERIOD_UNSTABLE).
    """
    if any(np.isnan(x) for x in [effect_a, effect_b, *ci_a, *ci_b]):
        return 0.0

    # 1. Sign agreement
    sign_ok = float(
        (effect_a - zero_effect) * (effect_b - zero_effect) > 0
    )

    # 2. CI Jaccard overlap
    overlap_lo   = max(ci_a[0], ci_b[0])
    overlap_hi   = min(ci_a[1], ci_b[1])
    union_lo     = min(ci_a[0], ci_b[0])
    union_hi     = max(ci_a[1], ci_b[1])
    union_width  = union_hi - union_lo
    if union_width > 0 and overlap_hi > overlap_lo:
        ci_overlap = (overlap_hi - overlap_lo) / union_width
    else:
        ci_overlap = 0.0

    # 3. Effect magnitude similarity
    denom      = abs(effect_a) + abs(effect_b) + 1e-9
    similarity = 1.0 - abs(effect_a - effect_b) / denom

    score = 0.30 * sign_ok + 0.40 * ci_overlap + 0.30 * similarity
    return float(np.clip(score, 0.0, 1.0))


def subperiod_mask(
    ts:         np.ndarray,   # m1.ts — any datetime-like array
    start_str:  str,          # "2018-01-01"
    end_str:    str,          # "2021-12-31"
) -> np.ndarray:
    """Boolean mask selecting M1 bars within [start_str, end_str]."""
    start  = pd.Timestamp(start_str)
    end    = pd.Timestamp(end_str)
    ts_idx = pd.DatetimeIndex(ts)
    # Strip timezone if present so tz-aware m1.ts can compare to tz-naive bounds
    if ts_idx.tz is not None:
        ts_idx = ts_idx.tz_convert("UTC").tz_localize(None)
    return np.asarray((ts_idx >= start) & (ts_idx <= end))


