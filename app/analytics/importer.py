import logging
import os
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from app.analytics.schema import (
    create_schema,
    insert_fill,
    load_order_links,
    record_ingest_success,
)
from app.venues import asset_class_of
from app.execution.positions import (
    TRADE_HISTORY_DAYS,
    TRADE_WINDOW_DAYS,
    _client_id,
    _timestamp,
    _trade_side,
    strategy_codes,
)
from app.execution.router import load_strategies

logger = logging.getLogger(__name__)

UNCLASSIFIED = "未分類"
# 2026-10-07 の公開より前の約定は、32 文字の ID があっても未分類にする。
CLASSIFIED_FROM = datetime(2026, 10, 7, tzinfo=ZoneInfo("Asia/Tokyo"))
INGEST_INTERVAL = timedelta(minutes=1)
PAGE_LIMIT = 1000
ARCUS_FILLS_URL = "https://api.arcus.xyz/v1/fills"
ARCUS_ACCOUNT_INDEX = 0


def analytics_futures_exchange():
    api_key = os.environ.get("ANALYTICS_MEXC_FUTURES_API_KEY", "")
    secret = os.environ.get("ANALYTICS_MEXC_FUTURES_API_SECRET", "")
    if not api_key or not secret:
        raise RuntimeError("futures read credentials are not configured")
    import ccxt

    return ccxt.mexc(
        {
            "apiKey": api_key,
            "secret": secret,
            "enableRateLimit": True,
            "options": {"defaultType": "swap"},
        }
    )


def analytics_exchange():
    api_key = os.environ.get("ANALYTICS_MEXC_API_KEY", "")
    secret = os.environ.get("ANALYTICS_MEXC_API_SECRET", "")
    if not api_key or not secret:
        raise RuntimeError("analytics read credentials are not configured")
    import ccxt

    return ccxt.mexc(
        {
            "apiKey": api_key,
            "secret": secret,
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        }
    )


def fetch_spot_trades(
    exchange,
    symbols: list[str],
    now: datetime,
    *,
    page_limit: int = PAGE_LIMIT,
    time_key: str = "until",
) -> list[dict]:
    if not hasattr(exchange, "fetch_my_trades"):
        raise RuntimeError("spot trades are unavailable")
    start = now - timedelta(days=TRADE_HISTORY_DAYS)
    trades: list[dict] = []
    for symbol in symbols:
        window_start = start
        while window_start < now:
            window_end = min(window_start + timedelta(days=TRADE_WINDOW_DAYS), now)
            until_ms = int(window_end.timestamp() * 1000)
            cursor = int(window_start.timestamp() * 1000)
            while True:
                batch = exchange.fetch_my_trades(symbol, cursor, page_limit, {time_key: until_ms}) or []
                trades.extend(batch)
                if len(batch) < page_limit:
                    break
                last = max(_timestamp(trade) for trade in batch)
                if last <= cursor:
                    break
                cursor = last
            window_start = window_end
    return trades


