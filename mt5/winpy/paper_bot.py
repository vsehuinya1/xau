"""Paper-trading bot for dollar-shock momentum (research/H11), demo account only.

Runs in the container's Windows Python, with the repo's xau package mounted at
/opt/xau-lib so signals come from the tested code (xau/dollar_shock.py).

Each minute, once EURUSD and USDJPY have both closed a new M1 bar, it computes
their z-scores from the last 400 bars and checks for a shock. On a shock
(30-minute cooldown) it opens gold against the dollar if no position is open.
It closes each position 30 minutes after entry.

Guards: refuses non-demo accounts; one position at a time; no new entries
after the day's realised loss reaches DAILY_LOSS, or while the STOP file
exists. Logs to Z:/data/paper/ (host: data/mt5/paper/).

Environment: PAPER_LOT (default 0.10), PAPER_DRY_RUN=1 for signals only.
"""
import csv
import datetime as dt
import os
import sys
import time

sys.path.insert(0, "Z:/opt/xau-lib")

import MetaTrader5 as mt5  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from xau.dollar_shock import COOLDOWN, gold_direction, z_scores  # noqa: E402

GOLD, EUR, JPY = "XAUUSD", "EURUSD", "USDJPY"
K = 3.0
HOLD_MINUTES = 30
WINDOW = 400
LOT = float(os.environ.get("PAPER_LOT", "0.10"))
DRY_RUN = os.environ.get("PAPER_DRY_RUN") == "1"
DAILY_LOSS = 1000.0       # $ of realised loss per server day before entries stop
MAGIC = 26092502
OUT = "Z:/data/paper"
STOP_FILE = os.path.join(OUT, "STOP")
FILLING_FOK, FILLING_IOC = 1, 2  # SYMBOL_FILLING_* bit flags


def log(msg):
    print(f"{dt.datetime.utcnow():%Y-%m-%d %H:%M:%S}Z paper_bot: {msg}", flush=True)


def append(name, row):
    path = os.path.join(OUT, name)
    new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row))
        if new:
            w.writeheader()
        w.writerow(row)


def closed_bars(sym):
    """The last WINDOW closed M1 bars. Times are server time, labelled as UTC; z-scores only
    use differences between bars, so the label doesn't matter."""
    r = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M1, 1, WINDOW)  # position 0 is the forming bar
    if r is None or len(r) < WINDOW // 2:
        return None
    df = pd.DataFrame(r)
    df.index = pd.to_datetime(df.time, unit="s", utc=True)
    return df[["open", "high", "low", "close", "spread"]]


def filling():
    mode = mt5.symbol_info(GOLD).filling_mode
    return mt5.ORDER_FILLING_IOC if mode & FILLING_IOC else mt5.ORDER_FILLING_FOK if mode & FILLING_FOK else mt5.ORDER_FILLING_RETURN


def send(side, position=None):
    tick = mt5.symbol_info_tick(GOLD)
    price = tick.ask if side > 0 else tick.bid
    req = dict(action=mt5.TRADE_ACTION_DEAL, symbol=GOLD, volume=LOT, price=price, deviation=100, magic=MAGIC,
               type=mt5.ORDER_TYPE_BUY if side > 0 else mt5.ORDER_TYPE_SELL, comment="dsm",
               type_time=mt5.ORDER_TIME_GTC, type_filling=filling())
    if position is not None:
        req["position"] = position
    t0 = time.perf_counter()
    res = mt5.order_send(req)
    ms = (time.perf_counter() - t0) * 1000
    return res, tick, price, ms


def realised_today():
    """Realised $ P&L of this bot's deals since the current server day began."""
    now = mt5.symbol_info_tick(GOLD).time
    start = now - now % 86400
    deals = mt5.history_deals_get(start, now + 60) or []
    return sum(d.profit + d.commission + d.swap + d.fee for d in deals if d.magic == MAGIC)


def my_position():
    ps = [p for p in (mt5.positions_get(symbol=GOLD) or []) if p.magic == MAGIC]
    return ps[0] if ps else None


