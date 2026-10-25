import os
from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import urlencode

import httpx

from app.execution.positions import strategy_codes
from app.execution.router import load_strategies
from app.portal_model import hold_label

ACCOUNT_INDEX = 0
ORIGIN = "https://api.arcus.xyz"


def arcus_open_orders(now: datetime) -> dict | None:
    status, body = _read("/v1/openOrders")
    if status != 200 or body is None:
        return None
    rows = body.get("orders")
    if not isinstance(rows, list):
        return None
    codes = strategy_codes([strategy.strategy_id for strategy in load_strategies().values()])
    prepared = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        prepared.append(_order_row(row, codes, now))
    prepared.sort(key=lambda item: (item["created"] is None, item["created"] or now, item["order_id"]))
    return {
        "rows": prepared,
        "count": len(prepared),
        "buy": 0,
        "sell": 0,
        "unclassified": sum(1 for item in prepared if item["unclassified"]),
    }


def arcus_balance() -> dict | None:
    status, body = _read("/v1/account")
    if status == 404:
        return {"equity": Decimal("0"), "free": Decimal("0"), "margin": Decimal("0"), "positions": 0}
    if status != 200 or body is None:
        return None
    try:
        equity = Decimal(str(body["equity"]))
        free = Decimal(str(body["freeCollateral"]))
    except (KeyError, ValueError, ArithmeticError):
        return None
    positions = body.get("positions")
    return {
        "equity": equity,
        "free": free,
        "margin": equity - free,
        "positions": len(positions) if isinstance(positions, dict) else 0,
    }


def _read(path: str) -> tuple[int, dict | None]:
    address = os.environ.get("ARCUS_ADDRESS", "").strip() or os.environ.get("ANALYTICS_ARCUS_ADDRESS", "").strip()
    if not address:
        return 0, None
    query = urlencode({"address": address, "accountIndex": ACCOUNT_INDEX})
    try:
        response = httpx.get(f"{ORIGIN}{path}?{query}", timeout=8.0)
    except httpx.HTTPError:
        return 0, None
    try:
        body = response.json()
    except ValueError:
        body = None
    if not isinstance(body, dict):
        body = None
    return response.status_code, body


def _order_row(row: dict, codes: dict[str, str], now: datetime) -> dict:
    client_id = str(row.get("clientId") or "")
    created = _created(row.get("createdAt"))
    strategy = _strategy_name(client_id, codes)
    amount = _decimal(row.get("originalSize"))
    remaining = _decimal(row.get("remainingSize"))
    return {
        "created": created,
        "order_id": str(row.get("orderId") or ""),
        "strategy_name": strategy,
        "symbol": _symbol(str(row.get("marketDisplayName") or "")),
        "side": _side(str(row.get("side") or ""), bool(row.get("reduceOnly")), client_id),
        "order_type": str(row.get("type") or "").upper(),
        "price": _decimal(row.get("price")),
        "amount": amount,
        "remaining": remaining,
        "elapsed": None if created is None else hold_label(now - created),
        "unclassified": strategy == "未分類",
    }


def _strategy_name(client_id: str, codes: dict[str, str]) -> str:
    if len(client_id) != 32 or client_id[10] not in {"b", "s", "h", "c", "l", "f"}:
        return "未分類"
    return codes.get(client_id[:10], "未分類")


def _side(side: str, reduce_only: bool, client_id: str) -> str:
    if len(client_id) == 32:
        mark = {"h": "SHORT", "c": "COVER", "l": "LONG", "f": "FLAT"}.get(client_id[10])
        if mark:
            return mark
    if reduce_only:
        return "FLAT" if side.upper() == "SELL" else "COVER"
    return "SHORT" if side.upper() == "SELL" else "LONG"


def _symbol(name: str) -> str:
    if "-" not in name:
        return name
    base, quote = name.split("-", 1)
    return f"{base}/{quote}"


def _created(value) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if number < 10**14:
        return None
    return datetime.fromtimestamp(number / 1_000_000, tz=timezone.utc)


def _decimal(value) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (ValueError, ArithmeticError):
        return None