def fill_from_trade(trade: dict, codes: dict[str, str], *, venue: str = "mexc_spot") -> dict:
    trade_id = _text(_field(trade, "id"))
    if venue == "mexc_futures" and trade_id:
        trade_id = f"swap:{trade_id}"
    symbol = _text(_field(trade, "symbol"))
    if venue == "mexc_futures" and symbol.endswith(":USDT"):
        symbol = symbol.split(":", 1)[0]
    side = _trade_side(trade)
    if venue == "mexc_futures":
        info = trade.get("info") if isinstance(trade.get("info"), dict) else {}
        side = _futures_side(side) or _futures_side(info.get("side")) or side
    if not trade_id or not symbol or side not in ("buy", "sell"):
        raise ValueError("trade is incomplete")
    quantity = _number(trade, "amount", "qty")
    price = _number(trade, "price")
    if quantity is None or quantity <= 0 or price is None:
        raise ValueError("trade is incomplete")
    if venue == "mexc_futures":
        size = _contract_size(symbol)
        if size > 0:
            quantity = quantity * size
    cost = _number(trade, "cost", "quoteQty")
    if venue == "mexc_futures" or cost is None:
        cost = price * quantity
    fee, fee_asset = _fee_parts(trade)
    filled_at_ms = _timestamp(trade)
    if filled_at_ms <= 0:
        raise ValueError("trade is incomplete")
    filled_at = datetime.fromtimestamp(filled_at_ms / 1000, timezone.utc)
    order_id = _text(_field(trade, "order", "orderId"))
    if not order_id:
        raise ValueError("trade is incomplete")
    exchange_client_order_id = _client_id(trade) or None
    if venue == "mexc_futures" and not exchange_client_order_id:
        info = trade.get("info")
        external = info.get("externalOid") if isinstance(info, dict) else None
        if isinstance(external, str) and external:
            exchange_client_order_id = external
    return {
        "trade_id": trade_id,
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "quote_spent": cost if side == "buy" else Decimal("0"),
        "quote_received": cost if side == "sell" else Decimal("0"),
        "fee": fee,
        "fee_asset": fee_asset,
        "filled_at": filled_at,
        "fill_price": price,
        "exchange_order_id": order_id,
        "exchange_client_order_id": exchange_client_order_id,
        "strategy_name": _strategy_name(exchange_client_order_id, side, filled_at, codes, venue=venue),
        "market": "swap" if venue == "mexc_futures" else "spot",
        "venue": venue,
        "signal_time": None,
        "signal_price": None,
        "client_order_id": None,
    }


def store_trades(
    connection,
    trades: list[dict],
    strategies: dict,
    *,
    succeeded_at: datetime,
    arcus_fills: list[dict] | None = None,
) -> int:
    codes = strategy_codes([strategy.strategy_id for strategy in strategies.values()])
    inserted = 0
    with connection.transaction():
        create_schema(connection)
        links = load_order_links(connection)
        for trade in trades:
            row = fill_from_trade(trade, codes)
            _attach_link(row, links)
            if insert_fill(connection, ignore_conflict=True, **row):
                inserted += 1
        for fill in arcus_fills or []:
            row = fill_from_arcus(fill, codes)
            _attach_link(row, links)
            if insert_fill(connection, ignore_conflict=True, **row):
                inserted += 1
        record_ingest_success(connection, succeeded_at)
    return inserted


def run_ingest(
    connection,
    exchange,
    strategies: dict,
    *,
    now: datetime | None = None,
    arcus_get=None,
) -> int:
    if now is None:
        now = datetime.now(timezone.utc)
    spot = {
        strategy_id: strategy
        for strategy_id, strategy in strategies.items()
        if getattr(strategy, "venue", "mexc_spot") == "mexc_spot"
    }
    symbols = sorted({strategy.symbol for strategy in spot.values()})
    trades = fetch_spot_trades(exchange, symbols, now)
    arcus_fills = _load_arcus_fills(now, arcus_get)
    inserted = store_trades(connection, trades, strategies, succeeded_at=now, arcus_fills=arcus_fills)
    inserted += _ingest_futures(connection, strategies, now)
    return inserted


def run_forever(run, sleeper, *, interval: timedelta = INGEST_INTERVAL, cycles: int | None = None) -> None:
    completed = 0
    while cycles is None or completed < cycles:
        try:
            run()
        except Exception as exc:
            logger.error("spot ingest failed: %s", type(exc).__name__)
        completed += 1
        if cycles is not None and completed >= cycles:
            return
        sleeper(interval.total_seconds())


def main() -> None:
    import psycopg

    url = os.environ["ANALYTICS_DATABASE_URL"]

    def run() -> None:
        with psycopg.connect(url) as connection:
            run_ingest(connection, analytics_exchange(), load_strategies())

    run_forever(run, time.sleep)


