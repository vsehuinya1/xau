# H06 results

Run 2026-09-25 10:39 UTC on M1 bars 2018-01-01 to 2025-09-30, as pre-registered in `H06-volume-profile.md` (commit 41465d9).

## Verdict

| part / timeframe / level / path | events | t 60m | C1 | C2 | C3 | C4 | C5 | PASS |
|---|---|---|---|---|---|---|---|---|
| A / M5 / POC / acceptance | 1198 | -1.527 | no | no | no | no | no | no |
| A / M5 / POC / reclaim | 1451 | -0.674 | no | no | no | no | no | no |
| A / M5 / value-area edge / acceptance | 2071 | 1.224 | no | no | yes | no | no | no |
| A / M5 / value-area edge / reclaim | 2642 | 1.205 | no | no | no | no | no | no |
| B / M5 / 80% rule / re-entry | 401 | 0.737 | no | yes | no | no | yes | no |
| A / M15 / POC / acceptance | 1143 | -1.275 | no | no | no | no | no | no |
| A / M15 / POC / reclaim | 1453 | 0.873 | no | no | no | no | no | no |
| A / M15 / value-area edge / acceptance | 1952 | -0.397 | no | no | no | no | no | no |
| A / M15 / value-area edge / reclaim | 2601 | 0.979 | no | yes | no | no | no | no |
| B / M15 / 80% rule / re-entry | 441 | 1.279 | no | yes | no | no | yes | no |

C1: t >= 3 against the matched control at 60m. C2: after-cost 60m move > 0 in 2024-Sep 2025. C3: positive excess in all three sub-periods. C4: t >= 2 without the best session (Part A) or weekday (Part B). C5: C2 holds without the top 1% of events.

## Each test in full

|  | A / M5 / POC / acceptance | A / M5 / POC / reclaim | A / M5 / value-area edge / acceptance | A / M5 / value-area edge / reclaim | B / M5 / 80% rule / re-entry | A / M15 / POC / acceptance | A / M15 / POC / reclaim | A / M15 / value-area edge / acceptance | A / M15 / value-area edge / reclaim | B / M15 / 80% rule / re-entry |
|---|---|---|---|---|---|---|---|---|---|---|
| events | 1198 | 1451 | 2071 | 2642 | 401 | 1143 | 1453 | 1952 | 2601 | 441 |
| days | 945 | 1111 | 1341 | 1521 | 401 | 908 | 1117 | 1300 | 1543 | 441 |
| excess 30m (ATR) | -0.048 | -0.023 | 0.031 | 0.009 | 0.025 | -0.039 | 0.063 | -0.033 | -0.006 | 0.057 |
| t 30m | -0.821 | -0.412 | 0.640 | 0.219 | 0.373 | -1.091 | 1.707 | -0.844 | -0.249 | 1.087 |
| excess 60m (ATR) | -0.112 | -0.056 | 0.085 | 0.065 | 0.085 | -0.061 | 0.045 | -0.019 | 0.034 | 0.095 |
| t 60m | -1.527 | -0.674 | 1.224 | 1.205 | 0.737 | -1.275 | 0.873 | -0.397 | 0.979 | 1.279 |
| excess 120m (ATR) | -0.052 | -0.085 | 0.062 | 0.119 | -0.027 | -0.038 | -0.026 | -0.009 | 0.045 | 0.050 |
| t 120m | -0.465 | -0.750 | 0.712 | 1.656 | -0.155 | -0.550 | -0.389 | -0.152 | 0.917 | 0.465 |
| move 60m (ATR) | -0.157 | -0.057 | 0.055 | 0.067 | 0.089 | -0.085 | 0.044 | -0.031 | 0.035 | 0.098 |
| 2024-25 events | 267 | 310 | 464 | 617 | 90 | 288 | 280 | 444 | 595 | 97 |
| 2024-25 move 60m $ | -0.148 | -0.509 | 0.130 | 0.167 | 0.601 | -0.291 | -0.012 | -0.015 | 0.293 | 0.504 |
| 2024-25 cost $ | 0.236 | 0.236 | 0.234 | 0.229 | 0.213 | 0.233 | 0.231 | 0.232 | 0.229 | 0.213 |
| 2024-25 net 60m $ | -0.384 | -0.745 | -0.104 | -0.062 | 0.388 | -0.524 | -0.243 | -0.248 | 0.064 | 0.292 |
| excess 2018-20 | -0.065 | -0.128 | 0.096 | 0.036 | 0.115 | -0.059 | -0.028 | -0.069 | -0.016 | 0.003 |
| excess 2021-22 | -0.438 | 0.040 | 0.082 | -0.020 | -0.187 | 0.030 | 0.116 | -0.022 | -0.054 | -0.012 |
| excess 2023-Sep25 | 0.042 | -0.050 | 0.075 | 0.159 | 0.247 | -0.119 | 0.082 | 0.038 | 0.154 | 0.274 |
| t without best session | -2.669 | -2.020 | -0.631 | 0.526 |  | -1.718 | -0.662 | -0.863 | -0.002 |  |
| best session | Asia | Asia | Asia | Asia |  | London | Asia | Asia | NY am |  |
| 2024-25 net, top 1% cut | -0.669 | -1.009 | -0.371 | -0.307 | 0.175 | -0.805 | -0.461 | -0.557 | -0.185 | 0.093 |
| t without best weekday |  |  |  |  | -0.036 |  |  |  |  | 0.597 |
| best weekday |  |  |  |  | Wed |  |  |  |  | Wed |

