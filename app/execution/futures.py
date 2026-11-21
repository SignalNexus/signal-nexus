import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_FLOOR
from threading import Lock

logger = logging.getLogger(__name__)

from app.execution.exchange import futures_client
from app.execution.live import LiveResult
from app.execution.positions import (
    HISTORY_DAYS,
    _client_id,
    _filled,
    _timestamp,
    framed_client_order_id,
    free_usdt,
    strategy_codes,
    strategy_of,
)
from app.execution.router import Strategy, load_strategies
from app.notifications.analytics import report_order_link

CONTRACT_SIZE = {
    "ETH/USDT:USDT": 0.01,
    "SOL/USDT:USDT": 0.1,
    "HYPE/USDT:USDT": 0.1,
    "BNB/USDT:USDT": 0.01,
}

_lock = Lock()
_working: set[str] = set()
_lots: dict[str, float] = {}
_loaded = False


def clear_futures_state() -> None:
    global _loaded
    with _lock:
        _lots.clear()
        _working.clear()
        _loaded = False


def swap_symbol(symbol: str) -> str:
    base = symbol.split("/")[0]
    return f"{base}/USDT:USDT"


# 先物の履歴は 1 回 100 件までで、状態を付けないと照会自体が失敗する。
HISTORY_PAGE_SIZE = 100
_HISTORY_PAGES = 20
_HISTORY_STATES = "2,3,4"


def fetch_futures_history(exchange, symbol: str, since: int) -> list[dict]:
    direct = getattr(exchange, "contractPrivateGetOrderListHistoryOrders", None)
    if direct is None:
        return list(exchange.fetch_orders(symbol, since, HISTORY_PAGE_SIZE) or [])
    end = int(datetime.now(timezone.utc).timestamp() * 1000)
    contract = f"{symbol.split('/')[0]}_USDT"
    collected: list[dict] = []
    seen: set[str] = set()
    for page in range(1, _HISTORY_PAGES + 1):
        payload = direct(
            {
                "symbol": contract,
                "states": _HISTORY_STATES,
                "start_time": since,
                "end_time": end,
                "page_num": page,
                "page_size": HISTORY_PAGE_SIZE,
            }
        )
        rows = _history_rows(payload)
        added = 0
        for row in rows:
            order_id = str(row.get("orderId") or "")
            if order_id and order_id in seen:
                continue
            if order_id:
                seen.add(order_id)
            collected.append(_unified_history_order(row, symbol))
            added += 1
        if added == 0 or len(rows) < HISTORY_PAGE_SIZE:
            break
    return collected


def _history_rows(payload) -> list[dict]:
    if not isinstance(payload, dict) or payload.get("success") is False:
        raise RuntimeError("mexc futures history was rejected")
    code = payload.get("code")
    if code not in (None, 0, "0"):
        raise RuntimeError("mexc futures history was rejected")
    data = payload.get("data")
    if data is None:
        return []
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict) and isinstance(data.get("resultList"), list):
        return [row for row in data["resultList"] if isinstance(row, dict)]
    raise RuntimeError("mexc futures history was rejected")


def _unified_history_order(row: dict, symbol: str) -> dict:
    filled = row.get("dealVol")
    try:
        has_fill = float(filled or 0) > 0
    except (TypeError, ValueError):
        has_fill = False
    state = str(row.get("state") or "")
    timestamp = row.get("updateTime") or row.get("createTime")
    return {
        "id": str(row.get("orderId") or ""),
        "symbol": symbol,
        "status": "closed" if has_fill or state in {"3", "4"} else "open",
        "filled": 0 if filled in (None, "") else filled,
        "timestamp": timestamp,
        "clientOrderId": str(row.get("externalOid") or ""),
        "info": row,
    }


def execute_futures(
    exchange,
    strategy: Strategy,
    action: str,
    client_order_id: str,
    strategies: dict[str, Strategy],
) -> LiveResult:
    if action not in ("SHORT", "COVER", "LONG", "FLAT"):
        raise RuntimeError("unsupported action")
    try:
        load_futures_lots(exchange, strategies)
        from app.execution.strategy_lots import configured

        if configured():
            refresh_futures_from_store()
    except Exception:
        return LiveResult("not_sent", False, "position history unavailable")
    exchange_id = framed_client_order_id(
        strategy.strategy_id, client_order_id, action, venue=strategy.venue
    )
    symbol = swap_symbol(strategy.symbol)
    if action in ("SHORT", "LONG"):
        side = "sell" if action == "SHORT" else "buy"
        return _open(exchange, strategy, symbol, exchange_id, client_order_id, side)
    side = "buy" if action == "COVER" else "sell"
    return _close(exchange, strategy, symbol, exchange_id, client_order_id, side)


