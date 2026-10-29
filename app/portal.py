import hashlib
import hmac
import os
import time
from contextvars import ContextVar
from datetime import datetime, timezone
from threading import Lock

import httpx
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.core.security import portal_password_matches
from app.execution.mexc_open_orders import restore_open_orders
from app.execution.mexc_remote import MexcRemoteError, fetch_open_orders
from app.portal_data import read_backtests
from app.portal_pages import STYLE, login_page, render_analytics, render_dashboard, render_operations, render_trading
from app.portal_text import html_lang, t

router = APIRouter()
COOKIE = "portal_session"
MAX_AGE = 30 * 24 * 60 * 60
_dashboard_summary: ContextVar[bool] = ContextVar("dashboard_summary", default=False)
_board_cache_lock = Lock()
_board_cache: dict[bool, dict] = {}


@router.get("/portal")
def portal_page(request: Request) -> HTMLResponse:
    if not _session_ok(request):
        return _html(login_page(""))
    token = _dashboard_summary.set(True)
    try:
        return _html(render_dashboard(_board()))
    finally:
        _dashboard_summary.reset(token)


@router.get("/portal/trading")
def trading_page(request: Request, view: str = "positions") -> HTMLResponse:
    if not _session_ok(request):
        return _html(login_page(""))
    balances = None
    orders = None
    fetched_at = None
    board = None
    if view == "balances":
        balances, fetched_at = _balances()
    elif view == "orders":
        orders, fetched_at = _open_orders()
    elif view == "trades":
        board = _analytics_slice("/api/trades", "trades")
    else:
        board = _analytics_slice("/api/positions", "positions")
    return _html(render_trading(view, board, balances, orders, fetched_at))


@router.get("/portal/analytics")
def analytics_page(request: Request, view: str = "strategies") -> HTMLResponse:
    if not _session_ok(request):
        return _html(login_page(""))
    token = _dashboard_summary.set(True)
    try:
        return _html(render_analytics(view, _board(), read_backtests()))
    finally:
        _dashboard_summary.reset(token)


@router.get("/portal/operations")
def operations_page(request: Request, view: str = "schedule") -> HTMLResponse:
    if not _session_ok(request):
        return _html(login_page(""))
    audits = _audit_rows() if view == "audit" else None
    return _html(render_operations(view, audits))


@router.post("/portal/login")
def portal_login(password: str = Form(default="")) -> Response:
    if not portal_password_matches(password):
        return _html(login_page(t("パスワードが違います。")), status_code=401)
    response = RedirectResponse("/portal", status_code=303)
    response.set_cookie(
        COOKIE,
        _cookie_value(),
        max_age=MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=True,
        path="/",
    )
    return response


@router.post("/portal/logout")
def portal_logout() -> RedirectResponse:
    response = RedirectResponse("/portal", status_code=303)
    response.delete_cookie(COOKIE, path="/", secure=True, httponly=True, samesite="lax")
    return response


def _clear_cached_board() -> None:
    with _board_cache_lock:
        _board_cache.clear()


def _board() -> dict | None:
    summary = _dashboard_summary.get()
    try:
        fresh = _dashboard()
    except Exception:
        fresh = None
    with _board_cache_lock:
        if fresh is not None:
            fresh["board_fetched_at"] = datetime.now(timezone.utc).isoformat()
            fresh["board_stale"] = False
            _board_cache[summary] = fresh
            return fresh
        cached = _board_cache.get(summary)
        if cached is None:
            return None
        stale = dict(cached)
        stale["board_stale"] = True
        return stale


def _session_ok(request: Request) -> bool:
    password = os.environ.get("PORTAL_PASSWORD", "")
    return _cookie_valid(password, request.cookies.get(COOKIE, ""))


