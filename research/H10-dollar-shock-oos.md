# H10: Does dollar-shock momentum hold up out of sample (2009–2017)?

**Status:** PRE-REGISTERED 2026-09-25 under the user's standing goal. Nothing
had been run before this file was committed, and none of the 2009–2017
histdata had been examined. Results go in `H10-results.md`.

## Purpose

H07, H08 and H09 all pointed the same way on 2018–2025 Pepperstone data:
after a sharp, broad dollar move, gold keeps moving in the dollar-implied
direction for 15–30 minutes. The strongest numbers came from diagnostics,
though, and all three studies used the same data. This is a **confirmation
test** on 8½ years we have never looked at, with the rules fixed in advance
and copied from H08.

## Data

- **Source:** histdata.com free M1 bid bars for XAUUSD, EURUSD and USDJPY,
  2009–2017.
- **Timestamps:** EST with no daylight saving (UTC−5), converted to UTC.
- **Spreads:** none, so costs can't be judged here. They were judged on
  2024–25 Pepperstone data in H08, where k = 3 gave +$0.25/oz after costs.
- **Why EURUSD and USDJPY:** histdata has no dollar index, so a broad dollar
  shock is defined from these two instead.

## Events

These are H08's rules, with EURUSD standing in for the dollar index.

- **z-scores:** at each M1 close, the pair's 5-minute move divided by its M5
  ATR (14 bars, from M5 bars closed at or before that bar opened).
- **Dollar up:** z(EURUSD) ≤ −k and z(USDJPY) ≥ k at the same close.
- **Dollar down:** z(EURUSD) ≥ k and z(USDJPY) ≤ −k at the same close.
- **Gold direction:** against the dollar.
- **Tests:** k = 2 and k = 3, a 30-minute cooldown each.
- **Entry:** the first gold M1 bar opening at or after that close, within 5
  minutes.

## Measurements and controls

- **Forward move:** from the entry bar's open, at 5, 15 (primary) and 30
  minutes, in gold ATR units.
- **Controls:** every gold M1 moment in 2009–2017, in both directions, matched
  on session × New York hour × prior 15-minute move bin, as in H07.

## Confirmation criteria

The effect counts as confirmed if, for at least one k, both of these hold:

1. **Real:** the mean 15-minute excess is > 0 with t ≥ 2.24, clustered by
   trading day. That is one-sided p < 0.0125, a Bonferroni split of 2.5%
   across the two k values.
2. **Consistent:** the mean excess is positive in each of 2009–11, 2012–14 and
   2015–17.

The bar is 2.24, not 3. This tests an effect already seen, with its rules
fixed in advance, on fresh data; it is not a search.

## Outcome

- **If confirmed:** dollar-shock momentum becomes the lead strategy.
  - **Next rules:** write the trade rules (H10b) with the parameter grid
    declared up front.
  - **Costs:** judge them on 2024–25 Pepperstone data.
  - **Final checks:** the holdout, then paper trading.
- **If not confirmed:** the lead is dropped.

## Trial count

2 tests, so the running total becomes 30. Diagnostics: the 5- and 30-minute
horizons, per session, per sub-period, and by shock size.
