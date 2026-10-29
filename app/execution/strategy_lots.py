import logging
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal

logger = logging.getLogger(__name__)
SYNC_INTERVAL_SECONDS = 3600


class LotStoreError(RuntimeError):
    pass


def configured() -> bool:
    return bool(os.environ.get("ANALYTICS_DATABASE_URL", "").strip())


def connect():
    url = os.environ.get("ANALYTICS_DATABASE_URL", "").strip()
    if not url:
        return None
    import psycopg

    return psycopg.connect(url)


def note_fill(
    venue: str,
    order_key: str,
    strategy_id: str,
    closing: bool,
    filled: Decimal,
    *,
    symbol: str | None = None,
    bought_at_ms: int | None = None,
    fill_price: Decimal | None = None,
    protect: bool = False,
) -> Decimal:
    if filled < 0:
        filled = Decimal("0")
    with _use() as connection:
        from app.analytics.schema import (
            create_schema,
            load_applied_fill,
            load_strategy_lots,
            save_applied_fill,
            save_spot_meta,
            save_strategy_lot,
            delete_spot_meta,
        )

        create_schema(connection)
        previous = load_applied_fill(connection, venue, order_key)
        if filled < previous:
            filled = previous
        delta = filled - previous
        current = load_strategy_lots(connection, venue).get(strategy_id, Decimal("0"))
        updated = current - delta if closing else current + delta
        if updated <= 0:
            updated = Decimal("0")
        save_strategy_lot(connection, venue, strategy_id, updated)
        save_applied_fill(connection, venue, order_key, filled)
        if venue == "mexc_spot":
            if updated <= 0:
                delete_spot_meta(connection, strategy_id)
            elif symbol and bought_at_ms is not None and current <= 0:
                save_spot_meta(connection, strategy_id, symbol, bought_at_ms)
        _sync_stop(connection, venue, strategy_id, updated, closing, filled=delta, fill_price=fill_price, protect=protect)
    return updated


def set_quantity(venue: str, strategy_id: str, quantity: Decimal) -> None:
    with _use() as connection:
        from app.analytics.schema import create_schema, save_strategy_lot

        create_schema(connection)
        save_strategy_lot(connection, venue, strategy_id, quantity)


def load_venue(venue: str) -> dict[str, Decimal]:
    with _use() as connection:
        from app.analytics.schema import create_schema, load_strategy_lots

        create_schema(connection)
        return load_strategy_lots(connection, venue)


def load_spot_state() -> tuple[dict[str, Decimal], dict[str, tuple[str, int]], dict[str, int], bool]:
    with _use() as connection:
        from app.analytics.schema import (
            create_schema,
            load_sold_exits,
            load_spot_meta,
            load_strategy_lots,
            venue_was_synced,
        )

        create_schema(connection)
        return (
            load_strategy_lots(connection, "mexc_spot"),
            load_spot_meta(connection),
            load_sold_exits(connection),
            venue_was_synced(connection, "mexc_spot"),
        )


def remember_sold_exit(strategy_id: str, exit_bar_close_ms: int) -> None:
    if not configured():
        return
    try:
        with _use() as connection:
            from app.analytics.schema import create_schema, save_sold_exit

            create_schema(connection)
            save_sold_exit(connection, strategy_id, exit_bar_close_ms)
    except LotStoreError:
        logger.warning("sold exit was not stored")


def was_synced(venue: str) -> bool:
    with _use() as connection:
        from app.analytics.schema import create_schema, venue_was_synced

        create_schema(connection)
        return venue_was_synced(connection, venue)


def mark_synced(venue: str) -> None:
    with _use() as connection:
        from app.analytics.schema import create_schema, mark_venue_synced

        create_schema(connection)
        mark_venue_synced(connection, venue, datetime.now(timezone.utc))


def apply_spot_history(orders: list[dict], trades: list[dict], codes: dict[str, str]) -> None:
    for order_key, strategy_id, side, net, symbol, timestamp in spot_fill_events(orders, trades, codes):
        note_fill(
            "mexc_spot",
            order_key,
            strategy_id,
            side == "sell",
            Decimal(str(net)),
            symbol=symbol,
            bought_at_ms=timestamp,
        )


def apply_futures_history(orders: list[dict], codes: dict[str, str]) -> None:
    for order_key, strategy_id, closing, filled in futures_fill_events(orders, codes):
        note_fill("mexc_futures", order_key, strategy_id, closing, Decimal(str(filled)))


def apply_arcus_fills(fills: list[dict], codes: dict[str, str]) -> None:
    grouped: dict[str, tuple[str, bool, Decimal]] = {}
    for fill in fills:
        client_id = str(fill.get("clientId") or "")
        if len(client_id) != 32 or client_id[10] not in ("h", "c", "l", "f"):
            continue
        strategy_id = codes.get(client_id[:10])
        if strategy_id is None:
            continue
        try:
            size = Decimal(str(fill.get("size") or "0"))
        except Exception:
            continue
        if size <= 0:
            continue
        closing = client_id[10] in ("c", "f")
        current = grouped.get(client_id)
        if current is None:
            grouped[client_id] = (strategy_id, closing, size)
        else:
            grouped[client_id] = (strategy_id, closing, current[2] + size)
    for order_key, (strategy_id, closing, size) in grouped.items():
        note_fill("arcus", order_key, strategy_id, closing, size)


