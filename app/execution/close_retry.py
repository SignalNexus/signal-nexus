"""Retry a cover that failed while the fill ledger still shows a position."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from threading import Lock

logger = logging.getLogger(__name__)

RETRY_SECONDS = 60
RETRY_FOR = timedelta(hours=6)
_CLOSING = {"COVER", "FLAT"}
_RETRYABLE = (
    "timeout",
    "collision",
    "filled base missing",
    "filled quantity missing",
    "status unknown",
    "status unavailable",
    "position history unavailable",
)
_lock = Lock()


@dataclass
class PendingClose:
    venue: str
    strategy_id: str
    action: str
    client_order_id: str
    started_at: datetime
    next_at: datetime
    attempts: int = 0


_pending: dict[tuple[str, str], PendingClose] = {}


def unfinished_close(action: str, status: str, sent: bool, reason: str, quantity: Decimal) -> bool:
    if action not in _CLOSING or status != "order_failed" or not sent or quantity <= 0:
        return False
    text = reason.lower()
    return any(part in text for part in _RETRYABLE)


def note_if_unfinished(strategy, action: str, result, client_order_id: str) -> None:
    if not client_order_id:
        return
    from app.execution.strategy_lots import close_quantity

    quantity = close_quantity(strategy.venue, strategy.strategy_id)
    if not unfinished_close(action, result.status, result.sent, result.reason, quantity):
        return
    now = datetime.now(timezone.utc)
    row = PendingClose(
        strategy.venue,
        strategy.strategy_id,
        action,
        client_order_id,
        now,
        now + timedelta(seconds=RETRY_SECONDS),
    )
    with _lock:
        _pending[(row.venue, row.strategy_id)] = row


def retry_due(now: datetime, execute) -> list[str]:
    from app.core.config import kill_switch_enabled
    from app.execution.strategy_lots import close_quantity

    if kill_switch_enabled():
        return []
    with _lock:
        due = [row for row in _pending.values() if row.next_at <= now]
    done = []
    for row in due:
        if now - row.started_at > RETRY_FOR:
            _drop(row)
            continue
        quantity = close_quantity(row.venue, row.strategy_id)
        if quantity <= 0:
            _drop(row)
            done.append(row.strategy_id)
            continue
        try:
            result = execute(row)
        except Exception:
            logger.warning("unfinished close was not retried")
            _schedule(row, now)
            continue
        row.attempts += 1
        if result.status != "order_failed" or not unfinished_close(
            row.action, result.status, result.sent, result.reason, quantity
        ):
            _drop(row)
            done.append(row.strategy_id)
            continue
        _schedule(row, now)
    return done


def watch_forever(sleeper) -> None:
    while True:
        sleeper(RETRY_SECONDS)
        try:
            from app.execution.dispatch import execute_order
            from app.execution.router import load_strategies

            def execute(row: PendingClose):
                strategies = load_strategies()
                strategy = strategies[row.strategy_id]
                deployment = next(item for item in strategy.deployments if item.venue == row.venue and item.enabled)
                return execute_order(strategy.bound(deployment), row.action, row.client_order_id, None)

            retry_due(datetime.now(timezone.utc), execute)
        except Exception:
            logger.warning("unfinished closes were not retried")


def clear_pending_closes() -> None:
    with _lock:
        _pending.clear()


def _schedule(row: PendingClose, now: datetime) -> None:
    row.next_at = now + timedelta(seconds=RETRY_SECONDS)
    with _lock:
        _pending[(row.venue, row.strategy_id)] = row


def _drop(row: PendingClose) -> None:
    with _lock:
        _pending.pop((row.venue, row.strategy_id), None)
