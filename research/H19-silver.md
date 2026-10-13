# H19: Trade silver on dollar shocks, with a volatility gate

**Status:** PRE-REGISTERED 2026-10-13. The user asked to "Try silver".
Nothing had been run before this file was committed. Silver's returns after
dollar shocks had never been measured. H07 used silver only as a possible
leader of gold.

**Run 2026-10-13: FAILED.** The holdout was not opened. See `H19-results.md`.
- **Weak follow-through:** silver keeps moving with the shock, but only by
  about half as much per unit of volatility as gold (β = 0.154 against
  gold's 0.330).
  - Gross per trade: +5.0 bp in 2009–17 (t = 2.80, short of 3) and +3.5 bp
    in 2018–25 (t = 1.66).
- **Costs:** a realistic round trip averages 8 bp in 2018–25, so the ungated
  trade loses 4.5 bp (t = −2.1).
- **Gate:** it keeps only 17 trades in 7¾ years. Their +12 bp mean has
  t = 0.5, which is noise.
- **No added events:** all 17 fall on shocks gold also traded, with a
  correlation of 0.79.

## Why silver

H18 showed the forex pairs don't keep moving after a shock; they *are* the
shock. Gold works because it reacts to the dollar with a lag (H07–H10).
Silver is the other dollar-priced metal and may lag the same way.

Silver costs far more relative to its price:
- **Spread:** about 5 bp of price, against about 0.25 bp for gold.
- **Volatility:** silver moves only about 1.7× as much as gold (jobs-report
  minutes, 2012–2017 histdata).

So H17's volatility gate is part of the rule from the start.

## Rule

- **Signal:** the live dollar shock, unchanged: EURUSD and USDJPY both at
  least 3 × M5 ATR in 5 minutes in the same dollar direction
  (`xau/dollar_shock.py`). There is a 30-minute cooldown.
- **Trade:** XAGUSD against the dollar, the same direction as the gold trade.
  Enter at silver's next M1 open (skip if none within 5 minutes) and exit
  30 minutes later. One silver position at a time.
- **Gate:** take the trade only if β × silver's M5 ATR(14) at the shock is at
  least the trade's realistic cost.
  - **β:** calibrated on histdata 2009–2017 as in H17: a least-squares fit
    through the origin of gross $/oz per trade on ATR.

## Costs, measured on the Pepperstone Razor demo, 2026-10-13

Costs are expressed as a fraction of the entry price so they scale with
silver's price, which rose from $12 to $60 over 2018–2026. The bar spread
field has stayed at 4–6 bp of price since 2018.

- **Commission:** none. A 0.01-lot round trip was charged only the spread
  ($0.030) and filled within $0.001 of the quote.
- **Realistic cost per round trip:** the entry bar's spread field
  ($0.001 per point) + 0.3 bp slippage + a news add-on:
  - **+4 bp for entries 08:30–08:44 New York.** At the 08:31 entry over
    2026-08-31 to 10-13, the first silver quote was at most $0.021 (3.4 bp)
    above the bar spread field. This is the counterpart of gold's +$0.80,
    which came from gold's worst first-quote excess of $0.82.
  - **+1 bp otherwise.** The median calm spread was $0.004 above the bar
    field.
- **Double-spread check (the CLAUDE.md convention):** the realistic cost
  plus the entry bar's spread once more.
- **Stress diagnostic, not a criterion:** a +16 bp news add-on. That is the
  worst spread seen anywhere in the first 10 seconds after 08:31, on the
  2026-09-04 jobs report.

## Tests

- **Primary metric:** net bp of the entry price per trade, clustered t by
  trading day.
- **Replication on histdata 2009–2017, ungated:** silver's gross move in the
  trade direction has mean > 0 with t ≥ 3. This sample is also used to
  calibrate β, but β only scales the gate and doesn't decide the sign of
  this test.
- **Pass on Pepperstone 2018 to Sep 2025, gated.** All of these must hold:
  1. Mean realistic net > 0, with t ≥ 2.
  2. Mean net at double spread > 0.
  3. Mean realistic net > 0 in each sub-period: 2018–20, 2021–22 and
     2023 to Sep 2025.
  4. Mean realistic net > 0 without the top 1% of trades.
- **Holdout, run only if the replication and all four criteria pass:**
  gated realistic net > 0 over Oct 2025 to Sep 2026.
  - Silver's returns there have never been looked at.
  - The signal and gold's results there are already known, so this is
    weaker evidence than gold's holdout was.

## Diagnostics

These are reported and do not decide the outcome:
- the ungated results;
- the stress cost;
- the correlation with gold's gated trade on the same shock;
- how many silver trades fall on shocks where gold's gate skipped.

The trades overlap with gold's in time. A pass would add silver to the paper
bot as a share of the same risk per shock, not as extra risk.

## Trial count

1, so the running total becomes 53.
