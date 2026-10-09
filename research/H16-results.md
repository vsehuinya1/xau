# H16 results

Run 2026-10-09 08:44 UTC, as pre-registered in `H16-dollar-enhancements.md` (commit 690ced3). Hold 30 min; costs include H11's news-heavy add-on.

## Verdict

| test | PASS |
|---|---|
| T1 six-currency broad shock | no |
| T2 gold already followed (judged on 2009-2017) | no |

## Results

| strategy / sample | trades | mean net (news-heavy) $/oz | t (news-heavy) | mean net (base) $/oz | win rate % | total (news-heavy) $/oz |
|---|---|---|---|---|---|---|
| baseline (EUR+JPY) / histdata 2009-2017 | 773 | -0.196 | -1.273 | 0.101 | 41.138 | -151.540 |
| T1 six-currency broad shock / histdata 2009-2017 | 788 | -0.241 | -1.689 | 0.009 | 39.340 | -189.990 |
| T2 baseline, gold already followed / histdata 2009-2017 | 596 | -0.094 | -0.508 | 0.230 | 43.289 | -56.210 |
| (diagnostic) baseline, gold not yet followed / histdata 2009-2017 | 177 | -0.539 | -2.287 | -0.332 | 33.898 | -95.330 |
| baseline (EUR+JPY) / Pepperstone 2018-Sep 2025 | 718 | 0.382 | 1.640 | 0.707 | 44.011 | 274.510 |
| T1 six-currency broad shock / Pepperstone 2018-Sep 2025 | 730 | 0.089 | 0.422 | 0.402 | 43.562 | 65.290 |
| T2 baseline, gold already followed / Pepperstone 2018-Sep 2025 | 613 | 0.293 | 1.135 | 0.639 | 44.209 | 179.770 |
| (diagnostic) baseline, gold not yet followed / Pepperstone 2018-Sep 2025 | 105 | 0.902 | 1.923 | 1.102 | 42.857 | 94.740 |
