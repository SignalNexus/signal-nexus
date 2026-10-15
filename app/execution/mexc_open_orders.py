from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal

from app.execution.exchange import futures_client, mexc_client
from app.execution.positions import strategy_codes
from app.execution.router import load_strategies
from app.portal_model import orders_view


def open_orders_payload(now: datetime | None = None) -> dict:
    fetched_at = now or datetime.now(timezone.utc)
    with ThreadPoolExecutor(max_workers=3) as pool:
        spot_call = pool.submit(_spot_open_orders, fetched_at)
        futures_call = pool.submit(_futures_open_orders, fetched_at)
        arcus_call = pool.submit(_arcus_open_orders, fetched_at)
        spot = spot_call.result()
        futures = futures_call.result()
        arcus = arcus_call.result()
    return {
        "fetched_at": fetched_at.isoformat(),
        "spot": _json_view(spot),
        "futures": _json_view(futures),
        "arcus": _json_view(arcus),
    }


def restore_open_orders(payload: dict) -> tuple[dict | None, datetime | None]:
    fetched_at = datetime.fromisoformat(str(payload["fetched_at"]))
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    spot = _restore_view(payload.get("spot"))
    futures = _restore_view(payload.get("futures"))
    if spot is None and futures is None and "arcus" not in payload:
        return None, None
    restored = {"spot": spot, "futures": futures}
    if "arcus" in payload:
        restored["arcus"] = _restore_view(payload.get("arcus"))
    return restored, fetched_at


def _arcus_open_orders(fetched_at: datetime):
    try:
        from app.execution.arcus_read import arcus_open_orders

        return arcus_open_orders(fetched_at)
    except Exception:
        return None


def _spot_open_orders(fetched_at: datetime):
    try:
        exchange = mexc_client()
        try:
            raw = _order_rows(exchange.spotPrivateGetOpenOrders({}))
        except Exception:
            symbols = sorted(
                {
                    strategy.symbol
                    for strategy in load_strategies().values()
                    for deployment in strategy.deployments
                    if deployment.enabled and deployment.venue == "mexc_spot"
                }
            )
            raw = []
            with ThreadPoolExecutor(max_workers=8) as pool:
                for batch in pool.map(_spot_symbol_orders, symbols):
                    raw.extend(batch)
        codes = strategy_codes([strategy.strategy_id for strategy in load_strategies().values()])
        return orders_view([_unified_order(row) for row in raw], codes, fetched_at)
    except Exception:
        return None


def _spot_symbol_orders(symbol: str) -> list:
    try:
        return _order_rows(mexc_client().spotPrivateGetOpenOrders({"symbol": symbol.replace("/", "")}))
    except Exception:
        return []


def _futures_open_orders(fetched_at: datetime):
    try:
        payload = futures_client().contractPrivateGetOrderListOpenOrders({"page_size": 100})
        raw = _order_rows(payload)
        codes = strategy_codes([strategy.strategy_id for strategy in load_strategies().values()])
        return orders_view([_unified_order(row) for row in raw], codes, fetched_at)
    except Exception:
        return None


def _order_rows(payload) -> list:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list) and payload.get("success") is not False:
            return [row for row in data if isinstance(row, dict)]
    raise RuntimeError("orders were not read")


def _unified_order(row: dict) -> dict:
    amount = row.get("origQty", row.get("vol"))
    filled = row.get("executedQty", row.get("dealVol"))
    client_id = row.get("clientOrderId") or row.get("externalOid") or ""
    timestamp = row.get("time") or row.get("createTime")
    return {
        "id": str(row.get("orderId") or row.get("id") or ""),
        "symbol": _slash_symbol(str(row.get("symbol") or "")),
        "side": str(row.get("side") or ""),
        "type": row.get("type") or row.get("orderType") or "",
        "price": row.get("price"),
        "amount": amount,
        "filled": filled,
        "timestamp": None if timestamp in (None, "") else int(timestamp),
        "clientOrderId": client_id,
        "info": row,
    }


def _slash_symbol(symbol: str) -> str:
    if "/" in symbol:
        return symbol.split(":", 1)[0]
    if symbol.endswith("_USDT"):
        return f"{symbol[:-5]}/USDT"
    if symbol.endswith("USDT") and len(symbol) > 4:
        return f"{symbol[:-4]}/USDT"
    return symbol


def _json_view(view: dict | None) -> dict | None:
    if view is None:
        return None
    rows = []
    for row in view["rows"]:
        copied = dict(row)
        created = copied["created"]
        copied["created"] = None if created is None else created.isoformat()
        for key in ("price", "amount", "remaining"):
            value = copied[key]
            copied[key] = None if value is None else format(value, "f")
        rows.append(copied)
    return {**view, "rows": rows}


def _restore_view(view: dict | None) -> dict | None:
    if not isinstance(view, dict):
        return None
    rows = []
    for row in view.get("rows") or []:
        if not isinstance(row, dict):
            continue
        copied = dict(row)
        created = copied.get("created")
        if created:
            parsed = datetime.fromisoformat(str(created))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            copied["created"] = parsed
        else:
            copied["created"] = None
        for key in ("price", "amount", "remaining"):
            value = copied.get(key)
            copied[key] = None if value in (None, "") else Decimal(str(value))
        rows.append(copied)
    restored = dict(view)
    restored["rows"] = rows
    return restored
