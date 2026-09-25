# H06: Do volume-profile levels (prior-day POC, VAH, VAL) give gold an edge on M5/M15?

**Status:** PRE-REGISTERED 2026-09-25 (commit 41465d9), approved by the user.
**Run 2026-09-25: FAILED, all 10 tests.**
- **Best result:** the M15 80% rule at t = 1.28, against the required 3.
- **Part A:** POC and value-area-edge reactions were all within t = ±1.6 on
  both M5 and M15.
- **The 80% rule:** price reached the far edge first in only 31% of trades.
  It closed back outside first in 57%, and neither happened by 17:00 in 12%.
- **Excursions:** as in H01–H03, favourable and adverse moves were about
  equal.

See `H06-results.md`.
**Origin:** the user saw volume-profile levels used in a video about BTC and
asked for our own version on gold, with signals on M5 and M15 and both setups.

## Question

Do the prior day's volume-profile levels act as support/resistance, or lead to
the classic "80% rule" rotation, strongly enough to trade after costs?

## Why it might work

A volume profile shows where trading concentrated. The idea from Market
Profile trading (J. Dalton and others) is:
- **POC:** the price that attracted the most business, the day's "fair value".
- **Value area:** accepted prices. Moves away from it get tested, and a return
  into it tends to rotate through it.

These levels differ from H01's price extremes, which failed: they mark where
volume piled up, not where price peaked.

## The volume profile

- **Source:** the prior trading day's M1 bars (18:00–17:00 New York). Each
  bar's tick volume is spread evenly over its low–high range, across 100
  equal rows spanning the day's low to high. Spot gold has no exchange
  volume, so tick volume is the standard proxy, the same as TradingView's
  gold CFD feeds.
- **POC:** the middle of the row with the most volume. Ties go to the lowest
  such row.
- **Value area:** start from the POC row. Repeatedly add the neighbouring row,
  above or below, that has more volume (above on ties), until at least 70% of
  the day's volume is included.
  - **VAH:** the top of the highest row included.
  - **VAL:** the bottom of the lowest row included.
- **Availability:** the levels are known from the start of the next trading
  day.

## Data, costs, units

- **Bars:** Pepperstone M1 bars from 2018-01-01 to 2025-09-30 (holdout locked).
- **Costs:** the reference bar's spread plus $0.11/oz per round trip, as in
  H01.
- **Signal bars:** M5 and M15 bars, on New York-time bins.
- **ATR:** the mean of the last 14 true ranges on the same timeframe, from
  bars that closed at or before the event's first bar opened. It is used for
  thresholds and as the unit.

## Part A: level reactions (8 tests)

There are 2 level types:
- **value-area edges:** VAH and VAL pooled;
- **POC.**

Each is tested on 2 paths, reclaim and acceptance, on 2 timeframes, M5 and M15.

- **Push:** the first bar of the trading day, on the timeframe, whose high goes
  above a level that was above the previous bar's close, with the mirror case
  for lows. There is one event per level, per side, per day. Levels can be
  pushed from either side.
- **Path:** decided among the push bar's close and the next 2 closes, first
  one wins.
  - **Reclaim:** a close back on the original side. The trade is a reversal.
  - **Acceptance:** a close beyond the level by at least 0.1 ATR. The trade is
    a continuation.
  - **Neither:** no event.
- **Reference:** the first M1 bar opening at or after the deciding close. The
  event is dropped if that bar opens more than 5 minutes later.
- **Controls:** as in H01.
  - **Matching:** every M1 moment, both directions, matched on session × New
    York hour × prior 15-minute move bin (edges −2, −1, −0.5, −0.25, 0, 0.25,
    0.5, 1 and 2 ATR).
  - **Exclusions:** moments within 0.5 ATR of that day's POC, VAH or VAL.
  - **Units:** computed per timeframe, in that timeframe's ATR.

## Part B: the 80% rule (2 tests: M5 and M15)

- **Open outside value:** the open of the first M1 bar at or after 08:00
  London time (the London open) is above VAH or below VAL.
- **Accepted back inside:** between the London open and 12:00 New York, bars
  close inside the value area for 60 minutes in a row. That's 4 consecutive
  M15 closes or 12 consecutive M5 closes, mirroring the rule's "two
  consecutive 30-minute periods". A close outside resets the count. There is
  at most one trade per day.
- **Direction:** towards the far edge, short if the day opened above VAH and
  long if it opened below VAL.
- **Reference:** the first M1 bar opening at or after the confirming close,
  within 5 minutes.
- **Controls:** as in H02 and H03, with every M1 moment matched on session ×
  hour × prior-move bin.

## Measurements

These apply to both parts.

- **Forward move:** from the reference open, signed in the trade direction, at
  30, 60 (primary) and 120 minutes. It is reported in ATR units and in
  dollars after costs.
- **Excursions:** within 120 minutes.
- **Part B only:** the share of trades that reach the far edge before a close
  back outside on the entry side, by 17:00 New York. This checks the rule's
  "80%" claim.

## Pass criteria

H01's five criteria apply to every test, measured at 60 minutes.

1. **Beats the control:** the mean excess is t ≥ 3, clustered by trading day.
2. **Pays its costs now:** the mean after-cost move is positive in 2024 to Sep
   2025.
3. **Consistent over time:** the excess is positive in 2018–20, 2021–22 and
   2023 to Sep 2025.
4. **Not one group:**
   - **Part A:** dropping each session in turn leaves t ≥ 2.
   - **Part B:** each trade sits between London and midday New York, so
     weekdays are dropped instead.
5. **Not a few outliers:** criterion 2 still holds after dropping events at or
   above the 99th percentile of the after-cost move.

## Outcome

- **If a test passes:** write H06b with full trade rules for it only, covering
  invalidation, targets (for example the far value-area edge) and sizing.
  Declare its parameter grid up front and test it walk-forward.
- **If none pass:** volume-profile levels join H01's levels as no edge on
  their own.

## Trial count

10 primary tests, so the running total becomes 21. The 30- and 120-minute
horizons, the splits and the Part B hit rate are diagnostics.

## Implementation details

These were fixed before running.

1. **Volume per row:** each bar's tick volume is split equally among the rows
   its low–high range touches. Row k covers [low + k·w, low + (k+1)·w), with
   the day's high in the top row.
2. **Next trading day:** "the next trading day" is the next one in the data,
   so Friday's profile applies on Monday.
3. **Part B open:** the London-open bar must open within 5 minutes of 08:00
   London, or the day is skipped.
4. **Part B "inside":** VAL ≤ close ≤ VAH. The counted closes are those of
   bars closing after 08:00 London and no later than 12:00 New York.
5. **Part B ATR:** ATR is used for units only, taken as of the reference bar's
   open, as in H02 and H03.
6. **Part B hit rate:** the far edge counts as reached when an M1 high or low
   touches it. The invalidating close is a timeframe close, both after the
   entry and by 17:00 New York.
7. **Everything else:** forward prices, prior move, clustering, sub-periods,
   criterion 5 and cost follow H01's details 7–14.
