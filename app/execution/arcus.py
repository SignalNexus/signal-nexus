import json
import logging
import os
import time
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from threading import Lock
from urllib.parse import urlencode

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.execution.live import LiveResult
from app.execution.positions import exchange_client_order_id

MAINNET = "https://api.arcus.xyz"
ACCOUNT_INDEX = 0
WAIT_SECONDS = 5
MONTH_US = 40 * 86_400 * 1_000_000
MARKETS = {
    "ETH/USDT": (2, "ETH-USD"),
    "SOL/USDT": (3, "SOL-USD"),
    "HYPE/USDT": (6, "HYPE-USD"),
    "BNB/USDT": (62, "BNB-USD"),
}
SIDES = {"BUY": 0, "SELL": 1}
TIF = {"GTT": 0, "FOK": 1, "IOC": 2, "ALO": 3}


class ArcusError(Exception):
    pass


def signing_key(secret_hex: str) -> tuple[Ed25519PrivateKey, str]:
    try:
        raw = bytes.fromhex(secret_hex.strip())
    except ValueError as exc:
        raise ArcusError("arcus signing key is not hex") from None
    if len(raw) != 32:
        raise ArcusError("arcus signing key must be 32 bytes")
    key = Ed25519PrivateKey.from_private_bytes(raw)
    return key, key.public_key().public_bytes_raw().hex()


def canonical(fields: dict) -> str:
    return json.dumps(fields, separators=(",", ":"), sort_keys=True)


def ticks(value: Decimal, unit: Decimal) -> int:
    count = value / unit
    if count != count.to_integral_value():
        raise ArcusError("price or size is not on the market step")
    return int(count)


def snap_floor(value: Decimal, unit: Decimal) -> Decimal:
    return (value / unit).to_integral_value(rounding=ROUND_FLOOR) * unit


def snap_ceil(value: Decimal, unit: Decimal) -> Decimal:
    return (value / unit).to_integral_value(rounding=ROUND_CEILING) * unit


def protective_price(side: str, mark: Decimal, tick: Decimal) -> Decimal:
    factor = Decimal("0.95") if side == "SELL" else Decimal("1.10")
    price = snap_floor(mark * factor, tick)
    if side == "BUY" and mark > 0:
        while price > 0 and (price - mark) / mark >= Decimal("0.10"):
            price -= tick
    return price


def ask_beyond_mark(ask: Decimal, mark: Decimal) -> bool:
    if mark <= 0:
        return False
    return abs(ask - mark) / mark > Decimal("0.10")


def bid_beyond_mark(bid: Decimal, mark: Decimal) -> bool:
    if mark <= 0:
        return False
    return abs(bid - mark) / mark > Decimal("0.05")


_ACTIONS = {
    "SHORT": ("SELL", False),
    "COVER": ("BUY", True),
    "LONG": ("BUY", False),
    "FLAT": ("SELL", True),
}
logger = logging.getLogger(__name__)
_lots_guard = Lock()
_lots: dict[str, Decimal] = {}
_loaded = False


def refresh_arcus_from_store() -> None:
    global _loaded
    from app.execution.strategy_lots import load_venue

    stored = load_venue("arcus")
    with _lots_guard:
        _lots.clear()
        _lots.update(stored)
        _loaded = True


def clear_arcus_lots() -> None:
    global _loaded
    with _lots_guard:
        _lots.clear()
        _loaded = False


def arcus_client() -> "ArcusClient":
    address = os.environ.get("ARCUS_ADDRESS", "").strip()
    secret = os.environ.get("ARCUS_SIGNING_KEY", "").strip()
    if not address or not secret:
        raise ArcusError("arcus signing key is not configured")
    return ArcusClient(address, secret)


def apply_configured_leverage() -> None:
    from app.execution.router import leverage_book
    from app.venues import enabled_venues

    if "arcus" not in enabled_venues():
        return
    book = leverage_book("arcus")
    if not book:
        return
    arcus_client().apply_leverage(book)


