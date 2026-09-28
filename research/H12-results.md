# H12 results

Run 2026-09-28 09:33 UTC, as pre-registered in `H12-published-strategies.md` (commit 55fe90c).

## Verdict

| test | PASS |
|---|---|
| A intraday momentum 13:00-13:30 NY | no |
| B1 short into AM fix | no |
| B2 long after PM fix | no |
| C turn of month | no |
| D 200-day filter | no |

## Intraday tests (A, B): both samples must show net > 0 with t >= 2

| test / sample | trades | mean net $/oz | t (NW 5) | mean gross $/oz | t gross | win rate % | total net $/oz | mean cost $/oz |
|---|---|---|---|---|---|---|---|---|
| A / histdata 2009-2017 | 2255 | -0.380 | -7.816 | 0.130 | 2.677 | 37.871 | -856.620 | 0.510 |
| A / Pepperstone 2018-Sep 2025 | 1987 | -0.184 | -3.165 | 0.025 | 0.436 | 45.496 | -365.330 | 0.209 |
| A / holdout Oct 2025-Sep 2026 (diagnostic) | 253 | -0.712 | -0.996 | -0.479 | -0.671 | 47.431 | -180.170 | 0.233 |
| B1 / histdata 2009-2017 | 2269 | -0.237 | -4.568 | 0.273 | 5.259 | 42.618 | -537.910 | 0.510 |
| B1 / Pepperstone 2018-Sep 2025 | 1999 | -0.293 | -3.807 | -0.080 | -1.077 | 43.822 | -584.910 | 0.213 |
| B1 / holdout Oct 2025-Sep 2026 (diagnostic) | 253 | 2.144 | 3.138 | 2.388 | 3.501 | 60.474 | 542.340 | 0.244 |
| B2 / histdata 2009-2017 | 2270 | -0.305 | -3.289 | 0.205 | 2.208 | 47.093 | -692.670 | 0.510 |
| B2 / Pepperstone 2018-Sep 2025 | 1999 | -0.011 | -0.080 | 0.181 | 1.304 | 48.924 | -22.080 | 0.193 |
| B2 / holdout Oct 2025-Sep 2026 (diagnostic) | 253 | -2.424 | -1.283 | -2.188 | -1.158 | 52.569 | -613.340 | 0.236 |

## Daily tests (C, D), June 1999 to Sep 2025, with H05's swap and cost model

| test | trades | mean net % per trade | t | mean net 1st half % | mean net 2nd half % | PASS | net %/yr | t (NW 10) | Sharpe 1st half | buy-and-hold Sharpe 1st half | Sharpe 2nd half | buy-and-hold Sharpe 2nd half | time long % |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C turn of month | 317 | 0.192 | 1.908 | 0.202 | 0.182 | no |  |  |  |  |  |  |  |
| D 200-day filter |  |  |  |  |  | no | 3.531 | 1.335 | 0.295 | 0.488 | 0.201 | 0.179 | 68.708 |

Buy-and-hold over the same period: 5.86%/yr net of swap.

