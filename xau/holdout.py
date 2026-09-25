"""The locked holdout (decided 2026-09-25).

Market data from HOLDOUT_START on stays out of research until a strategy is
final; it is then tested once. The loaders refuse it unless called with
allow_holdout=True. Allowed uses: the final test; data-quality checks that
look at timestamps, gaps or spreads; the cost model's spreads. Anything that
looks at returns or signals is not.

The recorded Pepperstone ticks (from 2026-08-28) all fall inside it and act
as a second, forward holdout.
"""
import pandas as pd

HOLDOUT_START = pd.Timestamp("2025-10-01", tz="UTC")


def check(end, allow_holdout):
    """Raise unless [.., end) stays before the holdout or the caller opted in."""
    if not allow_holdout and end > HOLDOUT_START:
        raise PermissionError(
            f"data from {HOLDOUT_START:%Y-%m-%d} on is the locked holdout "
            "(see xau/holdout.py); pass allow_holdout=True only for an allowed use")
