# H15: Average-daily-range exhaustion, faded, with a dollar-shock filter for gold

**Status:** PRE-REGISTERED 2026-10-09. The user asked for a strategy from
LuxAlgo's library, adapted and enhanced for gold and different from
dollar-shock momentum. Nothing had been run before this file was committed (commit 2a70adf).

**Run 2026-10-09: BOTH FAILED.**
- **T1 (as adapted):** net −$0.69/trade in 2009–17 (t = −3.7) and −$0.39 in
  2018–25 (t = −1.4). Before costs it is about zero: a day reaching its
  average range doesn't mean it stops.
- **T2 (dollar-shock filter):** better in both samples (−$0.61 and −$0.22), so
  skipping dollar-driven extensions helps. It is still negative.
- **Oct 2025 to Sep 2026 (diagnostic):** +$2.98 and +$1.90 per trade, with
  t < 1.1.

See `H15-results.md`.

## Source and why it was chosen

The source is LuxAlgo's "Average Daily Range" (luxalgo.com/library). It
averages the daily high–low over a lookback and treats the projected range
boundaries as areas for mean reversion: "the asset has exhausted its typical
daily volatility".

It was chosen because its mechanism, a spent daily volatility budget, hasn't
been tested here. It is also the opposite of the live dollar-shock strategy:
mean reversion rather than momentum. Most other library entries repeat tested
ideas: sweeps (H01), value areas (H06), and structure/SMC.

## Rules (shorts shown; longs mirror them)

- **ADR:** the mean of (high − low) over the previous 14 trading days. A
  trading day runs 18:00–17:00 New York.
- **Exhaustion short:** the first M5 close of the trading day that is at or
  above (the day's low so far + ADR). At that point the day has used its
  average range and price is at the top.
- **Exhaustion long:** the first M5 close at or below (the day's high so far −
  ADR).
- **Limits:** one trade per side per day, and no entries after 16:00 New York.
- **Entry:** the open of the first M1 bar at or after the M5 close, within 5
  minutes.
- **Exits:** a stop 0.25 × ADR from entry, a target 0.5 × ADR (2 : 1), and
  otherwise the last close before 17:00 New York.
  - **Fills:** the stop or target level, or the bar's open if a bar gaps
    through it.
  - **Both hit in one bar:** the stop is assumed to come first.
- **Positions:** one at a time.

## Tests

- **T1:** the rules above, as adapted from LuxAlgo.
- **T2:** the gold-specific enhancement.
  - **Rule:** skip the trade if a broad dollar shock occurred in the 60
    minutes up to the trigger. A shock is EURUSD and USDJPY both moving ≥ 2
    ATR in 5 minutes in the same dollar direction, as in H08 and H10.
  - **Reason:** H08–H10 showed that dollar-driven gold moves continue, so they
    shouldn't be faded.

## Samples, costs and pass criteria

The same as H13:
- **histdata 2009–2017:** EURUSD and USDJPY also from histdata; $0.51/oz per
  round trip.
- **Pepperstone 2018 to Sep 2025:** the entry bar's spread plus $0.11.
- **Pass:** in **both** samples, mean net $/oz per trade > 0 with t ≥ 2,
  clustered by trading day.

**Trial count:** 2, so the running total becomes 43. Oct 2025 to Sep 2026 is
a diagnostic only.
