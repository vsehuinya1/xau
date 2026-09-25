# H05: Does gold's multi-day trend pay after swap and trading costs?

**Status:** PRE-REGISTERED 2026-09-25, approved by the user ("As drafted"),
including the t ≥ 2 bar. Nothing had been run, and no pre-2018 returns had been
looked at, before this file was committed. Results go in `H05-results.md`.
**Covers:** direction 4 (a higher-timeframe signal with M1/M5 execution),
chosen by the user on 2026-09-25 along with allowing overnight holding.

## Question

Does following gold's trend over the past 1, 3 and 12 months (long when up,
short when down) earn money after trading costs and overnight swap, across 26
years that include gold's bull and bear markets?

## Why it might work

Time-series momentum is one of the most replicated effects in finance. Across
decades and dozens of futures markets, gold included, the sign of an asset's
return over the past months predicts its next month (Moskowitz, Ooi and
Pedersen, 2012, and many later studies). The usual explanations are investors
under-reacting to news and then over-reacting late, plus hedging flows.

## Data

- **Daily closes:** the last price of each Monday–Friday trading day, before
  the 17:00 New York rollover. They are built from Pepperstone's bars: daily
  bars for 1998–2015 (checked against known historical prices), hourly bars
  for 2016 and M1 bars from 2017. The data runs to 2025-09-30, with the
  holdout locked.
- **Test period:** decisions from 1999-06-01, once 12 months of history
  exist, to 2025-09-29.
- **Interest rates:** the effective Fed funds rate (FRED series DFF) for each
  day, using the latest value on or before it.

## Signal

On each trading day's close, with R_L the log return over the last L trading
days:

    position = average of sign(R_21), sign(R_63), sign(R_252)   (−1, −1/3, +1/3 or +1)

The position is held from that close to the next.

## Costs

- **Trading:** each unit of position change costs ($0.40 spread + $0.11) / price.
  $0.40 is above every spread we've measured and is used for all years,
  because the pre-2018 bars carry no spreads.
- **Swap:** positions held through the 17:00 rollover are charged 3 nights on
  Wednesdays and 1 night otherwise, as in MT5.
  - **Long:** pays (Fed funds + 3.51%) a year.
  - **Short:** earns (Fed funds − 1.18%) a year, which is a cost when that is
    negative.
  - **Calibration:** the markups make the model match today's quote: long
    −$0.87/oz a night and short +$0.32/oz a night at $4,280, with Fed funds at
    3.88%.

## Pass criteria

All five must hold, on daily net returns.

1. **Real:** mean > 0 with t ≥ 2, using Newey–West standard errors with 10
   lags. The bar is 2, not 3, because a daily strategy's t is roughly
   Sharpe × √years, so t ≥ 3 would reject even a strong single-market
   strategy. This is one primary test of a widely documented effect, and the
   final deflated-Sharpe check still counts every trial.
2. **Pays in today's cost regime:** mean > 0 from 2022-03-17, when Fed rates
   and swaps rose, to Sep 2025.
3. **Consistent over time:** mean > 0 in each of 1999–2007, 2008–2016 and 2017
   to Sep 2025.
4. **Not one lookback:** each lookback on its own (position = sign(R_L) for 21,
   63 and 252 days) has mean > 0 over the full period.
5. **Not one year:** dropping the best calendar year leaves mean > 0 with
   t ≥ 1.5.

## Diagnostics

These are not criteria:
- buy-and-hold with swap, for comparison;
- the strategy's alpha over buy-and-hold;
- returns by year;
- maximum drawdown;
- trades per year;
- time spent long and short.

## Outcome

- **If it passes:** write H05b on execution and sizing:
  - **Timing:** when within the day to trade on M1/M5.
  - **Sizing:** volatility-scaled position sizing.
  - **Final test:** the holdout.
- **If it fails:** step back again. Leading markets and macro surprises are
  still open.

## Trial count

1 primary test, so the running total becomes 11. Criterion 4's lookbacks are
a robustness check, not a selection.

## Implementation details

1. **Trading days:** from `xau.sessions.trading_day`, which rolls over at
   17:00 New York. Weekend-labelled days are dropped. Holidays with no bars
   are skipped, and lookbacks count the trading days present.
2. **Last decision:** the last decision is at the 2025-09-29 close, so the
   last return ends at the 2025-09-30 close, inside the research window.
3. **Swap in percent:** annual swap percentages are divided by 365 per night
   and applied to the position's value at the decision close.
