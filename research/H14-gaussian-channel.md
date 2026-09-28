# H14: The Gaussian channel trend system on H1 and H4

**Status:** PRE-REGISTERED 2026-09-28, at the user's request. Nothing had been
run before this file was committed.

## Indicator

This uses the defaults of DonovanWall's "Gaussian Channel" for TradingView.

- **Source:** hlc3.
- **Filter:** 4 poles, sampling period 144, with no reduced-lag or fast-response
  modes.
  - β = (1 − cos(2π/144)) / (1.414^(2/4) − 1).
  - α = −β + √(β² + 2β).
  - f = α⁴·x + 4(1−α)f₁ − 6(1−α)²f₂ + 4(1−α)³f₃ − (1−α)⁴f₄.
- **Bands:** the same filter applied to true range gives fTR. The upper band is
  f + 1.414·fTR and the lower band is f − 1.414·fTR.
- **Bars:** H1 and H4, resampled from M1 on UTC bins.

## Rules (decided at each bar's close, executed at the next bar's open)

- **Long:** enter when f > the previous f and close > the upper band. Exit when
  close < the upper band.
- **Short:** the mirror. Enter when f < the previous f and close < the lower
  band. Exit when close > the lower band.
- **Positions:** one position at a time, and always flat before reversing.

## Costs

- **Trading:** Pepperstone uses the entry bar's M1 spread plus $0.11; histdata
  uses a flat $0.51/oz per round trip.
- **Swap:** charged for each 17:00 New York rollover crossed, triple on
  Wednesdays. Longs pay (Fed funds + 3.51%) a year and shorts earn
  (Fed funds − 1.18%) a year, on price, as in H05.

## Tests and pass criteria

Two tests, H1 and H4. Each must have, in **both** histdata 2009–2017 and
Pepperstone 2018 to Sep 2025, a mean net $/oz per trade > 0 with t ≥ 2 (a
t-test on the trades).

**Trial count:** 2, so the running total becomes 41. Oct 2025 to Sep 2026 is a
diagnostic only.
