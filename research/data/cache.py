"""
research/data/cache.py — Hash-based intermediate result caching.

Every expensive intermediate computation (impulse detection, FVG catalogue,
N-day high/low arrays, etc.) is cached on disk keyed by
sha256(function_name + params + data_fingerprint).

Cache is invalidated automatically when parameters or source data change.
Format: feather (fast columnar I/O for DataFrames) or pickle (arbitrary).
"""
from __future__ import annotations

import hashlib
import pickle
from functools import wraps
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / ".research_cache"


def _fingerprint_data(ts: np.ndarray) -> str:
    """Cheap fingerprint of a dataset: first ts + last ts + length."""
    return f"{len(ts)}:{ts[0]}:{ts[-1]}"


def _make_key(func_name: str, params: dict, data_fp: str) -> str:
    payload = f"{func_name}|{sorted(params.items())}|{data_fp}"
    return hashlib.sha256(payload.encode()).hexdigest()[:20]


def _cache_path(func_name: str, key: str, fmt: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{func_name}_{key}.{fmt}"


def load_from_cache(
    func_name: str,
    params:    dict,
    data_fp:   str,
    fmt:       str = "feather",
) -> Any | None:
    key  = _make_key(func_name, params, data_fp)
    path = _cache_path(func_name, key, fmt)
    if not path.exists():
        return None
    try:
        if fmt == "feather":
            return pd.read_feather(path)
        elif fmt == "parquet":
            return pd.read_parquet(path)
        else:
            return pickle.loads(path.read_bytes())
    except Exception:
        return None


def save_to_cache(
    result:    Any,
    func_name: str,
    params:    dict,
    data_fp:   str,
    fmt:       str = "feather",
) -> None:
    key  = _make_key(func_name, params, data_fp)
    path = _cache_path(func_name, key, fmt)
    try:
        if fmt == "feather" and isinstance(result, pd.DataFrame):
            result.to_feather(path)
        elif fmt == "parquet" and isinstance(result, pd.DataFrame):
            result.to_parquet(path, index=False)
        else:
            path.write_bytes(pickle.dumps(result))
    except Exception as exc:
        print(f"  [cache] WARNING: could not save {path}: {exc}")


def disk_cached(
    fmt:       str = "feather",
    params_fn: Callable | None = None,  # optional: extract params from kwargs
) -> Callable:
    """
    Decorator. Caches the return value of the wrapped function.

    The wrapped function must accept `data_fp: str` as a keyword argument
    (the data fingerprint string used for cache keying).

    Usage
    -----
    @disk_cached(fmt="feather")
    def detect_impulses(m5, n_bars, atr_mult, data_fp="") -> pd.DataFrame:
        ...
    """
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            data_fp = kwargs.get("data_fp", "")
            params  = {k: v for k, v in kwargs.items() if k != "data_fp"}
            cached  = load_from_cache(fn.__name__, params, data_fp, fmt)
            if cached is not None:
                return cached
            result = fn(*args, **kwargs)
            save_to_cache(result, fn.__name__, params, data_fp, fmt)
            return result
        return wrapper
    return decorator
