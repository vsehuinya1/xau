# CLAUDE.md

## Project

A trading bot for gold (XAUUSD). The repo was cleared on 2026-09-25 to start fresh. The earlier research code is still in git history: see commit `4351760` and the commits before it.

## Lessons from the earlier research (2018–2025 one-minute data)

These hypotheses were tested and **failed** after trading costs. Don't rebuild them without a new angle:
- Trading in the direction of the move after US data releases (CPI, jobs reports, Fed decisions). The results didn't beat trades placed at random times, and the profits came from a handful of trades.
- Session and time-of-day effects: session breakouts, opening-range breakouts, and fading failed breakouts.
- Breakouts after a quiet, low-volatility stretch. This passed the first test but failed walk-forward testing.
- Dollar pairs (EURUSD, GBPUSD, USDJPY) moving before gold.
- London-session breakout. None of the 200 parameter sets passed.
- "Smart Money Concepts" signals (market structure breaks, fair value gaps, order blocks). None showed a proven edge.

## Data gotchas

- One-minute data from histdata.com is timestamped in **EST with no daylight-saving shift**, not UTC. Convert before any session or event logic. This bug once invalidated results.
- Treat any out-of-sample profit factor above about 3 as a bug or too few trades until you've checked it.

## Conventions

- Before running a backtest, write down the kill criteria it has to pass.
- Always include realistic costs: spread plus slippage. Also check the results at double the spread.
- Test on out-of-sample and walk-forward windows. Check that profits aren't concentrated in a few trades, one year, or one type of setup.
- Scratch outputs and downloaded data stay out of git.

## Execution

Planned live bridge: MetaTrader 5 through the `MetaTrader5` Python package. It needs a Windows VPS.
