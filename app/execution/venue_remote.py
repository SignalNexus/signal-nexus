import os

from app.execution.handoff import RemoteError, live_result, send
from app.execution.live import LiveResult


class VenueRemoteError(RuntimeError):
    pass


def execute_venue_remote(strategy, action: str, client_order_id: str) -> LiveResult:
    try:
        payload = send(
            "POST",
            "/api/venue/order",
            {
                "strategy_id": strategy.strategy_id,
                "venue": strategy.venue,
                "action": action,
                "client_order_id": client_order_id,
            },
            timeout=20.0,
            label="venue",
        )
    except RemoteError as exc:
        raise VenueRemoteError(str(exc)) from None
    return live_result(payload, with_quote=False)


def hands_off() -> bool:
    return bool(os.environ.get("ANALYTICS_API_URL", "").strip())
