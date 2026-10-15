import os
import threading
import time

import httpx

_pending: list[tuple[str, str, str, str, str, str]] = []
_guard = threading.Lock()
_flusher: threading.Thread | None = None


def append_audit(
    kind: str,
    strategy: str,
    symbol: str,
    reason: str,
    discord_status: str = "",
    discord_detail: str = "",
) -> bool:
    return _post(
        "/api/audits",
        {
            "kind": kind,
            "strategy": strategy,
            "symbol": symbol,
            "reason": reason,
            "discord_status": discord_status,
            "discord_detail": discord_detail,
        },
    )


def enqueue_audit(
    kind: str,
    strategy: str,
    symbol: str,
    reason: str,
    discord_status: str = "",
    discord_detail: str = "",
) -> None:
    global _flusher
    with _guard:
        _pending.append((kind, strategy, symbol, reason, discord_status, discord_detail))
        if _flusher is not None and _flusher.is_alive():
            return
        _flusher = threading.Thread(target=_flush_forever, daemon=True)
        _flusher.start()


def flush_pending_audits() -> None:
    with _guard:
        batch = list(_pending)
        _pending.clear()
    failed = [item for item in batch if not append_audit(*item)]
    if not failed:
        return
    with _guard:
        _pending[:0] = failed


def _flush_forever() -> None:
    while True:
        time.sleep(15)
        flush_pending_audits()


def report_order_link(
    exchange_client_order_id: str,
    client_order_id: str,
    *,
    signal_time: str | None = None,
    signal_price: str | None = None,
) -> None:
    body = {
        "exchange_client_order_id": exchange_client_order_id,
        "client_order_id": client_order_id,
    }
    if signal_time is not None:
        body["signal_time"] = signal_time
    if signal_price is not None:
        body["signal_price"] = signal_price
    _post("/api/order-links", body)


def _post(path: str, body: dict) -> bool:
    base = os.environ.get("ANALYTICS_API_URL", "").strip().rstrip("/")
    secret = os.environ.get("ANALYTICS_API_SECRET", "")
    if not base or not secret:
        return True
    try:
        response = httpx.post(
            f"{base}{path}",
            json=body,
            headers={"Authorization": f"Bearer {secret}"},
            timeout=5.0,
        )
        response.raise_for_status()
    except Exception:
        return False
    return True