def cancel_open_futures_orders() -> None:
    strategies = _mexc_futures(load_strategies())
    if not strategies:
        return
    exchange = futures_client()
    codes = strategy_codes(list(strategies))
    symbols = sorted({swap_symbol(strategy.symbol) for strategy in strategies.values()})
    for symbol in symbols:
        for order in exchange.fetch_open_orders(symbol) or []:
            client_id = _client_id(order)
            if not _known_futures_order(client_id, codes):
                continue
            order_id = order.get("id")
            if order_id:
                exchange.cancel_order(order_id, symbol)


def refresh_futures_from_store() -> None:
    global _loaded
    from app.execution.strategy_lots import load_venue

    stored = load_venue("mexc_futures")
    with _lock:
        _lots.clear()
        _lots.update({strategy_id: float(quantity) for strategy_id, quantity in stored.items()})
        _loaded = True


def load_futures_lots(exchange, strategies: dict[str, Strategy]) -> None:
    global _loaded
    with _lock:
        if _loaded:
            return
    from app.execution.strategy_lots import (
        apply_futures_history,
        configured,
        load_venue,
        mark_synced,
        was_synced,
    )

    futures = _tracked_futures(strategies)
    if not configured():
        _rebuild_futures(exchange, futures)
        return
    stored = load_venue("mexc_futures")
    synced = was_synced("mexc_futures")
    try:
        codes = strategy_codes(list(futures))
        since = int((datetime.now(timezone.utc) - timedelta(days=HISTORY_DAYS)).timestamp() * 1000)
        collected: list[dict] = []
        for symbol in sorted({swap_symbol(strategy.symbol) for strategy in futures.values()}):
            collected.extend(fetch_futures_history(exchange, symbol, since))
        apply_futures_history(collected, codes)
        mark_synced("mexc_futures")
    except Exception:
        if not synced and not stored:
            raise
    refresh_futures_from_store()


def _rebuild_futures(exchange, futures: dict[str, Strategy]) -> None:
    global _loaded
    codes = strategy_codes(list(futures))
    since = int((datetime.now(timezone.utc) - timedelta(days=HISTORY_DAYS)).timestamp() * 1000)
    collected: list[dict] = []
    for symbol in sorted({swap_symbol(strategy.symbol) for strategy in futures.values()}):
        collected.extend(fetch_futures_history(exchange, symbol, since))
    rebuilt = lots_from_orders(collected, codes)
    with _lock:
        if _loaded:
            return
        _lots.clear()
        _lots.update(rebuilt)
        _loaded = True


def _tracked_futures(strategies: dict[str, Strategy]) -> dict[str, Strategy]:
    selected: dict[str, Strategy] = {}
    for strategy_id, strategy in strategies.items():
        for deployment in strategy.deployments:
            if deployment.venue == "mexc_futures":
                selected[strategy_id] = strategy.bound(deployment)
    return selected


def _known_futures_order(client_id: str, codes: dict[str, str]) -> bool:
    return strategy_of(client_id, codes) is not None


def _futures_identity(client_id: str, codes: dict[str, str]) -> tuple[str, str] | None:
    return strategy_of(client_id, codes)


def lots_from_orders(orders: list[dict], codes: dict[str, str]) -> dict[str, float]:
    events: list[tuple[int, str, str, float]] = []
    for order in orders:
        client_id = _client_id(order)
        identified = _futures_identity(client_id, codes)
        if identified is None:
            continue
        strategy_id, mark = identified
        status = str(order.get("status") or "").lower()
        if status not in ("closed", "filled"):
            continue
        filled = _filled(order)
        if filled <= 0:
            continue
        events.append((_timestamp(order), strategy_id, mark, filled))
    events.sort(key=lambda item: item[0])
    lots: dict[str, float] = {}
    for _timestamp_ms, strategy_id, mark, filled in events:
        current = lots.get(strategy_id, 0.0)
        if mark in ("h", "l"):
            lots[strategy_id] = current + filled
            continue
        left = current - filled
        if left <= 1e-9:
            lots.pop(strategy_id, None)
        else:
            lots[strategy_id] = left
    return lots


def _mexc_futures(strategies: dict[str, Strategy]) -> dict[str, Strategy]:
    selected: dict[str, Strategy] = {}
    for strategy_id, strategy in strategies.items():
        for deployment in strategy.deployments:
            if deployment.enabled and deployment.venue == "mexc_futures":
                selected[strategy_id] = strategy.bound(deployment)
    return selected


