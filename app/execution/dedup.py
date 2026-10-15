from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock

_TTL = timedelta(minutes=10)
_lock = Lock()


@dataclass
class _Signal:
    seen_at: datetime
    venues: dict[str, str]


_seen: dict[str, _Signal] = {}


def claim(client_order_id: str, venues: list[str], *, now: datetime | None = None) -> list[str]:
    current = now or datetime.now(timezone.utc)
    with _lock:
        _drop_expired(current)
        state = _seen.get(client_order_id)
        if state is None:
            _seen[client_order_id] = _Signal(current, {venue: "open" for venue in venues})
            return list(venues)
        return [venue for venue in venues if state.venues.get(venue) == "retry"]


def settle(client_order_id: str, venue: str, *, retry: bool) -> None:
    with _lock:
        state = _seen.get(client_order_id)
        if state is None:
            return
        state.venues[venue] = "retry" if retry else "done"
        if state.venues and all(status == "retry" for status in state.venues.values()):
            del _seen[client_order_id]


def clear_reservations() -> None:
    with _lock:
        _seen.clear()


def _drop_expired(current: datetime) -> None:
    expired = [key for key, state in _seen.items() if current - state.seen_at >= _TTL]
    for key in expired:
        del _seen[key]