def _ingest_futures(connection, strategies: dict, now: datetime) -> int:
    futures = {
        strategy_id: strategy
        for strategy_id, strategy in strategies.items()
        if getattr(strategy, "venue", "mexc_spot") == "mexc_futures"
    }
    if not futures:
        return 0
    if not os.environ.get("ANALYTICS_MEXC_FUTURES_API_KEY") or not os.environ.get("ANALYTICS_MEXC_FUTURES_API_SECRET"):
        return 0
    from app.execution.futures import fetch_futures_history, swap_symbol
    from app.execution.positions import HISTORY_DAYS

    exchange = analytics_futures_exchange()
    symbols = sorted({swap_symbol(strategy.symbol) for strategy in futures.values()})
    # 契約の約定は end_time で区切る。until を付けると照会が失敗する。
    trades = _read_futures(lambda: fetch_spot_trades(exchange, symbols, now, time_key="end_time"), "deals")
    since = int((now - timedelta(days=HISTORY_DAYS)).timestamp() * 1000)
    history: list[dict] = []
    for symbol in symbols:
        history.extend(
            _read_futures(lambda symbol=symbol: fetch_futures_history(exchange, symbol, since), "history")
        )
    positions = _open_futures_positions(exchange, symbols)
    logger.warning(
        "futures rows deals=%s history=%s positions=%s",
        len(trades),
        len(history),
        len(positions),
    )
    if not trades and not history and not positions:
        return 0
    codes = strategy_codes([strategy.strategy_id for strategy in strategies.values()])
    inserted = 0
    with connection.transaction():
        create_schema(connection)
        links = load_order_links(connection)
        for trade in trades:
            try:
                row = fill_from_trade(trade, codes, venue="mexc_futures")
                _attach_link(row, links)
                if _store_futures_fill(connection, row):
                    inserted += 1
            except Exception as exc:
                logger.error("futures deal was skipped: %s", type(exc).__name__)
        for order in history:
            try:
                row = fill_from_futures_order(order, codes)
                if row is None:
                    continue
                _attach_link(row, links)
                if _store_futures_fill(connection, row):
                    inserted += 1
            except Exception as exc:
                logger.error("futures history was skipped: %s", type(exc).__name__)
        inserted += _store_open_futures(connection, positions)
    logger.warning("futures stored=%s", inserted)
    if inserted:
        _refresh_futures_lots()
    return inserted


def _refresh_futures_lots() -> None:
    from app.execution.strategy_lots import configured

    if not configured():
        return
    try:
        from app.execution.futures import refresh_futures_from_store

        refresh_futures_from_store()
    except Exception:
        logger.warning("futures lot was not refreshed")


def _read_futures(read, label: str):
    try:
        return read() or []
    except Exception as exc:
        logger.error("futures %s were not read: %s", label, type(exc).__name__)
        return []


def _open_futures_positions(exchange, symbols: list[str]) -> list[dict]:
    direct = getattr(exchange, "contractPrivateGetPositionOpenPositions", None)
    if direct is None:
        return []
    try:
        rows = _position_rows(direct({}))
    except Exception as exc:
        logger.error("futures positions were not read: %s", type(exc).__name__)
        rows = []
    if rows:
        return rows
    collected: list[dict] = []
    for symbol in symbols:
        contract = f"{symbol.split('/')[0]}_USDT"
        try:
            collected.extend(_position_rows(direct({"symbol": contract})))
        except Exception as exc:
            logger.error("futures positions were not read: %s", type(exc).__name__)
    return collected


def _position_rows(payload) -> list[dict]:
    if not isinstance(payload, dict) or payload.get("success") is False:
        raise RuntimeError("mexc futures positions were rejected")
    code = payload.get("code")
    if code not in (None, 0, "0"):
        raise RuntimeError("mexc futures positions were rejected")
    data = payload.get("data")
    if data is None:
        return []
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        nested = data.get("resultList")
        if isinstance(nested, list):
            return [row for row in nested if isinstance(row, dict)]
        if data.get("positionId") not in (None, "") or data.get("holdVol") not in (None, ""):
            return [data]
    return []


