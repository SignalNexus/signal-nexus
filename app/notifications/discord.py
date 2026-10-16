import logging
import os
import re
import threading
import time
from decimal import Decimal

import httpx

from app.core.config import execution_mode
from app.notifications.analytics import append_audit, enqueue_audit

logger = logging.getLogger(__name__)

# Discord が数秒で空く制限だけ、その場で 1 回送り直す。
# 1 分を超える 429 は連打で待ちが伸びるので、そのプロセスの以降の POST は止める。
_DISCORD_POSTS_ENABLED = True
_RETRY_LIMIT_SECONDS = 5.0
_PAUSE_AFTER_SECONDS = 60.0
_send_lock = threading.Lock()
_blocked_until = 0.0
_paused = False


def reset_discord_limit() -> None:
    global _blocked_until, _paused
    with _send_lock:
        _blocked_until = 0.0
        _paused = False


class AuditMessage(str):
    kind: str
    strategy: str
    symbol: str
    reason: str

    def __new__(
        cls,
        text: str,
        *,
        kind: str,
        strategy: str,
        symbol: str = "",
        reason: str = "",
    ):
        created = str.__new__(cls, text)
        created.kind = kind
        created.strategy = strategy
        created.symbol = symbol
        created.reason = reason
        return created


def send_audit(message: str) -> None:
    if not isinstance(message, AuditMessage):
        _post_discord(message)
        return
    if _forward_copy(message):
        return
    status, detail = discord_copy(message)
    stored = append_audit(
        message.kind,
        message.strategy,
        message.symbol,
        message.reason,
        status,
        detail,
    )
    if not stored:
        enqueue_audit(message.kind, message.strategy, message.symbol, message.reason, status, detail)


def _forward_copy(message: AuditMessage) -> bool:
    if os.environ.get("DISCORD_WEBHOOK_URL", "").strip():
        return False
    url = os.environ.get("AUDIT_COPY_URL", "").strip()
    secret = os.environ.get("ANALYTICS_API_SECRET", "")
    if not url or not secret:
        return False
    try:
        response = httpx.post(
            url,
            json={
                "kind": message.kind,
                "strategy": message.strategy,
                "symbol": message.symbol,
                "reason": message.reason,
                "content": str(message),
            },
            headers={"Authorization": f"Bearer {secret}"},
            timeout=5.0,
        )
        if response.status_code != 200:
            logger.warning("audit copy was not forwarded")
    except Exception:
        logger.warning("audit copy was not forwarded")
    return True


def discord_copy(message: str) -> tuple[str, str]:
    url = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if not url:
        logger.warning("discord copy was not sent: not configured")
        return "not_configured", ""
    if not _DISCORD_POSTS_ENABLED:
        logger.warning("discord copy is paused")
        return "failed", "paused"
    with _send_lock:
        return _discord_copy_locked(url, message)


def _discord_copy_locked(url: str, message: str) -> tuple[str, str]:
    global _blocked_until, _paused
    if _paused:
        return "failed", "429 paused"
    now = time.monotonic()
    if now < _blocked_until:
        detail = _failure_text(429, "", min(_PAUSE_AFTER_SECONDS, _blocked_until - now))
        logger.warning("discord copy failed: %s", detail)
        return "failed", detail
    status, detail, retry_after = _post_once(url, message)
    if status == "sent":
        return "sent", ""
    if retry_after is not None and retry_after <= _RETRY_LIMIT_SECONDS:
        time.sleep(retry_after)
        status, detail, retry_after = _post_once(url, message)
        if status == "sent":
            return "sent", ""
    stopped, detail = _stop_for_long_limit(retry_after, detail)
    if stopped:
        return "failed", detail
    if retry_after is not None:
        _blocked_until = time.monotonic() + min(retry_after, _PAUSE_AFTER_SECONDS)
    if status != "sent":
        logger.warning("discord copy failed: %s", detail)
    return status, detail


def _stop_for_long_limit(retry_after: float | None, detail: str) -> tuple[bool, str]:
    global _paused
    if not detail.startswith("429"):
        return False, detail
    if retry_after is not None and retry_after <= _PAUSE_AFTER_SECONDS:
        return False, detail
    _paused = True
    logger.warning("discord copy paused")
    if retry_after is not None:
        return True, "429 paused"
    return True, detail