def main():
    assert mt5.initialize(timeout=60000), mt5.last_error()
    acc = mt5.account_info()
    if acc.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
        raise SystemExit(f"refusing: account {acc.login} on {acc.server} is not a demo account")
    for s in (GOLD, EUR, JPY):
        mt5.symbol_select(s, True)
    os.makedirs(OUT, exist_ok=True)
    log(f"started on {acc.server} #{acc.login}, lot {LOT}, dry run {DRY_RUN}, k {K}, hold {HOLD_MINUTES} min")
    last_bar, last_shock = None, None
    while True:
        # exit: close our position once it has been open HOLD_MINUTES (server clock)
        pos = my_position()
        if pos is not None:
            now = mt5.symbol_info_tick(GOLD).time
            if now >= pos.time + HOLD_MINUTES * 60:
                side = -1 if pos.type == mt5.POSITION_TYPE_BUY else 1
                res, tick, quote, ms = send(side, pos.ticket)
                append("trades.csv", {"utc": f"{dt.datetime.utcnow():%Y-%m-%d %H:%M:%S}", "event": "exit",
                                      "ticket": pos.ticket, "side": -side, "quote": quote, "bid": tick.bid, "ask": tick.ask,
                                      "fill": getattr(res, "price", None), "retcode": getattr(res, "retcode", None),
                                      "latency_ms": round(ms), "z_eur": "", "z_jpy": "", "position_profit": pos.profit})
                log(f"exit ticket {pos.ticket}: retcode {getattr(res, 'retcode', None)} fill {getattr(res, 'price', None)}")

        # signal: evaluate once per newly closed minute of both FX pairs
        eur, jpy = closed_bars(EUR), closed_bars(JPY)
        if eur is None or jpy is None or eur.index[-1] != jpy.index[-1] or eur.index[-1] == last_bar:
            time.sleep(1)
            continue
        last_bar = eur.index[-1]
        z_eur, z_jpy = z_scores(eur).iloc[-1], z_scores(jpy).iloc[-1]
        if last_bar.minute == 0:  # hourly heartbeat
            log(f"alive: bar {last_bar:%H:%M} server, z EURUSD {z_eur:+.2f}, USDJPY {z_jpy:+.2f}, "
                f"position {'open' if my_position() is not None else 'none'}")
        side = int(gold_direction(z_eur, z_jpy, K)) if np.isfinite(z_eur) and np.isfinite(z_jpy) else 0
        bar_close = last_bar + pd.Timedelta(minutes=1)
        if side == 0 or (last_shock is not None and bar_close < last_shock + pd.Timedelta(minutes=COOLDOWN)):
            continue
        last_shock = bar_close
        reason = ("dry run" if DRY_RUN else "position open" if my_position() is not None
                  else "STOP file" if os.path.exists(STOP_FILE)
                  else "daily loss limit" if realised_today() <= -DAILY_LOSS else "")
        row = {"utc": f"{dt.datetime.utcnow():%Y-%m-%d %H:%M:%S}", "server_bar_close": f"{bar_close:%Y-%m-%d %H:%M}",
               "z_eur": round(z_eur, 3), "z_jpy": round(z_jpy, 3), "side": side, "skipped": reason}
        append("signals.csv", row)
        log(f"shock at {bar_close:%H:%M} server: z EURUSD {z_eur:+.2f}, USDJPY {z_jpy:+.2f} -> "
            f"{'buy' if side > 0 else 'sell'} gold{' (skipped: ' + reason + ')' if reason else ''}")
        if reason:
            continue
        res, tick, quote, ms = send(side)
        append("trades.csv", {"utc": row["utc"], "event": "entry", "ticket": getattr(res, "order", None), "side": side,
                              "quote": quote, "bid": tick.bid, "ask": tick.ask, "fill": getattr(res, "price", None),
                              "retcode": getattr(res, "retcode", None), "latency_ms": round(ms),
                              "z_eur": row["z_eur"], "z_jpy": row["z_jpy"], "position_profit": ""})
        log(f"entry: retcode {getattr(res, 'retcode', None)} fill {getattr(res, 'price', None)} "
            f"(quote {quote}, spread {tick.ask - tick.bid:.2f}, {ms:.0f} ms)")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        log(f"stopped: {e!r}")
        sys.exit(1)
