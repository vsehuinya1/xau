# H09 results

Run 2026-09-25 11:20 UTC on M1 bars 2018-01-01 to 2025-09-30, as pre-registered in `H09-quiet-dollar-shocks.md` (commit 2b63dab). The test is 'dollar quiet'; 'dollar confirmed' is a diagnostic contrast.

## Verdict

| gold shock, fade | events | t 15m | C1 | C2 | C3 | C4 | C5 | PASS |
|---|---|---|---|---|---|---|---|---|
| dollar quiet | 1064 | -0.010 | no | no | no | no | no | no |
| dollar confirmed | 1299 | -1.853 | no | no | no | no | no | no |

C1: t >= 3 against the matched control at 15m. C2: after-cost 15m move > 0 in 2024-Sep 2025. C3: positive excess in all three sub-periods. C4: t >= 2 without the best session. C5: C2 holds without the top 1% of events.

## Each in full

|  | dollar quiet | dollar confirmed |
|---|---|---|
| events | 1064 | 1299 |
| days | 821 | 984 |
| excess 5m (ATR) | 0.049 | -0.119 |
| t 5m | 0.992 | -2.028 |
| excess 15m (ATR) | -0.001 | -0.159 |
| t 15m | -0.010 | -1.853 |
| excess 30m (ATR) | 0.110 | -0.236 |
| t 30m | 1.301 | -2.186 |
| move 15m (ATR) | -0.002 | -0.160 |
| 2024-25 events | 263 | 211 |
| 2024-25 move 15m $ | -0.389 | -0.210 |
| 2024-25 cost $ | 0.253 | 0.255 |
| 2024-25 net 15m $ | -0.642 | -0.465 |
| excess 2018-20 | 0.074 | -0.098 |
| excess 2021-22 | 0.107 | 0.044 |
| excess 2023-Sep25 | -0.172 | -0.413 |
| t without best session | -0.846 | -2.078 |
| best session | NY pm | London |
| 2024-25 net, top 1% cut | -0.798 | -0.714 |

Controls: 2,740,999 gold M1 moments, each used long and short.


## Dollar quiet, by session (diagnostic)

| session | events | excess 15m (ATR) | move 15m (ATR) | t 15m |
|---|---|---|---|---|
| Asia | 479 | -0.205 | -0.223 | -1.881 |
| London | 219 | 0.204 | 0.226 | 1.637 |
| NY am | 246 | -0.014 | -0.029 | -0.092 |
| NY pm | 120 | 0.468 | 0.525 | 2.405 |