def _post_once(url: str, message: str) -> tuple[str, str, float | None]:
    try:
        # Webhook への POST。_DISCORD_POSTS_ENABLED が False のあいだは呼ばない。
        response = httpx.post(url, json={"content": message}, timeout=5.0)
    except Exception as exc:
        detail = type(exc).__name__[:80]
        return "failed", detail, None
    if response.status_code in (200, 204):
        return "sent", "", None
    retry_after = _retry_after(response) if response.status_code == 429 else None
    return "failed", _failure_text(response.status_code, _discord_message(response), retry_after), retry_after


def _retry_after(response) -> float | None:
    value = None
    try:
        payload = response.json()
    except Exception:
        payload = None
    if isinstance(payload, dict) and isinstance(payload.get("retry_after"), (int, float)) and not isinstance(payload.get("retry_after"), bool):
        value = float(payload["retry_after"])
    if value is None:
        header = ""
        headers = getattr(response, "headers", None)
        if headers is not None:
            header = str(headers.get("Retry-After") or "")
        try:
            value = float(header)
        except ValueError:
            value = None
    if value is None or value < 0:
        return None
    return value


def _discord_message(response) -> str:
    try:
        payload = response.json()
    except Exception:
        payload = None
    if not isinstance(payload, dict):
        return ""
    raw = payload.get("message")
    if not isinstance(raw, str):
        return ""
    text = re.sub(r"https?://\S+", "", raw)
    return " ".join(text.split())[:80]


def _failure_text(status: int, message: str, retry_after: float | None) -> str:
    parts = [str(status)]
    if message:
        parts.append(message)
    if retry_after is not None:
        parts.append(f"wait {max(0, round(retry_after))}s")
    return " ".join(parts)[:120]


def _post_discord(message: str) -> None:
    discord_copy(message)


def _title(text: str) -> str:
    label = f"* {text.ljust(21)} *"
    bar = "*" * len(label)
    return f"```\n{bar}\n{label}\n{bar}\n```"


def _venue_lines(venue: str | None) -> str:
    if not venue:
        return ""
    return f"\nVenue:\n{venue}\n"


def _size_quote(value: float) -> str:
    if value == int(value):
        return f"{int(value)} USDT"
    return f"{value} USDT"


def validation_rejected(strategy: str, reason: str) -> AuditMessage:
    return AuditMessage(
        (
            f"{_title('VALIDATION REJECTED')}\n"
            "Environment:\n"
            f"{execution_mode()}\n"
            "\n"
            "Strategy:\n"
            f"{strategy}\n"
            "\n"
            "Reason:\n"
            f"{reason}\n"
            "\n"
            "Status:\n"
            "422"
        ),
        kind="validation_rejected",
        strategy=strategy,
        reason=reason,
    )


def signal_received(
    strategy: str, symbol: str, action: str, size_quote: float, *, venue: str | None = None
) -> AuditMessage:
    return AuditMessage(
        (
            f"{_title('SIGNAL RECEIVED')}\n"
            "Environment:\n"
            f"{execution_mode()}\n"
            "\n"
            "Strategy:\n"
            f"{strategy}\n"
            f"{_venue_lines(venue)}"
            "\n"
            "Symbol:\n"
            f"{symbol}\n"
            "\n"
            "Action:\n"
            f"{action}\n"
            "\n"
            "Size quote:\n"
            f"{_size_quote(size_quote)}"
        ),
        kind="signal_received",
        strategy=strategy,
        symbol=symbol,
    )


def order_planned(
    strategy: str, symbol: str, action: str, size_quote: float, *, venue: str | None = None
) -> AuditMessage:
    return AuditMessage(
        (
            f"{_title('ORDER PLANNED')}\n"
            "Environment:\n"
            f"{execution_mode()}\n"
            "\n"
            "Strategy:\n"
            f"{strategy}\n"
            f"{_venue_lines(venue)}"
            "\n"
            "Symbol:\n"
            f"{symbol}\n"
            "\n"
            "Action:\n"
            f"{action}\n"
            "\n"
            "Size quote:\n"
            f"{_size_quote(size_quote)}"
        ),
        kind="order_planned",
        strategy=strategy,
        symbol=symbol,
    )


