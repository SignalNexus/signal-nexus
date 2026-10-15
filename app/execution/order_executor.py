from decimal import Decimal, ROUND_DOWN

# Without MX deduction MEXC takes the buy fee from the coin received.
TAKER_FEE_RATE = 0.0005


def _symbol_info(exchange, symbol: str) -> dict:
    load = getattr(exchange, "load_markets", None)
    markets = getattr(exchange, "markets", None)
    if callable(load) and not markets:
        load()
        markets = getattr(exchange, "markets", None)
    if not isinstance(markets, dict):
        return {}
    market = markets.get(symbol)
    if not isinstance(market, dict):
        return {}
    info = market.get("info")
    return info if isinstance(info, dict) else {}


def _decimal_places(info: dict, key: str) -> int | None:
    raw = info.get(key)
    if isinstance(raw, bool) or raw in (None, ""):
        return None
    try:
        places = int(raw)
    except (TypeError, ValueError):
        return None
    if places < 0 or places > 18:
        return None
    return places


def floor_to_places(value: float, places: int) -> str:
    quantum = Decimal(1).scaleb(-places)
    floored = Decimal(str(value)).quantize(quantum, rounding=ROUND_DOWN)
    return format(floored, "f")


def sized_amount(exchange, symbol: str, amount: float) -> float | str:
    places = _decimal_places(_symbol_info(exchange, symbol), "baseAssetPrecision")
    if places is None:
        return amount
    return floor_to_places(amount, places)


def sized_price(exchange, symbol: str, price: float) -> float | str:
    places = _decimal_places(_symbol_info(exchange, symbol), "quoteAssetPrecision")
    if places is None:
        return price
    return floor_to_places(price, places)


def place_market_order(
    exchange,
    symbol: str,
    action: str,
    size_quote: float,
    *,
    client_order_id: str,
    base_amount: float | None = None,
) -> tuple[str, float, float | None, float]:
    exchange_id = {"clientOrderId": client_order_id, "newClientOrderId": client_order_id}
    if action == "BUY":
        created = exchange.create_order(
            symbol,
            "market",
            "buy",
            None,
            None,
            {"cost": size_quote, "quoteOrderQty": size_quote, **exchange_id},
        )
    elif action == "SELL":
        if base_amount is None or base_amount <= 0:
            raise RuntimeError("bought quantity missing")
        base_amount = sized_amount(exchange, symbol, base_amount)
        if Decimal(str(base_amount)) <= 0:
            raise RuntimeError("bought quantity missing")
        created = exchange.create_order(
            symbol,
            "market",
            "sell",
            base_amount,
            None,
            exchange_id,
        )
    else:
        raise RuntimeError("unsupported action")
    order_id = created.get("id")
    if not order_id:
        raise RuntimeError("order id missing")
    fetched = exchange.fetch_order(order_id, symbol)
    status = fetched.get("status")
    if not status:
        raise RuntimeError("order status missing")
    gross = _filled_base(fetched)
    filled = gross
    if action == "BUY" and filled > 0:
        filled = max(0.0, filled - _base_fee(exchange, order_id, symbol, filled))
    return str(status), filled, average_price(fetched), gross


def _base_fee(exchange, order_id: str, symbol: str, filled: float) -> float:
    base = symbol.split("/")[0]
    try:
        trades = exchange.fetch_order_trades(order_id, symbol) or []
    except Exception:
        trades = []
    fees = [base_fee_of(trade, base) for trade in trades]
    if not trades or any(fee is None for fee in fees):
        return filled * TAKER_FEE_RATE
    return sum(fees)


def base_fee_of(trade: dict, base: str) -> float | None:
    fee = trade.get("fee")
    if isinstance(fee, dict) and fee.get("currency"):
        currency, cost = fee.get("currency"), fee.get("cost")
    else:
        info = trade.get("info") if isinstance(trade.get("info"), dict) else {}
        currency, cost = info.get("commissionAsset"), info.get("commission")
    if not currency or cost in (None, ""):
        return None
    return float(cost) if str(currency).upper() == base.upper() else 0.0


