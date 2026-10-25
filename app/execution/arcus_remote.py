from app.execution.arcus import ArcusError
from app.execution.handoff import RemoteError, live_result, send
from app.execution.live import LiveResult


def apply_remote_leverage() -> None:
    from app.venues import enabled_venues

    if "arcus" not in enabled_venues():
        return
    _post("/api/arcus/leverage", {})


def execute_arcus_remote(strategy, action: str, client_order_id: str) -> LiveResult:
    payload = _post(
        "/api/arcus/order",
        {
            "strategy_id": strategy.strategy_id,
            "action": action,
            "client_order_id": client_order_id,
        },
    )
    return live_result(payload, with_quote=False)


def _post(path: str, body: dict) -> dict:
    try:
        return send("POST", path, body, timeout=20.0, label="arcus")
    except RemoteError as exc:
        raise ArcusError(str(exc)) from None
