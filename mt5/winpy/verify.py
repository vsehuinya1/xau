"""Re-fetch archived tick hours still on the server and compare with the files.

Catches hours the recorder saved while MT5 was still syncing history. Only
reports; it doesn't rewrite anything. Hours the server has already dropped
(before its oldest tick) are skipped.

Run with the Windows Python in the container:
  docker exec -i xau-mt5 bash -c 'wine "$WINEPREFIX/drive_c/Program Files/Python311/python.exe" -' < mt5/winpy/verify.py
"""
import datetime as dt
import glob
import os

import MetaTrader5 as mt5
import numpy as np

SYMBOL = os.environ.get("REC_SYMBOL", "XAUUSD")
OUT = os.environ.get("REC_OUT", "Z:/data/ticks")
HOUR = dt.timedelta(hours=1)
EPOCH = dt.datetime(1970, 1, 1)

assert mt5.initialize(timeout=60000), mt5.last_error()
root = os.path.join(OUT, mt5.account_info().server, SYMBOL)
oldest = mt5.copy_ticks_from(SYMBOL, int((dt.datetime(2000, 1, 1) - EPOCH).total_seconds()), 1, mt5.COPY_TICKS_ALL)
oldest_ms = int(oldest[0]["time_msc"])

checked = bad = 0
for path in sorted(glob.glob(os.path.join(root, "*", "*", "*", "*.npz"))):
    y, m, d, h = os.path.relpath(path, root).replace("\\", "/")[:-4].split("/")
    lo = int((dt.datetime(int(y), int(m), int(d), int(h)) - EPOCH).total_seconds())
    if lo * 1000 < oldest_ms:
        continue
    ticks = mt5.copy_ticks_range(SYMBOL, lo, lo + 3600, mt5.COPY_TICKS_ALL)
    ticks = ticks[(ticks["time_msc"] >= lo * 1000) & (ticks["time_msc"] < (lo + 3600) * 1000)]
    with np.load(path) as z:
        same = len(z["time_msc"]) == len(ticks) and np.array_equal(z["time_msc"], ticks["time_msc"]) \
            and np.array_equal(z["bid"], ticks["bid"]) and np.array_equal(z["ask"], ticks["ask"])
        if not same:
            bad += 1
            print(f"MISMATCH {y}-{m}-{d} {h}:00 file={len(z['time_msc'])} server={len(ticks)}", flush=True)
    checked += 1
print(f"checked {checked} hours, {bad} mismatches")
mt5.shutdown()
