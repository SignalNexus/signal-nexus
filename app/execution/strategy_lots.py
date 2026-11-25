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
        if delta > 0 and closing:
            record_close_gap(connection, venue, strategy_id, delta)
        elif delta > 0:
            record_open_gap(connection, venue, strategy_id, delta)
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


class PositionBook:
    def __init__(
        self,
        opened: Decimal,
        close_applied: Decimal | None,
        ingested_closes: Decimal,
        open_applied: Decimal | None,
        ingested_opens: Decimal,
    ) -> None:
        self.opened = opened
        self.close_applied = close_applied
        self.ingested_closes = ingested_closes
        self.open_applied = open_applied
        self.ingested_opens = ingested_opens


def close_quantity(venue: str, strategy_id: str, stored: Decimal | None = None) -> Decimal:
    # 履歴が先なら履歴を使う。ロットにだけあるクローズは履歴から引く。
    # ロットが履歴より多くても、まだ履歴に無い新規で説明できる分だけ残す。
    # 読み取れないときはロットを使う。MEXC先物は枚数に直してから比べる。
    if stored is None:
        try:
            stored = load_venue(venue).get(strategy_id, Decimal("0"))
        except Exception:
            stored = Decimal("0")
    else:
        stored = Decimal(stored)
    book = _position_book(venue, strategy_id)
    if book is None:
        return stored
    quantity = aligned_quantity(
        stored,
        book.opened,
        book.close_applied,
        book.ingested_closes,
        book.open_applied,
        book.ingested_opens,
    )
    if quantity < stored and configured():
        try:
            set_quantity(venue, strategy_id, quantity)
        except Exception:
            logger.warning("aligned lot was not stored")
    return quantity


def fill_open_quantity(venue: str, strategy_id: str) -> Decimal:
    return close_quantity(venue, strategy_id)


def attributable(own: Decimal, others: Decimal, account: Decimal | None) -> Decimal:
    # 口座残が読めないときは、その戦略の台帳数量のまま出す。
    if account is None:
        return own
    if account < 0:
        account = Decimal("0")
    room = account - others
    if room < 0:
        room = Decimal("0")
    if own < room:
        return own
    return room


BOOK_DIFFERS = "position book differs from the account"


def books_differ(own: Decimal, others: Decimal, account: Decimal, step: Decimal | None) -> bool:
    # この戦略の台帳がゼロなら、口座が開いていてもこの戦略の決済はフラットとして扱う。
    if own <= 0 or (account == 0 and others == 0):
        return False
    gap = own + others - account
    if gap < 0:
        gap = -gap
    tolerance = step if step is not None and step > 0 else Decimal("0")
    return gap > tolerance


def close_hold(venue: str, strategy_id: str, own: Decimal, account: Decimal | None, step: Decimal | None) -> str | None:
    # 口座が読めない、または他戦略の台帳が読めないときは止めない。
    if account is None:
        return None
    others = _peer_open(venue, strategy_id)
    if others is None:
        return None
    if books_differ(own, others, account, step):
        return BOOK_DIFFERS
    return None


def sized_close(venue: str, strategy_id: str, own: Decimal, account: Decimal | None) -> Decimal:
    if account is None:
        return own
    if account <= 0:
        return Decimal("0")
    others = _peer_open(venue, strategy_id)
    if others is None:
        if own < account:
            return own
        return account
    return attributable(own, others, account)


def record_close_gap(connection, venue: str, strategy_id: str, delta: Decimal) -> None:
    if delta <= 0:
        return
    from app.analytics.schema import load_close_applied, save_close_applied

    current = load_close_applied(connection, venue, strategy_id)
    if current is None:
        current = _measured(connection, venue, strategy_id, opening=False)
        if current is None:
            return
    save_close_applied(connection, venue, strategy_id, current + delta)


def record_open_gap(connection, venue: str, strategy_id: str, delta: Decimal) -> None:
    if delta <= 0:
        return
    from app.analytics.schema import load_open_applied, save_open_applied

    current = load_open_applied(connection, venue, strategy_id)
    if current is None:
        current = _measured(connection, venue, strategy_id, opening=True)
        if current is None:
            return
    save_open_applied(connection, venue, strategy_id, current + delta)


def aligned_quantity(
    stored: Decimal,
    opened: Decimal,
    close_applied: Decimal | None,
    ingested_closes: Decimal,
    open_applied: Decimal | None,
    ingested_opens: Decimal,
) -> Decimal:
    fill_adjusted = adjusted_open(opened, close_applied, ingested_closes)
    if stored <= fill_adjusted:
        return fill_adjusted
    if open_applied is None:
        return stored
    pending = open_applied - ingested_opens
    if pending < 0:
        pending = Decimal("0")
    room = fill_adjusted + pending
    if room < stored:
        return room
    return stored


