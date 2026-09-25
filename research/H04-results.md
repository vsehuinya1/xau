# H04 results

Run 2026-09-25 09:33 UTC on M1 bars 2018-01-01 to 2025-09-30, as pre-registered in `H04-time-of-day.md` (commit 4707015).

## Verdict

| test | days | mean S (bp) | t | C1 | C2 | C3 | C4 | C5 | PASS |
|---|---|---|---|---|---|---|---|---|---|
| S (Asia long + NY short) | 1900 | 0.446 | 0.251 | no | no | no | no | no | no |

C1: mean S > 0 with t >= 3 (clustered by week). C2: mean S after both legs' costs > 0 in 2024-Sep 2025. C3: mean S > 0 in all three sub-periods. C4: t >= 2 without the best weekday. C5: C2 holds without the top 1% of days.

## The test in full

|  | S |
|---|---|
| 2024-25 days | 436 |
| 2024-25 mean S (bp) | 0.446 |
| 2024-25 cost, both legs (bp) | 1.764 |
| 2024-25 mean net (bp) | -1.318 |
| 2024-25 mean S ($/oz) | -0.059 |
| mean S 2018-20 (bp) | -1.380 |
| mean S 2021-22 (bp) | 2.767 |
| mean S 2023-Sep25 (bp) | 0.651 |
| t without best weekday | -0.536 |
| best weekday | Fri |
| 2024-25 net, top 1% cut (bp) | -4.438 |

## Each leg by year (diagnostic)

Returns are signed as traded: Asia long, New York short. London is unsigned (long).

| leg / year | days | mean (bp) | t |
|---|---|---|---|
| Asia bp / 2018 | 212 | -3.012 | -2.131 |
| Asia bp / 2019 | 251 | 0.490 | 0.233 |
| Asia bp / 2020 | 251 | 0.904 | 0.369 |
| Asia bp / 2021 | 251 | 4.800 | 2.088 |
| Asia bp / 2022 | 250 | -1.178 | -0.531 |
| Asia bp / 2023 | 249 | 0.601 | 0.271 |
| Asia bp / 2024 | 249 | 2.868 | 1.060 |
| Asia bp / 2025 | 187 | 4.462 | 0.955 |
| Asia bp / all | 1900 | 1.221 | 1.357 |
| New York bp / 2018 | 212 | 2.630 | 1.079 |
| New York bp / 2019 | 251 | -1.651 | -0.538 |
| New York bp / 2020 | 251 | -3.345 | -0.461 |
| New York bp / 2021 | 251 | 2.778 | 0.610 |
| New York bp / 2022 | 250 | -0.886 | -0.182 |
| New York bp / 2023 | 249 | 0.410 | 0.098 |
| New York bp / 2024 | 249 | 0.649 | 0.170 |
| New York bp / 2025 | 187 | -8.105 | -2.040 |
| New York bp / all | 1900 | -0.775 | -0.480 |
| London (unsigned) bp / 2018 | 212 | 0.974 | 0.593 |
| London (unsigned) bp / 2019 | 251 | 1.909 | 1.044 |
| London (unsigned) bp / 2020 | 251 | 0.879 | 0.220 |
| London (unsigned) bp / 2021 | 251 | -3.555 | -1.639 |
| London (unsigned) bp / 2022 | 250 | -2.107 | -0.908 |
| London (unsigned) bp / 2023 | 249 | 1.225 | 0.600 |
| London (unsigned) bp / 2024 | 249 | 2.521 | 1.071 |
| London (unsigned) bp / 2025 | 187 | 4.731 | 1.428 |
| London (unsigned) bp / all | 1900 | 0.687 | 0.759 |
| S / 2018 | 212 | -0.382 | -0.144 |
| S / 2019 | 251 | -1.161 | -0.299 |
| S / 2020 | 251 | -2.441 | -0.340 |
| S / 2021 | 251 | 7.579 | 1.576 |
| S / 2022 | 250 | -2.064 | -0.386 |
| S / 2023 | 249 | 1.011 | 0.234 |
| S / 2024 | 249 | 3.517 | 0.831 |
| S / 2025 | 187 | -3.643 | -0.557 |
| S / all | 1900 | 0.446 | 0.251 |