def order_not_sent(
    strategy: str,
    symbol: str,
    action: str,
    size_quote: float,
    reason: str,
    *,
    venue: str | None = None,
) -> AuditMessage:
    return AuditMessage(
        (
            f"{_title('ORDER NOT SENT')}\n"
            "Environment:\n"
            f"{execution_mode()}\n"
            "\n"
            "Strategy:\n"
            f"{strategy}\n"
            f"{_venue_lines(venue)}"
            "\n"
            "Symbol:\n"
            f"{symbol}\n"
            "\n"
            "Action:\n"
            f"{action}\n"
            "\n"
            "Size quote:\n"
            f"{_size_quote(size_quote)}\n"
            "\n"
            "Reason:\n"
            f"{reason}"
        ),
        kind="order_not_sent",
        strategy=strategy,
        symbol=symbol,
        reason=reason,
    )


def sell_resend_skipped(strategy: str, symbol: str, reason: str, exit_bar_close: str) -> AuditMessage:
    return AuditMessage(
        f"SELL RESEND SKIPPED | {execution_mode()} | {strategy} | {symbol} | {reason} {exit_bar_close}",
        kind="sell_resend_skipped",
        strategy=strategy,
        symbol=symbol,
        reason=f"{reason} {exit_bar_close}",
    )


def order_success(
    strategy: str,
    symbol: str,
    action: str,
    size_quote: float,
    status: str,
    average: float | None = None,
    *,
    venue: str | None = None,
    realized: Decimal | None = None,
) -> AuditMessage:
    message = (
        f"{_title('ORDER SUCCESS')}\n"
        "Environment:\n"
        f"{execution_mode()}\n"
        "\n"
        "Strategy:\n"
        f"{strategy}\n"
        f"{_venue_lines(venue)}"
        "\n"
        "Symbol:\n"
        f"{symbol}\n"
        "\n"
        "Action:\n"
        f"{action}\n"
        "\n"
        "Size quote:\n"
        f"{_size_quote(size_quote)}\n"
        "\n"
        "Status:\n"
        f"{status}"
    )
    if average is not None and average > 0:
        message += f"\n\nAverage price:\n{_price(average)}"
    if realized is not None:
        message += _pnl_line(realized, symbol)
    return AuditMessage(
        message,
        kind="order_success",
        strategy=strategy,
        symbol=symbol,
        reason=status,
    )


def _price(value: float) -> str:
    return f"{value:.8f}".rstrip("0").rstrip(".")


def _pnl_line(value: Decimal, symbol: str) -> str:
    quote = symbol.split("/")[-1] if "/" in symbol else "USDT"
    text = f"{value:,.2f}" if value <= 0 else f"+{value:,.2f}"
    return f"\n\nRealized PnL:\n{text} {quote}"


def order_failed(strategy: str, reason: str, *, venue: str | None = None) -> AuditMessage:
    return AuditMessage(
        (
            f"{_title('ORDER FAILED')}\n"
            "Environment:\n"
            f"{execution_mode()}\n"
            "\n"
            "Strategy:\n"
            f"{strategy}\n"
            f"{_venue_lines(venue)}"
            "\n"
            "Reason:\n"
            f"{reason}"
        ),
        kind="order_failed",
        strategy=strategy,
        reason=reason,
    )


def duplicate_discarded(
    strategy: str, symbol: str, action: str, size_quote: float, *, venue: str | None = None
) -> AuditMessage:
    return AuditMessage(
        (
            f"{_title('DUPLICATE DISCARDED')}\n"
            "Environment:\n"
            f"{execution_mode()}\n"
            "\n"
            "Strategy:\n"
            f"{strategy}\n"
            f"{_venue_lines(venue)}"
            "\n"
            "Symbol:\n"
            f"{symbol}\n"
            "\n"
            "Action:\n"
            f"{action}\n"
            "\n"
            "Size quote:\n"
            f"{_size_quote(size_quote)}"
        ),
        kind="duplicate_discarded",
        strategy=strategy,
        symbol=symbol,
    )
