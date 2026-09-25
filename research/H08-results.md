# H08 results

Run 2026-09-25 11:17 UTC on M1 bars 2018-01-01 to 2025-09-30, as pre-registered in `H08-dollar-shocks.md` (commit 1a28112). A pass is provisional until confirmed on the holdout.

## Verdict

| test | events | t 15m | C1 | C2 | C3 | C4 | C5 | PASS |
|---|---|---|---|---|---|---|---|---|
| k=2 | 3512 | 2.839 | no | no | yes | yes | no | no |
| k=3 | 899 | 2.287 | no | yes | yes | no | no | no |

C1: t >= 3 against the matched control at 15m. C2: after-cost 15m move > 0 in 2024-Sep 2025. C3: positive excess in all three sub-periods. C4: t >= 2 without the best session. C5: C2 holds without the top 1% of events.

## Each test in full

|  | k=2 | k=3 |
|---|---|---|
| events | 3512 | 899 |
| days | 1647 | 749 |
| excess 5m (ATR) | 0.045 | 0.236 |
| t 5m | 1.818 | 3.269 |
| excess 15m (ATR) | 0.107 | 0.244 |
| t 15m | 2.839 | 2.287 |
| excess 30m (ATR) | 0.135 | 0.435 |
| t 30m | 2.822 | 3.331 |
| move 15m (ATR) | 0.107 | 0.248 |
| 2024-25 events | 863 | 258 |
| 2024-25 move 15m $ | 0.154 | 0.495 |
| 2024-25 cost $ | 0.231 | 0.245 |
| 2024-25 net 15m $ | -0.078 | 0.250 |
| excess 2018-20 | 0.053 | 0.014 |
| excess 2021-22 | 0.061 | 0.171 |
| excess 2023-Sep25 | 0.187 | 0.436 |
| t without best session | 2.152 | 0.789 |
| best session | NY pm | NY am |
| 2024-25 net, top 1% cut | -0.287 | -0.014 |

Controls: 2,740,999 gold M1 moments, each used long and short.


## By session (diagnostic)

| test / session | events | excess 15m (ATR) | net 15m $ (all years) | t 15m |
|---|---|---|---|---|
| k=2 / Asia | 1481 | 0.074 | -0.158 | 1.682 |
| k=2 / London | 416 | 0.040 | -0.073 | 0.502 |
| k=2 / NY am | 1057 | 0.113 | 0.029 | 1.305 |
| k=2 / NY pm | 558 | 0.236 | -0.017 | 1.976 |
| k=3 / Asia | 258 | 0.019 | -0.207 | 0.169 |
| k=3 / London | 45 | -0.163 | -0.187 | -0.486 |
| k=3 / NY am | 426 | 0.401 | 0.524 | 2.283 |
| k=3 / NY pm | 170 | 0.300 | 0.040 | 0.966 |

## By whether gold had already followed (diagnostic)

| test / gold_followed | events | excess 15m (ATR) | net 15m $ (all years) | t 15m |
|---|---|---|---|---|
| k=2 / False | 1314 | 0.038 | -0.166 | 0.775 |
| k=2 / True | 2198 | 0.149 | -0.011 | 2.767 |
| k=3 / False | 143 | 0.093 | 0.189 | 0.561 |
| k=3 / True | 756 | 0.273 | 0.187 | 2.197 |

## By shock size (smaller of the two z) (diagnostic)

| test / shock size | events | excess 15m (ATR) | net 15m $ (all years) | t 15m |
|---|---|---|---|---|
| k=2 / [2.0, 2.5) | 2467 | 0.046 | -0.185 | 1.226 |
| k=2 / [2.5, 3.0) | 590 | -0.026 | -0.169 | -0.291 |
| k=2 / [3.0, 4.0) | 253 | 0.393 | 0.346 | 2.332 |
| k=2 / [4.0, inf) | 202 | 0.884 | 1.114 | 2.614 |
| k=3 / [3.0, 4.0) | 617 | 0.029 | -0.130 | 0.300 |
| k=3 / [4.0, inf) | 282 | 0.714 | 0.881 | 2.691 |
