# H19 results

Run 2026-10-13 15:33 UTC, as pre-registered in `H19-silver.md`. Per trade, in bp of silver's entry price; 30-minute hold.

Calibrated on histdata 2009-2017: **beta = 0.154** (gross $/oz per trade per $ of silver M5 ATR). Gate: trade only if 0.154 x ATR >= the trade's realistic cost.

## Criteria

| criterion | PASS |
|---|---|
| R  histdata 2009-17 gross > 0, t >= 3 (ungated) | no |
| 1  gated realistic net > 0, t >= 2 | no |
| 2  gated net at double spread > 0 | yes |
| 3  gated net > 0 in every sub-period | yes |
| 4  gated net > 0 without the top 1% | yes |

**Overall: FAIL** (holdout not opened)

## Results

| strategy / sample | trades | trades/yr | gross bp | t gross | net bp (realistic) | t net | net bp (2x spread) | net bp (stress) | net bp w/o top 1% | total bp | max drawdown bp | cost bp |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ungated / histdata 2009-2017 | 766 | 85.111 | 4.997 | 2.800 | 2.844 | 1.596 | 2.844 | -0.572 | 0.600 | 2178.173 | 994.435 | 2.154 |
| ungated / 2018-Sep 2025 | 718 | 92.645 | 3.515 | 1.664 | -4.459 | -2.098 | -10.171 | -8.303 | -6.604 | -3201.231 | 3842.322 | 7.973 |
| gated / 2018-Sep 2025 | 17 | 2.194 | 16.896 | 0.699 | 12.444 | 0.510 | 9.468 | 11.738 | 2.891 | 211.548 | 343.057 | 4.452 |

## Gated net bp by sub-period

| sub-period | net bp |
|---|---|
| 2018-20 | 10.193 |
| 2021-22 | 45.905 |
| 2023-Sep25 | 11.471 |

Gated trades at 08:30-08:44 New York: 1 of 17.


## By year, 2018-2025 (realistic net, bp)

| year | ungated trades | gated trades | ungated net bp | gated net bp |
|---|---|---|---|---|
| 2018 | 67 | 0.000 | -188.636 | 0.000 |
| 2019 | 91 | 3.000 | 8.623 | 76.014 |
| 2020 | 50 | 11 | -601.878 | 66.686 |
| 2021 | 87 | 1.000 | 467.041 | 45.905 |
| 2022 | 103 | 0.000 | -1274.330 | 0.000 |
| 2023 | 120 | 1.000 | -762.853 | 17.271 |
| 2024 | 110 | 1.000 | -536.612 | 5.672 |
| 2025 | 90 | 0.000 | -312.585 | 0.000 |

## Overlap with gold's live strategy, 2018-Sep 2025

| measure | value |
|---|---|
| silver gated trades | 17 |
| gold gated trades | 325 |
| silver trades on shocks gold also traded | 17 |
| silver trades where gold's gate skipped | 0.000 |
| correlation of net bp on shared shocks | 0.785 |
| silver net bp on shocks gold skipped |  |
