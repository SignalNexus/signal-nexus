import os
from datetime import datetime, timedelta, timezone

MIN_SECRET_LENGTH = 24
DEFAULT_MAX_BAR_AGE_SECONDS = 300


def execution_mode() -> str:
    mode = os.environ.get("EXECUTION_MODE", "dry_run")
    if mode == "live":
        return "live"
    return "dry_run"


def kill_switch_enabled() -> bool:
    return os.environ.get("KILL_SWITCH", "false") == "true"


def require_secret_strength(*names: str) -> None:
    """Refuse to start when a configured operator secret is shorter than 24 characters.

    An unset name is left to the request check, which already fails closed.
    The analytics process does not hold the webhook secret or the portal password.
    """
    weak = [name for name in names if 0 < len(os.environ.get(name, "")) < MIN_SECRET_LENGTH]
    if weak:
        raise RuntimeError("secret is shorter than 24 characters: " + ", ".join(weak))


def max_bar_age_seconds() -> int:
    raw = os.environ.get("MAX_BAR_AGE_SECONDS", "").strip()
    if not raw:
        return DEFAULT_MAX_BAR_AGE_SECONDS
    if not raw.isdigit() or int(raw) <= 0:
        raise RuntimeError("MAX_BAR_AGE_SECONDS must be a positive integer")
    return int(raw)


def bar_time_within_window(parsed: datetime, *, now: datetime | None = None) -> bool:
    current = now or datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return abs(current - parsed) <= timedelta(seconds=max_bar_age_seconds())


def fastapi_doc_kwargs() -> dict:
    """OpenAPI routes stay off unless ENABLE_API_DOCS=true at process start."""
    if os.environ.get("ENABLE_API_DOCS", "false") == "true":
        return {}
    return {"docs_url": None, "redoc_url": None, "openapi_url": None}


def analytics_bind_host() -> str:
    host = os.environ.get("ANALYTICS_BIND_HOST", "127.0.0.1").strip()
    return host or "127.0.0.1"
