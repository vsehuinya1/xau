# H13: The M1 EMA-ribbon pullback system, with and without a Bollinger filter

**Status:** PRE-REGISTERED 2026-09-28. The user asked for this on the strength
of an X post by @jtrader on 2026-09-28: "VECTOR paired with my ema system",
two winning XAUUSD shorts on M1 in the Asia session. VECTOR is proprietary, so
only the EMA system as drawn is tested. The user asked to "add anything that
helps, like Bollinger bands", and exactly one Bollinger variant is fixed here
in advance. Nothing had been run before this file was committed.

## Rules (M1, with shorts shown; longs mirror them)

- **Indicators:** EMA 20 and EMA 50 form the "ribbon", and EMA 200 is the slow
  line. All are on M1 closes, using `ewm(span, adjust=False)`. These are
  common defaults, because the post's settings aren't visible.
- **Downtrend at bar i:** close < EMA200 and EMA20 < EMA50.
- **Trigger at bar i:** a downtrend, with high ≥ EMA20 (price rallied into the
  ribbon) and close < EMA20 (it was rejected).
- **Entry:** the open of bar i+1. It must be in the **Asia session** (18:00–03:00
  New York), as in the post, and within 5 minutes of the trigger.
- **Stop:** the highest high of bars i−9 to i. It is widened to at least
  0.5 × ATR(14, M1) from entry.
- **Target:** 1.5 × the risk, in line with the post's 1.7 : 1 and 0.9 : 1
  trades.
- **Time stop:** exit at the close of the 120th bar if neither the stop nor the
  target has been hit.
- **Fills:** a stop or target fills at its level, or at the bar's open if the
  bar gaps through it. If both are hit in the same bar, the stop is assumed to
  come first.
- **Positions:** one position at a time.

## Tests

1. **T1, the EMA system as drawn.**
2. **T2, T1 plus a Bollinger impulse filter.** A short also needs at least one
   close below the lower Bollinger band (20, 2) in the 20 bars before the
   trigger, with the mirror for longs. The reason: EMA pullback systems fail
   in chop, so only trade after a real impulse.

## Samples and costs, as in H12

- **histdata M1, 2009–2017:** $0.51/oz per round trip.
- **Pepperstone M1, 2018 to Sep 2025:** the entry bar's spread plus $0.11.

Stops are judged on bid prices, which is slightly generous, because a real
short is stopped on the ask. That favours the system, so a failure is
conclusive.

## Pass criteria

In **both** samples: the mean net $/oz per trade is > 0 with t ≥ 2, clustered
by trading day.

## Trial count

2 tests, so the running total becomes 39. Diagnostics:
- win rate, R-multiple and profit factor;
- other sessions;
- Oct 2025 to Sep 2026, whose price path has been seen;
- a replay of the post's evening (2026-09-27), as an illustration only.