def execute_arcus(strategy, action: str, client_order_id: str, client: "ArcusClient | None" = None) -> LiveResult:
    if action not in _ACTIONS:
        raise ArcusError("unsupported action")
    if strategy.symbol not in MARKETS:
        return LiveResult("not_sent", False, "market unavailable")
    venue = arcus_client() if client is None else client
    held = _lot(strategy.strategy_id)
    step = _order_step(venue, strategy.symbol)
    if action in ("COVER", "FLAT"):
        if held <= 0:
            return LiveResult("not_sent", False, "position already flat")
        quantity = held if step is None else snap_floor(held, step)
        if quantity <= 0:
            return LiveResult("not_sent", False, "remainder below order step")
    else:
        if held > 0 and (step is None or snap_floor(held, step) > 0):
            return LiveResult("not_sent", False, "position already open")
        quantity = _open_quantity(venue, strategy.symbol, Decimal(str(strategy.size_quote)))
        if quantity <= 0:
            return LiveResult("not_sent", False, "quantity below minimum")
    prepared = venue.prepare(action, strategy.symbol, quantity, client_order_id, strategy.strategy_id)

    def settle() -> None:
        follow = prepared["follow"]
        if follow is not None:
            follow()
        _apply_lot(strategy.strategy_id, action, prepared["holder"]["result"], client_order_id)

    if prepared["follow"] is not None:

        def finish() -> None:
            try:
                settle()
            except Exception as exc:
                from app.execution.order_executor import public_order_error
                from app.notifications.discord import order_failed, send_audit

                send_audit(order_failed(strategy.strategy_id, public_order_error(exc), venue=strategy.venue))
                return
            _report_arcus(strategy, action, prepared["holder"]["result"], client_order_id)

        return LiveResult("accepted", True, follow_up=finish)
    settle()
    closed = prepared["holder"]["result"]
    filled = closed.get("filled") or Decimal("0")
    if not isinstance(filled, Decimal):
        filled = Decimal(str(filled))
    return LiveResult(
        "accepted",
        True,
        realized=_arcus_realized(strategy, action, filled, closed, client_order_id),
    )


def _place_fields(
    *,
    address: str,
    market_id: int,
    side: str,
    tif: str,
    price: Decimal,
    quantity: Decimal,
    reduce_only: bool,
    client_id: str,
    good_til_us: int,
    now_ns: int,
    tick: Decimal,
    step: Decimal,
) -> dict:
    fields = {
        "ad": address.lower(),
        "ai": ACCOUNT_INDEX,
        "ct": now_ns,
        "g": good_til_us * 1000,
        "m": market_id,
        "op": 1,
        "p": ticks(price, tick),
        "q": ticks(quantity, step),
        "r": 1 if reduce_only else 0,
        "s": SIDES[side],
        "t": TIF[tif],
        "v": 1,
    }
    if client_id:
        fields["c"] = client_id
    return fields