def _cookie_value() -> str:
    password = os.environ.get("PORTAL_PASSWORD", "")
    expires = int(datetime.now(timezone.utc).timestamp()) + MAX_AGE
    body = str(expires)
    signature = hmac.new(password.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{signature}"


def _cookie_valid(password: str, value: str) -> bool:
    if not password or "." not in value:
        return False
    body, signature = value.split(".", 1)
    expected = hmac.new(password.encode(), body.encode(), hashlib.sha256).hexdigest()
    if len(signature) != len(expected) or not hmac.compare_digest(signature, expected):
        return False
    try:
        expires = int(body)
    except ValueError:
        return False
    return expires >= int(datetime.now(timezone.utc).timestamp())


def _dashboard() -> dict:
    base = os.environ.get("ANALYTICS_API_URL", "").strip().rstrip("/")
    secret = os.environ.get("ANALYTICS_API_SECRET", "")
    if not base or not secret:
        raise RuntimeError("analytics api is not configured")
    headers = {"Authorization": f"Bearer {secret}"}
    # ダッシュボードは 8 秒で打ち切る。10 秒以上の表示は要件を外れる。
    summary = _dashboard_summary.get()
    path = "/api/board?summary=1" if summary else "/api/board"
    budget = 8.0 if summary else 10.0
    with httpx.Client(timeout=budget) as client:
        response = _board_response(client, f"{base}{path}", headers, summary=summary, budget=budget)
        if response.status_code != 404:
            response.raise_for_status()
            board = response.json()
            return {
                "pnl": board["pnl"],
                "pnl_by_venue": board.get("pnl_by_venue"),
                "pnl_by_asset_class": board.get("pnl_by_asset_class"),
                "volume": board.get("volume"),
                "volume_by_venue": board.get("volume_by_venue"),
                "volume_by_asset_class": board.get("volume_by_asset_class"),
                "positions": board["positions"],
                "trades": board["trades"],
                "strategy_rows": board["strategies"],
                "ticker_rows": board["tickers"],
                "audits": board.get("audits"),
                "ingest_succeeded_at": board.get("ingest_succeeded_at"),
            }

        def get(path: str) -> dict:
            separate = client.get(f"{base}{path}", headers=headers)
            separate.raise_for_status()
            return separate.json()

        pnl = get("/api/pnl")
        positions = get("/api/positions")
        trades = get("/api/trades")
        strategies = get("/api/strategies")
        try:
            audits = get("/api/audits")["audits"]
        except Exception:
            audits = None
        try:
            tickers = get("/api/tickers")["tickers"]
        except Exception:
            tickers = None
    return {
        "pnl": pnl,
        "pnl_by_venue": None,
        "pnl_by_asset_class": None,
        "volume": None,
        "volume_by_venue": None,
        "volume_by_asset_class": None,
        "positions": positions["positions"],
        "trades": trades["trades"],
        "strategy_rows": strategies["strategies"],
        "ticker_rows": tickers,
        "audits": audits,
        "ingest_succeeded_at": None,
    }


def _board_response(client: httpx.Client, url: str, headers: dict, *, summary: bool, budget: float):
    # 再起動直後の warming は短く待って取り直す。空の Dashboard を残さない。
    deadline = time.monotonic() + max(0.0, budget - 1.0)
    while True:
        response = client.get(url, headers=headers)
        if response.status_code != 503 or not summary or time.monotonic() >= deadline:
            return response
        time.sleep(0.4)


def _audit_rows() -> list | None:
    try:
        base = os.environ.get("ANALYTICS_API_URL", "").strip().rstrip("/")
        secret = os.environ.get("ANALYTICS_API_SECRET", "")
        if not base or not secret:
            raise RuntimeError("analytics api is not configured")
        headers = {"Authorization": f"Bearer {secret}"}
        with httpx.Client(timeout=8.0) as client:
            response = client.get(f"{base}/api/audits", headers=headers)
            response.raise_for_status()
            rows = response.json().get("audits")
        return rows if isinstance(rows, list) else None
    except Exception:
        return None


def _analytics_slice(path: str, key: str) -> dict | None:
    try:
        base = os.environ.get("ANALYTICS_API_URL", "").strip().rstrip("/")
        secret = os.environ.get("ANALYTICS_API_SECRET", "")
        if not base or not secret:
            raise RuntimeError("analytics api is not configured")
        headers = {"Authorization": f"Bearer {secret}"}
        with httpx.Client(timeout=8.0) as client:
            response = client.get(f"{base}{path}", headers=headers)
            response.raise_for_status()
            payload = response.json()
        return {key: payload.get(key) or []}
    except Exception:
        return None


def _balances():
    try:
        base = os.environ.get("ANALYTICS_API_URL", "").strip().rstrip("/")
        secret = os.environ.get("ANALYTICS_API_SECRET", "")
        if not base or not secret:
            raise RuntimeError("analytics api is not configured")
        headers = {"Authorization": f"Bearer {secret}"}
        with httpx.Client(timeout=8.0) as client:
            response = client.get(f"{base}/api/balance", headers=headers)
            response.raise_for_status()
            payload = response.json()
        fetched_at = datetime.fromisoformat(payload["fetched_at"])
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)
        restored = {
            "spot": {
                "usdt": payload["usdt"],
                "coins": payload.get("coins") or [],
                "count": int(payload.get("count") or 0),
            },
            "futures": payload.get("futures"),
        }
        if "arcus" in payload:
            restored["arcus"] = _arcus_balance(payload.get("arcus"))
        for key, value in payload.items():
            if key in ("fetched_at", "usdt", "coins", "count", "futures", "arcus", "spot"):
                continue
            if isinstance(value, dict):
                restored[key] = _arcus_balance(value)
        return restored, fetched_at
    except Exception:
        return None, None


def _arcus_balance(view) -> dict | None:
    if not isinstance(view, dict):
        return None
    return {
        "equity": view.get("equity"),
        "free": view.get("free"),
        "margin": view.get("margin"),
        "positions": int(view.get("positions") or 0),
    }


def _open_orders():
    try:
        return restore_open_orders(fetch_open_orders())
    except MexcRemoteError:
        return None, None


def _html(body: str, status_code: int = 200) -> HTMLResponse:
    page = f"""<!doctype html>
<html lang="{html_lang()}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Signal Nexus</title>
  <link rel="icon" href="/favicon.ico" type="image/png">
  <link rel="apple-touch-icon" href="/apple-touch-icon.png">
  <style>{STYLE}</style>
</head>
<body>{body}</body>
</html>"""
    return HTMLResponse(page, status_code=status_code, headers={"Cache-Control": "no-store"})
