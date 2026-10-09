# H17 results

Run 2026-10-09 09:28 UTC, as pre-registered in `H17-volatility-gate.md`.

Calibrated on histdata 2009-2017: **beta = 0.330** (gross $/oz per trade per $ of gold M5 ATR). Gate: trade only if 0.330 x ATR >= the trade's news-heavy cost.

## Criteria (2018-Sep 2025)

| criterion | PASS |
|---|---|
| 1 gated net > 0, t >= 2 | yes |
| 2 gated per-trade > ungated | yes |
| 3 gated total >= 90% of ungated | yes |

**Overall: PASS**

## Results

| strategy / sample | trades | trades/yr | mean net (news-heavy) $/oz | t | total (news-heavy) $/oz | max drawdown $/oz | mean ATR $ |
|---|---|---|---|---|---|---|---|
| ungated / 2018-Sep 2025 | 718 | 92.645 | 0.382 | 1.640 | 274.510 | 114.730 | 1.467 |
| gated / 2018-Sep 2025 | 326 | 42.065 | 0.989 | 2.648 | 322.450 | 55.380 | 1.902 |
| ungated / Oct 2025-Sep 2026 (diag.) | 116 | 116 | 3.964 | 1.963 | 459.820 | 144.530 | 6.197 |
| gated / Oct 2025-Sep 2026 (diag.) | 116 | 116 | 3.964 | 1.963 | 459.820 | 144.530 | 6.197 |
| ungated / calibration 2009-2017 | 773 | 85.889 | -0.196 | -1.273 | -151.540 | 238.080 | 1.005 |

## By year, 2018-2025 (news-heavy net $/oz)

| year | ungated trades | gated trades | ungated net | gated net |
|---|---|---|---|---|
| 2018 | 67 | 14 | -9.840 | 5.780 |
| 2019 | 91 | 38 | 10.430 | -3.920 |
| 2020 | 50 | 35 | -16.650 | -10.280 |
| 2021 | 87 | 37 | 68.480 | 87.170 |
| 2022 | 103 | 44 | -17.520 | 8.000 |
| 2023 | 120 | 48 | 27.960 | 28.100 |
| 2024 | 110 | 48 | 29.190 | 3.660 |
| 2025 | 90 | 62 | 182.460 | 203.940 |
