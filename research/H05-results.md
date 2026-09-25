# H05 results

Run 2026-09-25 09:48 UTC on Pepperstone daily closes 1998-2025-09-30, as pre-registered in `H05-multiday-trend.md` (commit f66ee9a).

## Verdict

| test | days | net %/yr | t (NW) | C1 | C2 | C3 | C4 | C5 | PASS |
|---|---|---|---|---|---|---|---|---|---|
| trend (1/3/12-month) | 6826 | -1.552 | -0.661 | no | yes | no | no | no | no |

C1: mean > 0 with t >= 2 (Newey-West, 10 lags). C2: mean > 0 since 2022-03-17. C3: mean > 0 in each era. C4: each lookback alone has mean > 0. C5: without the best year, mean > 0 and t >= 1.5.

## Details

|  | trend | buy-and-hold |
|---|---|---|
| net %/yr | -1.552 | 5.862 |
| gross %/yr | 2.820 | 11.257 |
| costs %/yr | -1.959 | -0.007 |
| swap %/yr | -2.413 | -5.389 |
| Sharpe | -0.124 | 0.349 |
| t (NW) | -0.661 | 1.837 |
| max drawdown % | 83.296 | 68.121 |
| position changes/yr | 28.230 |  |
| time long % | 64.342 |  |
| time short % | 35.570 |  |
| net %/yr since 2022-03-17 | 4.923 |  |
| net %/yr 1999-2007 | -2.720 |  |
| net %/yr 2008-2016 | -1.905 |  |
| net %/yr 2017-Sep25 | -0.031 |  |
| net %/yr, 21-day only | -4.298 |  |
| net %/yr, 63-day only | -2.982 |  |
| net %/yr, 252-day only | 0.160 |  |
| net %/yr without 2011 (best year) | -2.464 |  |
| t without 2011 | -1.043 |  |
| alpha over buy-and-hold %/yr | -4.918 |  |
| beta to buy-and-hold | 0.299 |  |
| t of alpha (NW) | -2.286 |  |

Returns are % of notional per year (daily mean x 252), at a fixed notional (no compounding).

## By year

| year | trend net % | buy-and-hold net % | mean position |
|---|---|---|---|
| 1999 | -2.450 | 3.469 | -0.388 |
| 2000 | -24.298 | -14.481 | -0.187 |
| 2001 | -16.168 | -3.932 | -0.068 |
| 2002 | 7.701 | 17.677 | 0.685 |
| 2003 | 4.971 | 14.676 | 0.642 |
| 2004 | -8.246 | 1.611 | 0.494 |
| 2005 | 1.174 | 10.630 | 0.497 |
| 2006 | 4.905 | 15.185 | 0.536 |
| 2007 | 8.257 | 20.066 | 0.603 |
| 2008 | -6.522 | 5.099 | 0.256 |
| 2009 | -9.813 | 20.350 | 0.501 |
| 2010 | 8.370 | 23.385 | 0.697 |
| 2011 | 22.154 | 8.258 | 0.627 |
| 2012 | -10.685 | 3.546 | 0.130 |
| 2013 | 8.991 | -33.324 | -0.686 |
| 2014 | -11.784 | -4.426 | -0.344 |
| 2015 | -12.816 | -13.545 | -0.514 |
| 2016 | -5.512 | 5.597 | 0.377 |
| 2017 | -8.802 | 8.378 | 0.160 |
| 2018 | -2.424 | -6.427 | -0.016 |
| 2019 | 5.758 | 11.852 | 0.305 |
| 2020 | -0.596 | 20.436 | 0.629 |
| 2021 | -11.853 | -6.377 | -0.103 |
| 2022 | -4.854 | -4.256 | -0.103 |
| 2023 | -1.550 | 4.723 | 0.442 |
| 2024 | 6.577 | 16.624 | 0.773 |
| 2025 | 17.468 | 33.987 | 0.813 |