def _contract_step(exchange, symbol: str) -> Decimal:
    market = getattr(exchange, "market", None)
    info = {}
    if callable(market):
        try:
            raw = market(symbol) or {}
            found = raw.get("info")
            if isinstance(found, dict):
                info = found
        except Exception:
            info = {}
    raw_step = info.get("volUnit")
    try:
        step = Decimal(str(raw_step))
    except Exception:
        step = Decimal("0")
    if step <= 0:
        return Decimal("1")
    return step


def _orderable_contracts(exchange, symbol: str, contracts: float) -> float:
    if contracts <= 0:
        return 0
    step = _contract_step(exchange, symbol)
    amount = (Decimal(str(contracts)) / step).to_integral_value(rounding=ROUND_FLOOR) * step
    if amount <= 0:
        return 0
    if amount == amount.to_integral_value():
        return int(amount)
    return float(amount)


def _open(
    exchange, strategy: Strategy, symbol: str, exchange_id: str, client_order_id: str, side: str
) -> LiveResult:
    current = _read_lot(strategy.strategy_id)
    if current > 0 and _orderable_contracts(exchange, symbol, current) > 0:
        return LiveResult("not_sent", False, "position already open")
    margin = strategy.size_quote / _leverage(strategy)
    try:
        free = free_usdt(exchange)
    except Exception:
        return LiveResult("not_sent", False, "USDT balance unavailable")
    if free < margin:
        return LiveResult("not_sent", False, "margin insufficient")
    contracts = _contracts(exchange, symbol, strategy.size_quote)
    if contracts < 1:
        return LiveResult("not_sent", False, "quantity below minimum")
    if not _claim(strategy.strategy_id):
        return LiveResult("not_sent", False, "entry already working")
    try:
        _arm(exchange, symbol, side, _leverage(strategy))
        order_id = _submit(
            exchange, symbol, side, contracts, exchange_id, reduce_only=False, leverage=_leverage(strategy)
        )
    except Exception:
        _release(strategy.strategy_id)
        raise
    if len(exchange_id) == 32:
        report_order_link(exchange_id, client_order_id)

    def complete() -> LiveResult:
        try:
            status, filled, average = _confirm(exchange, symbol, order_id)
            if filled <= 0:
                return LiveResult("order_failed", True, "filled quantity missing")
            _remember(strategy.strategy_id, _stored_futures(
                strategy.strategy_id, exchange_id, filled, closing=False, fill_price=average
            ))
            return LiveResult(status, True, average=average)
        finally:
            _release(strategy.strategy_id)

    from app.execution.live import handoff_follow_up

    return handoff_follow_up(strategy, "SHORT" if side == "sell" else "LONG", complete)


def _close(
    exchange, strategy: Strategy, symbol: str, exchange_id: str, client_order_id: str, side: str
) -> LiveResult:
    contracts = _read_lot(strategy.strategy_id)
    if contracts <= 0:
        return LiveResult("not_sent", False, "position already flat")
    orderable = _orderable_contracts(exchange, symbol, contracts)
    if orderable <= 0:
        return LiveResult("not_sent", False, "remainder below order step")
    if not _claim(strategy.strategy_id):
        return LiveResult("not_sent", False, "exit already working")
    try:
        order_id = _submit(exchange, symbol, side, orderable, exchange_id, reduce_only=True)
    except Exception:
        _release(strategy.strategy_id)
        raise
    if len(exchange_id) == 32:
        report_order_link(exchange_id, client_order_id)
    closing_action = "COVER" if side == "buy" else "FLAT"

    def complete() -> LiveResult:
        try:
            status, filled, average = _confirm(exchange, symbol, order_id)
            if filled <= 0:
                return LiveResult("order_failed", True, "filled quantity missing")
            _remember(strategy.strategy_id, _stored_futures(strategy.strategy_id, exchange_id, filled, closing=True))
            return LiveResult(
                status,
                True,
                average=average,
                realized=_futures_close_realized(strategy, symbol, filled, average, client_order_id, side),
            )
        finally:
            _release(strategy.strategy_id)

    from app.execution.live import handoff_follow_up

    return handoff_follow_up(strategy, closing_action, complete)