class ArcusClient:
    def __init__(self, address: str, secret_hex: str, transport=None, sleeper=None, clock=None):
        self.base = MAINNET
        self.address = address
        self.key, self.public = signing_key(secret_hex)
        self.transport = transport or _http
        self.sleeper = sleeper or time.sleep
        self.clock = clock or time.time_ns

    def send(self, action: str, symbol: str, quantity: Decimal, client_order_id: str, strategy_id: str) -> dict:
        prepared = self.prepare(action, symbol, quantity, client_order_id, strategy_id)
        follow = prepared["follow"]
        if follow is not None:
            follow()
        return prepared["holder"]["result"]

    def apply_leverage(self, book: dict[str, int]) -> None:
        for symbol in sorted(book):
            if symbol not in MARKETS:
                raise ArcusError("market unavailable")
            market_id, _name = MARKETS[symbol]
            self._set_leverage(market_id, book[symbol])

    def prepare(self, action: str, symbol: str, quantity: Decimal, client_order_id: str, strategy_id: str) -> dict:
        if action not in _ACTIONS:
            raise ArcusError("unsupported action")
        side, reduce_only = _ACTIONS[action]
        market_id, name = MARKETS[symbol]
        spec = self._market(name)
        book = self._bbo(name)
        limit_id = exchange_client_order_id(strategy_id, client_order_id, action, venue="arcus")
        if action == "COVER" and book[1] is not None and ask_beyond_mark(book[1], spec["mark"]):
            return _finished(self._leave_on_ask(market_id, spec, side, quantity, limit_id, book[1]))
        if action == "FLAT" and book[0] is not None and bid_beyond_mark(book[0], spec["mark"]):
            return _finished(self._leave_on_bid(market_id, spec, side, quantity, limit_id, book[0]))
        raw_touch = book[1] if side == "SELL" else book[0]
        touch = None if raw_touch is None else (snap_ceil(raw_touch, spec["tick"]) if side == "SELL" else snap_floor(raw_touch, spec["tick"]))
        crossed = book[0] is not None and book[1] is not None and book[0] >= book[1]
        if touch is None or crossed:
            market = self._market_order(action, strategy_id, client_order_id, name, market_id, spec, side, quantity, reduce_only)
            filled = self._filled_size(market)
            market_key = exchange_client_order_id(strategy_id, client_order_id, action, "remainder", "arcus")
            quoted = None
            if filled > 0 and isinstance(market, dict) and market.get("orderId"):
                quoted = _quoted_price(self._read(str(market["orderId"])))
            return _finished(
                {
                    "limit_order_id": None,
                    "filled": filled,
                    "remaining": quantity - filled,
                    "market": market,
                    "fills": [(market_key, filled)] if filled > 0 else [],
                    "prices": [(filled, quoted)] if filled > 0 and quoted is not None else [],
                }
            )
        placed = self._place(market_id, spec, side, "GTT", touch, quantity, reduce_only, limit_id)
        holder = {
            "result": {
                "limit_order_id": placed["orderId"],
                "filled": Decimal("0"),
                "remaining": quantity,
                "market": None,
            }
        }

        def follow() -> None:
            self.sleeper(WAIT_SECONDS)
            status = self._read(placed["orderId"])
            remaining = Decimal(str(status.get("remainingSize") or quantity))
            filled = Decimal(str(status.get("filledSize") or "0"))
            if remaining > 0:
                self._cancel(market_id, placed["orderId"])
                status = self._read(placed["orderId"])
                remaining = Decimal(str(status.get("remainingSize") or "0"))
                filled = Decimal(str(status.get("filledSize") or filled))
            market = None
            limit_filled = filled
            fills = [(limit_id, limit_filled)] if limit_filled > 0 else []
            prices = [(limit_filled, _quoted_price(status))] if limit_filled > 0 else []
            if remaining > 0:
                market = self._market_order(
                    action, strategy_id, client_order_id, name, market_id, spec, side, remaining, reduce_only
                )
                market_status = {}
                market_filled = Decimal("0")
                if isinstance(market, dict) and market.get("orderId"):
                    market_status = self._read(str(market["orderId"]))
                    market_filled = Decimal(str(market_status.get("filledSize") or "0"))
                filled = limit_filled + market_filled
                remaining = max(quantity - filled, Decimal("0"))
                if market_filled > 0:
                    market_key = exchange_client_order_id(
                        strategy_id, client_order_id, action, "remainder", "arcus"
                    )
                    fills.append((market_key, market_filled))
                    prices.append((market_filled, _quoted_price(market_status)))
            holder["result"] = {
                "limit_order_id": placed["orderId"],
                "filled": filled,
                "remaining": remaining,
                "market": market,
                "fills": fills,
                "prices": prices,
            }

        return {"follow": follow, "holder": holder}

    def _leave_on_ask(self, market_id, spec, side, quantity, client_order_id, ask: Decimal) -> dict:
        return self._leave_limit(market_id, spec, side, quantity, client_order_id, snap_ceil(ask, spec["tick"]))

    def _leave_on_bid(self, market_id, spec, side, quantity, client_order_id, bid: Decimal) -> dict:
        return self._leave_limit(market_id, spec, side, quantity, client_order_id, snap_floor(bid, spec["tick"]))

    def _leave_limit(self, market_id, spec, side, quantity, client_order_id, price: Decimal) -> dict:
        placed = self._place(market_id, spec, side, "GTT", price, quantity, True, client_order_id)
        status = self._read(placed["orderId"])
        remaining = Decimal(str(status.get("remainingSize") or quantity))
        filled = Decimal(str(status.get("filledSize") or "0"))
        quoted = _quoted_price(status)
        return {
            "limit_order_id": placed["orderId"],
            "filled": filled,
            "remaining": remaining,
            "market": None,
            "prices": [(filled, quoted)] if filled > 0 and quoted is not None else [],
        }

    def _filled_size(self, accepted: dict | None) -> Decimal:
        if not accepted or not accepted.get("orderId"):
            return Decimal("0")
        status = self._read(accepted["orderId"])
        return Decimal(str(status.get("filledSize") or "0"))

    def _place(self, market_id, spec, side, tif, price, quantity, reduce_only, client_id):
        now_ns = self.clock()
        good_til = now_ns // 1000 + MONTH_US
        size = snap_floor(quantity, spec["step"])
        if size <= 0:
            raise ArcusError("quantity below the market step")
        fields = _place_fields(
            address=self.address,
            market_id=market_id,
            side=side,
            tif=tif,
            price=price,
            quantity=size,
            reduce_only=reduce_only,
            client_id=client_id,
            good_til_us=good_til,
            now_ns=now_ns,
            tick=spec["tick"],
            step=spec["step"],
        )
        body = {
            "address": self.address,
            "accountIndex": ACCOUNT_INDEX,
            "marketId": market_id,
            "orderSide": side,
            "orderType": "LIMIT" if tif == "GTT" else "MARKET",
            "quantity": format(size, "f"),
            "price": format(price, "f"),
            "timeInForce": tif,
            "goodTilTime": str(good_til),
            "timestamp": now_ns,
        }
        if client_id:
            body["clientId"] = client_id
        body["reduceOnly"] = reduce_only
        accepted = self._post("/v1/placeOrder", fields, body)
        if not accepted.get("orderId"):
            raise ArcusError("order id missing")
        return accepted

    def _market_order(self, action, strategy_id, client_order_id, name, market_id, spec, side, quantity, reduce_only):
        mark = self._market(name)["mark"]
        if mark <= 0:
            raise ArcusError("mark price missing")
        price = protective_price(side, mark, spec["tick"])
        client_id = exchange_client_order_id(strategy_id, client_order_id, action, "remainder", "arcus")
        return self._place(market_id, spec, side, "IOC", price, quantity, reduce_only, client_id)

    def _cancel(self, market_id, order_id):
        now_ns = self.clock()
        fields = {
            "ad": self.address.lower(),
            "ai": ACCOUNT_INDEX,
            "ct": now_ns,
            "id": order_id,
            "m": market_id,
            "op": 2,
            "v": 1,
        }
        body = {
            "address": self.address,
            "accountIndex": ACCOUNT_INDEX,
            "marketId": market_id,
            "kind": "orderId",
            "orderId": order_id,
            "timestamp": now_ns,
        }
        self._post("/v1/cancelOrder", fields, body)

    def _set_leverage(self, market_id: int, leverage: int) -> None:
        now_ns = self.clock()
        body = {
            "address": self.address,
            "accountIndex": ACCOUNT_INDEX,
            "isolated": True,
            "leverage": leverage,
            "marketId": market_id,
        }
        message = f"{now_ns}setLeverage{canonical(body)}"
        signature = self.key.sign(message.encode()).hex()
        status, accepted = self.transport(
            "POST",
            f"{self.base}/v1/setLeverage?{urlencode({'address': self.address})}",
            body,
            {
                "X-API-Key": self.public,
                "X-Timestamp": str(now_ns),
                "X-Signature": signature,
                "Content-Type": "application/json",
            },
        )
        if status not in (200, 202) or not isinstance(accepted, dict) or accepted.get("status") == "REJECTED":
            reason = ""
            if isinstance(accepted, dict):
                reason = str(accepted.get("rejectReason") or accepted.get("error") or accepted.get("code") or "")
            detail = f"{status} {reason}".strip()
            raise ArcusError(f"arcus leverage was not accepted {detail}".rstrip())

    def _read(self, order_id: str) -> dict:
        url = f"{self.base}/v1/order/{order_id}?{urlencode({'address': self.address, 'accountIndex': ACCOUNT_INDEX})}"
        headers = {"X-API-Key": self.public}
        for attempt in range(5):
            status, payload = self.transport("GET", url, None, headers)
            if status == 200 and isinstance(payload, dict):
                return payload
            if attempt < 4:
                time.sleep(0.25)
        raise ArcusError("order status unavailable")

    def _market(self, name: str) -> dict:
        status, payload = self.transport("GET", f"{self.base}/v1/markets?market={name}", None, None)
        if status != 200 or not isinstance(payload, dict):
            raise ArcusError("market unavailable")
        rows = payload.get("markets") or []
        row = rows[0] if rows else None
        if not isinstance(row, dict):
            raise ArcusError("market unavailable")
        mark = Decimal(str(row.get("markPrice") or "0"))
        return {"tick": Decimal(str(row["tickSize"])), "step": Decimal(str(row["stepSize"])), "mark": mark}

    def _bbo(self, name: str) -> tuple[Decimal | None, Decimal | None]:
        status, payload = self.transport("GET", f"{self.base}/v1/bbo/{name}", None, None)
        if status != 200 or not isinstance(payload, dict):
            return None, None
        return _level(payload.get("bestBid")), _level(payload.get("bestAsk"))

    def _post(self, path: str, fields: dict, body: dict) -> dict:
        payload = canonical(fields)
        signature = self.key.sign(payload.encode()).hex()
        status, accepted = self.transport(
            "POST",
            f"{self.base}{path}?{urlencode({'address': self.address})}",
            body,
            {
                "X-API-Key": self.public,
                "X-Timestamp": str(fields["ct"]),
                "X-Signature": signature,
                "Content-Type": "application/json",
            },
        )
        if status not in (200, 202) or not isinstance(accepted, dict):
            raise ArcusError(f"arcus order was not accepted {_reject_reason(status, accepted)}")
        return accepted


