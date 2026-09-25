# Trials ledger

Every hypothesis and variant tested, across the whole programme. Each extra
test raises the odds that something looks good by luck, so the evidence
needed for a final strategy scales with the running total, for example
through a deflated Sharpe ratio.

Add a row when a hypothesis is registered, and update it when it's run.

| ID  | Hypothesis | Registered | Primary tests | Other trials | Result |
|-----|------------|------------|---------------|--------------|--------|
| H01 | Level pushes: sweep-and-reclaim vs break-and-retest | 2026-09-25 | 6 | 0 | **failed**: best t = 1.33 (needed 3); nothing profitable after costs and consistent |
| H02 | Trend pullback: M5 EMA trend, pullback to 20-EMA, M1 trigger | 2026-09-25 | 1 | 0 | **failed**: t = −0.09; no better than random, even within trends |
| H03 | Opening-range breakout: London open, NY 08:30 | 2026-09-25 | 2 | 0 | **failed**: London t = 1.55 (sign flips by year), NY t = −0.66 |

**Running total:** 9

## Unconfirmed observations

These are patterns spotted in diagnostics after a run. They are **not findings**,
because they were picked out of many splits. Confirming one needs data that
hasn't been looked at: forward paper trading, or the holdout at the very end.
Pursuing one adds every split it was picked from to the trial count.

- **From H01's ~40 diagnostic splits** (sessions, sides, horizons): accepted
  *upward* breaks of the prior-day high continued, with +0.44 ATR of excess at
  30 minutes (t = 4.2, 697 events). Downward breaks didn't (−0.20, t = −1.1).
  The pooled effect was strongest in 2018–20 and has been about zero since
  2023, so it may not be a lasting effect. It would count as about 40 trials
  if pursued.
