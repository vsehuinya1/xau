# H12: Do published gold strategies hold up on our data?

**Status:** PRE-REGISTERED 2026-09-28 (commit 55fe90c).
**Run 2026-09-28: ALL FIVE FAILED.**
- **A:** the 13:00–13:30 NY intraday momentum was real in 2009–2017 (gross
  +$0.13/trade, t = 2.7) but gone in 2018–25 (+$0.03), and it loses after costs
  in both samples.
- **B1:** the drop into the AM fix was strong in 2009–2017 (gross +$0.27,
  t = 5.3) but gone in 2018–25 (−$0.08). It loses after costs in both.
- **B2:** long after the PM fix grossed +$0.21 and +$0.18, and still lost after
  costs.
- **C:** turn of the month made +0.19% per trade after swap and costs, t = 1.91
  (just below 2), positive in both halves. It's the only near miss.
- **D:** the 200-day filter made +3.5%/yr (t = 1.3), below buy-and-hold's
  +5.9%/yr, and its Sharpe was worse in the first half.

The published effects existed, but they are too small for retail costs and
have mostly faded since 2018. See `H12-results.md`.

## Sources

The candidates come from a web search, ranked by strength of evidence.
Myfxbook and MQL5 "verified" accounts were excluded because their rules
aren't public, and several leads were too weak to test.

| Test | Idea | Source and evidence |
|---|---|---|
| A | **Intraday momentum** | Baltussen, Da, Lammers and Martens (2021), *Journal of Financial Economics* 142. For COMEX gold, 1984–2020, the return from the previous close to 30 minutes before the close predicts the last half-hour (β = 1.09, t = 2.95, OOS R² 0.08%). The proposed cause is hedging flows before the close. |
| B1, B2 | **London fix** | Nilsson (2015), and the Abrantes-Metz and Metz (2014) and Caminschi and Heaney (2014) line of work. Prices fall ahead of the AM fix and rise after the PM fix; reportedly still true after the 2015 switch to the electronic LBMA auction. |
| C | **Turn of the month** | In Gold We Trust (2024), on GLD for 2004–2023. The days around the month's turn beat the rest of the month. Descriptive only, with no significance tests. |
| D | **Trend filter, long or cash** | "An Extensive Test of Market Timing Strategies in the Gold Market" (Quantpedia summary). Of 4,000+ strategies tested over 1990–2015, only some trend-following strategies beat buy-and-hold after Hansen's SPA data-snooping test. They did it by leaving gold after long declines. |

## Tests

### A: intraday momentum (1 test)

- **Signal:** on each Monday–Friday trading day, s = sign(ln(P(13:00) / P(13:30 on the previous trading day))), with times in New York.
- **Price:** P(T) is the last M1 close at or before T.
- **Trade:** in direction s, entering at the open of the first M1 bar at or after 13:00 New York (within 5 minutes). Exit at P(13:30).

### B1 and B2: London fix (2 tests)

- **B1:** short from 09:30 to 10:30 London time, into the AM fix.
- **B2:** long from 15:00 to 16:00 London time, after the PM fix.
- **Timing:** every trading day, entering at the open of the first M1 bar at or after the start (within 5 minutes) and exiting at the last close at or before the end.

### C: turn of the month (1 test, daily)

- **Trade:** long from the close of the second-to-last trading day of each month to the close of the second trading day of the next month. That covers days −1, +1 and +2.

### D: trend filter (1 test, daily)

- **Rule:** long when the daily close is above its 200-day simple moving average, otherwise flat. It is decided at each close and held to the next.
- **Benchmark:** buy-and-hold, as in H05.

## Data and costs

- **A and B:** run on two independent samples.
  - **histdata M1, 2009–2017:** New York-local timestamps. It has no spreads, so the cost is a flat $0.51/oz per round trip, as used for pre-2018 data in H05.
  - **Pepperstone M1, 2018 to Sep 2025:** the entry bar's spread plus $0.11.
- **C and D:** Pepperstone daily closes, June 1999 to Sep 2025, as in H05.
  - **Trading cost:** $0.51 per unit of position change.
  - **Swap:** long positions pay H05's model, Fed funds + 3.51% a year, charged per night with Wednesdays counting three.

## Pass criteria

- **A, B1, B2:** in **both** samples, the mean net $/oz per trade is > 0 with t ≥ 2. t uses Newey–West with 5 lags on the daily trade series. Needing two independent samples makes a false pass unlikely.
- **C:** the mean net return per trade is > 0 with t ≥ 2 over 1999–2025, and it is positive in both halves (split at 2012-06-30).
- **D:** net daily return > 0 with t ≥ 2 (Newey–West, 10 lags) over the full period. Its Sharpe must beat buy-and-hold's in both halves.

## Trial count

5 tests, so the running total becomes 37. Results for Oct 2025 to Sep 2026 are
reported as a diagnostic only. That period was the holdout for H11, and gold's
path over it has been seen.