def _reject_reason(status: int, accepted) -> str:
    token = ""
    if isinstance(accepted, dict):
        for key in ("errorType", "rejectReason", "code"):
            value = accepted.get(key)
            if isinstance(value, str) and value and len(value) <= 40 and value.replace("_", "").isalnum():
                token = value
                break
    return f"{status} {token}".strip()


def _level(value) -> Decimal | None:
    if not isinstance(value, dict) or not value.get("price"):
        return None
    price = Decimal(str(value["price"]))
    if price <= 0:
        return None
    return price


def _http(method: str, url: str, body, headers) -> tuple[int, dict]:
    try:
        response = httpx.request(method, url, json=body, headers=headers, timeout=10.0)
    except httpx.HTTPError as exc:
        raise ArcusError("arcus request failed") from None
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    return response.status_code, payload if isinstance(payload, dict) else {}


def _finished(result: dict) -> dict:
    return {"follow": None, "holder": {"result": result}}


def _quoted_price(status: dict) -> Decimal | None:
    if not isinstance(status, dict):
        return None
    for key in ("avgPrice", "averagePrice", "avgFillPrice", "dealAvgPrice"):
        raw = status.get(key)
        if raw in (None, ""):
            continue
        try:
            price = Decimal(str(raw))
        except Exception:
            continue
        if price > 0:
            return price
    return None


