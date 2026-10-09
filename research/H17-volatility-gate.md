# H17: A volatility gate for dollar-shock momentum

**Status:** PRE-REGISTERED 2026-10-09, approved by the user ("Yes"). Nothing
had been run before this file was committed (commit de07eb5).

**Run 2026-10-09: PASSED.** β = 0.330 was calibrated on 2009–2017.

| 2018 to Sep 2025, news-heavy costs | Ungated | Gated |
|---|---|---|
| Trades | 718 | 326 |
| Net per trade | +$0.38 (t = 1.64) | +$0.99 (t = 2.65) |
| Total | +$275/oz | +$322/oz |
| Max drawdown | $115 | $55 |

- **By year:** the gate helped in 2018, 2021, 2022 and 2025 and hurt in 2019
  and 2024.
- **Oct 2025 to Sep 2026:** the gate blocked nothing; gold's ATR averaged
  about $6.
- **Use:** the gate goes into the paper bot. See `H17-results.md`.

## Why

H16 showed the live strategy lost money after costs in 2009–2017 even though
the effect was real there. The move after a dollar shock scales with gold's
volatility, while costs are roughly fixed in dollars. A gate that trades only
when the expected move beats the trade's cost follows from that cost
structure; it isn't a search for a better backtest.

## Rule

1. **Calibrate β on histdata 2009–2017** with the baseline strategy (H11
   rules, 30-minute hold).
   - **Fit:** gross $/oz per trade = β × ATR, a least-squares fit through the
     origin.
   - **ATR:** gold's M5 ATR(14) at the shock minute.
2. **Gate:** take a shock only if β × ATR ≥ cost.
   - **Cost:** the entry bar's spread + $0.11 + H11's news-heavy add-on
     (+$0.80 for entries 08:30–08:45 New York, +$0.10 otherwise).
   - **Known in advance:** all of this is known when the signal fires; the
     entry bar's spread is the live spread.
3. **Everything else:** unchanged from H11.

## Test on Pepperstone 2018 to Sep 2025, with β from step 1 unchanged

**Pass** requires all three, using news-heavy net:
1. The gated mean net per trade is > 0 with t ≥ 2, clustered by day.
2. The gated mean net per trade is higher than the ungated one.
3. The gated total net is at least 90% of the ungated total.

The holdout period, Oct 2025 to Sep 2026, is reported as a diagnostic. If it
passes, the gate goes into the paper bot.

**Trial count:** 1, so the running total becomes 46.