def _store_futures_fill(connection, row: dict) -> bool:
    if row["strategy_name"] != UNCLASSIFIED and _claim_unclassified_futures(connection, row):
        _drop_open_patch(connection, row["symbol"])
        _remember_futures_lot(connection, row)
        return True
    if _futures_order_known(connection, row["exchange_order_id"]):
        return False
    stored = insert_fill(connection, ignore_conflict=True, **row)
    if stored:
        _drop_open_patch(connection, row["symbol"])
        if row["strategy_name"] != UNCLASSIFIED:
            _remember_futures_lot(connection, row)
    return stored


def _claim_unclassified_futures(connection, row: dict) -> bool:
    order_id = row.get("exchange_order_id") or ""
    if not order_id:
        return False
    updated = connection.execute(
        """
        UPDATE fills
        SET strategy_name = %(strategy_name)s,
            exchange_client_order_id = %(exchange_client_order_id)s,
            client_order_id = COALESCE(%(client_order_id)s, client_order_id),
            signal_time = COALESCE(%(signal_time)s, signal_time),
            signal_price = COALESCE(%(signal_price)s, signal_price)
        WHERE venue = 'mexc_futures'
          AND exchange_order_id = %(exchange_order_id)s
          AND strategy_name = %(unclassified)s
        """,
        {
            "strategy_name": row["strategy_name"],
            "exchange_client_order_id": row.get("exchange_client_order_id"),
            "client_order_id": row.get("client_order_id"),
            "signal_time": row.get("signal_time"),
            "signal_price": row.get("signal_price"),
            "exchange_order_id": order_id,
            "unclassified": UNCLASSIFIED,
        },
    )
    return updated.rowcount > 0


def _remember_futures_lot(connection, row: dict) -> None:
    from app.analytics.schema import load_applied_fill, load_strategy_lots, save_applied_fill, save_strategy_lot

    client_id = row.get("exchange_client_order_id") or ""
    if len(client_id) != 32 or client_id[10] not in ("h", "c", "l", "f"):
        return
    size = _contract_size(row["symbol"])
    if size <= 0:
        return
    contracts = row["quantity"] / size
    if contracts <= 0:
        return
    previous = load_applied_fill(connection, "mexc_futures", client_id)
    if contracts < previous:
        contracts = previous
    delta = contracts - previous
    current = load_strategy_lots(connection, "mexc_futures").get(row["strategy_name"], Decimal("0"))
    updated = current - delta if client_id[10] in ("c", "f") else current + delta
    if updated <= 0:
        updated = Decimal("0")
    save_strategy_lot(connection, "mexc_futures", row["strategy_name"], updated)
    save_applied_fill(connection, "mexc_futures", client_id, contracts)


def _futures_order_known(connection, order_id: str) -> bool:
    if not order_id:
        return False
    return (
        connection.execute(
            """
            SELECT 1 FROM fills
            WHERE venue = 'mexc_futures' AND exchange_order_id = %(order_id)s
            LIMIT 1
            """,
            {"order_id": order_id},
        ).fetchone()
        is not None
    )


def _drop_open_patch(connection, symbol: str) -> None:
    connection.execute(
        """
        DELETE FROM fills
        WHERE venue = 'mexc_futures' AND symbol = %(symbol)s AND trade_id LIKE 'swap:open:%%'
        """,
        {"symbol": symbol},
    )


def _store_open_futures(connection, positions: list[dict]) -> int:
    known = {
        row[0]
        for row in connection.execute(
            """
            SELECT DISTINCT symbol FROM fills
            WHERE venue = 'mexc_futures' AND trade_id NOT LIKE 'swap:open:%%'
            """
        )
    }
    inserted = 0
    live: set[str] = set()
    for position in positions:
        row = fill_from_open_position(position)
        if row is None:
            continue
        live.add(row["trade_id"])
        if row["symbol"] in known:
            _drop_open_patch(connection, row["symbol"])
            continue
        connection.execute(
            "DELETE FROM fills WHERE trade_id = %(trade_id)s",
            {"trade_id": row["trade_id"]},
        )
        if insert_fill(connection, **row):
            inserted += 1
    connection.execute(
        """
        DELETE FROM fills
        WHERE venue = 'mexc_futures' AND trade_id LIKE 'swap:open:%%'
          AND NOT (trade_id = ANY(%(live)s))
        """,
        {"live": list(live)},
    )
    return inserted