def _combined_price(prices) -> float | None:
    quantity = Decimal("0")
    cost = Decimal("0")
    for filled, price in prices:
        amount = filled if isinstance(filled, Decimal) else Decimal(str(filled))
        if amount <= 0 or not isinstance(price, Decimal) or price <= 0:
            continue
        quantity += amount
        cost += amount * price
    if quantity <= 0:
        return None
    return float(cost / quantity)


def _report_arcus(strategy, action: str, result: dict, client_order_id: str) -> None:
    from app.notifications.discord import order_failed, order_success, send_audit

    filled = result.get("filled") or Decimal("0")
    if not isinstance(filled, Decimal):
        filled = Decimal(str(filled))
    if filled <= 0:
        send_audit(order_failed(strategy.strategy_id, "filled base missing", venue=strategy.venue))
        return
    send_audit(
        order_success(
            strategy.strategy_id,
            strategy.symbol,
            action,
            float(strategy.size_quote),
            "closed",
            _combined_price(result.get("prices") or []),
            venue=strategy.venue,
            realized=_arcus_realized(strategy, action, filled, result, client_order_id),
        )
    )


def _arcus_realized(strategy, action: str, filled: Decimal, result: dict, client_order_id: str) -> Decimal | None:
    if action not in ("COVER", "FLAT"):
        return None
    from app.analytics.history import closing_realized_pnl

    return closing_realized_pnl(
        strategy_name=strategy.strategy_id,
        symbol=strategy.symbol,
        venue=strategy.venue,
        trade_id=f"notify:{client_order_id}",
        side="buy" if action == "COVER" else "sell",
        quantity=filled,
        price=_combined_price(result.get("prices") or []),
        client_order_id=client_order_id,
    )