## M5: Part B setup counts and hit rate (diagnostic)

|  | days |
|---|---|
| days with levels | 2000 |
| London open bar | 1999 |
| opened outside value | 1161 |
| accepted back inside | 401 |

| outcome | % of trades |
|---|---|
| closed back outside first | 56.600 |
| far edge first | 31.700 |
| neither by 17:00 NY | 11.700 |

## M5: Part A by session (diagnostic)

| kind / path / session | events | excess 60m (ATR) | t 60m |
|---|---|---|---|
| POC / acceptance / Asia | 852 | -0.001 | -0.007 |
| POC / acceptance / London | 150 | -0.105 | -0.684 |
| POC / acceptance / NY am | 159 | -0.648 | -2.386 |
| POC / acceptance / NY pm | 37 | -0.417 | -1.641 |
| POC / reclaim / Asia | 1031 | 0.051 | 0.515 |
| POC / reclaim / London | 184 | -0.265 | -1.151 |
| POC / reclaim / NY am | 192 | -0.234 | -0.967 |
| POC / reclaim / NY pm | 44 | -0.918 | -2.138 |
| value-area edge / acceptance / Asia | 1318 | 0.173 | 1.920 |
| value-area edge / acceptance / London | 288 | -0.035 | -0.231 |
| value-area edge / acceptance / NY am | 366 | -0.066 | -0.404 |
| value-area edge / acceptance / NY pm | 99 | -0.190 | -0.472 |
| value-area edge / reclaim / Asia | 1669 | 0.073 | 1.112 |
| value-area edge / reclaim / London | 435 | -0.070 | -0.561 |
| value-area edge / reclaim / NY am | 432 | 0.195 | 1.127 |
| value-area edge / reclaim / NY pm | 106 | -0.028 | -0.098 |

## M5: excursions within 120 minutes, in ATR (diagnostic)

| test | MFE median | MAE median | MFE p75 | MAE p75 |
|---|---|---|---|---|
| 80% rule | 1.805 | 1.692 | 3.334 | 3.239 |
| POC / acceptance | 2.222 | 2.415 | 4.340 | 4.108 |
| POC / reclaim | 2.196 | 2.254 | 3.937 | 4.157 |
| value-area edge / acceptance | 2.330 | 2.324 | 4.498 | 4.232 |
| value-area edge / reclaim | 2.287 | 2.267 | 4.125 | 4.093 |

## M15: Part B setup counts and hit rate (diagnostic)

|  | days |
|---|---|
| days with levels | 2000 |
| London open bar | 1999 |
| opened outside value | 1161 |
| accepted back inside | 441 |

| outcome | % of trades |
|---|---|
| closed back outside first | 56.900 |
| far edge first | 31.100 |
| neither by 17:00 NY | 12 |

## M15: Part A by session (diagnostic)

| kind / path / session | events | excess 60m (ATR) | t 60m |
|---|---|---|---|
| POC / acceptance / Asia | 803 | -0.043 | -0.804 |
| POC / acceptance / London | 145 | 0.134 | 1.138 |
| POC / acceptance / NY am | 141 | -0.255 | -1.269 |
| POC / acceptance / NY pm | 54 | -0.350 | -2.224 |
| POC / reclaim / Asia | 995 | 0.095 | 1.579 |
| POC / reclaim / London | 209 | -0.105 | -0.772 |
| POC / reclaim / NY am | 201 | 0.028 | 0.174 |
| POC / reclaim / NY pm | 48 | -0.270 | -1.197 |
| value-area edge / acceptance / Asia | 1194 | 0.010 | 0.162 |
| value-area edge / acceptance / London | 302 | -0.053 | -0.560 |
| value-area edge / acceptance / NY am | 344 | -0.055 | -0.423 |
| value-area edge / acceptance / NY pm | 112 | -0.118 | -0.792 |
| value-area edge / reclaim / Asia | 1596 | -0.005 | -0.115 |
| value-area edge / reclaim / London | 454 | -0.012 | -0.165 |
| value-area edge / reclaim / NY am | 429 | 0.207 | 1.780 |
| value-area edge / reclaim / NY pm | 122 | 0.106 | 0.974 |

## M15: excursions within 120 minutes, in ATR (diagnostic)

| test | MFE median | MAE median | MFE p75 | MAE p75 |
|---|---|---|---|---|
| 80% rule | 1.116 | 1.059 | 2.145 | 1.962 |
| POC / acceptance | 1.224 | 1.350 | 2.541 | 2.424 |
| POC / reclaim | 1.330 | 1.244 | 2.400 | 2.300 |
| value-area edge / acceptance | 1.370 | 1.444 | 2.680 | 2.643 |
| value-area edge / reclaim | 1.326 | 1.338 | 2.470 | 2.421 |
