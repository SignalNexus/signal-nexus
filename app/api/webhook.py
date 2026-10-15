from datetime import datetime, timezone
from threading import Thread
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from app.analytics.schema import AUDIT_KINDS
from app.core.config import execution_mode, kill_switch_enabled
from app.core.security import analytics_secret_matches, webhook_secret_matches
from app.execution.dedup import claim, settle
from app.execution.dispatch import execute_order
from app.execution.order_executor import public_order_error
from app.execution.router import (
    Deployment,
    RegistryRejection,
    Strategy,
    load_strategies,
    rejection_reason,
    route,
    targets_for,
)
from app.notifications.discord import (
    AuditMessage,
    duplicate_discarded,
    order_failed,
    order_not_sent,
    order_planned,
    order_success,
    sell_resend_skipped,
    send_audit,
    signal_received,
    validation_rejected,
)

router = APIRouter()


class AuditCopyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    strategy: str = ""
    symbol: str = ""
    reason: str = ""
    content: str = Field(min_length=1, max_length=2000)

    @field_validator("kind")
    @classmethod
    def known_kind(cls, value: str) -> str:
        if value not in AUDIT_KINDS:
            raise ValueError("kind is invalid")
        return value


def _presented_secret(authorization: str | None) -> str:
    if not authorization:
        return ""
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return ""
    return token.strip()


@router.post("/api/audit-copies")
def accept_audit_copy(
    body: AuditCopyIn,
    authorization: str | None = Header(default=None),
) -> dict[str, str]:
    if not analytics_secret_matches(_presented_secret(authorization)):
        raise HTTPException(status_code=401, detail="unauthorized")
    send_audit(
        AuditMessage(
            body.content,
            kind=body.kind,
            strategy=body.strategy,
            symbol=body.symbol,
            reason=body.reason,
        )
    )
    return {"status": "ok"}


class WebhookPayload(BaseModel):
    secret: str = Field(min_length=1)
    strategy_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    action: Literal["BUY", "SELL", "STOP", "SHORT", "COVER", "LONG", "FLAT"]
    bar_time: str = Field(min_length=1)
    client_order_id: str = Field(min_length=1)
    exit_bar_close: str | None = None

    @field_validator("bar_time")
    @classmethod
    def bar_time_is_iso8601(cls, value: str) -> str:
        _parse_time(value, "bar_time")
        return value

    @field_validator("exit_bar_close")
    @classmethod
    def exit_bar_close_is_iso8601(cls, value: str | None) -> str | None:
        if value is not None:
            _parse_time(value, "exit_bar_close")
        return value

    @model_validator(mode="after")
    def exit_bar_close_only_on_sell(self) -> "WebhookPayload":
        if self.exit_bar_close is not None and self.action not in ("SELL", "STOP"):
            raise ValueError("exit_bar_close is only accepted with SELL or STOP")
        return self

    def exit_bar_close_ms(self) -> int | None:
        if self.exit_bar_close is None:
            return None
        return int(_parse_time(self.exit_bar_close, "exit_bar_close").timestamp() * 1000)


