import os
from datetime import datetime, timezone
from decimal import Decimal

from app.analytics.report import FillView, final_fill_realized, realized_for_closing_fill


def read_strategy_fills(strategy_name: str, symbol: str, venue: str) -> list[FillView] | None:
    url = os.environ.get("ANALYTICS_DATABASE_URL", "").strip()
    if not url:
        return None
    try:
        import psycopg

        from app.analytics.schema import load_fills

        with psycopg.connect(url, connect_timeout=3) as connection:
            rows = load_fills(connection)
    except Exception:
        return None
    found = []
    for row in rows:
        fill = _fill_view(row)
        if fill.strategy_name == strategy_name and fill.symbol == symbol and (fill.venue or "mexc_spot") == venue:
            found.append(fill)
    return found


def closing_realized_pnl(
    *,
    strategy_name: str,
    symbol: str,
    venue: str,
    trade_id: str,
    side: str,
    quantity: float | Decimal,
    price: float | Decimal | None,
    client_order_id: str | None = None,
    filled_at: datetime | None = None,
) -> Decimal | None:
    if price is None or price <= 0 or quantity is None or Decimal(str(quantity)) <= 0:
        return None
    history = read_strategy_fills(strategy_name, symbol, venue)
    if not history:
        return None
    qty = Decimal(str(quantity))
    key = client_order_id or trade_id
    already = [
        fill
        for fill in history
        if fill.side == side and fill.client_order_id == key and fill.quantity > 0
    ]
    if already and abs(sum((fill.quantity for fill in already), Decimal("0")) - qty) <= qty * Decimal("0.001"):
        found = final_fill_realized(history)
        parts = [found[fill.trade_id] for fill in already if fill.trade_id in found]
        if not parts:
            return None
        return sum(parts, Decimal("0"))
    notional = qty * Decimal(str(price))
    if side == "sell":
        spent, received = Decimal("0"), notional
    else:
        spent, received = notional, Decimal("0")
    closing = FillView(
        trade_id=trade_id,
        symbol=symbol,
        side=side,
        quantity=qty,
        quote_spent=spent,
        quote_received=received,
        fee=Decimal("0"),
        filled_at=filled_at or datetime.now(timezone.utc),
        strategy_name=strategy_name,
        client_order_id=client_order_id or trade_id,
        venue=venue,
    )
    return realized_for_closing_fill(history, closing)


def _fill_view(row: tuple) -> FillView:
    return FillView(
        trade_id=row[0],
        symbol=row[1],
        side=row[2],
        quantity=row[3],
        quote_spent=row[4],
        quote_received=row[5],
        fee=row[6],
        filled_at=row[7],
        strategy_name=row[8],
        client_order_id=row[9],
        fill_price=row[10],
        fee_asset=row[11],
        venue=row[12] if len(row) > 12 and row[12] else "mexc_spot",
        exchange_client_order_id=row[13] if len(row) > 13 and row[13] else None,
    )
