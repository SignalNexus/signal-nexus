import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock

from app.execution.order_executor import TAKER_FEE_RATE, base_fee_of

RESERVE_USDT = 0.0
HISTORY_DAYS = 6
# MEXC myTrades only reaches back about one month.
TRADE_HISTORY_DAYS = 28
TRADE_WINDOW_DAYS = 7

logger = logging.getLogger(__name__)
_lock = Lock()
_load_lock = Lock()
_loaded = False
_holdings: dict[str, "Holding"] = {}
_sold_exits: dict[str, int] = {}


@dataclass(frozen=True)
class Holding:
    symbol: str
    base_qty: float
    bought_at_ms: int = 0


def clear_positions() -> None:
    global _loaded
    with _lock:
        _holdings.clear()
        _sold_exits.clear()
        _loaded = False


def mark_sold_exit(strategy_id: str, exit_bar_close_ms: int) -> None:
    with _lock:
        _sold_exits[strategy_id] = exit_bar_close_ms
    from app.execution.strategy_lots import remember_sold_exit

    remember_sold_exit(strategy_id, exit_bar_close_ms)


def sold_exit(strategy_id: str) -> int | None:
    with _lock:
        return _sold_exits.get(strategy_id)


def open_holding(strategy_id: str) -> Holding | None:
    with _lock:
        return _holdings.get(strategy_id)


def remember(strategy_id: str, symbol: str, base_qty: float, bought_at_ms: int | None = None) -> None:
    if base_qty <= 0:
        raise ValueError("base quantity must be positive")
    if bought_at_ms is None:
        bought_at_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    with _lock:
        _holdings[strategy_id] = Holding(symbol, base_qty, bought_at_ms)


def reduce(strategy_id: str, sold_qty: float) -> None:
    if sold_qty <= 0:
        return
    with _lock:
        current = _holdings.get(strategy_id)
        if current is None:
            return
        left = current.base_qty - sold_qty
        if left <= max(1e-12, current.base_qty * 1e-8):
            del _holdings[strategy_id]
        else:
            _holdings[strategy_id] = Holding(current.symbol, left, current.bought_at_ms)


def invalidate() -> None:
    global _loaded
    with _lock:
        _loaded = False


def exchange_client_order_id(
    strategy_id: str, client_order_id: str, action: str, leg: str = "", venue: str = ""
) -> str:
    marks = {
        "BUY": "b",
        "SELL": "s",
        "STOP": "s",
        "SHORT": "h",
        "COVER": "c",
        "LONG": "l",
        "FLAT": "f",
    }
    if action not in marks:
        raise ValueError("unsupported action")
    code = strategy_code(strategy_id)
    mark = marks[action]
    material = f"{strategy_id}\n{client_order_id}\n{action}"
    if venue:
        material = f"{material}\n{venue}"
    if leg:
        material = f"{material}\n{leg}"
    digest = hashlib.sha256(material.encode()).hexdigest()
    return f"{code}{mark}{digest[:21]}"


def strategy_code(strategy_id: str) -> str:
    return hashlib.sha256(strategy_id.encode()).hexdigest()[:10]


def strategy_codes(strategy_ids: list[str]) -> dict[str, str]:
    codes: dict[str, str] = {}
    for strategy_id in strategy_ids:
        code = strategy_code(strategy_id)
        if code in codes:
            raise ValueError("strategy code collision")
        codes[code] = strategy_id
    return codes


def holdings_from_orders(
    orders: list[dict], codes: dict[str, str], trades: list[dict] | None = None
) -> dict[str, Holding]:
    from_trades = _orders_from_trades(trades or [], codes)
    events: list[tuple[int, str, str, float, str]] = list(from_trades.values())
    for order in orders:
        parsed = _parse_order(order, codes)
        if parsed is None or _client_id(order) in from_trades:
            continue
        timestamp, strategy_id, side, filled, symbol = parsed
        if side == "buy":
            filled *= 1 - TAKER_FEE_RATE
        events.append((timestamp, strategy_id, side, filled, symbol))
    events.sort(key=lambda item: item[0])
    holdings: dict[str, Holding] = {}
    for timestamp, strategy_id, side, filled, symbol in events:
        if side == "buy":
            current = holdings.get(strategy_id)
            if current is None or current.symbol != symbol:
                holdings[strategy_id] = Holding(symbol, filled, timestamp)
            else:
                holdings[strategy_id] = Holding(
                    symbol, current.base_qty + filled, current.bought_at_ms
                )
            continue
        current = holdings.get(strategy_id)
        if current is None:
            continue
        left = current.base_qty - filled
        if left <= max(1e-12, current.base_qty * 1e-8):
            del holdings[strategy_id]
        else:
            holdings[strategy_id] = Holding(current.symbol, left, current.bought_at_ms)
    return holdings


