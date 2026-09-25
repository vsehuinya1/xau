# H07: Do the dollar, EURUSD, USDJPY or silver move before gold?

**Status:** PRE-REGISTERED 2026-09-25 (commit 47d6e22) under the user's
standing goal.
**Run 2026-09-25: FAILED, but with the first genuine effect so far.**
- **USDJPY:** passed C1 (t = 3.11) and C3 (positive in every sub-period).
  Gold follows sharp USDJPY moves by +0.046 ATR over 15 minutes.
- **USDX and EURUSD:** point the same way, at t = 2.32 and 1.84.
- **Silver:** t = 0.60.
- **Why it fails:** the effect is too small to pay costs. In 2024–25 it was
  about $0.10–0.15/oz against a $0.24 round trip (C2), it sits mostly in Asia
  hours (C4), and it fails C5.
- **Conclusion:** the dollar leads gold by minutes, measurably but not
  profitably on its own. See `H07-results.md`.

## Question

When a closely linked market makes a sharp 5-minute move, does gold follow
over the next 15 minutes by more than random moments do, and by more than our
costs?

## Why it might work

Gold is priced in dollars and tied to US rates. Currency markets are deeper
and may price news and flows first. If gold lags them, even by minutes, a
sharp move in the leader predicts gold catching up.

## Leaders and the direction they should push gold

These signs were fixed from economics before looking at any data.

| Leader | Symbol | Sign | Reason |
|---|---|---|---|
| Dollar index | USDX | −1 | a stronger dollar means cheaper gold |
| EURUSD | EURUSD | +1 | a stronger euro means a weaker dollar |
| USDJPY | USDJPY | −1 | a stronger dollar and higher US yields |
| Silver | XAGUSD | +1 | the closest related metal |

US500 (from 2021 only) and the 10-year note future (from 2024 only) lack
2018–2025 history and are excluded.

## Events

- **Trigger:** at an M1 close, the leader's 5-minute move is at least 2 × the
  leader's ATR. The move is its close minus its last close at or before 5
  minutes earlier. ATR is the mean of 14 M5 true ranges, from M5 bars closed
  at or before that M1 bar opened.
- **Gold direction:** the sign of the leader's move × the leader's sign in the
  table.
- **Cooldown:** a leader can't trigger again within 30 minutes of its last
  event.
- **Entry (reference):** the first gold M1 bar opening at or after the
  leader bar's close. The event is dropped if that bar opens more than 5
  minutes later.

## Measurements

- **Forward move:** gold's move from the reference open, signed, at 5, 15
  (primary) and 30 minutes. It is reported in gold ATR units (gold's M5 ATR
  as of the reference open) and in dollars after costs.
- **Excursions:** within 30 minutes.

## Controls

Every gold M1 moment, in both directions, matched on session × New York hour
× gold's own prior 15-minute move bin, as in H02. If gold already moved with
the leader, the prior-move bin accounts for it.

## Pass criteria

H01's five criteria, at 15 minutes, for each leader:

1. **Beats the control:** t ≥ 3, clustered by trading day.
2. **Pays its costs now:** positive after costs in 2024 to Sep 2025.
3. **Consistent over time:** positive excess in 2018–20, 2021–22 and 2023 to
   Sep 2025.
4. **Not one session:** t ≥ 2 without the best session.
5. **Not a few outliers:** criterion 2 holds without the top 1% of events.

## Trial count

4 primary tests, so the running total becomes 25. These are diagnostics only:
- the 5- and 30-minute horizons;
- per-session splits;
- a split by whether gold had already moved at least 1 ATR in the implied
  direction.

## Implementation details

1. **Same clock:** all symbols come from the same Pepperstone server, so the
   server-time-to-UTC conversion is the same, including the winter 2017/18
   exception.
2. **Everything else:** forward prices, prior move, bins, clustering by
   trading day, sub-periods, criterion 5 and cost follow H01's details 7–14.
