"""Measure round-trip trading costs: buy the minimum lot at market, close it at
once, and report commission, slippage and latency from the deal history.

Refuses to run on anything but a demo account.

Run with the Windows Python in the container:
  docker exec -i xau-mt5 bash -c 'wine "$WINEPREFIX/drive_c/Program Files/Python311/python.exe" -' < mt5/winpy/cost_probe.py
"""
import time

import MetaTrader5 as mt5

SYMBOL = "XAUUSD"
MAGIC = 26092501  # tags this script's orders
# SYMBOL_FILLING_* bit flags from MQL5; the Python package doesn't export them.
FILLING_FOK, FILLING_IOC = 1, 2

assert mt5.initialize(timeout=60000), mt5.last_error()
account = mt5.account_info()
if account.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
    raise SystemExit(f"refusing: account {account.login} on {account.server} is not a demo account")
if not mt5.terminal_info().trade_allowed:
    raise SystemExit("Algo Trading is switched off in the terminal")

info = mt5.symbol_info(SYMBOL)
lot = info.volume_min
if info.filling_mode & FILLING_IOC:
    filling = mt5.ORDER_FILLING_IOC
elif info.filling_mode & FILLING_FOK:
    filling = mt5.ORDER_FILLING_FOK
else:
    filling = mt5.ORDER_FILLING_RETURN


def send(side, position=None):
    tick = mt5.symbol_info_tick(SYMBOL)
    quote = tick.ask if side == mt5.ORDER_TYPE_BUY else tick.bid
    request = dict(action=mt5.TRADE_ACTION_DEAL, symbol=SYMBOL, volume=lot, type=side, price=quote,
                   deviation=50, magic=MAGIC, comment="cost probe", type_time=mt5.ORDER_TIME_GTC,
                   type_filling=filling)
    if position is not None:
        request["position"] = position
    t0 = time.perf_counter()
    result = mt5.order_send(request)
    ms = (time.perf_counter() - t0) * 1000
    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        raise SystemExit(f"order_send failed: {result} {mt5.last_error()}")
    return result, tick, quote, ms


opened, open_tick, open_quote, open_ms = send(mt5.ORDER_TYPE_BUY)
position = next(p.ticket for p in mt5.positions_get(symbol=SYMBOL) if p.magic == MAGIC)
closed, close_tick, close_quote, close_ms = send(mt5.ORDER_TYPE_SELL, position)
time.sleep(1)
deals = mt5.history_deals_get(position=position)

commission = sum(d.commission for d in deals)
fees = sum(d.fee for d in deals)
profit = sum(d.profit for d in deals)
per_lot = 1 / lot
print(f"account {account.login} ({account.server}, demo); {lot} lot {SYMBOL}; filling {filling}")
print(f"open : quote ask {open_quote:.2f} (spread {open_tick.ask - open_tick.bid:.2f}) -> filled {opened.price:.2f}, "
      f"slippage {opened.price - open_quote:+.2f}, {open_ms:.0f} ms")
print(f"close: quote bid {close_quote:.2f} (spread {close_tick.ask - close_tick.bid:.2f}) -> filled {closed.price:.2f}, "
      f"slippage {close_quote - closed.price:+.2f}, {close_ms:.0f} ms")
print(f"deals: {[(d.entry, d.price, d.commission, d.fee, d.profit) for d in deals]}")
print(f"round trip: price P&L ${profit:.2f}, commission ${commission:.2f}, fees ${fees:.2f} "
      f"-> per 1.0 lot: commission ${commission * per_lot:.2f}, price cost ${-profit * per_lot:.2f}")
mt5.shutdown()
