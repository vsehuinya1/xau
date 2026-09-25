# H03: Do opening-range breakouts at the London open and after the 08:30 NY data keep going?

**Status:** PRE-REGISTERED 2026-09-25, approved by the user ("Yes"). Nothing had
been run before this file was committed; results go in `H03-results.md`.
**Covers:** candidate D (opening-range breakout).

## Question

When gold breaks out of its first 15-minute range after the London open, or
after the 08:30 New York data window, does it keep moving in the breakout
direction by more than random moments do, and by more than our costs?

## Why it might work

Information and orders arrive in bursts at session opens and scheduled US data
releases. The opening range captures the first round of price discovery, and a
breakout shows which side is winning. The counter-case: gold may snap back
after opening volatility, as it did around levels in H01.

## Data, costs and units

As in H01 and H02:
- **Bars:** Pepperstone M1 bars from 2018-01-01 to 2025-09-30 (holdout locked).
- **Costs:** the bar's spread plus $0.11/oz per round trip.
- **Volatility unit:** ATR = the mean of the last 14 M5 true ranges, taken as
  of the reference bar's open.

## The two tests

| Test | Range | Breakouts count until |
|------|-------|-----------------------|
| London | 08:00–08:15 London time | 13:00 London time |
| New York | 08:30–08:45 New York time | 12:00 New York time |

Using London time for the London open keeps it right during the weeks when UK
and US clocks change on different dates.

## Definitions

- **Range:** the high and low of the M1 bars in the 15-minute window on each
  trading day. The day is skipped if fewer than 10 of the 15 bars exist.
- **Normal-size filter:** the range height must lie between the 20th and 80th
  percentiles of the same test's heights over the previous 60 trading days
  that had a range. The current day is excluded from that history, and days
  without 60 prior ranges are skipped.
- **Breakout:** the first M5 bar (New York-time 5-minute bins) that closes
  after the range ends, and no later than the window end, with a close above
  the range high (long) or below the range low (short). There is one event
  per test per day, taken from the first breakout on either side.
- **Reference:** the first M1 bar opening at or after that M5 close. The event
  is dropped if that bar opens more than 5 minutes later.

## Measurements

- **Forward move:** from the reference open, in the breakout direction, at 30,
  60 (primary) and 120 minutes, in ATR units and in dollars after costs.
- **Excursions:** the largest move for and against the trade within 120
  minutes, also in multiples of the range height. That guides targets such as
  "2× the range" if a test passes.

## Controls

Every M1 moment in all sessions, in both directions, matched on session ×
New York hour × prior 15-minute move bin. This is the same as in H02.

## Pass criteria

All five must hold for a test, measured at 60 minutes. Criterion 4 is adapted
because each test lies inside one session by construction.

1. **Beats the control:** the mean 60-minute excess is at least t = 3, with
   standard errors clustered by trading day.
2. **Pays its costs now:** the mean 60-minute move after costs is positive in
   2024 to Sep 2025.
3. **Consistent over time:** the excess is positive in each of 2018–20,
   2021–22 and 2023 to Sep 2025.
4. **Not one weekday:** dropping each weekday in turn leaves t ≥ 2. For
   example, the result can't all come from Fridays with the jobs report.
5. **Not a few outliers:** criterion 2 still holds after dropping events at or
   above the 99th percentile of the after-cost move.

## Outcome

- **If both fail:** the brainstormed candidates A–D are exhausted. Step back
  before registering anything new.
- **If a test passes:** write H03b with full trade rules for it only:
  - **Entry:** as tested.
  - **Invalidation:** a close back inside the range.
  - **Exits:** a target in multiples of the range height, or a trailing stop;
    flat at the window end.

  Declare the parameter grid up front and test it walk-forward.

## Trial count

2 primary tests, so the running total becomes 9. These are diagnostics only:
the 30- and 120-minute horizons, the side, weekday and year splits, and the
excursions.

## Implementation details

1. **Clocks:** London time is Europe/London and New York time is
   America/New_York, from the UTC bar times.
2. **Weekday:** the New York calendar date of the range, which for both tests
   is also its trading day.
3. **Everything else:** forward prices, the prior move and its bins,
   sub-periods, criterion 5 and cost all follow H01's implementation details
   7–14, and ATR follows H02's detail 6.
