# H10 results

Run 2026-09-25 11:29 UTC on histdata M1 bars 2009-2017, as pre-registered in `H10-dollar-shock-oos.md` (commit 2f0522d). Controls: 3,078,029 gold moments.

## Verdict

| test | events | t 15m | real (t >= 2.24) | consistent (all sub-periods > 0) | CONFIRMED |
|---|---|---|---|---|---|
| k=2 | 3056 | 6.463 | yes | yes | yes |
| k=3 | 771 | 5.118 | yes | yes | yes |

## In full

|  | k=2 | k=3 |
|---|---|---|
| events | 3056 | 771 |
| days | 1532 | 645 |
| excess 5m (ATR) | 0.157 | 0.356 |
| t 5m | 5.760 | 4.504 |
| excess 15m (ATR) | 0.270 | 0.598 |
| t 15m | 6.463 | 5.118 |
| excess 30m (ATR) | 0.350 | 0.776 |
| t 30m | 6.350 | 5.312 |
| excess 2009-11 | 0.320 | 0.832 |
| excess 2012-14 | 0.201 | 0.410 |
| excess 2015-17 | 0.293 | 0.638 |
| real (t >= 2.24) | yes | yes |
| consistent (all sub-periods > 0) | yes | yes |
| CONFIRMED | yes | yes |

## By session (diagnostic)

| test / session | events | excess 15m (ATR) | t 15m |
|---|---|---|---|
| k=2 / Asia | 1372 | 0.201 | 4.087 |
| k=2 / London | 321 | 0.260 | 2.011 |
| k=2 / NY am | 865 | 0.370 | 4.074 |
| k=2 / NY pm | 498 | 0.295 | 2.340 |
| k=3 / Asia | 236 | 0.449 | 3.567 |
| k=3 / London | 40 | -0.038 | -0.072 |
| k=3 / NY am | 331 | 0.653 | 3.667 |
| k=3 / NY pm | 164 | 0.857 | 2.517 |

## By shock size (smaller |z|) (diagnostic)

| test / shock size | events | excess 15m (ATR) | t 15m |
|---|---|---|---|
| k=2 / [2.0, 2.5) | 2139 | 0.198 | 4.859 |
| k=2 / [2.5, 3.0) | 531 | 0.199 | 2.031 |
| k=2 / [3.0, 4.0) | 236 | 0.627 | 3.183 |
| k=2 / [4.0, inf) | 150 | 0.983 | 2.545 |
| k=3 / [3.0, 4.0) | 535 | 0.469 | 4.363 |
| k=3 / [4.0, inf) | 236 | 0.889 | 3.092 |
