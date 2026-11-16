"""Shared execution decisions. Adapters translate venue payloads. They do not invent fills."""

from decimal import Decimal

ORDER_STATUS_UNKNOWN = "order status unknown"


def sole_open_lot(strategy_id: str, peers: list[str], lots: dict[str, Decimal]) -> bool:
    """True when this strategy is the only positive lot among peers on one market."""
    open_ids = [peer for peer in peers if lots.get(peer, Decimal("0")) > 0]
    return open_ids == [strategy_id]
