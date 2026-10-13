# H18: Do forex pairs also follow broad dollar shocks?

**Status:** PRE-REGISTERED 2026-10-13. The user asked about adding forex pairs.
Nothing had been run before this file was committed. Forex moves after these
shocks had never been examined; earlier work only measured gold.

**Run 2026-10-13: FAILED, 0 of 6 pairs.** See `H18-results.md`.
- **Gross:** the pairs keep drifting with the dollar by only 0–2 pips in 30
  minutes. Costs are about 1.7–2.4 pips with the harsh add-on.
- **After costs:** in 2018–25, the best pair, USDJPY, is +0.03 pip (t = 0.03).
  Every other pair loses, most with t ≤ −2.7.
- **Why gold differs:** the FX pairs *are* the shock and have already moved by
  the time it registers. Gold reacts with a lag (H07–H10), and that lag is
  the tradable part.

## Question

After the live signal fires, does each of six dollar pairs keep moving in the
dollar's direction for 30 minutes, by more than costs? The signal is a broad
dollar shock: EURUSD and USDJPY both at least 3 ATR in 5 minutes, in the
dollar direction, as in H11 and `xau/dollar_shock.py`. If the pairs do follow,
each shock could be traded in more than one instrument.

## Rules (one test per pair)

- **Pairs:** EURUSD, GBPUSD, AUDUSD, USDJPY, USDCAD and USDCHF.
- **Trade:** in the dollar's direction. On a dollar-up shock, sell EURUSD,
  GBPUSD and AUDUSD, and buy USDJPY, USDCAD and USDCHF.
- **Entry:** the next M1 open of that pair, within 5 minutes; otherwise skip.
- **Exit:** after 30 minutes. One position per pair at a time; shocks have a
  30-minute cooldown.

## Costs, in pips per round trip

A pip is 0.0001, or 0.01 for USDJPY.
- **Pepperstone 2018 to Sep 2025:** the entry bar's spread, plus 0.7 pip
  (Razor commission of about $7 per 100k), plus 0.1 pip slippage.
- **histdata 2009–2017:** no spreads, so a flat 1.0 pip.
- **Harsh news add-on, both samples:** +2.0 pips for entries 08:30–08:45 New
  York, +0.2 pip otherwise. This is the forex counterpart of gold's
  news-heavy model.

## Pass criteria (per pair)

In **both** samples, the mean net pips per trade with the harsh add-on is > 0,
with t ≥ 2 clustered by day.

## Trial count

6, so the running total becomes 52. A pass would mean adding that pair to the
paper bot. Because the trades are correlated with the gold trade, sizing would
be planned around the combined risk per shock.