def cancel_resting_orders(exchange, strategies: dict) -> None:
    if not hasattr(exchange, "fetch_open_orders"):
        return
    codes = strategy_codes([strategy.strategy_id for strategy in strategies.values()])
    symbols = sorted({strategy.symbol for strategy in strategies.values()})
    for symbol in symbols:
        for order in exchange.fetch_open_orders(symbol) or []:
            client_id = _client_id(order)
            if len(client_id) != 32 or client_id[10] not in ("b", "s"):
                continue
            if codes.get(client_id[:10]) is None:
                continue
            order_id = order.get("id")
            if order_id:
                exchange.cancel_order(order_id, symbol)


def refresh_spot_from_store() -> None:
    global _loaded
    from app.execution.strategy_lots import load_spot_state

    lots, meta, sold, _synced = load_spot_state()
    holdings = {}
    for strategy_id, quantity in lots.items():
        if strategy_id not in meta:
            continue
        symbol, bought_at_ms = meta[strategy_id]
        holdings[strategy_id] = Holding(symbol, float(quantity), bought_at_ms)
    with _lock:
        _holdings.clear()
        _holdings.update(holdings)
        _sold_exits.clear()
        _sold_exits.update(sold)
        _loaded = True


def load_open_buys(exchange, strategies: dict) -> None:
    with _load_lock:
        _load_open_buys(exchange, strategies)


def _load_open_buys(exchange, strategies: dict) -> None:
    global _loaded
    with _lock:
        if _loaded:
            return
    from app.execution.strategy_lots import apply_spot_history, configured, load_spot_state, mark_synced

    if not configured():
        _rebuild_spot_from_exchange(exchange, strategies)
        return
    lots, _meta, _sold, synced = load_spot_state()
    try:
        now = datetime.now(timezone.utc)
        since = int((now - timedelta(days=HISTORY_DAYS)).timestamp() * 1000)
        symbols = sorted({strategy.symbol for strategy in strategies.values()})
        collected: list[dict] = []
        for symbol in symbols:
            collected.extend(_with_symbol(exchange.fetch_orders(symbol, since, 1000) or [], symbol))
        try:
            trades = _recent_trades(exchange, symbols, now)
        except Exception:
            trades = []
        codes = strategy_codes([strategy.strategy_id for strategy in strategies.values()])
        apply_spot_history(collected, trades, codes)
        mark_synced("mexc_spot")
    except Exception:
        if not synced and not lots:
            raise
        logger.warning("mexc spot lots were not synced")
    refresh_spot_from_store()


def _rebuild_spot_from_exchange(exchange, strategies: dict) -> None:
    global _loaded
    now = datetime.now(timezone.utc)
    since = int((now - timedelta(days=HISTORY_DAYS)).timestamp() * 1000)
    collected: list[dict] = []
    symbols = sorted({strategy.symbol for strategy in strategies.values()})
    for symbol in symbols:
        batch = exchange.fetch_orders(symbol, since, 1000) or []
        collected.extend(_with_symbol(batch, symbol))
    try:
        trades = _recent_trades(exchange, symbols, now)
    except Exception:
        trades = []
    codes = strategy_codes([strategy.strategy_id for strategy in strategies.values()])
    rebuilt = holdings_from_orders(collected, codes, trades)
    with _lock:
        _holdings.clear()
        _holdings.update(rebuilt)
        _loaded = True


def _with_symbol(rows: list[dict], symbol: str) -> list[dict]:
    out: list[dict] = []
    for row in rows:
        if row.get("symbol"):
            out.append(row)
            continue
        copied = dict(row)
        copied["symbol"] = symbol
        out.append(copied)
    return out


