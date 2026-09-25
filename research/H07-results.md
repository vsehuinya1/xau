# H07 results

Run 2026-09-25 11:14 UTC on M1 bars 2018-01-01 to 2025-09-30, as pre-registered in `H07-leading-markets.md` (commit 47d6e22).

## Verdict

| leader | events | t 15m | C1 | C2 | C3 | C4 | C5 | PASS |
|---|---|---|---|---|---|---|---|---|
| USDX | 13452 | 2.323 | no | no | yes | no | no | no |
| EURUSD | 13801 | 1.844 | no | no | no | no | no | no |
| USDJPY | 13721 | 3.105 | yes | no | yes | no | no | no |
| XAGUSD | 15345 | 0.600 | no | no | no | no | no | no |

C1: t >= 3 against the matched control at 15m. C2: after-cost 15m move > 0 in 2024-Sep 2025. C3: positive excess in all three sub-periods. C4: t >= 2 without the best session. C5: C2 holds without the top 1% of events.

## Each test in full

|  | USDX | EURUSD | USDJPY | XAGUSD |
|---|---|---|---|---|
| events | 13452 | 13801 | 13721 | 15345 |
| days | 1998 | 2001 | 2000 | 2000 |
| excess 5m (ATR) | 0.013 | 0.013 | 0.030 | -0.008 |
| t 5m | 1.355 | 1.451 | 3.158 | -0.856 |
| excess 15m (ATR) | 0.035 | 0.027 | 0.046 | 0.009 |
| t 15m | 2.323 | 1.844 | 3.105 | 0.600 |
| excess 30m (ATR) | 0.036 | 0.015 | 0.051 | -0.012 |
| t 30m | 1.741 | 0.752 | 2.442 | -0.561 |
| move 15m (ATR) | 0.035 | 0.023 | 0.040 | 0.000 |
| 2024-25 events | 2803 | 2771 | 2823 | 3015 |
| 2024-25 move 15m $ | 0.058 | -0.036 | 0.018 | 0.066 |
| 2024-25 cost $ | 0.230 | 0.229 | 0.236 | 0.234 |
| 2024-25 net 15m $ | -0.172 | -0.265 | -0.218 | -0.168 |
| excess 2018-20 | 0.014 | -0.002 | 0.041 | 0.007 |
| excess 2021-22 | 0.061 | 0.061 | 0.041 | -0.032 |
| excess 2023-Sep25 | 0.041 | 0.034 | 0.056 | 0.045 |
| t without best session | 1.669 | 0.982 | 1.891 | -0.185 |
| best session | NY pm | NY am | Asia | Asia |
| 2024-25 net, top 1% cut | -0.331 | -0.410 | -0.381 | -0.328 |

Controls: 2,740,999 gold M1 moments, each used long and short.


## By session (diagnostic)

| leader / session | events | excess 15m (ATR) | t 15m |
|---|---|---|---|
| EURUSD / Asia | 7262 | 0.018 | 0.956 |
| EURUSD / London | 2563 | -0.021 | -0.720 |
| EURUSD / NY am | 2361 | 0.085 | 1.851 |
| EURUSD / NY pm | 1615 | 0.056 | 1.200 |
| USDJPY / Asia | 6861 | 0.049 | 2.487 |
| USDJPY / London | 2316 | 0.035 | 1.142 |
| USDJPY / NY am | 2502 | 0.071 | 1.574 |
| USDJPY / NY pm | 2042 | 0.018 | 0.439 |
| USDX / Asia | 6505 | 0.018 | 0.853 |
| USDX / London | 2663 | 0.004 | 0.148 |
| USDX / NY am | 2510 | 0.075 | 1.657 |
| USDX / NY pm | 1774 | 0.090 | 2.100 |
| XAGUSD / Asia | 7799 | 0.022 | 1.027 |
| XAGUSD / London | 2894 | -0.012 | -0.418 |
| XAGUSD / NY am | 2772 | -0.012 | -0.275 |
| XAGUSD / NY pm | 1880 | 0.020 | 0.467 |

## By whether gold had already followed (diagnostic)

| leader / gold_followed | events | excess 15m (ATR) | t 15m |
|---|---|---|---|
| EURUSD / False | 8946 | 0.008 | 0.518 |
| EURUSD / True | 4855 | 0.061 | 2.047 |
| USDJPY / False | 8812 | 0.050 | 2.982 |
| USDJPY / True | 4909 | 0.039 | 1.358 |
| USDX / False | 8258 | 0.020 | 1.106 |
| USDX / True | 5194 | 0.060 | 2.178 |
| XAGUSD / False | 4286 | 0.014 | 0.543 |
| XAGUSD / True | 11059 | 0.007 | 0.390 |

## Excursions within 30 minutes, in gold ATR (diagnostic)

| leader | MFE median | MAE median |
|---|---|---|
| EURUSD | 1.171 | 1.202 |
| USDJPY | 1.173 | 1.188 |
| USDX | 1.205 | 1.221 |
| XAGUSD | 1.278 | 1.338 |