def _connect():
    url = os.environ.get("ANALYTICS_DATABASE_URL", "").strip()
    if not url:
        return None
    import psycopg

    return psycopg.connect(url)


def _ensure_loaded_locked() -> None:
    global _loaded
    if _loaded:
        return
    from app.execution.strategy_lots import configured, load_venue

    if not configured():
        _loaded = True
        return
    try:
        loaded = load_venue("arcus")
    except Exception:
        raise ArcusError("position history unavailable") from None
    _lots.clear()
    _lots.update(loaded)
    _loaded = True


def _store_lot(strategy_id: str, quantity: Decimal) -> None:
    try:
        connection = _connect()
    except Exception:
        logger.warning("arcus lot was not stored")
        return
    if connection is None:
        return
    try:
        from app.execution.strategy_lots import set_quantity

        set_quantity("arcus", strategy_id, quantity)
    except Exception:
        logger.warning("arcus lot was not stored")


def _order_step(client, symbol: str) -> Decimal | None:
    market = getattr(client, "_market", None)
    if not callable(market) or symbol not in MARKETS:
        return None
    try:
        _market_id, name = MARKETS[symbol]
        step = market(name)["step"]
    except Exception:
        return None
    if not isinstance(step, Decimal) or step <= 0:
        return None
    return step


def _lot(strategy_id: str) -> Decimal:
    with _lots_guard:
        _ensure_loaded_locked()
        return _lots.get(strategy_id, Decimal("0"))


def _apply_lot(strategy_id: str, action: str, result: dict, client_order_id: str | None = None) -> None:
    fills = result.get("fills")
    if fills:
        from app.execution.strategy_lots import LotStoreError, configured, note_fill

        if configured():
            updated = Decimal("0")
            try:
                for order_key, amount in fills:
                    updated = note_fill(
                        "arcus",
                        str(order_key),
                        strategy_id,
                        action in ("COVER", "FLAT"),
                        amount if isinstance(amount, Decimal) else Decimal(str(amount)),
                    )
            except LotStoreError:
                logger.warning("arcus lot was not stored")
                fills = None
            else:
                with _lots_guard:
                    _ensure_loaded_locked()
                    if updated <= 0:
                        _lots.pop(strategy_id, None)
                    else:
                        _lots[strategy_id] = updated
                return
    filled = result.get("filled") or Decimal("0")
    if not isinstance(filled, Decimal):
        filled = Decimal(str(filled))
    with _lots_guard:
        _ensure_loaded_locked()
        current = _lots.get(strategy_id, Decimal("0"))
        if action in ("LONG", "SHORT"):
            if filled <= 0:
                return
            updated = current + filled
        else:
            updated = current - filled
        if updated <= 0:
            _lots.pop(strategy_id, None)
            updated = Decimal("0")
        else:
            _lots[strategy_id] = updated
        _store_lot(strategy_id, updated)


def _open_quantity(client: ArcusClient, symbol: str, notional: Decimal) -> Decimal:
    _market_id, name = MARKETS[symbol]
    spec = client._market(name)
    mark = spec["mark"]
    if mark <= 0:
        return Decimal("0")
    return snap_floor(notional / mark, spec["step"])