def _recent_trades(exchange, symbols: list[str], now: datetime) -> list[dict]:
    if not hasattr(exchange, "fetch_my_trades"):
        return []
    start = now - timedelta(days=TRADE_HISTORY_DAYS)
    trades: list[dict] = []
    for symbol in symbols:
        window_start = start
        while window_start < now:
            window_end = min(window_start + timedelta(days=TRADE_WINDOW_DAYS), now)
            batch = exchange.fetch_my_trades(
                symbol,
                int(window_start.timestamp() * 1000),
                1000,
                {"until": int(window_end.timestamp() * 1000)},
            )
            trades.extend(_with_symbol(batch or [], symbol))
            window_start = window_end
    return trades


def _orders_from_trades(
    trades: list[dict], codes: dict[str, str]
) -> dict[str, tuple[int, str, str, float, str]]:
    grouped: dict[str, tuple[int, str, str, float, str]] = {}
    for trade in trades:
        client_id = _client_id(trade)
        if len(client_id) != 32:
            continue
        strategy_id = codes.get(client_id[:10])
        mark = client_id[10]
        if strategy_id is None or mark not in ("b", "s"):
            continue
        side = "buy" if mark == "b" else "sell"
        if _trade_side(trade) not in ("", side):
            continue
        qty = _trade_qty(trade)
        symbol = trade.get("symbol")
        if qty <= 0 or not isinstance(symbol, str) or not symbol:
            continue
        if side == "buy":
            fee = base_fee_of(trade, symbol.split("/")[0])
            qty -= qty * TAKER_FEE_RATE if fee is None else fee
        timestamp = _timestamp(trade)
        current = grouped.get(client_id)
        if current is None:
            grouped[client_id] = (timestamp, strategy_id, side, qty, symbol)
        else:
            grouped[client_id] = (min(current[0], timestamp), strategy_id, side, current[3] + qty, symbol)
    return grouped


def _trade_side(trade: dict) -> str:
    side = str(trade.get("side") or "").lower()
    if side:
        return side
    info = trade.get("info")
    if isinstance(info, dict) and isinstance(info.get("isBuyer"), bool):
        return "buy" if info["isBuyer"] else "sell"
    return ""


def _trade_qty(trade: dict) -> float:
    for source in _sources(trade):
        for key in ("amount", "qty"):
            value = source.get(key)
            if value not in (None, ""):
                return float(value)
    return 0.0


def free_usdt(exchange) -> float:
    balance = exchange.fetch_balance()
    usdt = balance.get("USDT") if isinstance(balance, dict) else None
    if not isinstance(usdt, dict) or usdt.get("free") is None:
        raise RuntimeError("USDT balance unavailable")
    return float(usdt["free"])


def _parse_order(
    order: dict, codes: dict[str, str]
) -> tuple[int, str, str, float, str] | None:
    client_id = _client_id(order)
    if len(client_id) != 32:
        return None
    strategy_id = codes.get(client_id[:10])
    mark = client_id[10]
    if strategy_id is None or mark not in ("b", "s"):
        return None
    side = "buy" if mark == "b" else "sell"
    reported = str(order.get("side") or "").lower()
    if reported and reported != side:
        return None
    status = str(order.get("status") or "").lower()
    if status not in ("closed", "filled"):
        return None
    filled = _filled(order)
    if filled <= 0:
        return None
    symbol = order.get("symbol")
    if not isinstance(symbol, str) or not symbol:
        return None
    return _timestamp(order), strategy_id, side, filled, symbol


def _client_id(order: dict) -> str:
    for source in _sources(order):
        for key in ("clientOrderId", "origClientOrderId"):
            value = source.get(key)
            if isinstance(value, str) and value:
                return value
    return ""


def _filled(order: dict) -> float:
    for source in _sources(order):
        for key in ("filled", "executedQty"):
            value = source.get(key)
            if value not in (None, ""):
                return float(value)
    return 0.0


def _timestamp(order: dict) -> int:
    for source in _sources(order):
        for key in ("timestamp", "time", "updateTime"):
            value = source.get(key)
            if value not in (None, ""):
                return int(value)
    return 0


def _sources(order: dict) -> list[dict]:
    sources = [order]
    info = order.get("info")
    if isinstance(info, dict):
        sources.append(info)
    return sources
