# CLAUDE.md

## Project

A trading bot for gold (XAUUSD). The repo was cleared on 2026-09-25 to start fresh. The earlier research code is still in git history: the backtests end at commit `4351760` and the Market Diagnostics Framework ends at `dea649e`.

## Earlier research: unverified

**The earlier research processes were flawed. Treat none of their conclusions as established.** A "failed" idea below might work when tested properly, and a "passed" one might not. Use these only as leads for what to test again:
- Trading in the direction of the move after US data releases (CPI, jobs reports, Fed decisions). The results didn't beat trades placed at random times, and the profits came from a handful of trades.
- Session and time-of-day effects: session breakouts, opening-range breakouts, and fading failed breakouts.
- Breakouts after a quiet, low-volatility stretch. This passed the first test but failed walk-forward testing.
- Dollar pairs (EURUSD, GBPUSD, USDJPY) moving before gold.
- London-session breakout. None of the 200 parameter sets passed.
- "Smart Money Concepts" signals (market structure breaks, fair value gaps, order blocks). None showed a proven edge.
- Market Diagnostics Framework (D01–D11, an 8-year run). Its findings weren't carried over.

## Data gotchas

- One-minute data from histdata.com is timestamped in **EST with no daylight-saving shift**, not UTC. Convert before any session or event logic. This bug once invalidated results.
- Treat any out-of-sample profit factor above about 3 as a bug or too few trades until you've checked it.
- MT5 timestamps (tick `time`/`time_msc` and bar `time`) are in the broker's server time, not UTC, even though they look like Unix times. Pepperstone-Demo was exactly UTC+3 on 2026-09-25. It is probably UTC+2 in northern winter; verify that after the DST change.
- On Pepperstone-Demo, tick history goes back only about 4 weeks: when checked on 2026-09-25, the earliest tick was 2026-08-28. One-minute bars are capped by the terminal's MaxBars setting (100,000 bars, about 3 months). Daily bars go back to 2012.
- XAUUSD at Pepperstone: 100 oz per lot, 0.01 lot minimum, and a $0.01 move is worth $1 per lot.

## Conventions

- Before running a backtest, write down the kill criteria it has to pass.
- Always include realistic costs: spread plus slippage. Also check the results at double the spread.
- Test on out-of-sample and walk-forward windows. Check that profits aren't concentrated in a few trades, one year, or one type of setup.
- Scratch outputs and downloaded data stay out of git.

## MT5 container (`mt5/`)

- Start it with `cd mt5 && docker compose up -d --build`. The first start installs WebView2, MT5 and Windows Python 3.11 with the `MetaTrader5` package into the `xau-mt5_wine` volume. That takes about 8 minutes. MT5 then updates itself inside the volume.
- The screen is served over VNC on 127.0.0.1:5900 only, and the password is in `mt5/.env`, which git ignores. Claude drives the screen from the VPS with a VNC client (vncdotool). Don't route setup steps through the user's own machines.
- To log in automatically, set `MT5_LOGIN`, `MT5_PASSWORD` and `MT5_SERVER` in `mt5/.env`. The entrypoint passes them to MT5 through a startup config file (`/config:`). MT5 can only log in to servers it knows about; adding a new broker's servers takes a one-time "Find your company" search in the account wizard.
- Pepperstone's Kenyan entity has one MT5 server, `PepperstoneKE-MT5-Live01`, and it has no demo accounts. Demos are on other Pepperstone servers, whose feeds may differ from the live Kenyan one.
- Two versions are pinned deliberately:
  - **Wine 10.0 stable.** Under Wine 11, the Python IPC times out.
  - **numpy 1.26.4.** numpy 2.x calls `ucrtbase.crealf`, which Wine 10 doesn't have.
- `mt5.initialize()` works only once the terminal is logged in to an account. Before that, it returns an IPC timeout (-10005). To run a script with the Windows Python: `docker exec -i xau-mt5 bash -c 'wine "$WINEPREFIX/drive_c/Program Files/Python311/python.exe" -' < script.py`.

## Decisions (2026-09-25)

- **Broker:** MetaTrader 5, through the `MetaTrader5` Python package. Live trading needs a Windows machine or VPS. Research can run on Linux.
- **Strategy:** research a new edge using a sound process, then build the bot around whatever holds up.
- **Timeframe:** intraday (M1–M15), flat by the end of the day.
- **Launch:** a paper/demo account first, with full logging. Real money only after a set evaluation period.
