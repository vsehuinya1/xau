# H01 results

Run 2026-09-25 08:51 UTC on M1 bars 2018-01-01 to 2025-09-30, as pre-registered in `H01-level-pokes.md` (commit ab8ba89).

## Verdict

| level / path | events | t 30m | C1 | C2 | C3 | C4 | C5 | PASS |
|---|---|---|---|---|---|---|---|---|
| Asia / acceptance | 1699 | 0.660 | no | yes | no | no | no | no |
| Asia / reclaim | 3358 | -0.489 | no | no | no | no | no | no |
| prior-day / acceptance | 1339 | 1.332 | no | yes | no | no | no | no |
| prior-day / reclaim | 2316 | -0.925 | no | no | no | no | no | no |
| round / acceptance | 601 | 1.215 | no | no | no | no | no | no |
| round / reclaim | 1314 | -1.405 | no | no | no | no | no | no |

C1: t >= 3 against the matched control. C2: after-cost 30m move > 0 in 2024-Sep 2025. C3: positive excess in all three sub-periods. C4: t >= 2 without the best session. C5: C2 holds without the top 1% of events.

## Pushes by level and path

| kind | acceptance | neither | reclaim | All |
|---|---|---|---|---|
| Asia | 1700 | 1 | 3359 | 5060 |
| prior-day | 1340 | 0 | 2316 | 3656 |
| round | 603 | 0 | 1315 | 1918 |
| All | 3643 | 1 | 6990 | 10634 |

Controls: 2,407,682 M1 moments, each used long and short.

## Each test in full

|  | Asia / acceptance | Asia / reclaim | prior-day / acceptance | prior-day / reclaim | round / acceptance | round / reclaim |
|---|---|---|---|---|---|---|
| events | 1699 | 3358 | 1339 | 2316 | 601 | 1314 |
| days | 1280 | 1812 | 1094 | 1493 | 535 | 874 |
| excess 15m (ATR) | 0.044 | -0.020 | 0.114 | -0.034 | 0.143 | -0.056 |
| t 15m | 1.084 | -0.778 | 1.922 | -0.966 | 1.735 | -1.270 |
| excess 30m (ATR) | 0.038 | -0.016 | 0.135 | -0.055 | 0.137 | -0.074 |
| t 30m | 0.660 | -0.489 | 1.332 | -0.925 | 1.215 | -1.405 |
| excess 60m (ATR) | 0.003 | -0.027 | 0.230 | -0.018 | 0.092 | -0.145 |
| t 60m | 0.035 | -0.626 | 2.098 | -0.305 | 0.712 | -2.330 |
| move 30m (ATR) | 0.029 | -0.014 | 0.124 | -0.053 | 0.124 | -0.073 |
| 2024-25 events | 346 | 748 | 285 | 545 | 208 | 457 |
| 2024-25 move 30m $ | 0.438 | 0.146 | 0.236 | -0.052 | -0.268 | -0.188 |
| 2024-25 cost $ | 0.219 | 0.214 | 0.230 | 0.241 | 0.244 | 0.231 |
| 2024-25 net 30m $ | 0.219 | -0.068 | 0.006 | -0.294 | -0.512 | -0.419 |
| excess 2018-20 | -0.026 | 0.003 | 0.364 | -0.018 | 0.432 | -0.054 |
| excess 2021-22 | 0.051 | -0.111 | 0.036 | -0.107 | 0.162 | -0.088 |
| excess 2023-Sep25 | 0.102 | 0.035 | -0.028 | -0.058 | -0.083 | -0.079 |
| t without best session | -0.204 | -1.166 | 0.903 | -1.042 | 0.993 | -1.445 |
| best session | NY am | NY am | NY am | Asia | NY am | Asia |
| 2024-25 net, top 1% cut | -0.040 | -0.265 | -0.219 | -0.523 | -0.793 | -0.625 |

## By session (diagnostic)

| kind / path / session | events | excess 30m (ATR) | t 30m |
|---|---|---|---|
| Asia / acceptance / London | 1117 | -0.025 | -0.427 |
| Asia / acceptance / NY am | 498 | 0.157 | 1.171 |
| Asia / acceptance / NY pm | 84 | 0.165 | 0.637 |
| Asia / reclaim / London | 2200 | -0.026 | -0.778 |
| Asia / reclaim / NY am | 988 | 0.040 | 0.513 |
| Asia / reclaim / NY pm | 170 | -0.207 | -1.180 |
| prior-day / acceptance / Asia | 667 | 0.092 | 0.515 |
| prior-day / acceptance / London | 237 | 0.062 | 0.411 |
| prior-day / acceptance / NY am | 348 | 0.190 | 1.255 |
| prior-day / acceptance / NY pm | 87 | 0.446 | 1.582 |
| prior-day / reclaim / Asia | 1154 | -0.049 | -0.475 |
| prior-day / reclaim / London | 431 | -0.073 | -0.871 |
| prior-day / reclaim / NY am | 588 | -0.015 | -0.176 |
| prior-day / reclaim / NY pm | 143 | -0.214 | -1.104 |
| round / acceptance / Asia | 281 | 0.138 | 0.726 |
| round / acceptance / London | 102 | 0.156 | 0.826 |
| round / acceptance / NY am | 173 | 0.139 | 0.698 |
| round / acceptance / NY pm | 45 | 0.082 | 0.243 |
| round / reclaim / Asia | 589 | -0.038 | -0.485 |
| round / reclaim / London | 235 | -0.035 | -0.334 |
| round / reclaim / NY am | 361 | -0.104 | -0.921 |
| round / reclaim / NY pm | 129 | -0.227 | -1.466 |

## By side (diagnostic)

| kind / path / side | events | excess 30m (ATR) | t 30m |
|---|---|---|---|
| Asia / acceptance / -1 | 814 | 0.010 | 0.119 |
| Asia / acceptance / 1 | 885 | 0.063 | 0.757 |
| Asia / reclaim / -1 | 1724 | 0.014 | 0.230 |
| Asia / reclaim / 1 | 1634 | -0.047 | -0.842 |
| prior-day / acceptance / -1 | 642 | -0.195 | -1.070 |
| prior-day / acceptance / 1 | 697 | 0.440 | 4.238 |
| prior-day / reclaim / -1 | 1184 | 0.188 | 2.697 |
| prior-day / reclaim / 1 | 1132 | -0.310 | -2.736 |
| round / acceptance / -1 | 314 | 0.048 | 0.300 |
| round / acceptance / 1 | 287 | 0.235 | 1.400 |
| round / reclaim / -1 | 637 | -0.112 | -1.043 |
| round / reclaim / 1 | 677 | -0.039 | -0.436 |

## Excursions within 60 minutes, in ATR (diagnostic)

| kind / path | MFE median | MFE p75 | MAE median | MAE p75 |
|---|---|---|---|---|
| Asia / acceptance | 1.676 | 3.133 | 1.699 | 2.959 |
| Asia / reclaim | 1.628 | 2.902 | 1.666 | 2.928 |
| prior-day / acceptance | 1.939 | 3.720 | 1.725 | 3.257 |
| prior-day / reclaim | 1.706 | 3.224 | 1.796 | 3.282 |
| round / acceptance | 1.737 | 3.547 | 1.750 | 3.196 |
| round / reclaim | 1.627 | 3.012 | 1.711 | 3.190 |
