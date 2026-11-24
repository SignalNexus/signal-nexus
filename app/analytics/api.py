import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from decimal import Decimal
from pathlib import Path
from threading import Lock, Thread

import httpx
import psycopg
from fastapi import FastAPI, Header, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, field_validator

from app.analytics.report import (
    FillView,
    attach_notional,
    attach_volumes,
    final_fill_realized,
    freeze_books,
    held_opens,
    mark_opens,
    month_forecast,
    period_rows,
    reconstruct,
    replay_books,
    strategy_rows,
    ticker_rows,
    volume_rows,
    volume_rows_from_daily,
)
from app.venues import is_futures, is_spot
from app.analytics.schema import (
    AUDIT_KINDS,
    create_schema,
    insert_audit,
    link_order,
    load_audits,
    load_audit_page,
    load_audit_summary,
    load_all_strategy_lots,
    load_daily_notional,
    load_fill_page,
    load_fill_prefix_checksum,
    load_fill_venues,
    load_fills,
    load_fills_for_keys,
    load_fills_since,
    load_notional_by,
    load_fills_for_names,
    ensure_read_indexes,
    load_ingest_succeeded_at,
    load_latest_signal,
    load_open_fill_keys,
    load_trade_summary,
)
from app.core.config import analytics_bind_host, fastapi_doc_kwargs, require_secret_strength
from app.core.security import analytics_secret_matches
from app.execution.admission import order_block_reason
from app.execution.arcus import ArcusError, apply_configured_leverage, execute_arcus
from app.execution.futures import execute_futures
from app.execution.live import defer_venue_work, execute_live, order_deferred
from app.execution.mexc_open_orders import open_orders_payload
from app.execution.order_executor import public_order_error
from app.execution.router import load_strategies
from app.portal_data import read_month_target

logger = logging.getLogger(__name__)

app = FastAPI(title="Signal Nexus Analytics", **fastapi_doc_kwargs())

# 画面の取得は集計の計算を待たない。計算は裏で回し、直前の結果を返す。
# 再起動直後も空にしないよう、直前の結果はディスクにも残す。
_board_lock = Lock()
_board_build_lock = Lock()
_board_snapshot: dict | None = None
_trade_snapshot: list | None = None
_schema_for = ""


class AuditIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    strategy: str = ""
    symbol: str = ""
    reason: str = ""
    discord_status: str = ""
    discord_detail: str = ""
    venue: str = ""

    @field_validator("kind")
    @classmethod
    def known_kind(cls, value: str) -> str:
        if value not in AUDIT_KINDS:
            raise ValueError("kind is invalid")
        return value

    @field_validator("discord_status")
    @classmethod
    def known_discord_status(cls, value: str) -> str:
        if value not in ("", "sent", "failed", "not_configured"):
            raise ValueError("discord_status is invalid")
        return value

    @field_validator("discord_detail")
    @classmethod
    def discord_detail_is_short(cls, value: str) -> str:
        if len(value) > 120:
            raise ValueError("discord_detail is too long")
        return value

    @field_validator("venue")
    @classmethod
    def venue_is_short(cls, value: str) -> str:
        if len(value) > 64:
            raise ValueError("venue is too long")
        return value


def _presented_secret(authorization: str | None) -> str:
    if not authorization:
        return ""
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return ""
    return token.strip()


class OrderLinkIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exchange_client_order_id: str
    client_order_id: str
    signal_time: datetime | None = None
    signal_price: Decimal | None = None

    @field_validator("exchange_client_order_id")
    @classmethod
    def exchange_id_is_32_chars(cls, value: str) -> str:
        if len(value) != 32:
            raise ValueError("exchange_client_order_id must be 32 characters")
        return value

    @field_validator("client_order_id")
    @classmethod
    def client_order_id_present(cls, value: str) -> str:
        if not value:
            raise ValueError("client_order_id is required")
        return value

    @field_validator("signal_time")
    @classmethod
    def signal_time_has_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("signal_time must include a timezone")
        return value


@app.post("/api/audits")
def append_audit(
    body: AuditIn,
    authorization: str | None = Header(default=None),
) -> dict[str, str]:
    if not analytics_secret_matches(_presented_secret(authorization)):
        raise HTTPException(status_code=401, detail="unauthorized")
    try:
        _store_audit(body)
    except Exception:
        raise HTTPException(status_code=500, detail="audit was not stored") from None
    return {"status": "ok"}


class ArcusOrderIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_id: str
    action: str
    client_order_id: str

    @field_validator("strategy_id", "action", "client_order_id")
    @classmethod
    def present(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field is required")
        return value


@app.post("/api/arcus/leverage")
def arcus_leverage(authorization: str | None = Header(default=None)) -> dict[str, str]:
    _require_secret(authorization)
    try:
        apply_configured_leverage()
    except ArcusError as exc:
        raise HTTPException(status_code=502, detail=str(exc)[:300]) from None
    return {"status": "applied"}


@app.post("/api/arcus/order")
def arcus_order(
    body: ArcusOrderIn,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    _require_secret(authorization)
    try:
        strategy = load_strategies()[body.strategy_id]
    except KeyError:
        raise HTTPException(status_code=404, detail="strategy is unavailable") from None
    if strategy.venue != "arcus":
        raise HTTPException(status_code=404, detail="strategy is unavailable")
    _refuse_blocked_order(strategy, body.action)
    try:
        with order_deferred():
            result = defer_venue_work(
                strategy,
                body.action,
                lambda: execute_arcus(strategy, body.action, body.client_order_id),
                body.client_order_id,
            )
    except ArcusError as exc:
        raise HTTPException(status_code=502, detail=public_order_error(exc)) from None
    deferred = _deferred_response(result)
    if deferred is not None:
        return deferred
    return {
        "status": result.status,
        "sent": result.sent,
        "deferred": False,
        "reason": result.reason,
        "realized": None if result.realized is None else str(result.realized),
    }


class VenueOrderIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_id: str
    venue: str
    action: str
    client_order_id: str

    @field_validator("strategy_id", "venue", "action", "client_order_id")
    @classmethod
    def present(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field is required")
        return value


@app.post("/api/venue/order")
def venue_order(
    body: VenueOrderIn,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    from app.execution.venue_port import port_for

    _require_secret(authorization)
    try:
        strategy = load_strategies()[body.strategy_id]
    except KeyError:
        raise HTTPException(status_code=404, detail="strategy is unavailable") from None
    matched = [item for item in strategy.deployments if item.enabled and item.venue == body.venue]
    if len(matched) != 1:
        raise HTTPException(status_code=404, detail="strategy is unavailable")
    strategy = strategy.bound(matched[0])
    port = port_for(body.venue)
    if port is None:
        raise HTTPException(status_code=404, detail="strategy is unavailable")
    _refuse_blocked_order(strategy, body.action)
    try:
        with order_deferred():
            result = defer_venue_work(
                strategy,
                body.action,
                lambda: port.execute(strategy, body.action, body.client_order_id),
                body.client_order_id,
            )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=public_order_error(exc)) from None
    deferred = _deferred_response(result)
    if deferred is not None:
        return deferred
    return {
        "status": result.status,
        "sent": result.sent,
        "deferred": False,
        "reason": result.reason,
        "realized": None if result.realized is None else str(result.realized),
    }


class MexcOrderIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_id: str
    action: str
    client_order_id: str
    exit_bar_close_ms: int | None = None

    @field_validator("strategy_id", "action", "client_order_id")
    @classmethod
    def present(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field is required")
        return value


@app.post("/api/mexc/order")
def mexc_order(
    body: MexcOrderIn,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    _require_secret(authorization)
    try:
        strategy = load_strategies()[body.strategy_id]
    except KeyError:
        raise HTTPException(status_code=404, detail="strategy is unavailable") from None
    if strategy.venue not in ("mexc_spot", "mexc_futures"):
        raise HTTPException(status_code=404, detail="strategy is unavailable")
    _refuse_blocked_order(strategy, body.action)
    try:
        with order_deferred():
            if strategy.venue == "mexc_spot":
                from app.execution.exchange import mexc_client

                result = defer_venue_work(
                    strategy,
                    body.action,
                    lambda: execute_live(
                        mexc_client(),
                        strategy,
                        body.action,
                        body.client_order_id,
                        load_strategies(),
                        body.exit_bar_close_ms,
                    ),
                    body.client_order_id,
                )
            else:
                from app.execution.exchange import futures_client

                result = defer_venue_work(
                    strategy,
                    body.action,
                    lambda: execute_futures(
                        futures_client(),
                        strategy,
                        body.action,
                        body.client_order_id,
                        load_strategies(),
                    ),
                    body.client_order_id,
                )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=public_order_error(exc)) from None
    deferred = _deferred_response(result)
    if deferred is not None:
        return deferred
    return {
        "status": result.status,
        "sent": result.sent,
        "deferred": False,
        "reason": result.reason,
        "resend_skipped": result.resend_skipped,
        "average": result.average,
        "realized": None if result.realized is None else str(result.realized),
    }


def _refuse_blocked_order(strategy, action: str) -> None:
    reason = order_block_reason(strategy, action)
    if reason is None:
        return
    kind = "order_not_sent" if reason in ("KILL_SWITCH", "profit lock") else "validation_rejected"
    try:
        _store_audit(
            AuditIn(
                kind=kind,
                strategy=strategy.strategy_id,
                symbol=strategy.symbol,
                reason=reason,
                venue=strategy.venue,
            )
        )
    except Exception:
        logger.warning("order rejection was not stored")
    raise HTTPException(status_code=403, detail=reason)


def _deferred_response(result) -> dict[str, object] | None:
    if result.follow_up is None:
        return None
    Thread(target=result.follow_up, daemon=True).start()
    return {"status": "accepted", "sent": True, "deferred": True, "reason": ""}


@app.get("/api/mexc/open-orders")
def mexc_open_orders(authorization: str | None = Header(default=None)) -> dict:
    _require_secret(authorization)
    return open_orders_payload()


def _sync_lots_forever() -> None:
    while True:
        time.sleep(3600)
        try:
            from app.execution.strategy_lots import sync_configured_venues

            sync_configured_venues()
        except Exception:
            logger.warning("strategy lots were not synced")


def _watch_position_gaps_forever() -> None:
    while True:
        time.sleep(60)
        try:
            from app.execution.position_gap import watch_once

            watch_once()
        except Exception:
            logger.warning("position gap was not checked")


def _import_venue_fills_forever() -> None:
    global _warm_stamp
    while True:
        try:
            from app.analytics.importer import ingest_venue_fills

            with _connect() as connection:
                inserted = ingest_venue_fills(connection, datetime.now(timezone.utc))
            if inserted:
                _warm_stamp = None
        except Exception:
            logger.warning("venue fills were not read")
        time.sleep(60)


def _preload_mexc() -> None:
    if os.environ.get("MEXC_API_KEY", "").strip() and os.environ.get("MEXC_API_SECRET", "").strip():
        try:
            from app.execution.exchange import mexc_client
            from app.execution.positions import cancel_resting_orders, load_open_buys

            exchange = mexc_client()
            strategies = load_strategies()
            cancel_resting_orders(exchange, strategies)
            from app.execution.strategy_lots import configured

            if not configured():
                load_open_buys(exchange, strategies)
        except Exception:
            logger.warning("mexc positions were not loaded")
    if os.environ.get("MEXC_FUTURES_API_KEY", "").strip() and os.environ.get("MEXC_FUTURES_API_SECRET", "").strip():
        try:
            from app.execution.futures import cancel_open_futures_orders

            cancel_open_futures_orders()
        except Exception:
            logger.warning("mexc futures orders were not cancelled")
    try:
        from app.execution.strategy_lots import sync_configured_venues

        sync_configured_venues()
    except Exception:
        logger.warning("strategy lots were not synced")


def _apply_added_leverage() -> None:
    from app.execution.venue_port import ports

    for venue_id, port in ports().items():
        try:
            port.apply_leverage()
        except Exception:
            logger.warning("venue leverage was not applied: %s", venue_id)


@asynccontextmanager
async def _lifespan(_app):
    from app.execution.venue_port import load_ports

    require_secret_strength("ANALYTICS_API_SECRET")
    load_ports()
    Thread(target=_preload_mexc, daemon=True).start()
    if os.environ.get("ANALYTICS_DATABASE_URL", "").strip():
        with _connect() as connection:
            ensure_read_indexes(connection)
        Thread(target=_sync_lots_forever, daemon=True).start()
        Thread(target=_watch_position_gaps_forever, daemon=True).start()
        Thread(target=_import_venue_fills_forever, daemon=True).start()
        if os.environ.get("PROTECTIVE_STOP_WATCH", "1") != "0":
            from app.execution.protective_stop import watch_forever

            Thread(target=lambda: watch_forever(time.sleep), daemon=True).start()
            from app.execution.close_retry import watch_forever as watch_closes

            Thread(target=lambda: watch_closes(time.sleep), daemon=True).start()
        if os.environ.get("ANALYTICS_BOARD_REFRESH") == "1":
            _load_board_snapshot()
            Thread(target=_warm_board_forever, daemon=True).start()
    if (
        os.environ.get("ARCUS_APPLY_LEVERAGE") == "1"
        and os.environ.get("ARCUS_ADDRESS", "").strip()
        and os.environ.get("ARCUS_SIGNING_KEY", "").strip()
    ):

        def quiet() -> None:
            try:
                apply_configured_leverage()
            except ArcusError as exc:
                logger.warning("%s", exc)
            except Exception:
                logger.warning("arcus leverage was not applied")

        Thread(target=quiet, daemon=True).start()
    Thread(target=_apply_added_leverage, daemon=True).start()
    yield


app.router.lifespan_context = _lifespan


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/balance")
def balance(authorization: str | None = Header(default=None)) -> dict:
    _require_secret(authorization)
    try:
        fetched_at = datetime.now(timezone.utc)
        with ThreadPoolExecutor(max_workers=3) as pool:
            spot_call = pool.submit(_spot_balance)
            futures_call = pool.submit(_futures_balance)
            arcus_call = pool.submit(_arcus_balance)
            view = spot_call.result()
            futures_view = futures_call.result()
            arcus_view = arcus_call.result()
    except Exception:
        raise HTTPException(status_code=503, detail="balance was not read") from None
    return {
        "fetched_at": fetched_at.isoformat(),
        **_balance_json(view),
        "futures": None if futures_view is None else _balance_json(futures_view),
        "arcus": _arcus_balance_json(arcus_view),
        **_added_balances(),
    }


def _audit_json(row: tuple) -> dict[str, str]:
    return {
        "recorded_at": row[0].isoformat(),
        "kind": row[1],
        "strategy": row[2],
        "symbol": row[3],
        "reason": row[4],
        "discord_status": row[5],
        "discord_detail": row[6],
        "venue": row[7] if len(row) > 7 else "",
    }


@app.get("/api/audits")
def audits(
    authorization: str | None = Header(default=None),
    limit: int | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
) -> dict:
    _require_secret(authorization)
    try:
        with _connect() as connection:
            create_schema(connection)
            if limit is None:
                rows = load_audits(connection)
                return {"audits": [_audit_json(row) for row in rows]}
            size = min(max(limit, 1), 200)
            summary = load_audit_summary(connection)
            rows = load_audit_page(connection, limit=size, offset=offset)
    except Exception:
        raise HTTPException(status_code=500, detail="analytics was not read") from None
    latest = summary["latest_failure"]
    return {
        "audits": [_audit_json(row) for row in rows],
        "count": summary["count"],
        "success": summary["success"],
        "failed": summary["failed"],
        "latest_failure": None if latest is None else latest.isoformat(),
        "limit": size,
        "offset": offset,
    }


@app.get("/api/trades")
def trades(
    request: Request,
    authorization: str | None = Header(default=None),
    limit: int | None = Query(default=None),
) -> dict:
    _require_secret(authorization)
    if limit is None:
        cached = _cached_trades()
        if cached is not None:
            return {"trades": cached}
        return {"trades": _trade_rows(_load_fill_views())}
    size = min(max(limit, 1), 100)
    offsets = {}
    for key, value in request.query_params.items():
        if key.startswith("o_") and str(value).isdigit():
            offsets[key[2:]] = int(value)
    return _paged_trades(size, offsets)


@app.get("/api/positions")
def positions(authorization: str | None = Header(default=None)) -> dict:
    _require_secret(authorization)
    _closed, opens = reconstruct(_load_open_fill_views())
    opens = _held_opens(opens)
    marked = mark_opens(opens, _mark_prices(opens))
    return {"positions": [_position_json(item) for item in marked]}


@app.get("/api/pnl")
def pnl(authorization: str | None = Header(default=None)) -> dict:
    _require_secret(authorization)
    closed, _opens = reconstruct(_load_fill_views())
    now = datetime.now(timezone.utc)
    return _pnl_json(closed, now, forecast=True)


@app.get("/api/strategies")
def strategies(authorization: str | None = Header(default=None)) -> dict:
    _require_secret(authorization)
    fills = _load_fill_views()
    closed, _opens = reconstruct(fills)
    rows = attach_volumes(strategy_rows(closed), fills, by="strategy")
    return {"strategies": [_strategy_json(row) for row in rows]}


@app.get("/api/tickers")
def tickers(authorization: str | None = Header(default=None)) -> dict:
    _require_secret(authorization)
    fills = _load_fill_views()
    closed, _opens = reconstruct(fills)
    rows = attach_volumes(ticker_rows(closed), fills, by="ticker")
    return {"tickers": [_ticker_json(row) for row in rows]}


@app.get("/api/board")
def board(summary: bool = False, authorization: str | None = Header(default=None)) -> dict:
    _require_secret(authorization)
    if summary:
        payload = _ensure_board()
        return _publish_board(_summary_board(payload))
    if _board_refresh_enabled():
        payload = _cached_board()
        if payload is None:
            payload = _load_board_snapshot()
        if payload is None:
            raise HTTPException(status_code=503, detail="board is warming")
        if payload.get("board_scope") == "summary":
            raise HTTPException(status_code=503, detail="board is warming")
        return _publish_board(payload)
    return _publish_board(_build_board())


def _build_board() -> dict:
    return _assemble_board(_load_board_sources(), summary=False)


def _build_summary_board() -> dict:
    # 30 秒ごとの再構築は、約定の全行と監査の全行を残さない。
    # 前日より前の FIFO は固定し、増えた約定だけを足す。
    sources, prepared, daily, strategy_notional, symbol_notional = _load_summary_sources()
    return _assemble_board(
        sources,
        summary=True,
        prepared=prepared,
        daily=daily,
        strategy_notional=strategy_notional,
        symbol_notional=symbol_notional,
    )


def _assemble_board(
    sources: tuple[list[FillView], list | None, datetime | None],
    *,
    summary: bool,
    prepared: tuple | None = None,
    daily: list | None = None,
    strategy_notional: dict | None = None,
    symbol_notional: dict | None = None,
) -> dict:
    fills, audit_rows, succeeded_at = sources
    if prepared is None:
        closed, opens = reconstruct(fills)
        trade_rows = _trade_rows(fills)
        _remember_trades(trade_rows)
    else:
        closed, opens = prepared
        _remember_incremental_trades(fills, closed, _fifo_cutoff(now))
        trade_rows = []
    now = datetime.now(timezone.utc)
    opens = _held_opens(opens)
    marked = mark_opens(opens, _mark_prices(opens))
    if daily is None:
        volume = _volume_json(fills, now)
        volume_by_venue = {
            venue: _volume_json([item for item in fills if item.venue == venue], now)
            for venue in _volume_venues(fills)
        }
        volume_by_asset_class = {
            "spot": _volume_json(_class_fills(fills, "spot"), now),
            "futures": _volume_json(_class_fills(fills, "futures"), now),
        }
        strategies = attach_volumes(strategy_rows(closed), fills, by="strategy")
        tickers = attach_volumes(ticker_rows(closed), fills, by="ticker")
    else:
        volume = _volume_json_daily(daily, now)
        venues = sorted({venue for _day, venue, _amount in daily})
        volume_by_venue = {
            venue: _volume_json_daily([row for row in daily if row[1] == venue], now) for venue in venues
        }
        volume_by_asset_class = {
            "spot": _volume_json_daily([row for row in daily if is_spot(row[1])], now),
            "futures": _volume_json_daily([row for row in daily if is_futures(row[1])], now),
        }
        strategies = attach_notional(strategy_rows(closed), strategy_notional or {}, by="strategy")
        tickers = attach_notional(ticker_rows(closed), symbol_notional or {}, by="ticker")
    payload = {
        "pnl": _pnl_json(closed, now, forecast=True),
        "pnl_by_venue": {
            venue: _pnl_json([item for item in closed if item.venue == venue], now, forecast=False)
            for venue in sorted({item.venue for item in closed})
        },
        "pnl_by_asset_class": {
            "spot": _pnl_json(_class_closed(closed, "spot"), now, forecast=False),
            "futures": _pnl_json(_class_closed(closed, "futures"), now, forecast=False),
        },
        "volume": volume,
        "volume_by_venue": volume_by_venue,
        "volume_by_asset_class": volume_by_asset_class,
        "positions": [_position_json(item) for item in marked],
        "trades": [] if summary else trade_rows,
        "strategies": [_strategy_json(row) for row in strategies],
        "tickers": [_ticker_json(row) for row in tickers],
        "audits": None if audit_rows is None else [_audit_json(row) for row in audit_rows],
        "ingest_succeeded_at": None if succeeded_at is None else succeeded_at.isoformat(),
    }
    if summary:
        payload["board_scope"] = "summary"
    return payload


@app.post("/api/order-links")
def append_order_link(
    body: OrderLinkIn,
    authorization: str | None = Header(default=None),
) -> dict[str, str]:
    if not analytics_secret_matches(_presented_secret(authorization)):
        raise HTTPException(status_code=401, detail="unauthorized")
    try:
        _store_link(body)
    except Exception:
        raise HTTPException(status_code=500, detail="order link was not stored") from None
    return {"status": "ok"}


def _connect():
    url = os.environ.get("ANALYTICS_DATABASE_URL", "")
    if not url:
        raise RuntimeError("analytics database is not configured")
    return psycopg.connect(url)


def _store_audit(body: AuditIn) -> None:
    recorded_at = datetime.now(timezone.utc)
    with _connect() as connection:
        create_schema(connection)
        insert_audit(
            connection,
            kind=body.kind,
            strategy=body.strategy,
            symbol=body.symbol,
            reason=body.reason,
            recorded_at=recorded_at,
            discord_status=body.discord_status,
            discord_detail=body.discord_detail,
            venue=body.venue,
        )


def _require_secret(authorization: str | None) -> None:
    if not analytics_secret_matches(_presented_secret(authorization)):
        raise HTTPException(status_code=401, detail="unauthorized")


def _fill_view(row: tuple) -> FillView:
    return FillView(
        trade_id=row[0],
        symbol=row[1],
        side=row[2],
        quantity=row[3],
        quote_spent=row[4],
        quote_received=row[5],
        fee=row[6],
        filled_at=row[7],
        strategy_name=row[8],
        client_order_id=row[9],
        fill_price=row[10],
        fee_asset=row[11],
        venue=row[12] if len(row) > 12 and row[12] else "mexc_spot",
        exchange_client_order_id=row[13] if len(row) > 13 and row[13] else None,
    )


def _load_fill_views() -> list[FillView]:
    try:
        with _connect() as connection:
            create_schema(connection)
            rows = load_fills(connection)
    except Exception:
        raise HTTPException(status_code=500, detail="analytics was not read") from None
    return [_fill_view(row) for row in rows]


def _load_open_fill_views() -> list[FillView]:
    try:
        with _connect() as connection:
            create_schema(connection)
            keys = load_open_fill_keys(connection)
            rows = load_fills_for_keys(connection, keys)
    except Exception:
        raise HTTPException(status_code=500, detail="analytics was not read") from None
    return [_fill_view(row) for row in rows]


def _paged_trades(limit: int, offsets: dict[str, int]) -> dict:
    try:
        with _connect() as connection:
            create_schema(connection)
            venues = load_fill_venues(connection)
            today = datetime.now(ZoneInfo("Asia/Tokyo")).replace(hour=0, minute=0, second=0, microsecond=0)
            pages = {}
            rows = []
            for venue in venues:
                offset = max(0, offsets.get(venue, 0))
                summary = load_trade_summary(connection, venue, today)
                page = load_fill_page(connection, venue, limit=limit, offset=offset)
                fills = [_fill_view(row) for row in page]
                names = list({fill.strategy_name for fill in fills})
                history = [_fill_view(row) for row in load_fills_for_names(connection, venue, names)]
                realized = final_fill_realized(history)
                traded = []
                for fill in fills:
                    item = _fill_json(fill)
                    amount = realized.get(fill.trade_id)
                    item["realized"] = None if amount is None else _decimal(amount)
                    traded.append(item)
                pages[venue] = {
                    "count": summary["count"],
                    "today": summary["today"],
                    "buy": summary["buy"],
                    "sell": summary["sell"],
                    "unclassified": summary["unclassified"],
                    "volume": format(summary["volume"], "f"),
                    "offset": offset,
                    "limit": limit,
                    "trades": traded,
                }
                rows.extend(traded)
    except Exception:
        raise HTTPException(status_code=500, detail="analytics was not read") from None
    return {"trades": rows, "pages": pages}


def _board_refresh_enabled() -> bool:
    return os.environ.get("ANALYTICS_BOARD_REFRESH") == "1"


def _snapshot_path() -> Path:
    raw = os.environ.get("ANALYTICS_BOARD_SNAPSHOT", "").strip()
    if raw:
        return Path(raw)
    home = os.environ.get("HOME", "").strip()
    base = Path(home) if home else Path("/tmp")
    return base / "signal-nexus-board.json"


def _cached_board() -> dict | None:
    with _board_lock:
        return _board_snapshot


def _remember_board(payload: dict) -> None:
    global _board_snapshot
    with _board_lock:
        _board_snapshot = payload
    _write_board_snapshot(payload)


def _write_board_snapshot(payload: dict) -> None:
    path = _snapshot_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        tmp.replace(path)
    except Exception as exc:
        logger.warning("board snapshot was not saved: %s", type(exc).__name__)


def _load_board_snapshot() -> dict | None:
    path = _snapshot_path()
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(loaded, dict):
        return None
    global _board_snapshot
    with _board_lock:
        if _board_snapshot is None:
            _board_snapshot = loaded
        return _board_snapshot


def _ensure_board() -> dict:
    payload = _cached_board()
    if payload is not None:
        return payload
    with _board_build_lock:
        payload = _cached_board()
        if payload is not None:
            return payload
        payload = _load_board_snapshot()
        if payload is not None:
            return payload
        payload = _build_summary_board()
        _remember_board(payload)
        return payload


def _cached_trades() -> list | None:
    with _board_lock:
        return None if _trade_snapshot is None else list(_trade_snapshot)


def _remember_trades(rows: list) -> None:
    global _trade_snapshot
    with _board_lock:
        _trade_snapshot = list(rows)


def _clear_board_cache() -> None:
    global _board_snapshot, _trade_snapshot, _warm_stamp, _fifo_state
    _warm_stamp = None
    with _fifo_lock:
        _fifo_state = None
    _clear_mark_cache()
    with _board_lock:
        _board_snapshot = None
        _trade_snapshot = None
    try:
        _snapshot_path().unlink(missing_ok=True)
    except Exception:
        pass


def _summary_board(payload: dict) -> dict:
    audits = payload.get("audits")
    latest = None
    if audits:
        received = [row for row in audits if row.get("kind") == "signal_received"]
        if received:
            latest = max(received, key=lambda row: row.get("recorded_at") or "")
    trimmed = dict(payload)
    trimmed["trades"] = []
    trimmed["tickers"] = []
    if audits is None:
        trimmed["audits"] = None
    elif latest is None:
        trimmed["audits"] = []
    else:
        trimmed["audits"] = [latest]
    return trimmed


_warm_stamp: str | None = None


def _ingest_stamp() -> str | None:
    with _connect() as connection:
        _ensure_schema(connection)
        stamp = load_ingest_succeeded_at(connection)
    if stamp is None:
        return None
    return stamp.isoformat()


def _refresh_summary_board() -> None:
    global _warm_stamp
    stamp = _ingest_stamp()
    cached = _cached_board()
    if cached is not None and stamp == _warm_stamp and _marks_complete(cached):
        return
    with _board_build_lock:
        cached = _cached_board()
        if cached is not None and stamp == _warm_stamp and _marks_complete(cached):
            return
        payload = _build_summary_board()
        _reuse_marks(payload, cached)
    _remember_board(payload)
    _warm_stamp = payload.get("ingest_succeeded_at") if _marks_complete(payload) else None


def _marks_complete(payload: dict) -> bool:
    return all(row.get("unrealized") not in (None, "") for row in payload.get("positions") or [])


def _reuse_marks(payload: dict, previous: dict | None) -> None:
    if not previous:
        return
    kept = {
        (row.get("venue"), row.get("strategy_name"), row.get("symbol")): row.get("unrealized")
        for row in previous.get("positions") or []
        if row.get("unrealized") not in (None, "")
    }
    rows = []
    for row in payload.get("positions") or []:
        if row.get("unrealized") in (None, ""):
            value = kept.get((row.get("venue"), row.get("strategy_name"), row.get("symbol")))
            if value not in (None, ""):
                row = {**row, "unrealized": value}
        rows.append(row)
    payload["positions"] = rows


def _publish_board(payload: dict) -> dict:
    body = dict(payload)
    body.pop("board_scope", None)
    return body


def _warm_board_forever() -> None:
    while True:
        try:
            _refresh_summary_board()
        except Exception as exc:
            logger.warning("board was not refreshed: %s", type(exc).__name__)
        time.sleep(30)


def _ensure_schema(connection) -> None:
    global _schema_for
    url = os.environ.get("ANALYTICS_DATABASE_URL", "")
    if url and _schema_for == url:
        return
    create_schema(connection)
    _schema_for = url


def _load_board_sources() -> tuple[list[FillView], list | None, datetime | None]:
    try:
        with _connect() as connection:
            _ensure_schema(connection)
            fills = [_fill_view(row) for row in load_fills(connection)]
            succeeded_at = load_ingest_succeeded_at(connection)
            try:
                with connection.transaction():
                    audits = load_audits(connection)
            except Exception:
                audits = None
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="analytics was not read") from None
    return fills, audits, succeeded_at


_fifo_lock = Lock()
_fifo_state: tuple | None = None


def _fifo_cutoff(now: datetime) -> datetime:
    # UTC の前日 0 時より前を固定する。昨日と今日の約定は毎回足す。
    day = now.astimezone(timezone.utc).date() - timedelta(days=1)
    return datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)


def _load_summary_sources():
    try:
        cutoff = _fifo_cutoff(datetime.now(timezone.utc))
        with _connect() as connection:
            _ensure_schema(connection)
            checksum = load_fill_prefix_checksum(connection, cutoff)
            frozen = _frozen_books(cutoff, checksum)
            if frozen is None:
                fills = [_fill_view(row) for row in load_fills(connection)]
                closed, books = freeze_books(fills, cutoff)
                _store_frozen(cutoff, checksum, closed, books)
                prepared = None
                daily = None
                strategy_notional = None
                symbol_notional = None
            else:
                fills = [_fill_view(row) for row in load_fills_since(connection, cutoff)]
                prepared = replay_books(frozen[0], frozen[1], fills)
                daily = [
                    (row[0], row[1], Decimal(row[2])) for row in load_daily_notional(connection)
                ]
                strategy_notional = _notional_map(load_notional_by(connection, "strategy_name"), skip_unclassified=True)
                symbol_notional = _notional_map(load_notional_by(connection, "symbol"), skip_unclassified=False)
            succeeded_at = load_ingest_succeeded_at(connection)
            try:
                with connection.transaction():
                    latest = load_latest_signal(connection)
                audits = [] if latest is None else [latest]
            except Exception:
                audits = None
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="analytics was not read") from None
    return (fills, audits, succeeded_at), prepared, daily, strategy_notional, symbol_notional


def _frozen_books(cutoff: datetime, checksum: tuple) -> tuple | None:
    with _fifo_lock:
        state = _fifo_state
    if state is None or state[0] != cutoff or state[1] != checksum:
        return None
    return state[2], state[3]


def _store_frozen(cutoff: datetime, checksum: tuple, closed: list, books: dict) -> None:
    global _fifo_state
    with _fifo_lock:
        _fifo_state = (cutoff, checksum, closed, books)


def _notional_map(rows: list[tuple], *, skip_unclassified: bool) -> dict[tuple[str, str], Decimal]:
    totals: dict[tuple[str, str], Decimal] = {}
    for name, venue, amount in rows:
        label = name or "未分類"
        if skip_unclassified and label == "未分類":
            continue
        totals[(label, venue)] = Decimal(amount)
    return totals


_mark_lock = Lock()
_last_marks: dict[tuple[str, str], Decimal] = {}
MARK_TIMEOUT = 2.5


def _clear_mark_cache() -> None:
    with _mark_lock:
        _last_marks.clear()


def _keep_marks(wanted: set[tuple[str, str]], fresh: dict[tuple[str, str], Decimal]) -> dict:
    with _mark_lock:
        kept: dict[tuple[str, str], Decimal] = {}
        for pair in wanted:
            if pair in fresh:
                _last_marks[pair] = fresh[pair]
                kept[pair] = fresh[pair]
            elif pair in _last_marks:
                kept[pair] = _last_marks[pair]
        for pair in [key for key in _last_marks if key not in wanted]:
            del _last_marks[pair]
        return kept


def _mark_prices(opens) -> dict:
    # ccxt の銘柄一覧は現物と先物を毎回まとめて取る。建玉の数だけ足すとタブが10秒になる。
    if not opens:
        return _keep_marks(set(), {})
    wanted = {(position.symbol, position.venue) for position in opens}
    fresh: dict[tuple[str, str], Decimal] = {}

    def read(pair: tuple[str, str]) -> tuple[tuple[str, str], Decimal | None]:
        symbol, venue = pair
        try:
            if venue == "mexc_futures":
                response = httpx.get(
                    "https://contract.mexc.com/api/v1/contract/ticker",
                    params={"symbol": symbol.replace("/", "_")},
                    timeout=MARK_TIMEOUT,
                )
            elif venue == "mexc_spot":
                response = httpx.get(
                    "https://api.mexc.com/api/v3/ticker/price",
                    params={"symbol": symbol.replace("/", "")},
                    timeout=MARK_TIMEOUT,
                )
            elif venue == "arcus":
                response = httpx.get(
                    "https://api.arcus.xyz/v1/markets",
                    params={"market": symbol.replace("/", "-")},
                    timeout=MARK_TIMEOUT,
                )
            else:
                from app.execution.venue_port import port_for

                port = port_for(venue)
                if port is None:
                    return pair, None
                from app.venues import order_symbol

                one = ThreadPoolExecutor(max_workers=1)
                try:
                    return pair, one.submit(port.mark, order_symbol(symbol, venue)).result(timeout=MARK_TIMEOUT)
                except Exception:
                    return pair, None
                finally:
                    one.shutdown(wait=False, cancel_futures=True)
            response.raise_for_status()
            return pair, _public_last(response.json(), venue)
        except Exception:
            return pair, None

    with ThreadPoolExecutor(max_workers=8) as pool:
        for pair, last in pool.map(read, wanted):
            if last is not None:
                fresh[pair] = last
    return _keep_marks(wanted, fresh)


def _public_last(body, venue: str) -> Decimal | None:
    if venue == "mexc_futures":
        data = body.get("data") if isinstance(body, dict) else None
        if isinstance(data, list):
            data = data[0] if data else None
        price = data.get("lastPrice") if isinstance(data, dict) else None
    elif venue == "arcus":
        markets = body.get("markets") if isinstance(body, dict) else None
        row = markets[0] if isinstance(markets, list) and markets else None
        price = row.get("markPrice") if isinstance(row, dict) else None
    else:
        if isinstance(body, list):
            body = body[0] if body else None
        price = body.get("price") if isinstance(body, dict) else None
    if price in (None, ""):
        return None
    return Decimal(str(price))


def _spot_balance() -> dict:
    from app.analytics.importer import analytics_exchange
    from app.portal_model import balances_view

    payload = analytics_exchange().spotPrivateGetAccount({})
    rows = payload.get("balances") if isinstance(payload, dict) else None
    return balances_view(_currency_rows(rows, "asset", "free", "locked"))


def _currency_rows(rows, code_key: str, free_key: str, used_key: str) -> dict:
    view = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        code = row.get(code_key)
        if code:
            view[str(code)] = {"free": row.get(free_key), "used": row.get(used_key)}
    return view


def _futures_rows(rows) -> list[dict]:
    prepared = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        copied = dict(row)
        copied["frozenBalance"] = format(
            _balance_amount(row.get("frozenBalance")) + _balance_amount(row.get("positionMargin")),
            "f",
        )
        prepared.append(copied)
    return prepared


def _balance_amount(value) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _decimal(value: Decimal) -> str:
    return format(value, "f")


def _trade_rows(fills: list[FillView]) -> list[dict]:
    realized = final_fill_realized(fills)
    return _rows_with_realized(fills, realized)


def _remember_incremental_trades(fills: list[FillView], closed: list, cutoff: datetime) -> None:
    # 前日より前の行は残し、それ以降だけ増分の決済損益で置き換える。
    previous = _cached_trades()
    if not previous:
        return
    realized = {trade.final_trade_id: trade.realized for trade in closed if trade.final_trade_id}
    recent = _rows_with_realized(fills, realized)
    cutoff_text = cutoff.isoformat()
    kept = [row for row in previous if str(row.get("filled_at") or "") < cutoff_text]
    _remember_trades([*kept, *recent])


def _rows_with_realized(fills: list[FillView], realized: dict) -> list[dict]:
    rows = []
    for fill in fills:
        row = _fill_json(fill)
        amount = realized.get(fill.trade_id)
        row["realized"] = None if amount is None else _decimal(amount)
        rows.append(row)
    return rows


def _fill_json(fill: FillView) -> dict:
    return {
        "trade_id": fill.trade_id,
        "symbol": fill.symbol,
        "side": fill.side,
        "quantity": _decimal(fill.quantity),
        "quote_spent": _decimal(fill.quote_spent),
        "quote_received": _decimal(fill.quote_received),
        "filled_at": fill.filled_at.isoformat(),
        "strategy_name": fill.strategy_name,
        "fill_price": None if fill.fill_price is None else _decimal(fill.fill_price),
        "venue": fill.venue,
    }


def _period_json(row: dict) -> dict:
    return {"period": row["period"], "realized": _decimal(row["realized"])}


def _volume_period_json(row: dict) -> dict:
    return {"period": row["period"], "volume": _decimal(row["volume"])}


def _class_closed(closed, asset_class: str):
    wanted = is_spot if asset_class == "spot" else is_futures
    return [item for item in closed if wanted(item.venue)]


def _class_fills(fills: list[FillView], asset_class: str) -> list[FillView]:
    wanted = is_spot if asset_class == "spot" else is_futures
    return [fill for fill in fills if wanted(fill.venue)]


def _volume_venues(fills: list[FillView]) -> list[str]:
    present = {fill.venue for fill in fills}
    names = ["mexc_futures"]
    for venue in sorted(present):
        if venue not in names:
            names.append(venue)
    return names


def _volume_json(fills: list[FillView], now: datetime) -> dict:
    periods = volume_rows(fills, now)
    return {name: [_volume_period_json(row) for row in rows] for name, rows in periods.items()}


def _volume_json_daily(rows: list, now: datetime) -> dict:
    periods = volume_rows_from_daily(rows, now)
    return {name: [_volume_period_json(row) for row in period_rows] for name, period_rows in periods.items()}


def _forecast_json(row: dict) -> dict:
    return {
        "month": row["month"],
        "target": None if row["target"] is None else _decimal(row["target"]),
        "actual": _decimal(row["actual"]),
        "achievement": None if row["achievement"] is None else _decimal(row["achievement"]),
        "remaining": None if row["remaining"] is None else _decimal(row["remaining"]),
        "forecast": _decimal(row["forecast"]),
        "elapsed_days": row["elapsed_days"],
        "days_in_month": row["days_in_month"],
    }


def _strategy_json(row: dict) -> dict:
    return _metric_json(row, "strategy_name")


def _ticker_json(row: dict) -> dict:
    return _metric_json(row, "symbol")


def _held_opens(opens):
    try:
        from app.execution.strategy_lots import configured, connect

        if not configured():
            return opens
        with connect() as connection:
            create_schema(connection)
            return held_opens(opens, load_all_strategy_lots(connection))
    except Exception:
        return opens


def _position_json(item) -> dict:
    return {
        "strategy_name": item.strategy_name,
        "symbol": item.symbol,
        "venue": item.venue,
        "quantity": _decimal(item.quantity),
        "quote_spent": _decimal(item.quote_spent),
        "opened_at": item.opened_at.isoformat(),
        "unrealized": None if item.unrealized is None else _decimal(item.unrealized),
        "side": item.side or "",
    }


def _pnl_json(closed, now: datetime, *, forecast: bool) -> dict:
    periods = period_rows(closed, now)
    body = {
        "days": [_period_json(row) for row in periods["days"]],
        "weeks": [_period_json(row) for row in periods["weeks"]],
        "months": [_period_json(row) for row in periods["months"]],
        "years": [_period_json(row) for row in periods["years"]],
    }
    if forecast:
        body["forecast"] = _forecast_json(month_forecast(closed, now, read_month_target()))
    return body


def _futures_balance():
    try:
        from app.analytics.importer import analytics_futures_exchange
        from app.portal_model import balances_view

        payload = analytics_futures_exchange().contractPrivateGetAccountAssets({})
        if isinstance(payload, dict) and payload.get("success") is False:
            return None
        rows = payload.get("data") if isinstance(payload, dict) else None
        return balances_view(
            _currency_rows(_futures_rows(rows), "currency", "availableBalance", "frozenBalance")
        )
    except Exception:
        return None


def _arcus_balance() -> dict | None:
    try:
        from app.execution.arcus_read import arcus_balance

        return arcus_balance()
    except Exception:
        return None


def _added_balances() -> dict:
    from app.execution.venue_port import ports

    added = {}
    for venue_id, port in ports().items():
        try:
            added[venue_id] = _arcus_balance_json(port.balance())
        except Exception:
            added[venue_id] = None
    return added


def _arcus_balance_json(view: dict | None) -> dict | None:
    if view is None:
        return None
    return {
        "equity": _decimal(view["equity"]),
        "free": _decimal(view["free"]),
        "margin": _decimal(view["margin"]),
        "positions": view["positions"],
    }


def _balance_json(view: dict) -> dict:
    return {
        "usdt": {key: _decimal(view["usdt"][key]) for key in ("free", "used", "total")},
        "count": view["count"],
        "coins": [
            {
                "code": row["code"],
                "free": _decimal(row["free"]),
                "used": _decimal(row["used"]),
                "total": _decimal(row["total"]),
            }
            for row in view["coins"]
        ],
    }


def _metric_json(row: dict, name_key: str) -> dict:
    return {
        name_key: row[name_key],
        "venue": row.get("venue") or "mexc_spot",
        "count": row["count"],
        "realized": _decimal(row["realized"]),
        "quote_spent": _decimal(row["quote_spent"]),
        "win_rate": None if row["win_rate"] is None else _decimal(row["win_rate"]),
        "profit_rate": None if row["profit_rate"] is None else _decimal(row["profit_rate"]),
        "profit_factor": None if row["profit_factor"] is None else _decimal(row["profit_factor"]),
        "per_trade": None if row["per_trade"] is None else _decimal(row["per_trade"]),
        "volume": _decimal(row.get("volume") or Decimal("0")),
    }


def _store_link(body: OrderLinkIn) -> None:
    with _connect() as connection:
        create_schema(connection)
        link_order(
            connection,
            exchange_client_order_id=body.exchange_client_order_id,
            client_order_id=body.client_order_id,
            signal_time=body.signal_time,
            signal_price=body.signal_price,
        )


def main() -> None:
    import uvicorn

    port = int(os.environ.get("ANALYTICS_API_PORT", "8080"))
    uvicorn.run(app, host=analytics_bind_host(), port=port)


if __name__ == "__main__":
    main()