def spot_fill_events(orders: list[dict], trades: list[dict], codes: dict[str, str]):
    from app.execution.positions import _client_id, _filled, _orders_from_trades, _timestamp

    events = []
    seen: set[str] = set()
    for client_id, parsed in _orders_from_trades(trades or [], codes).items():
        timestamp, strategy_id, side, net, symbol = parsed
        events.append((client_id, strategy_id, side, net, symbol, timestamp))
        seen.add(client_id)
    for order in orders:
        client_id = _client_id(order)
        if not client_id or client_id in seen or len(client_id) != 32:
            continue
        strategy_id = codes.get(client_id[:10])
        mark = client_id[10]
        if strategy_id is None or mark not in ("b", "s"):
            continue
        filled = _filled(order)
        if filled <= 0:
            continue
        side = "buy" if mark == "b" else "sell"
        reported = str(order.get("side") or "").lower()
        if reported and reported != side:
            continue
        symbol = order.get("symbol")
        if not isinstance(symbol, str) or not symbol:
            continue
        net = filled * (1 - _taker_fee()) if side == "buy" else filled
        events.append((client_id, strategy_id, side, net, symbol, _timestamp(order)))
    events.sort(key=lambda item: item[5])
    return events


def futures_fill_events(orders: list[dict], codes: dict[str, str]):
    from app.execution.positions import _client_id, _filled

    events = []
    for order in orders:
        client_id = _client_id(order)
        if len(client_id) != 32 or client_id[10] not in ("h", "c", "l", "f"):
            continue
        strategy_id = codes.get(client_id[:10])
        if strategy_id is None:
            continue
        filled = _filled(order)
        if filled <= 0:
            continue
        events.append((client_id, strategy_id, client_id[10] in ("c", "f"), filled))
    return events


def sync_configured_venues() -> None:
    if not configured():
        return
    _sync_spot()
    _sync_futures()
    _sync_arcus()


def _sync_spot() -> None:
    if not (os.environ.get("MEXC_API_KEY", "").strip() and os.environ.get("MEXC_API_SECRET", "").strip()):
        return
    from app.execution.exchange import mexc_client
    from app.execution.positions import (
        HISTORY_DAYS,
        _recent_trades,
        _with_symbol,
        refresh_spot_from_store,
        strategy_codes,
    )
    from app.execution.router import load_strategies

    exchange = mexc_client()
    strategies = load_strategies()
    now = datetime.now(timezone.utc)
    since = int((now - timedelta(days=HISTORY_DAYS)).timestamp() * 1000)
    symbols = sorted({strategy.symbol for strategy in strategies.values()})
    orders = []
    for symbol in symbols:
        orders.extend(_with_symbol(exchange.fetch_orders(symbol, since, 1000) or [], symbol))
    trades = _recent_trades(exchange, symbols, now)
    codes = strategy_codes([strategy.strategy_id for strategy in strategies.values()])
    apply_spot_history(orders, trades, codes)
    mark_synced("mexc_spot")
    refresh_spot_from_store()


def _sync_futures() -> None:
    if not (
        os.environ.get("MEXC_FUTURES_API_KEY", "").strip()
        and os.environ.get("MEXC_FUTURES_API_SECRET", "").strip()
    ):
        return
    from app.execution.exchange import futures_client
    from app.execution.futures import fetch_futures_history, refresh_futures_from_store, swap_symbol
    from app.execution.positions import HISTORY_DAYS, strategy_codes
    from app.execution.router import load_strategies

    strategies = {
        strategy_id: strategy
        for strategy_id, strategy in load_strategies().items()
        for deployment in strategy.deployments
        if deployment.venue == "mexc_futures"
    }
    if not strategies:
        mark_synced("mexc_futures")
        return
    exchange = futures_client()
    since = int((datetime.now(timezone.utc) - timedelta(days=HISTORY_DAYS)).timestamp() * 1000)
    orders = []
    for symbol in sorted({swap_symbol(strategy.symbol) for strategy in strategies.values()}):
        orders.extend(fetch_futures_history(exchange, symbol, since))
    apply_futures_history(orders, strategy_codes(list(strategies)))
    mark_synced("mexc_futures")
    refresh_futures_from_store()


def _sync_arcus() -> None:
    address = os.environ.get("ARCUS_ADDRESS", "").strip() or os.environ.get("ANALYTICS_ARCUS_ADDRESS", "").strip()
    if not address:
        return
    from app.analytics.importer import _get_arcus_fills, fetch_arcus_fills
    from app.execution.arcus import refresh_arcus_from_store
    from app.execution.positions import strategy_codes
    from app.execution.router import load_strategies

    strategies = [
        strategy.strategy_id
        for strategy in load_strategies().values()
        for deployment in strategy.deployments
        if deployment.venue == "arcus"
    ]
    fills = fetch_arcus_fills(_get_arcus_fills, address, datetime.now(timezone.utc))
    apply_arcus_fills(fills, strategy_codes(strategies))
    mark_synced("arcus")
    refresh_arcus_from_store()


def _sync_stop(connection, venue: str, strategy_id: str, updated: Decimal, closing: bool, *, filled: Decimal, fill_price: Decimal | None, protect: bool) -> None:
    try:
        with connection.savepoint():
            if updated <= 0:
                from app.execution.protective_stop import cancel_armed

                cancel_armed(connection, venue, strategy_id)
            elif protect and not closing and filled > 0 and fill_price is not None and fill_price > 0:
                from app.execution.protective_stop import arm_from_fill

                arm_from_fill(connection, venue, strategy_id, fill_price)
    except Exception:
        logger.warning("protective stop was not updated")


def _taker_fee() -> float:
    from app.execution.order_executor import TAKER_FEE_RATE

    return TAKER_FEE_RATE


class _use:
    def __enter__(self):
        try:
            self.connection = connect()
        except Exception:
            raise LotStoreError("position history unavailable") from None
        if self.connection is None:
            raise LotStoreError("position history unavailable")
        return self.connection

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.connection.commit()
        else:
            self.connection.rollback()
        self.connection.close()
        return False
