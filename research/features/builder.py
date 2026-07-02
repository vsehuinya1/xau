"""
research/features/builder.py — Incremental feature table assembly.

Each diagnostic contributes its columns via .add_features(). Final .build()
merges everything on bar_idx and writes to parquet.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from research.features.schema import FEATURE_SCHEMA, IDENTITY_COLS

FEATURE_STORE = Path(__file__).resolve().parent.parent.parent / "research" / "features" / "store"


class FeatureTableBuilder:
    """
    Incrementally assembles per-bar features from multiple diagnostics.
    All contributions are joined on `bar_idx` (left join: keeps all bars).
    """

    def __init__(self, n_bars: int, timestamps: np.ndarray):
        self._base = pd.DataFrame({
            "bar_idx":   np.arange(n_bars, dtype=np.int64),
            "timestamp": pd.DatetimeIndex(timestamps),
        })
        self._parts: list[tuple[pd.DataFrame, str]] = []

    # ── Public API ─────────────────────────────────────────────────────────────

    def add_features(self, df: pd.DataFrame, source: str) -> None:
        """
        Add a DataFrame of features. Must have a `bar_idx` column.
        Only columns present in FEATURE_SCHEMA are accepted.
        Unknown columns are dropped with a warning.
        """
        if "bar_idx" not in df.columns:
            raise ValueError(f"[{source}] DataFrame must contain 'bar_idx'")

        # Filter to known schema columns
        known = set(FEATURE_SCHEMA.keys()) | {"bar_idx"}
        unknown = set(df.columns) - known
        if unknown:
            print(f"  [features] {source}: dropping unknown columns: {unknown}")
        df = df[[c for c in df.columns if c in known]].copy()

        self._parts.append((df, source))

    def build(self, tag: str = "xauusd") -> pd.DataFrame:
        """Merge all contributions and write to parquet. Returns the table."""
        result = self._base.copy()
        for df, source in self._parts:
            result = result.merge(df, on="bar_idx", how="left")

        # Cast to schema dtypes where possible
        for col, (dtype, _) in FEATURE_SCHEMA.items():
            if col in result.columns and dtype != "datetime64[ns]":
                try:
                    result[col] = result[col].astype(dtype)
                except (ValueError, TypeError):
                    pass

        FEATURE_STORE.mkdir(parents=True, exist_ok=True)
        out = FEATURE_STORE / f"{tag}.parquet"
        result.to_parquet(out, index=False, compression="snappy")
        print(f"  [features] Saved feature table → {out}  "
              f"({len(result):,} rows × {len(result.columns)} cols)")
        return result

    def column_coverage(self) -> dict[str, str | None]:
        """Return {col: source_that_contributed_it} for all schema columns."""
        covered: dict[str, str | None] = {c: None for c in FEATURE_SCHEMA}
        for df, source in self._parts:
            for col in df.columns:
                if col in covered:
                    covered[col] = source
        return covered
