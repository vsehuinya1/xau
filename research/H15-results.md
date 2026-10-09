# H15 results

Run 2026-10-09 07:57 UTC, as pre-registered in `H15-adr-exhaustion.md` (commit 2a70adf). Net $/oz per trade.

## Verdict (both samples: net > 0 with t >= 2)

| test | PASS |
|---|---|
| T1 ADR exhaustion | no |
| T2 + dollar-shock filter | no |

## Results

| test / sample | trades | trades/yr | mean net $/oz | t (by day) | win rate % | profit factor | mean net in ADR units | total net $/oz | max drawdown $/oz | mean cost $/oz | short share % |
|---|---|---|---|---|---|---|---|---|---|---|---|
| T1 ADR exhaustion / histdata 2009-2017 | 888 | 98.667 | -0.685 | -3.695 | 39.527 | 0.746 | -0.041 | -608.050 | 628.795 | 0.510 | 51.014 |
| T1 ADR exhaustion / Pepperstone 2018-Sep 2025 | 821 | 105.935 | -0.391 | -1.377 | 39.464 | 0.885 | -0.023 | -321.194 | 454.518 | 0.198 | 52.862 |
| T2 + dollar-shock filter / histdata 2009-2017 | 721 | 80.111 | -0.612 | -2.906 | 40.638 | 0.769 | -0.037 | -441.119 | 477.379 | 0.510 | 48.821 |
| T2 + dollar-shock filter / Pepperstone 2018-Sep 2025 | 666 | 85.935 | -0.219 | -0.670 | 41.592 | 0.933 | -0.014 | -145.865 | 258.418 | 0.200 | 52.853 |
| T1 ADR exhaustion / Oct 2025-Sep 2026 (diagnostic) | 115 | 115 | 2.983 | 1.010 | 46.087 | 1.241 | 0.037 | 343.005 | 323.964 | 0.243 | 50.435 |
| T2 + dollar-shock filter / Oct 2025-Sep 2026 (diagnostic) | 86 | 86 | 1.895 | 0.513 | 43.023 | 1.139 | 0.029 | 162.938 | 353.624 | 0.245 | 44.186 |
