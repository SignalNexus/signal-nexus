"""Alert when a venue is open and every Signal Nexus lot on that symbol is flat."""

import logging
import os
from decimal import Decimal

logger = logging.getLogger(__name__)

_announced: set[tuple[str, str]] = set()


def venue_is_open_internally_flat(venue_size: Decimal, internal: Decimal) -> bool:
    return venue_size > 0 and internal <= 0


def clear_announced() -> None:
    _announced.clear()


def announce(gaps: list[tuple[str, str, Decimal, Decimal]]) -> list[tuple[str, str]]:
    from app.notifications.discord import position_mismatch, send_audit

    current = {(venue, symbol) for venue, symbol, _venue_size, _internal in gaps}
    fresh = [gap for gap in gaps if (gap[0], gap[1]) not in _announced]
    _announced.clear()
    _announced.update(current)
    sent = []
    for venue, symbol, venue_size, internal in fresh:
        send_audit(position_mismatch(venue, symbol, venue_size, internal))
        sent.append((venue, symbol))
    return sent


def watch_once() -> list[tuple[str, str]]:
    if not os.environ.get("ANALYTICS_DATABASE_URL", "").strip():
        return []
    try:
        gaps = _gaps()
    except Exception as exc:
        logger.warning("position gap was not read: %s", type(exc).__name__)
        return []
    return announce(gaps)


def _gaps() -> list[tuple[str, str, Decimal, Decimal]]:
    from app.execution.router import load_strategies
    from app.execution.strategy_lots import load_venue

    book = load_strategies()
    found: list[tuple[str, str, Decimal, Decimal]] = []
    found.extend(_lighter_gaps(book, load_venue))
    found.extend(_arcus_gaps(book, load_venue))
    found.extend(_futures_gaps(book, load_venue))
    return found


def _lighter_gaps(book, load_venue) -> list[tuple[str, str, Decimal, Decimal]]:
    from app.execution.venue_port import ports

    rows = []
    for venue_id, port in ports().items():
        reader = getattr(port, "position_sizes", None)
        if not callable(reader):
            continue
        try:
            sizes = reader()
        except Exception:
            logger.warning("venue positions were not read: %s", venue_id)
            continue
        if not isinstance(sizes, dict):
            continue
        lots = _lots(load_venue, venue_id)
        for symbol, size in sizes.items():
            if not isinstance(size, Decimal):
                continue
            internal = _sum_for(book, lots, venue_id, symbol)
            if venue_is_open_internally_flat(size, internal):
                rows.append((venue_id, symbol, size, internal))
    return rows


def _arcus_gaps(book, load_venue) -> list[tuple[str, str, Decimal, Decimal]]:
    if not (os.environ.get("ARCUS_ADDRESS", "").strip() and os.environ.get("ARCUS_SIGNING_KEY", "").strip()):
        return []
    from app.execution.arcus import MARKETS, arcus_client

    try:
        client = arcus_client()
    except Exception:
        logger.warning("arcus positions were not read")
        return []
    lots = _lots(load_venue, "arcus")
    rows = []
    symbols = sorted({item.symbol for item in book.values() if _on_venue(item, "arcus") and item.symbol in MARKETS})
    for symbol in symbols:
        try:
            size = client.position_size(symbol)
        except Exception:
            continue
        if size is None:
            continue
        internal = _sum_for(book, lots, "arcus", symbol)
        if venue_is_open_internally_flat(abs(size), internal):
            rows.append(("arcus", symbol, abs(size), internal))
    return rows


def _futures_gaps(book, load_venue) -> list[tuple[str, str, Decimal, Decimal]]:
    if not (
        os.environ.get("MEXC_FUTURES_API_KEY", "").strip()
        and os.environ.get("MEXC_FUTURES_API_SECRET", "").strip()
    ):
        return []
    from app.analytics.importer import _futures_symbol, _open_futures_positions, _plain_number
    from app.execution.exchange import futures_client
    from app.execution.futures import swap_symbol

    symbols = sorted({swap_symbol(item.symbol) for item in book.values() if _on_venue(item, "mexc_futures")})
    try:
        positions = _open_futures_positions(futures_client(), symbols)
    except Exception:
        logger.warning("futures positions were not read")
        return []
    venue_sizes: dict[str, Decimal] = {}
    for position in positions:
        symbol = _futures_symbol(str(position.get("symbol") or ""))
        hold = _plain_number(position.get("holdVol"))
        if not symbol or hold is None or hold <= 0:
            continue
        venue_sizes[symbol] = venue_sizes.get(symbol, Decimal("0")) + hold
    lots = _lots(load_venue, "mexc_futures")
    rows = []
    for symbol, size in venue_sizes.items():
        internal = _sum_for(book, lots, "mexc_futures", symbol)
        if venue_is_open_internally_flat(size, internal):
            rows.append(("mexc_futures", symbol, size, internal))
    return rows


def _lots(load_venue, venue: str) -> dict[str, Decimal]:
    try:
        return load_venue(venue)
    except Exception:
        logger.warning("strategy lots were not read: %s", venue)
        return {}


def _sum_for(book, lots: dict[str, Decimal], venue: str, symbol: str) -> Decimal:
    total = Decimal("0")
    for strategy_id, item in book.items():
        if item.symbol != symbol or not _on_venue(item, venue):
            continue
        total += lots.get(strategy_id, Decimal("0"))
    return total


def _on_venue(strategy, venue: str) -> bool:
    return any(deployment.enabled and deployment.venue == venue for deployment in strategy.deployments)
