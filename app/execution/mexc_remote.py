from app.execution.handoff import RemoteError, live_result, send
from app.execution.live import LiveResult


class MexcRemoteError(RuntimeError):
    pass


def execute_mexc_remote(strategy, action: str, client_order_id: str, exit_bar_close_ms: int | None = None) -> LiveResult:
    body = {
        "strategy_id": strategy.strategy_id,
        "action": action,
        "client_order_id": client_order_id,
    }
    if exit_bar_close_ms is not None:
        body["exit_bar_close_ms"] = exit_bar_close_ms
    return live_result(_post("/api/mexc/order", body), with_quote=True)


def fetch_open_orders() -> dict:
    return _get("/api/mexc/open-orders")


def _post(path: str, body: dict) -> dict:
    return _send("POST", path, body)


def _get(path: str) -> dict:
    return _send("GET", path, None)


def _send(method: str, path: str, body: dict | None) -> dict:
    try:
        return send(method, path, body, timeout=30.0, label="mexc")
    except RemoteError as exc:
        raise MexcRemoteError(str(exc)) from None