def fill_from_futures_order(order: dict, codes: dict[str, str]) -> dict | None:
    info = order.get("info") if isinstance(order.get("info"), dict) else order
    order_id = _text(info.get("orderId") or order.get("id"))
    deal = _plain_number(info.get("dealVol"))
    price = _plain_number(info.get("dealAvgPrice"))
    size = _contract_size(_text(order.get("symbol") or info.get("symbol")))
    side = _futures_side(info.get("side"))
    filled_at = _millis(info.get("updateTime") or info.get("createTime") or order.get("timestamp"))
    if not order_id or deal is None or deal <= 0 or price is None or price <= 0 or size <= 0 or side is None:
        return None
    if filled_at is None:
        return None
    quantity = deal * size
    cost = price * quantity
    external = info.get("externalOid") or order.get("clientOrderId") or ""
    client_id = external if isinstance(external, str) and external else None
    symbol = _futures_symbol(_text(order.get("symbol") or info.get("symbol")))
    fee = (_plain_number(info.get("takerFee")) or Decimal("0")) + (
        _plain_number(info.get("makerFee")) or Decimal("0")
    )
    return _futures_row(
        trade_id=f"swap:order:{order_id}",
        symbol=symbol,
        side=side,
        quantity=quantity,
        cost=cost,
        fee=fee,
        fee_asset=_text(info.get("feeCurrency")) or None,
        filled_at=filled_at,
        price=price,
        order_id=order_id,
        client_id=client_id,
        strategy_name=_strategy_name(client_id, side, filled_at, codes, venue="mexc_futures"),
    )


def fill_from_open_position(position: dict) -> dict | None:
    position_id = _text(position.get("positionId"))
    size = _contract_size(_text(position.get("symbol")))
    hold = _plain_number(position.get("holdVol"))
    price = _plain_number(position.get("holdAvgPrice")) or _plain_number(position.get("openAvgPrice"))
    side = "sell" if str(position.get("positionType") or "").lower() in ("2", "short") else None
    filled_at = _millis(position.get("createTime") or position.get("updateTime"))
    if not position_id or hold is None or hold <= 0 or price is None or price <= 0 or size <= 0 or side is None:
        return None
    if filled_at is None:
        return None
    quantity = hold * size
    return _futures_row(
        trade_id=f"swap:open:{position_id}",
        symbol=_futures_symbol(_text(position.get("symbol"))),
        side=side,
        quantity=quantity,
        cost=price * quantity,
        fee=Decimal("0"),
        fee_asset="USDT",
        filled_at=filled_at,
        price=price,
        order_id=f"open:{position_id}",
        client_id=None,
        strategy_name=UNCLASSIFIED,
    )


def _futures_row(
    *,
    trade_id: str,
    symbol: str,
    side: str,
    quantity: Decimal,
    cost: Decimal,
    fee: Decimal,
    fee_asset: str | None,
    filled_at: datetime,
    price: Decimal,
    order_id: str,
    client_id: str | None,
    strategy_name: str,
) -> dict:
    return {
        "trade_id": trade_id,
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "quote_spent": cost if side == "buy" else Decimal("0"),
        "quote_received": cost if side == "sell" else Decimal("0"),
        "fee": fee,
        "fee_asset": fee_asset,
        "filled_at": filled_at,
        "fill_price": price,
        "exchange_order_id": order_id,
        "exchange_client_order_id": client_id,
        "strategy_name": strategy_name,
        "market": "swap",
        "venue": "mexc_futures",
        "signal_time": None,
        "signal_price": None,
        "client_order_id": None,
    }


