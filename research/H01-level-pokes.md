# H01: What happens when gold pushes through an obvious level?

**Status:** PRE-REGISTERED 2026-09-25 (commit ab8ba89), approved by the user.
**Run 2026-09-25: FAILED.** None of the 6 tests passed; the best t was 1.33
against the required 3. The level family (A and B) is dropped. See
`H01-results.md` and the observation in `TRIALS.md`.
**Covers:** candidates A (sweep and reclaim) and B (break and retest).

## Question

When XAUUSD trades through an obvious level, does it snap back (the level
holds) or keep going (the break feeds a move)? Is either move bigger than our
costs?

## Why it might work

Order clustering in currency markets (Osler, 2003 and 2005). Take-profit orders
cluster *at* obvious levels, which produces reversals. Stop orders cluster just
*beyond* them, which makes price speed up once the level breaks. Which effect
wins in gold at M1/M5, if either does, is the empirical question.

## Data

- **Bars:** Pepperstone M1 bars (bid prices) from 2018-01-01 to 2025-09-30, loaded with
  `xau.bars.load_m1`. The holdout stays locked.
- **Costs per round trip:** the bar's spread at entry, plus $0.09/oz commission
  (the top of the measured $0.07–0.09 range), plus $0.02/oz slippage.
- **Volatility unit:** the 14-bar average true range (ATR) on M5 bars, using
  only bars that closed before the event.
- **Sessions,** in New York time: Asia 18:00–03:00, London 03:00–08:00, NY
  morning 08:00–12:00, NY afternoon 12:00–17:00. A trading day runs from
  18:00 to 17:00 New York time.

## Levels

All levels can be computed without hindsight.

1. **Prior-day high/low:** the previous trading day's high and low. Known from
   18:00 New York time.
2. **Asia high/low:** the high and low of the current day's Asia session. Known
   from 03:00 New York time, and used only after that.
3. **Round numbers:** multiples of $50.

## Events

- **Push:** the first M1 bar of the trading day whose high goes above a level
  that was above the previous bar's close. The mirror case applies for lows.
  There is one event per level, per side, per day.
- **Reclaim (candidate A):** within 10 minutes of the push, an M1 bar closes
  back on the original side. The trade direction is reversal. The reference
  price is the next M1 bar's open.
- **Acceptance (candidate B):** within 10 minutes of the push, an M5 bar closes
  beyond the level by at least 0.1 ATR. The trade direction is continuation.
  The reference price is the next M1 bar's open.
- Whichever of reclaim or acceptance happens first decides the path. A push
  can also end up as neither.

## Measurements

- **Forward move:** from the reference price, signed in the trade direction, at
  15, 30 and 60 minutes. The 30-minute move is the primary measure. Each is
  reported in ATR units and in dollars after costs.
- **Excursions:** the largest move for and against the trade within 60 minutes.
  These guide where invalidation should sit in any follow-up.

## Controls

Random moments matched on session, hour of day and the prior 15-minute move
(in ATR, binned), with no level within 0.5 ATR. This separates the effect of
the level from what price does after any move.

## Pass criteria

All five must hold for a given level type and path.

1. **Beats the control:** the mean 30-minute move beats the control with
   t ≥ 3, with standard errors clustered by day. The threshold is 3 rather than
   2 because this study makes 6 primary tests (3 level types × 2 paths) and
   more hypotheses will follow.
2. **Pays its costs now:** the mean 30-minute move is positive after costs in
   2024–Sep 2025, the cost regime we would trade in.
3. **Consistent over time:** it has the same sign in 2018–20, 2021–22 and
   2023–Sep 2025.
4. **Not one session:** removing the best session still leaves t ≥ 2 on
   criterion 1.
5. **Not a few outliers:** removing the top 1% of events still leaves the
   after-cost mean positive.

## Outcome

- **If nothing passes:** drop the level family (A and B) and move on to H02.
- **If something passes:** write H01b with full trade rules (entry,
  invalidation, exits) for the passing case only, with its parameter grid
  declared up front, and test it walk-forward.

## Trial count

6 primary tests. The 15- and 60-minute horizons and the per-session splits
are diagnostics, not selection criteria. Choosing sessions after seeing the
results adds 4 trials.

## Implementation details

These were fixed before running. They interpret the rules above and don't
change them.

1. **Sides:** any level can be pushed from either side. For example, a fall
   back through the prior-day high is a downward push of that level. The
   prior-day high and low are pooled into one level type, as are the Asia
   high and low.
2. **Push time:** the push is known at the close of the push bar.
3. **Reclaim window:** reclaim checks the push bar itself (a wick through the
   level that closes back inside) and the next 10 M1 bars.
4. **Acceptance window:** acceptance checks M5 bars, built on New York-time
   5-minute bins, that close within 10 minutes of the push bar's close.
5. **ATR:** the plain mean of the last 14 M5 true ranges, from M5 bars that
   closed at or before the push bar opened. The same ATR is used for the
   acceptance threshold and for the ATR units.
6. **Reference bar:** the first M1 bar opening at or after the deciding bar's
   close. The event is dropped if that bar opens more than 5 minutes later,
   because the market was closed.
7. **Forward prices:** the price at reference + h is the last M1 close at or
   before that time. Across the daily or weekend close, that is the last price
   before the close. Excursions use bars opening in [reference,
   reference + 60 min).
8. **Prior move:** the reference price minus the last close at or before
   reference − 15 min, signed by the trade direction and divided by ATR.
9. **Controls:** every M1 bar is a control moment in both directions, with its
   open as the reference.
   - Moments are excluded when a level is within 0.5 ATR: the current day's
     prior-day high/low, the Asia high/low (from 03:00 New York time), or the
     nearest $50.
   - Prior-move bin edges, in ATR: −2, −1, −0.5, −0.25, 0, 0.25, 0.5, 1, 2.
   - A matching cell is session × New York hour × bin.
   - Excess is the event's move minus the mean control move in its cell.
10. **Standard errors:** clustered by the trading day of the push.
11. **Sub-periods:** 2018–20, 2021–22 and 2023 to Sep 2025 are dated by the
    reference time, and criterion 3 uses the mean excess in each.
12. **Criterion 4:** drop each session in turn and take the lowest t.
13. **Criterion 5:** applies to the same 2024 to Sep 2025 sample as criterion
    2. Drop events at or above the 99th percentile of the after-cost dollar
    move.
14. **Cost:** the reference bar's `spread` × $0.01, plus $0.11.