def _parse_time(value: str, name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _public_validation_errors(exc: ValidationError) -> list[dict[str, object]]:
    errors: list[dict[str, object]] = []
    for error in exc.errors():
        item: dict[str, object] = {
            "loc": error["loc"],
            "msg": error["msg"],
            "type": error["type"],
        }
        if "secret" not in error["loc"]:
            item["input"] = error.get("input")
        errors.append(item)
    return errors


def _strategy_label(body: dict[str, object]) -> str:
    strategy_id = body.get("strategy_id")
    if isinstance(strategy_id, str):
        return strategy_id
    return ""


def _reject(
    tasks: BackgroundTasks,
    body: dict[str, object] | None,
    reason: str,
    detail: object,
) -> JSONResponse:
    strategy = _strategy_label(body) if body is not None else ""
    tasks.add_task(send_audit, validation_rejected(strategy, reason))
    return JSONResponse(status_code=422, content={"detail": detail})


def _validation_reason(exc: ValidationError) -> str:
    parts: list[str] = []
    for error in exc.errors():
        if "secret" in error["loc"]:
            parts.append("secret is invalid")
            continue
        location = ".".join(str(item) for item in error["loc"])
        parts.append(f"{location}: {error['msg']}")
    return "; ".join(parts) or "invalid payload"


def _execute_live(strategy, action, client_order_id, strategies, exit_bar_close_ms):
    return execute_order(strategy, action, client_order_id, exit_bar_close_ms)


def _overall(rows: list[dict[str, str]]) -> str:
    statuses = {row["status"] for row in rows}
    if len(statuses) == 1:
        return rows[0]["status"]
    return "partial"


def _start_follow_up(follow_up) -> None:
    Thread(target=follow_up, daemon=True).start()


def _notify(tasks: BackgroundTasks | None, message) -> None:
    if tasks is None:
        send_audit(message)
        return
    tasks.add_task(send_audit, message)


def _run_deployment(
    tasks: BackgroundTasks | None,
    payload: WebhookPayload,
    strategy: Strategy,
    deployment: Deployment,
    show_venue: bool,
) -> dict[str, str]:
    venue = deployment.venue if show_venue else None
    size_quote = deployment.size_quote
    bound = strategy.bound(deployment)
    received = signal_received(payload.strategy_id, payload.symbol, payload.action, size_quote, venue=venue)
    if kill_switch_enabled():
        settle(payload.client_order_id, deployment.venue, retry=False)
        _notify(tasks, received)
        _notify(
            tasks,
            order_not_sent(
                payload.strategy_id,
                payload.symbol,
                payload.action,
                size_quote,
                "KILL_SWITCH",
                venue=venue,
            ),
        )
        return {"venue": deployment.venue, "status": "killed"}
    if execution_mode() != "live":
        settle(payload.client_order_id, deployment.venue, retry=False)
        _notify(tasks, received)
        _notify(
            tasks,
            order_planned(payload.strategy_id, payload.symbol, payload.action, size_quote, venue=venue),
        )
        return {"venue": deployment.venue, "status": "dry_run"}
    _notify(tasks, received)
    try:
        result = _execute_live(
            bound,
            payload.action,
            payload.client_order_id,
            load_strategies(),
            payload.exit_bar_close_ms(),
        )
    except Exception as exc:
        settle(payload.client_order_id, deployment.venue, retry=False)
        _notify(tasks, order_failed(payload.strategy_id, public_order_error(exc), venue=venue))
        return {"venue": deployment.venue, "status": "order_failed"}
    if result.follow_up is not None:
        settle(payload.client_order_id, deployment.venue, retry=False)
        _start_follow_up(result.follow_up)
        return {"venue": deployment.venue, "status": "accepted"}
    if result.resend_skipped:
        settle(payload.client_order_id, deployment.venue, retry=True)
        _notify(
            tasks,
            sell_resend_skipped(
                payload.strategy_id,
                payload.symbol,
                result.reason,
                payload.exit_bar_close or "",
            ),
        )
        return {"venue": deployment.venue, "status": "not_sent"}
    if not result.sent:
        settle(payload.client_order_id, deployment.venue, retry=True)
        _notify(
            tasks,
            order_not_sent(
                payload.strategy_id,
                payload.symbol,
                payload.action,
                size_quote,
                result.reason,
                venue=venue,
            ),
        )
        return {"venue": deployment.venue, "status": "not_sent"}
    if result.status == "order_failed":
        settle(payload.client_order_id, deployment.venue, retry=False)
        _notify(tasks, order_failed(payload.strategy_id, result.reason, venue=venue))
        return {"venue": deployment.venue, "status": "order_failed"}
    settle(payload.client_order_id, deployment.venue, retry=False)
    _notify(
        tasks,
        order_success(
            payload.strategy_id,
            payload.symbol,
            payload.action,
            size_quote,
            result.status,
            result.average,
            venue=venue,
        ),
    )
    return {"venue": deployment.venue, "status": result.status}


def _run_live(
    payload: WebhookPayload,
    strategy: Strategy,
    chosen: list[Deployment],
    show_venue: bool,
) -> None:
    for deployment in chosen:
        _run_deployment(None, payload, strategy, deployment, show_venue)


def _accepted(targets: tuple[Deployment, ...], chosen: list[Deployment]) -> dict[str, object]:
    if len(targets) == 1:
        return {"status": "accepted"}
    return {
        "status": "accepted",
        "venues": [{"venue": deployment.venue, "status": "accepted"} for deployment in chosen],
    }


@router.post("/webhook")
async def receive_webhook(request: Request, tasks: BackgroundTasks) -> dict[str, object]:
    try:
        body = await request.json()
    except Exception:
        return _reject(tasks, None, "invalid json", "invalid json")
    if not isinstance(body, dict):
        return _reject(tasks, None, "payload must be an object", "payload must be an object")
    provided_secret = body.get("secret")
    if "secret" in body and (
        not isinstance(provided_secret, str) or not webhook_secret_matches(provided_secret)
    ):
        raise HTTPException(status_code=401, detail="unauthorized")
    if "size" in body:
        return _reject(tasks, body, "size is not accepted", "size is not accepted")
    if "size_quote" in body:
        return _reject(tasks, body, "size_quote is not accepted", "size_quote is not accepted")
    try:
        payload = WebhookPayload.model_validate(body)
    except ValidationError as exc:
        return _reject(tasks, body, _validation_reason(exc), _public_validation_errors(exc))
    try:
        strategy = route(payload.strategy_id, payload.symbol)
    except RegistryRejection as exc:
        return _reject(tasks, body, exc.reason, exc.reason)
    mismatch = rejection_reason(strategy, payload.action)
    if mismatch is not None:
        return _reject(tasks, body, mismatch, mismatch)
    targets = targets_for(strategy, payload.action)
    runnable = claim(payload.client_order_id, [deployment.venue for deployment in targets])
    chosen = [deployment for deployment in targets if deployment.venue in runnable]
    if not chosen:
        tasks.add_task(
            send_audit,
            duplicate_discarded(
                payload.strategy_id,
                payload.symbol,
                payload.action,
                targets[0].size_quote,
            ),
        )
        return {"status": "duplicate"}
    show_venue = len(targets) > 1
    if execution_mode() != "live" or kill_switch_enabled():
        rows = [
            _run_deployment(tasks, payload, strategy, deployment, show_venue) for deployment in chosen
        ]
        if len(targets) == 1:
            return {"status": rows[0]["status"]}
        return {"status": _overall(rows), "venues": rows}
    tasks.add_task(_run_live, payload, strategy, chosen, show_venue)
    return _accepted(targets, chosen)