def _futures_side(value) -> str | None:
    code = str(value or "")
    if code in ("1", "2"):
        return "buy"
    if code in ("3", "4"):
        return "sell"
    return None


def _futures_symbol(symbol: str) -> str:
    if symbol.endswith(":USDT"):
        return symbol.split(":", 1)[0]
    if symbol.endswith("_USDT"):
        return symbol[: -len("_USDT")] + "/USDT"
    return symbol


def _contract_size(symbol: str) -> Decimal:
    from app.execution.futures import CONTRACT_SIZE

    base = symbol.split(":")[0].split("_")[0].split("/")[0]
    size = CONTRACT_SIZE.get(f"{base}/USDT:USDT")
    if not size:
        return Decimal("0")
    return Decimal(str(size))


def _plain_number(value) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _millis(value) -> datetime | None:
    number = _plain_number(value)
    if number is None or number <= 0:
        return None
    millis = int(number)
    if millis < 100_000_000_000:
        if millis < 1_000_000_000:
            return None
        millis *= 1000
    return datetime.fromtimestamp(millis / 1000, timezone.utc)


def _attach_link(row: dict, links: dict) -> None:
    linked = links.get(row["exchange_client_order_id"] or "")
    if linked is None:
        return
    client_order_id, signal_time, signal_price = linked
    row["client_order_id"] = client_order_id
    if signal_time is not None:
        row["signal_time"] = signal_time
    if signal_price is not None:
        row["signal_price"] = signal_price


def _load_arcus_fills(now: datetime, get) -> list[dict]:
    address = os.environ.get("ANALYTICS_ARCUS_ADDRESS", "").strip()
    if not address:
        return []
    fills = fetch_arcus_fills(get or _get_arcus_fills, address, now)
    logger.warning("arcus fills %s", len(fills))
    return fills


def fetch_arcus_fills(reader, address: str, now: datetime, *, page_limit: int = PAGE_LIMIT) -> list[dict]:
    floor = 100_000_000_000_000
    start_us = int((now - timedelta(days=TRADE_HISTORY_DAYS)).timestamp() * 1_000_000)
    end_us = int(now.timestamp() * 1_000_000)
    if start_us < floor:
        start_us = floo
    if end_us < floor:
        raise RuntimeError("arcus fills unavailable")
    seen: set[str] = set()
    fills: list[dict] = []
    cursor = end_us
    while cursor >= start_us:
        batch = reader(address, start_us, cursor, page_limit)
        if not isinstance(batch, list):
            raise RuntimeError("arcus fills unavailable")
        oldest = None
        for row in batch:
            if not isinstance(row, dict):
                raise RuntimeError("arcus fills unavailable")
            trade_id = str(row.get("tradeId") or "")
            if trade_id:
                if trade_id in seen:
                    continue
                seen.add(trade_id)
            fills.append(row)
            created = row.get("createdAt")
            if created not in (None, ""):
                stamp = int(created)
                oldest = stamp if oldest is None else min(oldest, stamp)
        if len(batch) < page_limit:
            break
        if oldest is None or oldest >= cursor:
            break
        cursor = oldest
    return fills


