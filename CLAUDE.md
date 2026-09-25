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

## Current strategy: dollar-shock momentum (research/H07–H11)

**The rule:** when EURUSD and USDJPY both move at least 3 × their M5 ATR in 5
minutes in the same dollar direction, trade gold against the dollar at the
next M1 open and exit 30 minutes later. The code is in `xau/dollar_shock.py`.

**Evidence:**
- **Found** in 2018–2025 (H07–H09).
- **Confirmed** on 2009–2017 histdata never seen before: t = 6.5 (H10).
- **In-sample profit:** +$0.38/oz per trade under harsh news-time costs.
- **Holdout passed:** +$3.96/oz per trade over 116 trades from Oct 2025 to
  Sep 2026, t = 1.96 (H11).

**Risks:**
- **Fills at US releases:** the M1 bar spread field understates news-time
  spreads.
- **Lumpy returns:** 5 of 12 holdout months lost.
- **Changing strength:** the effect varied over time.

**Status:** next is paper trading on the demo account with real fills.

The holdout has now been used for this strategy. Further research can't treat
Oct 2025 to Sep 2026 as unseen.

## Data gotchas

- One-minute data from histdata.com is timestamped in **New York local time, including daylight saving**, whatever its "EST, no DST" label says.
  - **Evidence:** checked on 2012–2017 US jobs reports for XAUUSD, EURUSD and USDJPY.
  - **Old research:** its "EST" fix was an hour wrong every summer.
  - **Loader:** `xau.histdata.load_histdata` converts correctly.
- Treat any out-of-sample profit factor above about 3 as a bug or too few trades until you've checked it.
- MT5 timestamps (tick `time`/`time_msc` and bar `time`) are in the broker's server time, not UTC, even though they look like Unix times. Always convert them with `xau.servertime.server_to_utc`, never by hand.
  - **The rule:** Pepperstone's server runs at New York time + 7 hours.
  - **The exception:** in winter 2017/18 the server stayed on UTC+3. The converter has that exception built in. Because Pepperstone's close is set in server time, the daily break that winter ran 16:00–18:00 New York, so there are no bars at 16:00–16:59 New York.
  - **The evidence:** checked against the live clock, the 18:00 New York daily reopens (99.7% of 2,390 since 2017), and the 08:30 NFP spikes.
  - **The trap:** Pepperstone's closes are set in server time, so they look right whatever the clock does. Only market-driven times (reopens, news spikes) can reveal an offset error.
- On Pepperstone-Demo, tick history goes back only about 4 weeks: when checked on 2026-09-25, the earliest tick was 2026-08-28.
- Pepperstone's one-minute bars are real one-minute data only from mid-2017, with full coverage from 2018. Before that, the M1 series holds hourly bars (2016) and daily bars (1998–2015). Reaching the oldest bars needs MaxBars of at least 3.3 million; the entrypoint sets 5 million through the startup config, although `common.ini` keeps showing 100,000. Each bar carries a `spread` in points: the median was 7 in 2018 and 13 in 2026, matching the recorded ticks.
- XAUUSD at Pepperstone: 100 oz per lot, 0.01 lot minimum, and a $0.01 move is worth $1 per lot.
- Costs on the Razor demo, from a 0.01-lot round trip on 2026-09-25 (`mt5/winpy/cost_probe.py`):
  - **Commission:** $0.04 per side on 0.01 lot. MT5 rounds to the cent, so the per-lot rate is somewhere from $3.50 to $4.49 per side; confirm it with a larger demo trade.
  - **Spread:** $0.11 at the time.
  - **Total:** a round trip costs about $0.18–0.20 per ounce.
  - **Execution:** orders fill as IOC and take 150–200 ms from this VPS.
- Overnight swap on the Pepperstone demo, read on 2026-09-25 with `symbol_info("XAUUSD")`:
  - **Long:** −86.64 points per lot per night, which is −$0.87/oz and about 7% a year at $4,280.
  - **Short:** +31.65 points (+$0.32/oz).
  - **When:** charged at the 17:00 New York rollover, triple on Wednesdays.
  - **Caveat:** swaps follow interest rates and may differ on a live account, so re-read them before relying on them.
- MT5's Algo Trading switch must be on for `order_send`. It's on for the demo terminal.

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
- The tick recorder (`mt5/winpy/recorder.py`) runs inside the container whenever `MT5_LOGIN` is set. It archives each completed server-time hour of XAUUSD ticks to `data/mt5/ticks/<server>/<symbol>/YYYY/MM/DD/HH.npz`, as raw MT5 fields in server time. The container can write only to `data/mt5/`, which is owned by uid 1001.
  - An empty file means the market was closed. A missing file means that hour hasn't been archived.
  - Gaps shorter than the server's roughly 4-week retention refill themselves.
  - `offset_log.csv` records the observed server-clock offset every hour.
  - `mt5/winpy/verify.py` re-fetches the archived hours and compares them.
- `mt5/winpy/download_bars.py` saves all M1 bars to `data/mt5/bars/<server>/<symbol>/M1/YYYY.npz`. Re-run it to update them.
- On the Linux side, load ticks with `xau.ticks.load_ticks(start_utc, end_utc)`. It converts server time to UTC and raises an error if any hour in the range hasn't been archived. Load bars with `xau.bars.load_m1(start_utc, end_utc)`. Set up the environment with `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`.
- `mt5.initialize()` works only once the terminal is logged in to an account. Before that, it returns an IPC timeout (-10005). To run a script with the Windows Python: `docker exec -i xau-mt5 bash -c 'wine "$WINEPREFIX/drive_c/Program Files/Python311/python.exe" -' < script.py`.

## Decisions (2026-09-25)

- **Broker:** MetaTrader 5, through the `MetaTrader5` Python package. Live trading needs a Windows machine or VPS. Research can run on Linux.
- **Strategy:** research a new edge using a sound process, then build the bot around whatever holds up.
- **Timeframe:** execution on M1/M5, with signals from any timeframe. Overnight holding is allowed; the user changed this on 2026-09-25, replacing "flat by the end of the day". Overnight trades must include swap in their costs.
- **Launch:** a paper/demo account first, with full logging. Real money only after a set evaluation period.
- **Broker account:** Pepperstone. The demo is a Razor account on `Pepperstone-Demo` (Pepperstone Group Limited), in USD. Model costs as raw spread plus a commission per lot; the commission is still to be measured.
- **Holdout:** market data from 2025-10-01 UTC onward is locked until a strategy is final, and is then tested once. `xau/holdout.py` defines it, and the loaders enforce it (`allow_holdout=True` opts in). Allowed uses are the final test, data-quality checks, and spreads for the cost model. Nothing that looks at returns or signals. The recorded ticks are a second, forward holdout.
- **Price history:** Pepperstone ticks recorded by us from 2026-08-28 onward, plus Pepperstone's own M1 bars from 2018. Dukascopy ticks will provide bid/ask history as a cross-check, but Dukascopy answered 429/503 to this VPS on 2026-09-25, so download slowly and back off.