def adjusted_open(reconstructed: Decimal, applied: Decimal | None, ingested: Decimal) -> Decimal:
    if applied is None:
        return reconstructed
    pending = applied - ingested
    if pending < 0:
        pending = Decimal("0")
    opened = reconstructed - pending
    if opened < 0:
        return Decimal("0")
    return opened


def _position_book(venue: str, strategy_id: str) -> PositionBook | None:
    if not configured():
        return None
    try:
        from app.analytics.report import fill_view_from_row, reconstructed_open_quantity
        from app.analytics.schema import load_close_applied, load_open_applied, load_strategy_fills

        with connect() as connection:
            if connection is None:
                return None
            rows = load_strategy_fills(connection, venue, strategy_id)
            close_applied = load_close_applied(connection, venue, strategy_id)
            open_applied = load_open_applied(connection, venue, strategy_id)
            fills = [fill_view_from_row(row) for row in rows]
            opened = reconstructed_open_quantity(fills, venue, strategy_id)
            ingested_closes = _closing_quantity(fills, venue)
            ingested_opens = _opening_quantity(fills, venue)
            measured = _in_lot_units(venue, fills, opened, ingested_closes, ingested_opens)
            if measured is None:
                return None
            opened, ingested_closes, ingested_opens = measured
        return PositionBook(opened, close_applied, ingested_closes, open_applied, ingested_opens)
    except Exception:
        logger.warning("close quantity kept the lot")
        return None


def _measured(connection, venue: str, strategy_id: str, *, opening: bool) -> Decimal | None:
    from app.analytics.report import fill_view_from_row
    from app.analytics.schema import load_strategy_fills

    rows = load_strategy_fills(connection, venue, strategy_id)
    fills = [fill_view_from_row(row) for row in rows]
    quantity = _opening_quantity(fills, venue) if opening else _closing_quantity(fills, venue)
    measured = _in_lot_units(venue, fills, Decimal("0"), quantity, Decimal("0"))
    if measured is None:
        return None
    return measured[1]


def _in_lot_units(
    venue: str, fills, opened: Decimal, ingested_closes: Decimal, ingested_opens: Decimal
) -> tuple[Decimal, Decimal, Decimal] | None:
    divisor = _lot_divisor(venue, fills)
    if divisor is None:
        return None
    return opened / divisor, ingested_closes / divisor, ingested_opens / divisor


def _lot_divisor(venue: str, fills) -> Decimal | None:
    if venue != "mexc_futures":
        return Decimal("1")
    symbols = {fill.symbol for fill in fills if getattr(fill, "symbol", None)}
    if not symbols:
        return Decimal("1")
    if len(symbols) != 1:
        return None
    from app.execution.futures import CONTRACT_SIZE

    base = next(iter(symbols)).split(":")[0].split("_")[0].split("/")[0]
    size = CONTRACT_SIZE.get(f"{base}/USDT:USDT")
    if not size:
        return None
    return Decimal(str(size))


def _peer_open(venue: str, strategy_id: str) -> Decimal | None:
    try:
        from app.execution.router import load_strategies

        book = load_strategies()
        strategy = book.get(strategy_id)
        if strategy is None:
            return Decimal("0")
        total = Decimal("0")
        for peer_id, item in book.items():
            if peer_id == strategy_id or item.symbol != strategy.symbol:
                continue
            if not any(deployment.enabled and deployment.venue == venue for deployment in item.deployments):
                continue
            total += close_quantity(venue, peer_id)
        return total
    except Exception:
        logger.warning("peer lots were not read")
        return None


def _ingested_closes(connection, venue: str, strategy_id: str) -> Decimal:
    from app.analytics.report import fill_view_from_row
    from app.analytics.schema import load_strategy_fills

    rows = load_strategy_fills(connection, venue, strategy_id)
    fills = [fill_view_from_row(row) for row in rows]
    return _closing_quantity(fills, venue)


def _opening_quantity(fills, venue: str) -> Decimal:
    return _side_quantity(fills, venue, opening=True)


def _closing_quantity(fills, venue: str) -> Decimal:
    return _side_quantity(fills, venue, opening=False)


def _side_quantity(fills, venue: str, *, opening: bool) -> Decimal:
    from app.analytics.report import _arcus_long, _risex_sides
    from app.venues import is_futures

    short = bool(is_futures(venue) and not _arcus_long(fills, _risex_sides(fills, None)))
    side = "sell" if short == opening else "buy"
    return sum((fill.quantity for fill in fills if fill.side == side), Decimal("0"))


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
    for order_key, strategy_id, side, net, symbol, timestamp, price in spot_fill_events(orders, trades, codes):
        opening = side == "buy"
        note_fill(
            "mexc_spot",
            order_key,
            strategy_id,
            side == "sell",
            Decimal(str(net)),
            symbol=symbol,
            bought_at_ms=timestamp,
            fill_price=price,
            protect=opening and price is not None and price > 0,
        )


