# XAUUSD Systematic Strategy Research

Falsification-first backtest suite for gold edge hypotheses.

## Hypotheses (ranked)

1. **US Macro Shock Momentum** — post-release continuation (Test 1)
2. Session / time-of-day behavior (Test 2)
3. Volatility regime breakout (Test 3)
4. Real yield / USD lead-lag (Test 4)
5. Positioning / crowding reversal (Test 5)

## Quick start (VPS)

```bash
bash deploy/vps_setup_and_run.sh
tail -f /root/xau/results/test1_run.log
```

## Local

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 data/download_xauusd.py --start 2018 --end 2025
python3 backtests/test1_macro_momentum.py
```

## Test 1 falsification criteria

Kill if any of:
- Net expectancy ≤ 0 after 2× spread on all hold periods
- Profits from < 2 event types
- Random-time control matches/beats event trades
- 2022–2025 negative while 2018–2021 positive
- Removing top 5 trades flips PnL negative

## Test 2 (session / time-of-day)

```bash
bash deploy/vps_run_test2.sh
python3 backtests/test2_session_timing.py
```

Strategies: session breakout, opening-range breakout, failed-breakout fade.
Sessions: Asia/London/NY opens, London fix, US data window, NY close.

## Data

- XAUUSD M1 from [histdata.com](https://www.histdata.com/) (GMT timestamps)
- Event calendar: BLS CPI dates, first-Friday NFP, Fed FOMC decision days
