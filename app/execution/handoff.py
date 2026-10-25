import os
from decimal import Decimal

import httpx

from app.execution.live import LiveResult


class RemoteError(RuntimeError):
    pass


def send(method: str, path: str, body: dict | None, *, timeout: float, label: str) -> dict:
    base = os.environ.get("ANALYTICS_API_URL", "").strip().rstrip("/")
    secret = os.environ.get("ANALYTICS_API_SECRET", "")
    if not base or not secret:
        raise RemoteError(f"{label} executor is not configured")
    try:
        response = httpx.request(
            method,
            f"{base}{path}",
            json=body,
            headers={"Authorization": f"Bearer {secret}"},
            timeout=timeout,
        )
    except httpx.HTTPError:
        raise RemoteError(f"{label} executor was not reached") from None
    if response.status_code != 200:
        reason = ""
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if isinstance(payload, dict):
            reason = str(payload.get("detail") or payload.get("error") or "")
        raise RemoteError(f"{label} executor was not accepted {response.status_code} {reason}".rstrip())
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if not isinstance(payload, dict):
        raise RemoteError(f"{label} executor was not accepted")
    return payload


def live_result(payload: dict, *, with_quote: bool) -> LiveResult:
    if payload.get("deferred"):
        return LiveResult("accepted", True, follow_up=lambda: None)
    average = None
    resend_skipped = False
    if with_quote:
        raw = payload.get("average")
        average = None if raw is None else float(raw)
        resend_skipped = bool(payload.get("resend_skipped"))
    raw_realized = payload.get("realized")
    realized = None
    if raw_realized not in (None, ""):
        realized = Decimal(str(raw_realized))
    return LiveResult(
        str(payload.get("status") or "order_failed"),
        bool(payload.get("sent")),
        str(payload.get("reason") or ""),
        resend_skipped=resend_skipped,
        average=average,
        realized=realized,
    )