def apply_futures_history(orders: list[dict], codes: dict[str, str]) -> None:
    for order_key, strategy_id, closing, filled, price in futures_fill_events(orders, codes):
        note_fill(
            "mexc_futures",
            order_key,
            strategy_id,
            closing,
            Decimal(str(filled)),
            fill_price=price,
            protect=not closing and price is not None and price > 0,
        )


def apply_arcus_fills(fills: list[dict], codes: dict[str, str]) -> None:
    from app.execution.positions import strategy_of

    grouped: dict[str, tuple[str, bool, Decimal, Decimal]] = {}
    for fill in fills:
        client_id = str(fill.get("clientId") or "")
        identified = strategy_of(client_id, codes)
        if identified is None:
            continue
        strategy_id, mark = identified
        try:
            size = Decimal(str(fill.get("size") or "0"))
            price = Decimal(str(fill.get("price") or "0"))
        except Exception:
            continue
        if size <= 0:
            continue
        closing = mark in ("c", "f")
        quote = price * size if price > 0 else Decimal("0")
        current = grouped.get(client_id)
        if current is None:
            grouped[client_id] = (strategy_id, closing, size, quote)
        else:
            grouped[client_id] = (strategy_id, closing, current[2] + size, current[3] + quote)
    for order_key, (strategy_id, closing, size, quote) in grouped.items():
        price = quote / size if quote > 0 and size > 0 else None
        note_fill(
            "arcus",
            order_key,
            strategy_id,
            closing,
            size,
            fill_price=price,
            protect=not closing and price is not None and price > 0,
        )


def spot_fill_events(orders: list[dict], trades: list[dict], codes: dict[str, str]):
    from app.execution.positions import _client_id, _filled, _orders_from_trades, _timestamp

    events = []
    seen: set[str] = set()
    for client_id, parsed in _orders_from_trades(trades or [], codes).items():
        timestamp, strategy_id, side, net, symbol = parsed
        events.append((client_id, strategy_id, side, net, symbol, timestamp, None))
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
        events.append((client_id, strategy_id, side, net, symbol, _timestamp(order), _order_price(order)))
    events.sort(key=lambda item: item[5])
    return events


def futures_fill_events(orders: list[dict], codes: dict[str, str]):
    from app.execution.positions import _client_id, _filled, strategy_of

    events = []
    for order in orders:
        client_id = _client_id(order)
        identified = strategy_of(client_id, codes)
        if identified is None:
            continue
        strategy_id, mark = identified
        filled = _filled(order)
        if filled <= 0:
            continue
        events.append((client_id, strategy_id, mark in ("c", "f"), filled, _order_price(order)))
    return events


def _order_price(order: dict) -> Decimal | None:
    sources = [order]
    info = order.get("info")
    if isinstance(info, dict):
        sources.append(info)
    for source in sources:
        for key in ("average", "avgPrice", "dealAvgPrice", "price"):
            value = source.get(key)
            if value in (None, "", 0, "0"):
                continue
            try:
                price = Decimal(str(value))
            except Exception:
                continue
            if price > 0:
                return price
    return None


def sync_configured_venues() -> None:
    if not configured():
        return
    from app.execution.order_executor import public_order_error

    for name, worker in (
        ("mexc_spot", _sync_spot),
        ("mexc_futures", _sync_futures),
        ("arcus", _sync_arcus),
        ("added", _sync_added),
    ):
        try:
            worker()
        except Exception as exc:
            logger.warning(
                "strategy lots were not synced: %s %s: %s",
                name,
                type(exc).__name__,
                public_order_error(exc),
            )


def _sync_added() -> None:
    from app.execution.venue_port import ports

    for venue_id, port in ports().items():
        try:
            port.sync_lots()
        except Exception:
            logger.warning("venue lots were not synced: %s", venue_id)


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
    symbols = sorted(
        {
            strategy.bound(deployment).symbol
            for strategy in strategies.values()
            for deployment in strategy.deployments
            if deployment.enabled and deployment.venue == "mexc_spot"
        }
    )
    if not symbols:
        mark_synced("mexc_spot")
        refresh_spot_from_store()
        return
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
        connection.execute("SAVEPOINT protective_stop")
        try:
            if updated <= 0:
                from app.execution.protective_stop import cancel_armed

                cancel_armed(connection, venue, strategy_id)
            elif protect and not closing and fill_price is not None and fill_price > 0:
                from app.execution.protective_stop import arm_from_fill, stop_is_active

                if filled > 0 or not stop_is_active(connection, venue, strategy_id):
                    arm_from_fill(connection, venue, strategy_id, fill_price)
        except Exception:
            connection.execute("ROLLBACK TO SAVEPOINT protective_stop")
            raise
        connection.execute("RELEASE SAVEPOINT protective_stop")
    except Exception as exc:
        logger.warning("protective stop was not updated: %s", type(exc).__name__)


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