def _stored_futures(
    strategy_id: str, order_key: str, filled: float, closing: bool, fill_price: float | None = None
) -> float:
    from decimal import Decimal

    from app.execution.strategy_lots import LotStoreError, configured, note_fill

    current = _lots.get(strategy_id, 0.0)
    if not configured():
        updated = current - filled if closing else filled if not closing and current <= 0 else current + filled
        return 0.0 if updated <= 1e-9 else updated
    try:
        quantity = note_fill(
            "mexc_futures",
            order_key,
            strategy_id,
            closing,
            Decimal(str(filled)),
            fill_price=None if fill_price is None else Decimal(str(fill_price)),
            protect=not closing and fill_price not in (None, 0),
        )
    except LotStoreError:
        updated = current - filled if closing else current + filled
        return 0.0 if updated <= 1e-9 else updated
    return float(quantity)


def _contracts(exchange, symbol: str, notional: float) -> int:
    ticker = exchange.fetch_ticker(symbol)
    price = float(ticker.get("last") or 0)
    size = _contract_size(exchange, symbol)
    if price <= 0 or size <= 0:
        return 0
    return int(notional / (price * size))


def _contract_size(exchange, symbol: str) -> float:
    market = getattr(exchange, "market", None)
    if market is not None:
        try:
            info = market(symbol) or {}
            size = info.get("contractSize")
            if size:
                return float(size)
        except Exception:
            pass
    return CONTRACT_SIZE.get(symbol, 0.0)


def _leverage(strategy: Strategy) -> int:
    if strategy.leverage is None:
        raise RuntimeError("leverage is required")
    return strategy.leverage


def _arm(exchange, symbol: str, side: str, leverage: int) -> None:
    # changeLeverage の成功応答は {success, code} であり、レバレッジ行の配列ではない。
    # set_margin_mode はその応答を行配列として [0] から読むので、注文の前で落ちる。
    # 切り替える行はこちらで 1 件指定し、応答は解釈しない。
    short = side == "sell"
    _call(
        exchange,
        "set_leverage",
        leverage,
        symbol,
        {"openType": 1, "positionType": 2 if short else 1},
    )


def _call(exchange, method: str, *args) -> None:
    function = getattr(exchange, method, None)
    if function is None:
        return
    try:
        function(*args)
    except Exception as exc:
        text = str(exc).lower()
        if any(word in text for word in ("already", "no need", "not modified", "same")):
            return
        raise


def _read_lot(strategy_id: str) -> float:
    with _lock:
        return _lots.get(strategy_id, 0.0)


def _claim(strategy_id: str) -> bool:
    with _lock:
        if strategy_id in _working:
            return False
        _working.add(strategy_id)
        return True


def _release(strategy_id: str) -> None:
    with _lock:
        _working.discard(strategy_id)


def _remember(strategy_id: str, quantity: float) -> None:
    with _lock:
        if quantity <= 1e-9:
            _lots.pop(strategy_id, None)
        else:
            _lots[strategy_id] = quantity


def _confirm(exchange, symbol: str, order_id: str) -> tuple[str, float, float | None]:
    status, filled, average = _fetch_fill(exchange, symbol, order_id)
    if filled > 0:
        return status, filled, average
    return _fetch_fill(exchange, symbol, order_id)


def _fetch_fill(exchange, symbol: str, order_id: str) -> tuple[str, float, float | None]:
    try:
        fetched = exchange.fetch_order(order_id, symbol)
    except Exception as exc:
        logger.warning("futures fill was not reread: %s", type(exc).__name__)
        return "order_failed", 0.0, None
    status = str(fetched.get("status") or "")
    if not status:
        raise RuntimeError("order status missing")
    average = fetched.get("average")
    return status, float(fetched.get("filled") or 0), None if average in (None, "") else float(average)


def _submit(
    exchange,
    symbol: str,
    side: str,
    contracts: float,
    exchange_id: str,
    *,
    reduce_only: bool,
    leverage: int | None = None,
) -> str:
    params = {
        "reduceOnly": reduce_only,
        "clientOrderId": exchange_id,
        "newClientOrderId": exchange_id,
    }
    if not reduce_only:
        params["leverage"] = leverage
        params["openType"] = 1
    created = exchange.create_order(symbol, "market", side, contracts, None, params)
    order_id = created.get("id")
    if not order_id:
        raise RuntimeError("order id missing")
    return str(order_id)


def _futures_close_realized(strategy, symbol: str, filled: float, average, client_order_id: str, side: str):
    size = CONTRACT_SIZE.get(symbol)
    if not size or average is None or filled <= 0:
        return None
    from decimal import Decimal

    from app.analytics.history import closing_realized_pnl

    return closing_realized_pnl(
        strategy_name=strategy.strategy_id,
        symbol=strategy.symbol,
        venue=strategy.venue,
        trade_id=f"notify:{client_order_id}",
        side=side,
        quantity=Decimal(str(filled)) * Decimal(str(size)),
        price=average,
        client_order_id=client_order_id,
    )