def public_order_error(exc: Exception) -> str:
    text = str(exc)
    lowered = text.lower()
    if "secret" in lowered or "apikey" in lowered or "api_key" in lowered:
        return "order failed"
    return text[:300]


def top_of_book(exchange, symbol: str) -> tuple[float | None, float | None]:
    book = exchange.fetch_order_book(symbol, 5) or {}
    bids = book.get("bids") or []
    asks = book.get("asks") or []
    bid = float(bids[0][0]) if bids else None
    ask = float(asks[0][0]) if asks else None
    if bid is not None and bid <= 0:
        bid = None
    if ask is not None and ask <= 0:
        ask = None
    return bid, ask


def base_amount_for_quote(exchange, symbol: str, quote: float, price: float) -> float:
    raw = quote / price
    sized = sized_amount(exchange, symbol, raw)
    if isinstance(sized, str):
        return float(sized)
    precise = getattr(exchange, "amount_to_precision", None)
    if precise is None:
        return raw
    return float(precise(symbol, raw))


def place_limit_order(
    exchange,
    symbol: str,
    side: str,
    amount: float,
    price: float,
    *,
    client_order_id: str,
) -> str:
    if amount <= 0 or price <= 0:
        raise RuntimeError("limit amount missing")
    amount = sized_amount(exchange, symbol, amount)
    price = sized_price(exchange, symbol, price)
    if isinstance(price, float):
        precise = getattr(exchange, "price_to_precision", None)
        if precise is not None:
            price = float(precise(symbol, price))
    if Decimal(str(amount)) <= 0 or Decimal(str(price)) <= 0:
        raise RuntimeError("limit amount missing")
    created = exchange.create_order(
        symbol,
        "limit",
        side,
        amount,
        price,
        {"clientOrderId": client_order_id, "newClientOrderId": client_order_id},
    )
    order_id = created.get("id")
    if not order_id:
        raise RuntimeError("order id missing")
    return str(order_id)


def settle_limit(
    exchange, order_id: str, symbol: str, ordered: float
) -> tuple[float, float, float | None, float]:
    order = _refresh_after_cancel(exchange, order_id, symbol)
    status = str(order.get("status") or "").lower()
    if status not in ("closed", "filled", "canceled", "cancelled"):
        raise RuntimeError("limit still open")
    filled = _filled_base(order)
    net = max(0.0, filled - _base_fee(exchange, order_id, symbol, filled))
    remaining = max(0.0, ordered - filled)
    return net, remaining, average_price(order), filled


def _refresh_after_cancel(exchange, order_id: str, symbol: str) -> dict:
    order = exchange.fetch_order(order_id, symbol) or {}
    if _terminal(order):
        return order
    try:
        exchange.cancel_order(order_id, symbol)
    except Exception:
        pass
    order = exchange.fetch_order(order_id, symbol) or order
    if _terminal(order):
        return order
    try:
        exchange.cancel_order(order_id, symbol)
    except Exception:
        pass
    return exchange.fetch_order(order_id, symbol) or order


def _terminal(order: dict) -> bool:
    return str(order.get("status") or "").lower() in ("closed", "filled", "canceled", "cancelled")


def average_price(order: dict) -> float | None:
    sources = [order]
    info = order.get("info")
    if isinstance(info, dict):
        sources.append(info)
    for source in sources:
        for key in ("average", "avgPrice"):
            number = _positive(source.get(key))
            if number is not None:
                return number
    filled = _filled_base(order)
    cost = _positive(order.get("cost"))
    if filled > 0 and cost is not None:
        return cost / filled
    return None


def combined_average(parts: list[tuple[float, float | None]]) -> float | None:
    quantity = 0.0
    cost = 0.0
    for gross, price in parts:
        if gross > 0 and price is not None and price > 0:
            quantity += gross
            cost += gross * price
    if quantity <= 0:
        return None
    return cost / quantity


def _positive(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    return number


def _filled_base(order: dict) -> float:
    for source in (order, order.get("info") if isinstance(order.get("info"), dict) else {}):
        for key in ("filled", "executedQty"):
            value = source.get(key)
            if value not in (None, ""):
                return float(value)
    return 0.0