def fill_from_arcus(fill: dict, codes: dict[str, str]) -> dict:
    trade_id = str(fill.get("tradeId") or "")
    order_id = str(fill.get("orderId") or "")
    side = {"BUY": "buy", "SELL": "sell"}.get(str(fill.get("side") or "").upper())
    if not trade_id or not order_id or side is None:
        raise ValueError("trade is incomplete")
    try:
        quantity = Decimal(str(fill["size"]))
        price = Decimal(str(fill["price"]))
        created = int(fill["createdAt"])
        fee_raw = fill.get("fee")
        fee = Decimal("0") if fee_raw in (None, "") else Decimal(str(fee_raw))
    except Exception:
        raise ValueError("trade is incomplete") from None
    if quantity <= 0 or created < 100_000_000_000_000:
        raise ValueError("trade is incomplete")
    cost = price * quantity
    client_id = str(fill.get("clientId") or "") or None
    filled_at = datetime.fromtimestamp(created / 1_000_000, timezone.utc)
    return {
        "trade_id": f"arcus:{trade_id}",
        "symbol": _arcus_symbol(str(fill.get("marketDisplayName") or "")),
        "side": side,
        "quantity": quantity,
        "quote_spent": cost if side == "buy" else Decimal("0"),
        "quote_received": cost if side == "sell" else Decimal("0"),
        "fee": fee,
        "fee_asset": "USD",
        "filled_at": filled_at,
        "fill_price": price,
        "exchange_order_id": order_id,
        "exchange_client_order_id": client_id,
        "strategy_name": _strategy_name(client_id, side, filled_at, codes, venue="arcus"),
        "market": "swap",
        "venue": "arcus",
        "signal_time": None,
        "signal_price": None,
        "client_order_id": None,
    }


def _arcus_symbol(name: str) -> str:
    text = name.strip().upper()
    base, dash, quote = text.partition("-")
    if not dash or not base or not quote or "-" in quote or "/" in text:
        raise ValueError("trade is incomplete")
    return f"{base}/{quote}"


def _get_arcus_fills(address: str, start_us: int, end_us: int, limit: int) -> list[dict]:
    import httpx

    query = urlencode(
        {
            "address": address,
            "accountIndex": ARCUS_ACCOUNT_INDEX,
            "from": start_us,
            "to": end_us,
            "limit": limit,
        }
    )
    try:
        response = httpx.get(f"{ARCUS_FILLS_URL}?{query}", timeout=10.0)
    except httpx.HTTPError:
        raise RuntimeError("arcus fills unavailable") from None
    if response.status_code != 200:
        raise RuntimeError("arcus fills unavailable")
    try:
        payload = response.json()
    except ValueError:
        raise RuntimeError("arcus fills unavailable") from None
    rows = payload.get("fills") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise RuntimeError("arcus fills unavailable")
    return rows


def _strategy_name(
    exchange_client_order_id: str | None,
    side: str,
    filled_at: datetime,
    codes: dict[str, str],
    *,
    venue: str = "mexc_spot",
) -> str:
    client_id = exchange_client_order_id or ""
    if filled_at < CLASSIFIED_FROM or len(client_id) != 32:
        return UNCLASSIFIED
    kind = asset_class_of(venue)
    if kind == "futures":
        marks = ("c", "l") if side == "buy" else ("h", "f")
    elif kind == "spot":
        marks = ("b",) if side == "buy" else ("s",)
    else:
        return UNCLASSIFIED
    if client_id[10] not in marks:
        return UNCLASSIFIED
    return codes.get(client_id[:10], UNCLASSIFIED)


def _field(trade: dict, *keys: str):
    sources = [trade]
    info = trade.get("info")
    if isinstance(info, dict):
        sources.append(info)
    for source in sources:
        for key in keys:
            value = source.get(key)
            if value not in (None, ""):
                return value
    return None


def _text(value) -> str:
    if value is None:
        return ""
    return str(value)


def _number(trade: dict, *keys: str) -> Decimal | None:
    value = _field(trade, *keys)
    if isinstance(value, bool) or value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception as exc:
        raise ValueError("trade is incomplete") from exc


def _fee_parts(trade: dict) -> tuple[Decimal, str | None]:
    fee = trade.get("fee")
    if isinstance(fee, dict) and fee.get("cost") not in (None, ""):
        return Decimal(str(fee["cost"])), _asset(fee.get("currency"))
    info = trade.get("info")
    if isinstance(info, dict) and info.get("commission") not in (None, ""):
        return Decimal(str(info["commission"])), _asset(info.get("commissionAsset"))
    return Decimal("0"), None


def _asset(value) -> str | None:
    text = _text(value).strip().upper()
    return text or None


if __name__ == "__main__":
    main()
