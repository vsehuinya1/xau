# H08: Do broad dollar shocks move gold enough to trade?

**Status:** PRE-REGISTERED 2026-09-25 under the user's standing goal. Nothing
had been run before this file was committed; results go in `H08-results.md`.

**Caveat:** this hypothesis was motivated by H07's result on the same
2018–2025 data. A pass here is therefore provisional. It must also pass on
the locked holdout (from 2025-10-01), or in forward paper trading, before it
counts as an edge.

## Question

When the dollar index and USDJPY both jump sharply in the same direction in the
same 5 minutes, does gold follow by enough to beat costs?

## Why it might work

H07 found gold follows sharp dollar moves, but by only about half the
round-trip cost. A sharp move in one pair is often pair-specific news, such as
a euro or yen story, which gold has little reason to follow. When the broad
dollar index and USDJPY move sharply together, the shock is more likely a
genuine US dollar or rates shock. Gold should respond more to that: it is
priced in dollars, and USDJPY tracks US yields.

## Events

- **z-scores:** the same as H07. For USDX and USDJPY at each M1 close, the
  5-minute move divided by that market's M5 ATR.
- **Broad dollar shock:** at the same minute's close, z(USDX) ≥ k and
  z(USDJPY) ≥ k (dollar up), or both ≤ −k (dollar down).
- **Gold direction:** opposite to the dollar.
- **Tests:** k = 2 and k = 3, so 2 primary tests.
- **Cooldown:** 30 minutes between events, per test.
- **Entry:** the first gold M1 bar opening at or after that close, within 5
  minutes.

## Measurements, controls, pass criteria

The same as H07:
- **Horizons:** 5, 15 (primary) and 30 minutes.
- **Units and costs:** gold ATR units, and dollars after costs.
- **Controls:** matched on session × hour × gold's prior 15-minute move.
- **Pass criteria:** H01's five criteria at 15 minutes (t ≥ 3, net > 0 in
  2024–25, positive in all sub-periods, t ≥ 2 without the best session, and
  C2 without the top 1%).

## Trial count

2 primary tests, so the running total becomes 27. Diagnostics: the 5- and
30-minute horizons, per session, whether gold had already followed, and the
gold move per unit of dollar shock.

## Implementation details

The same as H07. The two markets' z-scores are paired on identical M1 close
times; minutes where either market has no bar are skipped.
