# H04: Does gold rise in Asian hours and fall in New York hours?

**Status:** PRE-REGISTERED 2026-09-25, approved by the user ("Yes"). Nothing had
been run, and no hour-of-day returns had been looked at, before this file was
committed. Results go in `H04-results.md`.
**Covers:** direction 1 (time of day), chosen by the user on 2026-09-25.

## Question

Is gold's return during Asian hours systematically higher than during New York
hours, by enough to trade after costs, separately from gold's overall trend?

## Why it might work

The pattern is often reported: gold tends to rise while Asia trades and fall
while New York trades. The proposed reason is structural. Physical demand from
Shanghai and India comes in Asian hours, while US data, futures-driven selling
and dollar moves hit in New York hours. Flows set by who trades when are the
kind of reason an effect could last. Our earlier controls matched on hour of
day, so H01–H03 never tested this.

## Construction

The overall trend is taken out by design.

- **Asia leg:** long from 19:00 to 03:00 New York time, for 8 hours. It starts
  one hour after the daily reopen, avoiding the rollover's wide spreads.
- **New York leg:** short from 08:00 to 16:00 New York time, for 8 hours. It
  ends one hour before the daily close.
- **Daily spread S:** the Asia leg's log return minus the New York leg's log
  return, both within the same trading day (18:00–17:00 New York). This is the
  return of holding both legs. Because both legs last 8 hours, a trend spread
  evenly over the hours cancels out.

Neither leg crosses the 17:00 rollover, so no swap is charged.

## Data, costs and units

- **Bars:** Pepperstone M1 bars from 2018-01-01 to 2025-09-30 (holdout locked).
- **Prices:** each leg enters and exits at the open of the M1 bar at its start
  and end time. If that bar is missing, the first bar opening within 5 minutes
  after is used; otherwise the leg, and that day's S, are skipped.
- **Units:** returns are log returns in basis points (bp).
- **Costs per leg:** the entry bar's spread plus $0.11, divided by the entry
  price. That is two costs per day.

## Pass criteria

All five must hold. Days are the observations, and standard errors are
clustered by calendar week to allow for correlation within a week.

1. **Real:** mean S > 0 with t ≥ 3.
2. **Pays its costs now:** mean S after both legs' costs is positive in 2024
   to Sep 2025.
3. **Consistent over time:** mean S > 0 in each of 2018–20, 2021–22 and 2023
   to Sep 2025.
4. **Not one weekday:** dropping each weekday in turn leaves t ≥ 2.
5. **Not a few outliers:** criterion 2 still holds after dropping days at or
   above the 99th percentile of after-cost S.

## Outcome

- **If it fails:** move on to direction 2, markets that lead gold.
- **If it passes:** write H04b with the trade rules:
  - **Legs:** which to trade (both, or one with a trend hedge).
  - **Timing:** execution times.
  - **Size:** position sizing.
  - **Robustness:** shifting the windows by ±1 hour is declared up front and
    counts as extra trials.

## Trial count

1 primary test, so the running total becomes 10. These are diagnostics only:
- each leg on its own, by year;
- the London hours (03:00–08:00 New York);
- the mean return per New York hour, by sub-period;
- the 2024–25 results in $/oz.
