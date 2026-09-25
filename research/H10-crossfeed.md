# H10 diagnostic: histdata vs Pepperstone, 2018-2024

Run 2026-09-25 11:31 UTC. The H10 definition (EURUSD and USDJPY both >= k ATR in 5 minutes, gold against the dollar) on both feeds over the same years.

|  | histdata / k=2 | histdata / k=3 | Pepperstone / k=2 | Pepperstone / k=3 |
|---|---|---|---|---|
| events | 2531 | 628 | 2530 | 628 |
| gold already followed | 0.639 | 0.793 | 0.646 | 0.804 |
| gold M5 ATR median $ | 0.955 | 1.166 | 0.983 | 1.184 |
| excess 5m (ATR) | 0.050 | 0.253 | 0.076 | 0.310 |
| move 5m $ | 0.035 | 0.227 | 0.070 | 0.347 |
| t 5m |  |  | 2.441 | 3.248 |
| excess 15m (ATR) | 0.064 | 0.251 | 0.100 | 0.367 |
| move 15m $ | 0.056 | 0.253 | 0.106 | 0.490 |
| t 15m |  |  | 2.088 | 2.613 |
| excess 30m (ATR) | 0.104 | 0.383 | 0.137 | 0.543 |
| move 30m $ | 0.077 | 0.433 | 0.125 | 0.685 |
| t 30m |  |  | 2.333 | 3.230 |
