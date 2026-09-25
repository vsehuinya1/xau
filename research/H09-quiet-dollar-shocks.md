# H09: Do sharp gold moves reverse when the dollar is quiet?

**Status:** PRE-REGISTERED 2026-09-25 (commit 2b63dab) under the user's
standing goal.
**Run 2026-09-25: FAILED.**
- **Dollar quiet (the test):** fading sharp gold moves while the dollar was
  quiet gave t = −0.01 over 1,064 events. These moves reverse no more than any
  big move does.
- **Dollar confirmed (the diagnostic contrast):** fading them lost −0.16 ATR
  (t = −1.85), and −0.41 ATR since 2023. So dollar-confirmed gold moves
  *continue*, which agrees with H08's momentum lead. The events overlap with
  H08's, so this is not independent confirmation.

See `H09-results.md`.

## Question

When gold moves sharply over 5 minutes but the dollar doesn't move, does gold
partly reverse over the next 15 minutes? It needs to reverse more than gold
does after equally large moves in general, and by more than our costs.

## Why it might work

Price changes driven by information persist, while those driven by liquidity
(a large order meeting thin depth) reverse as liquidity returns. This is
Campbell, Grossman and Wang (1993), and similar effects are well documented
in equities and currencies. A sharp gold move with no matching move in the
dollar index or USDJPY carries no dollar or rates news, so it is more likely
liquidity-driven. H08 suggested that dollar-driven gold moves continue; this
tests the other half of the theory.

## Events

- **Gold shock:** at a gold M1 close, gold's 5-minute move is at least 3 ×
  gold's M5 ATR, as in H07.
- **Dollar quiet:** at the same minute's close, |z(USDX)| < 1 and
  |z(USDJPY)| < 1, using H07's z-scores.
- **Direction:** fade the gold move.
- **Cooldown:** 30 minutes between events.
- **Entry:** the first gold M1 bar opening at or after that close, within 5
  minutes. Minutes where either dollar market has no bar are skipped.

## Measurements, controls, pass criteria

The same as H07:
- **Horizons:** 5, 15 (primary) and 30 minutes.
- **Units and costs:** gold ATR units, and dollars after costs.
- **Controls:** every gold moment, matched on session × hour × gold's prior
  15-minute move bin. The shock's own size puts events in the extreme bins,
  so the controls include ordinary reversal after big moves, and the test
  measures reversal beyond that.
- **Pass criteria:** H01's five criteria at 15 minutes.

## Trial count

1 primary test, so the running total becomes 28. Diagnostic: the same gold
shocks when the dollar *did* move with gold (both dollar z-scores ≥ 1 in the
gold-consistent direction). If the theory holds, those should reverse less or
continue.

## Implementation details

The same as H07 and H08. The events' prior 15-minute move is measured in the
fade direction, as always, so the shock itself lands in an extreme bin.
