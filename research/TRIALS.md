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

| H04 | Time of day: long Asia 19:00–03:00, short NY 08:00–16:00 (trend-neutral) | 2026-09-25 | 1 | 0 | **failed**: +0.45 bp/day, t = 0.25; sign flips by year |

| H05 | Multi-day trend: average sign of 1/3/12-month returns, daily, swap-inclusive | 2026-09-25 | 1 | 0 | **failed**: −1.55%/yr net, t = −0.66; timing alpha vs buy-and-hold −4.9%/yr |

| H06 | Volume profile: prior-day POC/VAH/VAL reactions (8) and the 80% rule (2), M5 and M15 | 2026-09-25 | 10 | 0 | **failed**: best t = 1.28; the "80% rule" reached the far edge first 31% of the time |

| H07 | Leading markets: USDX, EURUSD, USDJPY, silver 5-min moves → gold next 15 min | 2026-09-25 | 4 | 0 | **failed** on costs: USDJPY t = 3.11 and consistent (C1, C3), USDX t = 2.32, but the effect is about half the round-trip cost |

| H08 | Broad dollar shocks: USDX and USDJPY both ≥ k ATR in 5 min (k = 2, 3) → gold. Motivated by H07; a pass is provisional until the holdout | 2026-09-25 | 2 | 0 | **failed, close**: k = 2 t = 2.84 (C3, C4 pass); k = 3 t = 2.29 (C2, C3 pass) |

**Running total:** 27

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
- **From H08's diagnostics** (shock-size and followed splits, about 12 cells):
  gold continues in the direction of large broad dollar shocks, and the effect
  grows with shock size.
  - **Largest shocks:** when both USDX and USDJPY moved ≥ 4 ATR, 202 events
    (k = 2 test) gave +0.88 ATR at 15 minutes, +$1.11/oz after costs,
    t = 2.6.
  - **Why it's plausible:** momentum after US data releases.
  - **Why it's unconfirmed:** it was picked from diagnostics.
  - **Confirming it:** it needs data not yet examined. The 12-month holdout
    holds only about 25 such events, which is too few on its own, so forward
    paper trading is needed as well.
