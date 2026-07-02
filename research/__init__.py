"""Research package — XAUUSD Market Diagnostics Framework."""
from importlib import import_module as _im

# Eagerly import all diagnostics so their @register_diagnostic decorators fire
for _mod in (
    "research.diagnostics.d11_conditional_returns",
    "research.diagnostics.d01_session_persistence",
    "research.diagnostics.d02_impulse_pullback",
    "research.diagnostics.d03_prev_day_range",
    "research.diagnostics.d04_vol_clustering",
    "research.diagnostics.d05_trend_persistence",
    "research.diagnostics.d06_fvg_fill_rate",
    "research.diagnostics.d07_m15_breakout",
    "research.diagnostics.d08_intraday_timing",
    "research.diagnostics.d09_asian_range_predictor",
    "research.diagnostics.d10_weekday_effects",
):
    _im(_mod)
