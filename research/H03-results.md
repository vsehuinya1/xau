# H03 results

Run 2026-09-25 09:16 UTC on M1 bars 2018-01-01 to 2025-09-30, as pre-registered in `H03-opening-range.md` (commit 2ce29f4).

## Verdict

| test | events | t 60m | C1 | C2 | C3 | C4 | C5 | PASS |
|---|---|---|---|---|---|---|---|---|
| London | 1088 | 1.552 | no | no | yes | no | no | no |
| New York | 1102 | -0.662 | no | no | no | no | no | no |

C1: t >= 3 against the matched control at 60m. C2: after-cost 60m move > 0 in 2024-Sep 2025. C3: positive excess in all three sub-periods. C4: t >= 2 without the best weekday. C5: C2 holds without the top 1% of events.

## Ranges

| test | days with a range | normal-size | events |
|---|---|---|---|
| London | 2000 | 1089 | 1088 |
| New York | 2000 | 1104 | 1102 |

Controls: 2,740,909 M1 moments, each used long and short.

## Each test in full

|  | London | New York |
|---|---|---|
| events | 1088 | 1102 |
| days | 1088 | 1102 |
| excess 30m (ATR) | 0.079 | -0.097 |
| t 30m | 1.477 | -1.781 |
| excess 60m (ATR) | 0.112 | -0.055 |
| t 60m | 1.552 | -0.662 |
| excess 120m (ATR) | 0.070 | -0.048 |
| t 120m | 0.723 | -0.410 |
| move 60m (ATR) | 0.088 | 0.002 |
| 2024-25 events | 251 | 263 |
| 2024-25 move 60m $ | -0.080 | 0.022 |
| 2024-25 cost $ | 0.213 | 0.214 |
| 2024-25 net 60m $ | -0.293 | -0.192 |
| excess 2018-20 | 0.169 | -0.079 |
| excess 2021-22 | 0.170 | -0.177 |
| excess 2023-Sep25 | 0.012 | 0.054 |
| t without best weekday | 0.719 | -0.991 |
| best weekday | Tue | Tue |
| 2024-25 net, top 1% cut | -0.496 | -0.498 |

## By side (diagnostic)

| test / direction | events | excess 60m (ATR) | t 60m |
|---|---|---|---|
| London / -1 | 504 | 0.100 | 0.927 |
| London / 1 | 584 | 0.122 | 1.262 |
| New York / -1 | 533 | -0.052 | -0.438 |
| New York / 1 | 569 | -0.057 | -0.497 |

## By weekday (diagnostic)

| test / weekday | events | excess 60m (ATR) | t 60m |
|---|---|---|---|
| London / Fri | 221 | -0.011 | -0.069 |
| London / Mon | 216 | -0.051 | -0.315 |
| London / Thu | 207 | 0.271 | 1.719 |
| London / Tue | 225 | 0.318 | 2.004 |
| London / Wed | 219 | 0.033 | 0.194 |
| New York / Fri | 189 | -0.048 | -0.248 |
| New York / Mon | 218 | -0.328 | -1.747 |
| New York / Thu | 241 | -0.014 | -0.073 |
| New York / Tue | 228 | 0.089 | 0.490 |
| New York / Wed | 226 | 0.015 | 0.085 |

## By year (diagnostic)

| test / year | events | excess 60m (ATR) | t 60m |
|---|---|---|---|
| London / 2018 | 111 | 0.231 | 0.906 |
| London / 2019 | 142 | 0.385 | 1.819 |
| London / 2020 | 143 | -0.093 | -0.585 |
| London / 2021 | 147 | -0.012 | -0.060 |
| London / 2022 | 147 | 0.352 | 1.739 |
| London / 2023 | 147 | -0.099 | -0.608 |
| London / 2024 | 146 | 0.267 | 1.240 |
| London / 2025 | 105 | -0.188 | -0.848 |
| New York / 2018 | 109 | 0.073 | 0.300 |
| New York / 2019 | 156 | -0.178 | -0.868 |
| New York / 2020 | 140 | -0.087 | -0.420 |
| New York / 2021 | 148 | -0.268 | -1.092 |
| New York / 2022 | 137 | -0.080 | -0.385 |
| New York / 2023 | 149 | 0.077 | 0.315 |
| New York / 2024 | 157 | 0.090 | 0.369 |
| New York / 2025 | 106 | -0.033 | -0.120 |

## Excursions within 120 minutes (diagnostic)

| test | MFE median (ATR) | MAE median (ATR) | MFE median (x range) | MAE median (x range) | MFE p75 (x range) |
|---|---|---|---|---|---|
| London | 1.911 | 1.803 | 0.946 | 0.924 | 1.788 |
| New York | 2.332 | 2.365 | 1.084 | 1.130 | 1.976 |
