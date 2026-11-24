"""Stop a new entry after realized profit passes the average order size.

The average is the mean size_quote of every enabled deployment for that
symbol and direction. A losing close clears the lock and the running total.
A flat book does not.
"""

import logging
from collections import defaultdict
from decimal import Decimal

from app.analytics.report import _arcus_long, _risex_sides, fill_view_from_row, reconstruct
from app.execution.router import load_strategies
from app.venues import is_futures

logger = logging.getLogger(__name__)

_ENTRY = {"BUY", "LONG", "SHORT"}


def entry_block_reason(strategy, action: str) -> str | None:
    if action not in _ENTRY:
        return None
    try:
        if campaign_is_locked(strategy.symbol, strategy.side):
            return "profit lock"
    except Exception:
        logger.warning("profit lock was not read")
    return None


def average_order_size(symbol: str, side: str) -> Decimal | None:
    base = _base(symbol)
    amounts = []
    for strategy in load_strategies().values():
        if _base(strategy.symbol) != base or strategy.side != side:
            continue
        for deployment in strategy.deployments:
            if deployment.enabled and deployment.size_quote > 0:
                amounts.append(Decimal(str(deployment.size_quote)))
    if not amounts:
        return None
    return sum(amounts, Decimal("0")) / Decimal(len(amounts))


def campaign_is_locked(symbol: str, side: str) -> bool:
    limit = average_order_size(symbol, side)
    if limit is None:
        return False
    from app.execution.strategy_lots import configured, connect

    if not configured():
        return False
    connection = connect()
    if connection is None:
        return False
    try:
        from app.analytics.schema import load_fills

        rows = load_fills(connection)
    finally:
        connection.close()
    fills = [fill_view_from_row(row) for row in rows]
    closed, _opens = reconstruct(fills)
    sides = _trade_sides(fills)
    gains = [
        trade.realized
        for trade in sorted(closed, key=lambda item: (item.closed_at, item.final_trade_id))
        if _base(trade.symbol) == _base(symbol) and sides.get((trade.strategy_name, trade.symbol, trade.venue), "long") == side
    ]
    return locked_after(gains, limit)


def locked_after(gains: list[Decimal], limit: Decimal) -> bool:
    campaign = Decimal("0")
    locked = False
    for gain in gains:
        campaign += gain
        if not locked and campaign >= limit:
            locked = True
        if locked and gain < 0:
            locked = False
            campaign = Decimal("0")
    return locked


def _trade_sides(fills) -> dict[tuple[str, str, str], str]:
    grouped = defaultdict(list)
    for fill in fills:
        grouped[(fill.strategy_name, fill.symbol, fill.venue)].append(fill)
    risex = _risex_sides(fills, None)
    sides = {}
    for key, rows in grouped.items():
        _name, _symbol, venue = key
        short = bool(is_futures(venue) and not _arcus_long(rows, risex))
        sides[key] = "short" if short else "long"
    return sides


def _base(symbol: str) -> str:
    return symbol.split("/", 1)[0].upper()
