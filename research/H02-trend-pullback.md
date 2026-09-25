# H02: Does buying pullbacks in an M5 trend beat random timing?

**Status:** PRE-REGISTERED 2026-09-25, approved by the user ("Continue"). Nothing
had been run before this file was committed; results go in `H02-results.md`.
**Covers:** candidate C (trend pullback). Shorts mirror longs throughout.

## Question

When gold is trending on M5 and pulls back to its 20-period EMA, does
entering on the first sign of the trend resuming (on M1) earn more than a
random entry would? Is the difference bigger than our costs?

## Why it might work

Large participants spread orders across the session, which makes intraday
trends persist. A pullback lets a trend follower enter at a better price, and
the M1 trigger waits for evidence that the pullback is over.

## Data, costs and units

As in H01:
- **Bars:** Pepperstone M1 bars from 2018-01-01 to 2025-09-30 (holdout locked).
- **Costs:** the bar's spread plus $0.11/oz per round trip.
- **Volatility unit:** ATR = the mean of the last 14 M5 true ranges.
- **Sessions:** all four, in New York time.

## Definitions

M5 bars use New York-time 5-minute bins. Indicators are computed on completed
M5 closes. At any M1 bar, the values used are those of the last M5 bar that
closed at or before that M1 bar opened.

- **Uptrend:** the M5 close is above the 50-period EMA, the 20-period EMA is
  above the 50-period EMA, and the 50-period EMA is higher than it was 6 M5
  bars (30 minutes) earlier.
- **Touch (the pullback):** in an uptrend, an M1 bar's low reaches or goes
  below the 20-period EMA.
- **Trigger:** starting with the touch bar itself and lasting 15 minutes after
  it closes, the first M1 bar that closes above the previous M1 bar's high.
  Two conditions must hold:
  - the uptrend still holds at the trigger bar;
  - no M5 bar has closed below the 50-period EMA since the touch.
- **Separate pullbacks:** after a touch, whether or not it triggered, the next
  touch counts only after an M1 bar has closed back above the 20-period EMA.
- **Reference:** the first M1 bar opening at or after the trigger bar's close.
  The event is dropped if that bar opens more than 5 minutes later.
- **Direction:** long in uptrends and short in downtrends. Both are pooled.

## Measurements

- **Forward move:** from the reference open, signed in the trade direction, at
  30, 60 (primary) and 120 minutes, in ATR units and in dollars after costs.
- **Excursions:** the largest move for and against the trade within 120
  minutes.

## Controls

Every M1 moment in all sessions, in both directions, matched on session ×
New York hour × prior 15-minute move bin, as in H01. No moments are excluded
for being near a level.

## Pass criteria

All five must hold. They are the same as H01's, measured at 60 minutes.

1. **Beats the control:** the mean 60-minute excess is at least t = 3, with
   standard errors clustered by trading day.
2. **Pays its costs now:** the mean 60-minute move after costs is positive in
   2024 to Sep 2025.
3. **Consistent over time:** the excess is positive in each of 2018–20,
   2021–22 and 2023 to Sep 2025.
4. **Not one session:** dropping each session in turn leaves t ≥ 2.
5. **Not a few outliers:** criterion 2 still holds after dropping events at or
   above the 99th percentile of the after-cost move.

## Outcome

- **If it fails:** drop candidate C and move on to H03 (opening range).
- **If it passes:** write H02b with full trade rules (invalidation below the
  pullback low or an M5 close through the 50-period EMA, exits and sizing).
  Declare its parameter grid up front and test it walk-forward.

## Trial count

1 primary test, so the running total becomes 7. These are diagnostics only:
the 30- and 120-minute horizons, the per-session and per-side splits, and a
comparison against random in-trend moments, which asks whether the pullback
timing adds anything beyond simply being with the trend.

## Implementation details

These were fixed before running. They interpret the rules above and don't
change them.

1. **EMAs:** `ewm(span=n, adjust=False)` on the M5 closes from 2018-01-01.
2. **Touch bar as trigger:** the touch bar can itself be the trigger if it
   closes above the previous M1 bar's high.
3. **Trigger window:** bars closing no later than 15 minutes after the touch
   bar's close.
4. **The 50-period EMA check:** "no M5 close below the 50-period EMA since the
   touch" covers M5 bars closing after the touch bar opened, up to and
   including the trigger bar's close. Each is compared with its own 50-period
   EMA.
5. **Separate pullbacks:** the close that re-arms must come on a bar after the
   touch bar.
6. **ATR:** for ATR units and the prior move, ATR is taken as of the
   reference bar's open, as for the controls.
7. **Standard errors:** clustered by the trading day of the trigger bar.
8. **Everything else:** as in H01's implementation details 7–14, covering
   forward prices, the prior move and its bins, sub-periods, criteria 4 and 5,
   and cost. Excursions run over 120 minutes.
9. **In-trend control** (diagnostic): moments whose trend state at the bar's
   open is up, taken long, or down, taken short, matched on the same cells.
