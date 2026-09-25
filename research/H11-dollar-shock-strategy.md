# H11: The dollar-shock momentum strategy, with trade rules and costs

**Status:** PRE-REGISTERED 2026-09-25 (commit eb426bc) under the user's
standing goal.

**Run on 2018 to Sep 2025, 2026-09-25:**

| | H = 30 | H = 15 |
|---|---|---|
| Trades | 718 (93 a year) | 718 |
| Mean net per trade | +$0.71/oz (t = 3.04) | +$0.42/oz (t = 2.29) |
| Win rate | 47% | 47% |
| Sharpe | 1.09 | 0.81 |
| Max drawdown | $72/oz | $94/oz |
| Net by era (2018–20 / 2021–22 / 2023–25) | +0.19 / +0.55 / +1.14 | +0.12 / −0.07 / +0.90 |

- **H = 30 is chosen for the holdout.** It is profitable in 7 of 8 years.
  Most of the profit comes from New York-morning shocks, at +$1.20 per trade.
- **H = 15** fails the every-era rule because 2021–22 was negative.
- **Caveat:** these net figures are in-sample. The 2018–2025 data were used
  while exploring H07–H09, and H10 confirmed the effect's existence out of
  sample but not its net profit. The holdout has not been run; it is awaiting
  the user's approval.

See `H11-results.md`.

## Background

H10 confirmed on 2009–2017 data we had never examined (t = 6.46 and 5.12)
that gold keeps moving in the dollar-implied direction after broad dollar
shocks. The effect is weaker since 2018 but still present. This hypothesis
turns it into exact trade rules and measures real profitability after costs.

## Rules

- **Shock:** at an M1 close, the 5-minute moves of EURUSD and USDJPY are both
  at least 3 × their M5 ATR, in the dollar direction:
  - **dollar up:** EURUSD down and USDJPY up;
  - **dollar down:** EURUSD up and USDJPY down.

  This is H10's confirmed definition at k = 3, on Pepperstone's own EURUSD and
  USDJPY bars.
- **Trade:** gold against the dollar. Enter at the open of the next gold M1
  bar, within 5 minutes; otherwise skip.
- **Exit:** after H minutes, at the last gold price at or before entry + H.
  There is no stop and no target. Risk controls come later, sized off the
  results.
- **One position at a time:** a shock while a position is open is skipped.
  Shocks also need 30 minutes of cooldown, as in H10.
- **Grid:** H = 15 or 30 minutes, so 2 variants.
- **Costs:** the entry bar's spread plus $0.11/oz per round trip.

## Evaluation on 2018 to Sep 2025 (Pepperstone)

For each variant:
- trades and trades per year;
- mean net $/oz per trade with t, clustered by day;
- win rate and total net;
- Sharpe, from the per-trade figures annualised by trade frequency;
- maximum drawdown in $/oz;
- net by year and by sub-period.

**The variant for the holdout** is the one with the higher mean net per trade
over 2018 to Sep 2025. It must also be net positive in each of 2018–20,
2021–22 and 2023 to Sep 2025. If neither variant meets that, the strategy
stops here.

## The holdout (only after the user approves using it)

The chosen variant, with rules unchanged, runs once on the locked holdout,
from 2025-10-01 to the latest data.

- **Pass:** mean net per trade > 0 after costs. t is reported too, but the
  holdout has only about a year of data (around 100 trades), so it can't
  prove the edge on its own. Its job is to catch a breakdown.
- **Then:** a pass moves the strategy to paper trading on the demo account. A
  fail stops it.

## Trial count

2 variants, so the running total becomes 32.
