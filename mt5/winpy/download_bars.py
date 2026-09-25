"""Download all M1 bars of one symbol from the MT5 terminal, one file per year.

Timestamps stay in the broker's server time, as with the tick recorder.
Re-running rewrites every year, so it doubles as the update.
Output: <OUT>/<server>/<symbol>/M1/YYYY.npz with the raw MqlRates fields.

Run with the Windows Python in the container:
  docker exec -i xau-mt5 bash -c 'wine "$WINEPREFIX/drive_c/Program Files/Python311/python.exe" -' < mt5/winpy/download_bars.py
"""
import os

import MetaTrader5 as mt5
import numpy as np

SYMBOL = os.environ.get("REC_SYMBOL", "XAUUSD")
OUT = os.environ.get("BARS_OUT", "Z:/data/bars")

assert mt5.initialize(timeout=60000), mt5.last_error()
maxbars = mt5.terminal_info().maxbars
rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M1, 0, maxbars - 1)
if rates is None or not len(rates):
    raise SystemExit(f"copy_rates_from_pos failed: {mt5.last_error()}")
if len(rates) >= maxbars - 1:
    raise SystemExit(f"got {len(rates)} bars, the MaxBars cap; raise it to reach the oldest bars")

root = os.path.join(OUT, mt5.account_info().server, SYMBOL, "M1")
os.makedirs(root, exist_ok=True)
years = rates["time"].astype("datetime64[s]").astype("datetime64[Y]").astype(int) + 1970
for year in np.unique(years):
    part = rates[years == year]
    path = os.path.join(root, f"{year}.npz")
    with open(path + ".tmp", "wb") as f:
        np.savez_compressed(f, **{name: part[name] for name in part.dtype.names})
    os.replace(path + ".tmp", path)
    print(f"{year}: {len(part)} bars", flush=True)
mt5.shutdown()
