# H02 results

Run 2026-09-25 09:06 UTC on M1 bars 2018-01-01 to 2025-09-30, as pre-registered in `H02-trend-pullback.md` (commit c1933a0).

## Verdict

|  | events | t 60m | C1 | C2 | C3 | C4 | C5 | PASS |
|---|---|---|---|---|---|---|---|---|
| all | 99699 | -0.093 | no | no | no | no | no | no |

C1: t >= 3 against the matched control at 60m. C2: after-cost 60m move > 0 in 2024-Sep 2025. C3: positive excess in all three sub-periods. C4: t >= 2 without the best session. C5: C2 holds without the top 1% of events.

## Setups

|  | touch bars | pullbacks | triggers |
|---|---|---|---|
| long | 303455 | 63529 | 52344 |
| short | 285345 | 58692 | 47473 |

Events measured: 99,699. Controls: 2,740,909 M1 moments, each used long and short; in-trend controls: 2,230,141.

## The test in full

|  | all |
|---|---|
| events | 99699 |
| days | 2000 |
| excess 30m (ATR) | -0.006 |
| t 30m | -0.553 |
| excess 60m (ATR) | -0.002 |
| t 60m | -0.093 |
| excess 120m (ATR) | -0.002 |
| t 120m | -0.073 |
| move 60m (ATR) | 0.001 |
| 2024-25 events | 22715 |
| 2024-25 move 60m $ | 0.029 |
| 2024-25 cost $ | 0.225 |
| 2024-25 net 60m $ | -0.196 |
| excess 2018-20 | 0.020 |
| excess 2021-22 | -0.023 |
| excess 2023-Sep25 | -0.011 |
| t without best session | -1.175 |
| best session | Asia |
| 2024-25 net, top 1% cut | -0.413 |

## Against random in-trend moments (diagnostic)

| minutes | excess (ATR) | t |
|---|---|---|
| 30 | -0.013 | -1.206 |
| 60 | -0.019 | -1.003 |
| 120 | -0.034 | -0.991 |

## By session (diagnostic)

| session | events | excess 60m (ATR) | t 60m |
|---|---|---|---|
| Asia | 38746 | 0.038 | 1.250 |
| London | 22190 | -0.014 | -0.372 |
| NY am | 16842 | -0.026 | -0.540 |
| NY pm | 21921 | -0.041 | -1.372 |

## By side (diagnostic)

| direction | events | excess 60m (ATR) | t 60m |
|---|---|---|---|
| -1 | 47408 | -0.029 | -1.099 |
| 1 | 52291 | 0.023 | 0.892 |

## Excursions within 120 minutes, in ATR (diagnostic)

| excursion | median | p75 |
|---|---|---|
| favourable | 1.992 | 3.851 |
| adverse | 2.028 | 3.805 |
