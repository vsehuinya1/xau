"""Archive every tick of one symbol from the MT5 terminal into hourly files.

Runs in the Windows Python inside the MT5 container. It never streams: once a
server-time hour has ended (plus SETTLE_S), it fetches that hour with
copy_ticks_range and writes one file. The broker keeps about 4 weeks of ticks,
so after downtime the next run refills the gap; on the first run it backfills
from the oldest tick the server has.

Timestamps are left exactly as MT5 returns them, in the broker's server time.
Convert to UTC when loading (see CLAUDE.md). offset_log.csv records the
observed server-clock offset every hour as evidence for that conversion.

Output: <OUT>/<server>/<symbol>/YYYY/MM/DD/HH.npz (hour in server time), with
the raw tick fields as arrays. An hour with no ticks gets a file with empty
arrays, so "market closed" differs from "not archived yet".
"""
import calendar
import datetime as dt
import glob
import os
import sys
import time

import MetaTrader5 as mt5
import numpy as np

SYMBOL = os.environ.get("REC_SYMBOL", "XAUUSD")
OUT = os.environ.get("REC_OUT", "Z:/data/ticks")
SETTLE_S = 120
POLL_S = 30
HOUR = dt.timedelta(hours=1)


def log(msg):
    print(f"{dt.datetime.utcnow():%Y-%m-%d %H:%M:%S}Z recorder: {msg}", flush=True)


def epoch(server_dt):
    """Server-time datetime -> the 'epoch' MT5 uses for server time."""
    return calendar.timegm(server_dt.timetuple())


def from_epoch(seconds):
    return dt.datetime(1970, 1, 1) + dt.timedelta(seconds=int(seconds))


def connect():
    while not mt5.initialize(timeout=60000):
        log(f"initialize failed {mt5.last_error()}; retrying in 60s")
        time.sleep(60)
    if not mt5.symbol_select(SYMBOL, True):
        raise SystemExit(f"cannot select {SYMBOL}: {mt5.last_error()}")
    return mt5.account_info().server


def fetch_hour(start):
    """All ticks with start <= time < start + 1h, fetched until the count is stable."""
    lo, hi = epoch(start), epoch(start + HOUR)
    prev = None
    for _ in range(5):
        ticks = mt5.copy_ticks_range(SYMBOL, lo, hi, mt5.COPY_TICKS_ALL)
        if ticks is None:
            raise RuntimeError(f"copy_ticks_range failed for {start}: {mt5.last_error()}")
        ticks = ticks[(ticks["time_msc"] >= lo * 1000) & (ticks["time_msc"] < hi * 1000)]
        if prev is not None and len(ticks) == len(prev):
            return ticks
        prev = ticks
        time.sleep(2)
    raise RuntimeError(f"tick count for {start} never settled")


def write_hour(root, start, ticks):
    path = os.path.join(root, f"{start:%Y}", f"{start:%m}", f"{start:%d}", f"{start:%H}.npz")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        np.savez_compressed(f, **{name: ticks[name] for name in ticks.dtype.names})
    os.replace(tmp, path)


def last_archived(root):
    files = sorted(glob.glob(os.path.join(root, "*", "*", "*", "*.npz")))
    if not files:
        return None
    y, m, d, h = os.path.relpath(files[-1], root).replace("\\", "/")[:-4].split("/")
    return dt.datetime(int(y), int(m), int(d), int(h))


def log_offset(root, tick, now):
    """Call only with a tick known to be under a minute old at `now`."""
    offset_h = (tick.time_msc / 1000 - now) / 3600
    path = os.path.join(root, "offset_log.csv")
    new = not os.path.exists(path)
    with open(path, "a") as f:
        if new:
            f.write("utc,server_last_tick,offset_hours\n")
        f.write(f"{dt.datetime.utcnow():%Y-%m-%dT%H:%M:%S},{from_epoch(tick.time):%Y-%m-%dT%H:%M:%S},"
                f"{round(offset_h * 4) / 4:+.2f}\n")


def main():
    server = connect()
    root = os.path.join(OUT, server, SYMBOL)
    os.makedirs(root, exist_ok=True)

    last = last_archived(root)
    oldest = mt5.copy_ticks_from(SYMBOL, epoch(dt.datetime(2000, 1, 1)), 1, mt5.COPY_TICKS_ALL)
    if oldest is None or not len(oldest):
        raise SystemExit(f"no tick history for {SYMBOL}: {mt5.last_error()}")
    oldest_hour = from_epoch(oldest[0]["time"]).replace(minute=0, second=0)
    nxt = oldest_hour if last is None else last + HOUR
    if nxt < oldest_hour:
        log(f"gap: {nxt} to {oldest_hour} is no longer on the server")
        nxt = oldest_hour
    log(f"{server} {SYMBOL}: archiving from {nxt} (server time) into {root}")

    logged_hour = prev_msc = prev_poll = None
    while True:
        tick = mt5.symbol_info_tick(SYMBOL)
        now = time.time()
        if tick is None:
            raise RuntimeError(f"symbol_info_tick failed: {mt5.last_error()}")
        server_now = from_epoch(tick.time)

        # A tick that changed since a poll under a minute ago is under a minute old.
        this_hour = server_now.replace(minute=0, second=0)
        fresh = prev_msc is not None and tick.time_msc != prev_msc and now - prev_poll < 2 * POLL_S
        if fresh and logged_hour != this_hour:
            log_offset(root, tick, now)
            logged_hour = this_hour
        prev_msc, prev_poll = tick.time_msc, now

        while nxt + HOUR + dt.timedelta(seconds=SETTLE_S) <= server_now:
            ticks = fetch_hour(nxt)
            write_hour(root, nxt, ticks)
            log(f"{nxt:%Y-%m-%d %H}:00 {len(ticks)} ticks")
            nxt += HOUR
        time.sleep(POLL_S)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"stopped: {e!r}")
        sys.exit(1)
