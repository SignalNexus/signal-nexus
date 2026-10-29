import logging
import os
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from threading import Lock

import yaml

logger = logging.getLogger(__name__)

POLL_SECONDS = 5

_held: ContextVar[dict | None] = ContextVar("protective_stop_hold", default=None)
_skip_lock = Lock()
_skip_notices: set[tuple[str, str, str, str]] = set()


@dataclass(frozen=True)
class StopPolicy:
    enabled: bool
    loss_pct: Decimal | None = None
    profit_pct: Decimal | None = None


@dataclass(frozen=True)
class StopDefaults:
    global_policy: StopPolicy | None = None
    venues: tuple[tuple[str, StopPolicy], ...] = ()

    def venue_policy(self, venue: str) -> StopPolicy | None:
        for name, policy in self.venues:
            if name == venue:
                return policy
        return None


@dataclass(frozen=True)
class StopRow:
    venue: str
    strategy_id: str
    symbol: str
    side: str
    entry_price: Decimal
    stop_price: Decimal | None
    take_profit_price: Decimal | None
    loss_pct: Decimal | None
    profit_pct: Decimal | None
    status: str
    client_order_id: str
    trigger_price: Decimal | None
    armed_at: datetime
    triggered_at: datetime | None
    closed_at: datetime | None
    attempt_count: int
    unconfirmed: bool


def defaults_path() -> Path:
    from app.config_dir import config_file

    return config_file("protective_exit.yml")


def policy_from_mapping(block: object) -> StopPolicy:
    from app.execution.router import RegistryRejection

    if not isinstance(block, dict) or not isinstance(block.get("enabled"), bool):
        raise RegistryRejection("protective exit is invalid")
    loss_pct = _percent(block["loss_pct"]) if "loss_pct" in block else None
    profit_pct = _percent(block["profit_pct"]) if "profit_pct" in block else None
    if block["enabled"] and loss_pct is None and profit_pct is None:
        raise RegistryRejection("protective exit is invalid")
    return StopPolicy(block["enabled"], loss_pct, profit_pct)


def load_exit_defaults(path: Path | None = None) -> StopDefaults:
    from app.execution.router import RegistryRejection

    source = defaults_path() if path is None else path
    if not source.is_file():
        return StopDefaults()
    loaded = yaml.safe_load(source.read_text(encoding="utf-8"))
    if loaded is None:
        return StopDefaults()
    if not isinstance(loaded, dict) or set(loaded) - {"protective_exit", "venues"}:
        raise RegistryRejection("protective exit is invalid")
    global_policy = None
    if "protective_exit" in loaded:
        global_policy = policy_from_mapping(loaded["protective_exit"])
    venues = loaded.get("venues", {})
    if not isinstance(venues, dict):
        raise RegistryRejection("protective exit is invalid")
    from app.venues import load_venues

    known = load_venues()
    rows = []
    for venue, block in venues.items():
        if not isinstance(venue, str) or venue not in known:
            raise RegistryRejection("protective exit is invalid")
        rows.append((venue, policy_from_mapping(block)))
    return StopDefaults(global_policy, tuple(rows))


def resolve_policy(strategy, deployment, defaults: StopDefaults | None = None) -> StopPolicy:
    if deployment.protective_exit is not None:
        return deployment.protective_exit
    if strategy.protective_exit is not None:
        return strategy.protective_exit
    found = load_exit_defaults() if defaults is None else defaults
    venue_policy = found.venue_policy(deployment.venue)
    if venue_policy is not None:
        return venue_policy
    if found.global_policy is not None:
        return found.global_policy
    return StopPolicy(False, None)


def stop_price(side: str, entry: Decimal, loss_pct: Decimal) -> Decimal:
    if side == "long":
        return entry * (Decimal("100") - loss_pct) / Decimal("100")
    return entry * (Decimal("100") + loss_pct) / Decimal("100")


def take_profit_price(side: str, entry: Decimal, profit_pct: Decimal) -> Decimal:
    if side == "long":
        return entry * (Decimal("100") + profit_pct) / Decimal("100")
    return entry * (Decimal("100") - profit_pct) / Decimal("100")


def profit_reached(side: str, mark: Decimal, price: Decimal) -> bool:
    if side == "long":
        return mark >= price
    return mark <= price


def choose_trigger(row: StopRow, mark: Decimal) -> tuple[str, Decimal] | None:
    if row.stop_price is not None and crossed(row.side, mark, row.stop_price):
        return "stop", row.stop_price
    if row.take_profit_price is not None and profit_reached(row.side, mark, row.take_profit_price):
        return "take_profit", row.take_profit_price
    return None


def crossed(side: str, mark: Decimal, stop: Decimal) -> bool:
    if side == "long":
        return mark <= stop
    return mark >= stop


def format_price(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def reason_text(level: Decimal, mark: Decimal | None, cause: str | None = None, *, trigger: str = "stop") -> str:
    label = "stop" if trigger == "stop" else "take_profit"
    parts = ["protective_exit", f"{label}={format_price(level)}"]
    if mark is not None:
        parts.append(f"mark={format_price(mark)}")
    if cause:
        parts.append(cause)
    return " ".join(parts)


def exit_action(strategy) -> str:
    from app.venues import is_spot

    if is_spot(strategy.venue):
        return "STOP"
    if strategy.side == "short":
        return "COVER"
    return "FLAT"


def cause_for(reason: str) -> str:
    text = reason.lower()
    if "status unavailable" in text:
        return "state_unconfirmed"
    if "already flat" in text or "bought quantity missing" in text or "already sold" in text:
        return "already_flat"
    if "order step" in text:
        return "below_order_step"
    if "kill_switch" in text or reason == "KILL_SWITCH":
        return "kill_switch_enabled"
    return "venue_rejected"


def hold_exit(**kwargs) -> bool:
    box = _held.get()
    if box is None:
        return False
    box.clear()
    box.update(kwargs)
    return True


@contextmanager
def holding_exit():
    box: dict = {}
    token = _held.set(box)
    try:
        yield box
    finally:
        _held.reset(token)


def arm_from_fill(connection, venue: str, strategy_id: str, fill_price: Decimal) -> None:
    from app.execution.router import RegistryRejection, load_strategies

    try:
        strategies = load_strategies()
    except RegistryRejection:
        logger.warning("protective stop configuration was rejected")
        return
    strategy = strategies.get(strategy_id)
    if strategy is None:
        return
    deployment = next((item for item in strategy.deployments if item.venue == venue), None)
    if deployment is None or not deployment.enabled:
        cancel_armed(connection, venue, strategy_id)
        return
    policy = resolve_policy(strategy, deployment)
    if not policy.enabled or strategy.side not in ("long", "short"):
        cancel_armed(connection, venue, strategy_id)
        return
    if fill_price <= 0:
        return
    stop = None if policy.loss_pct is None else stop_price(strategy.side, fill_price, policy.loss_pct)
    target = None if policy.profit_pct is None else take_profit_price(strategy.side, fill_price, policy.profit_pct)
    if stop is not None and stop <= 0:
        stop = None
    if target is not None and target <= 0:
        target = None
    if stop is None and target is None:
        return
    now = datetime.now(timezone.utc)
    connection.execute(
        """
        INSERT INTO strategy_stops (
            venue, strategy_id, symbol, side, entry_price, stop_price, take_profit_price,
            loss_pct, profit_pct, status, client_order_id, trigger_price, armed_at,
            triggered_at, closed_at, attempt_count, unconfirmed
        )
        VALUES (
            %(venue)s, %(strategy_id)s, %(symbol)s, %(side)s, %(entry_price)s, %(stop_price)s,
            %(take_profit_price)s, %(loss_pct)s, %(profit_pct)s, 'armed', '', NULL, %(armed_at)s,
            NULL, NULL, 0, FALSE
        )
        ON CONFLICT (venue, strategy_id) DO UPDATE
        SET symbol = EXCLUDED.symbol,
            side = EXCLUDED.side,
            entry_price = EXCLUDED.entry_price,
            stop_price = EXCLUDED.stop_price,
            take_profit_price = EXCLUDED.take_profit_price,
            loss_pct = EXCLUDED.loss_pct,
            profit_pct = EXCLUDED.profit_pct,
            status = 'armed',
            client_order_id = '',
            trigger_price = NULL,
            armed_at = EXCLUDED.armed_at,
            triggered_at = NULL,
            closed_at = NULL,
            attempt_count = 0,
            unconfirmed = FALSE
        WHERE strategy_stops.status <> 'triggering'
        """,
        {
            "venue": venue,
            "strategy_id": strategy_id,
            "symbol": strategy.symbol,
            "side": strategy.side,
            "entry_price": fill_price,
            "stop_price": stop,
            "take_profit_price": target,
            "loss_pct": policy.loss_pct,
            "profit_pct": policy.profit_pct,
            "armed_at": now,
        },
    )


def cancel_armed(connection, venue: str, strategy_id: str) -> None:
    connection.execute(
        """
        UPDATE strategy_stops
        SET status = 'cancelled', closed_at = %(now)s
        WHERE venue = %(venue)s AND strategy_id = %(strategy_id)s AND status = 'armed'
        """,
        {"venue": venue, "strategy_id": strategy_id, "now": datetime.now(timezone.utc)},
    )


def load_active(connection) -> list[StopRow]:
    rows = connection.execute(
        """
        SELECT venue, strategy_id, symbol, side, entry_price, stop_price, take_profit_price,
               loss_pct, profit_pct, status, client_order_id, trigger_price, armed_at,
               triggered_at, closed_at, attempt_count, unconfirmed
        FROM strategy_stops
        WHERE status IN ('armed', 'triggering')
        ORDER BY venue, strategy_id
        """
    ).fetchall()
    return [_stop_row(row) for row in rows]


def retire_disabled(connection) -> None:
    from app.execution.router import RegistryRejection, load_strategies

    try:
        strategies = load_strategies()
        defaults = load_exit_defaults()
    except RegistryRejection:
        logger.warning("protective stop configuration was rejected")
        return
    for row in load_active(connection):
        if row.status != "armed":
            continue
        strategy = strategies.get(row.strategy_id)
        deployment = None if strategy is None else next(
            (item for item in strategy.deployments if item.venue == row.venue), None
        )
        if strategy is None or deployment is None or not deployment.enabled:
            cancel_armed(connection, row.venue, row.strategy_id)
            continue
        policy = resolve_policy(strategy, deployment, defaults)
        if not policy.enabled:
            cancel_armed(connection, row.venue, row.strategy_id)


def fresh_marks(pairs: set[tuple[str, str]]) -> dict[tuple[str, str], Decimal]:
    found = {}
    for pair in pairs:
        price = _read_mark(*pair)
        if price is not None and price > 0:
            found[pair] = price
    return found


def cycle(
    connection,
    *,
    marks: dict[tuple[str, str], Decimal] | None = None,
    submit=None,
    forward=None,
    kill: bool | None = None,
    live: bool | None = None,
) -> list[str]:
    from app.core.config import execution_mode, kill_switch_enabled

    if live is None:
        live = execution_mode() == "live"
    if not live:
        return []
    if kill is None:
        kill = kill_switch_enabled()
    if submit is None:
        submit = submit_close
    if forward is None:
        forward = forward_copy
    retire_disabled(connection)
    rows = load_active(connection)
    prices = fresh_marks({(row.symbol, row.venue) for row in rows}) if marks is None else marks
    events = []
    for row in rows:
        outcome = _evaluate_row(connection, row, prices, kill, submit, forward)
        if outcome:
            events.append(outcome)
    _commit(connection)
    return events


def watch_forever(sleeper, *, cycles: int | None = None) -> None:
    from app.execution.strategy_lots import configured

    ran = 0
    while cycles is None or ran < cycles:
        sleeper(POLL_SECONDS)
        ran += 1
        if not configured():
            continue
        try:
            _cycle_once()
        except Exception:
            logger.warning("protective stop cycle failed")


def submit_close(strategy, action: str, client_order_id: str):
    from app.execution.live import LiveResult
    from app.execution.router import load_strategies

    if strategy.venue == "arcus":
        from app.execution.arcus import execute_arcus

        return execute_arcus(strategy, action, client_order_id)
    strategies = load_strategies()
    if strategy.venue == "mexc_spot":
        from app.execution.exchange import mexc_client
        from app.execution.live import execute_live

        return execute_live(mexc_client(), strategy, action, client_order_id, strategies, None)
    if strategy.venue == "mexc_futures":
        from app.execution.exchange import futures_client
        from app.execution.futures import execute_futures

        return execute_futures(futures_client(), strategy, action, client_order_id, strategies)
    return LiveResult("not_sent", False, "market unavailable")


def forward_copy(message) -> tuple[str, str]:
    import httpx

    url = os.environ.get("AUDIT_COPY_URL", "").strip()
    secret = os.environ.get("ANALYTICS_API_SECRET", "").strip()
    if not url or not secret:
        return "not_configured", ""
    try:
        response = httpx.post(
            url,
            json={
                "kind": message.kind,
                "strategy": message.strategy,
                "symbol": message.symbol,
                "reason": message.reason,
                "venue": message.venue,
                "content": str(message),
                "deliver_only": True,
            },
            headers={"Authorization": f"Bearer {secret}"},
            timeout=5.0,
        )
        if response.status_code != 200:
            return "not_configured", ""
        body = response.json()
    except Exception:
        return "not_configured", ""
    if not isinstance(body, dict):
        return "not_configured", ""
    status = str(body.get("discord_status") or "not_configured")
    detail = str(body.get("discord_detail") or "")
    return status, detail


def _evaluate_row(connection, row: StopRow, marks, kill: bool, submit, forward) -> str | None:
    if row.status == "triggering":
        if _lot(connection, row) <= 0:
            _set_status(connection, row, "closed")
        return None
    mark = marks.get((row.symbol, row.venue))
    chosen = None if mark is None else choose_trigger(row, mark)
    if mark is None or chosen is None:
        return None
    trigger, level = chosen
    if kill:
        _notify_skip(connection, row, mark, "kill_switch_enabled", forward, trigger, level)
        return "skipped"
    strategy, deployment = _target(row)
    if strategy is None or deployment is None:
        cancel_armed(connection, row.venue, row.strategy_id)
        return None
    now = datetime.now(timezone.utc)
    client_order_id = f"protective-exit-{row.strategy_id}-{now.strftime('%Y%m%dT%H%M%S%fZ')}"
    claimed = connection.execute(
        """
        UPDATE strategy_stops
        SET status = 'triggering',
            client_order_id = %(client_order_id)s,
            trigger_price = %(mark)s,
            triggered_at = %(now)s,
            attempt_count = attempt_count + 1,
            unconfirmed = TRUE
        WHERE venue = %(venue)s AND strategy_id = %(strategy_id)s AND status = 'armed'
        """,
        {
            "client_order_id": client_order_id,
            "mark": mark,
            "now": now,
            "venue": row.venue,
            "strategy_id": row.strategy_id,
        },
    )
    if claimed.rowcount != 1:
        return None
    _commit(connection)
    bound = strategy.bound(deployment)
    action = exit_action(bound)
    before = _lot(connection, row)
    try:
        with holding_exit() as box:
            result = submit(bound, action, client_order_id)
            if result.follow_up is not None:
                _store_audit(connection, _message(row, "order_accepted", action, bound, reason_text(level, mark, trigger=trigger)), forward)
                result.follow_up()
    except Exception:
        logger.warning("protective stop exit failed")
        _store_audit(
            connection,
            _message(row, "order_failed", action, bound, reason_text(level, mark, "state_unconfirmed", trigger=trigger)),
            forward,
        )
        return "failed"
    return _settle(connection, row, mark, action, bound, result, box, forward, before, trigger, level)


def _settle(connection, row, mark, action, strategy, result, box, forward, before: Decimal, trigger: str, level: Decimal) -> str:
    kind = box.get("kind")
    if kind == "order_failed" or result.status == "order_failed":
        cause = cause_for(str(box.get("reason") or result.reason or ""))
        _store_audit(
            connection,
            _message(row, "order_failed", action, strategy, reason_text(level, mark, cause, trigger=trigger)),
            forward,
        )
        if cause == "state_unconfirmed":
            return "failed"
        _set_status(connection, row, "armed", unconfirmed=False)
        return "failed"
    if kind != "order_success" and not result.sent:
        cause = cause_for(result.reason)
        _notify_skip(connection, row, mark, cause, forward, trigger, level)
        if cause in ("already_flat", "below_order_step"):
            _set_status(connection, row, "closed")
        else:
            _set_status(connection, row, "armed", unconfirmed=False)
        return "skipped"
    after = _lot(connection, row)
    if before > 0 and after >= before:
        _store_audit(
            connection,
            _message(row, "order_failed", action, strategy, reason_text(level, mark, "state_unconfirmed", trigger=trigger)),
            forward,
        )
        return "failed"
    average = box.get("average") if kind == "order_success" else result.average
    realized = box.get("realized") if kind == "order_success" else result.realized
    _store_audit(
        connection,
        _message(
            row,
            "order_success",
            action,
            strategy,
            reason_text(level, mark, trigger=trigger),
            average=average,
            realized=realized,
        ),
        forward,
    )
    if after <= 0:
        _set_status(connection, row, "closed")
    else:
        _set_status(connection, row, "armed", unconfirmed=False)
    return "success"


def _message(row, kind: str, action: str, strategy, reason: str, average=None, realized=None):
    from app.notifications.discord import AuditMessage, order_accepted, order_failed, order_not_sent, order_success

    symbol = row.symbol
    venue = row.venue
    size_quote = float(strategy.size_quote)
    if kind == "order_success":
        return order_success(
            row.strategy_id,
            symbol,
            action,
            size_quote,
            reason,
            None if average in (None, 0) else float(average),
            venue=venue,
            realized=realized,
        )
    if kind == "order_accepted":
        base = order_accepted(row.strategy_id, symbol, action, venue=venue)
        return AuditMessage(
            f"{base}\n\nReason:\n{reason}",
            kind="order_accepted",
            strategy=row.strategy_id,
            symbol=symbol,
            reason=reason,
            venue=venue,
        )
    if kind == "order_failed":
        base = order_failed(row.strategy_id, reason, venue=venue)
        return AuditMessage(
            str(base),
            kind="order_failed",
            strategy=row.strategy_id,
            symbol=symbol,
            reason=reason,
            venue=venue,
        )
    return order_not_sent(row.strategy_id, symbol, action, size_quote, reason, venue=venue)


def _store_audit(connection, message, forward) -> None:
    from app.analytics.schema import insert_audit

    status, detail = forward(message)
    insert_audit(
        connection,
        kind=message.kind,
        strategy=message.strategy,
        symbol=message.symbol,
        reason=message.reason,
        recorded_at=datetime.now(timezone.utc),
        discord_status=status,
        discord_detail=detail,
        venue=message.venue,
    )
    _commit(connection)


def _notify_skip(connection, row, mark, cause: str, forward, trigger: str, level: Decimal) -> None:
    key = (row.venue, row.strategy_id, row.armed_at.isoformat(), cause)
    with _skip_lock:
        if key in _skip_notices:
            return
        _skip_notices.add(key)
    strategy, deployment = _target(row)
    if strategy is None or deployment is None:
        return
    bound = strategy.bound(deployment)
    _store_audit(
        connection,
        _message(row, "order_not_sent", exit_action(bound), bound, reason_text(level, mark, cause, trigger=trigger)),
        forward,
    )


def _target(row: StopRow):
    from app.execution.router import RegistryRejection, load_strategies

    try:
        strategy = load_strategies().get(row.strategy_id)
    except RegistryRejection:
        return None, None
    if strategy is None:
        return None, None
    deployment = next((item for item in strategy.deployments if item.venue == row.venue), None)
    return strategy, deployment


def _lot(connection, row: StopRow) -> Decimal:
    from app.analytics.schema import load_strategy_lots

    return load_strategy_lots(connection, row.venue).get(row.strategy_id, Decimal("0"))


def _set_status(connection, row: StopRow, status: str, *, unconfirmed: bool = False) -> None:
    closed_at = datetime.now(timezone.utc) if status in ("closed", "cancelled") else None
    connection.execute(
        """
        UPDATE strategy_stops
        SET status = %(status)s,
            unconfirmed = %(unconfirmed)s,
            closed_at = COALESCE(%(closed_at)s, closed_at),
            client_order_id = CASE WHEN %(status)s = 'armed' THEN '' ELSE client_order_id END,
            trigger_price = CASE WHEN %(status)s = 'armed' THEN NULL ELSE trigger_price END
        WHERE venue = %(venue)s AND strategy_id = %(strategy_id)s
        """,
        {
            "status": status,
            "unconfirmed": unconfirmed,
            "closed_at": closed_at,
            "venue": row.venue,
            "strategy_id": row.strategy_id,
        },
    )
    _commit(connection)


def _cycle_once() -> None:
    from app.analytics.schema import create_schema
    from app.execution.strategy_lots import connect

    connection = connect()
    if connection is None:
        return
    try:
        create_schema(connection)
        cycle(connection)
        _commit(connection)
    finally:
        connection.close()


def _commit(connection) -> None:
    if not getattr(connection, "autocommit", False):
        connection.commit()


def _percent(value: object) -> Decimal:
    from app.execution.router import RegistryRejection

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RegistryRejection("protective exit is invalid")
    text = format(value, "f") if isinstance(value, float) else str(value)
    loss_pct = Decimal(text)
    if loss_pct <= 0 or loss_pct >= 100:
        raise RegistryRejection("protective exit is invalid")
    return loss_pct


def _stop_row(record) -> StopRow:
    return StopRow(
        venue=record[0],
        strategy_id=record[1],
        symbol=record[2],
        side=record[3],
        entry_price=_decimal(record[4]),
        stop_price=_optional_decimal(record[5]),
        take_profit_price=_optional_decimal(record[6]),
        loss_pct=_optional_decimal(record[7]),
        profit_pct=_optional_decimal(record[8]),
        status=record[9],
        client_order_id=record[10] or "",
        trigger_price=_optional_decimal(record[11]),
        armed_at=record[12],
        triggered_at=record[13],
        closed_at=record[14],
        attempt_count=int(record[15]),
        unconfirmed=bool(record[16]),
    )


def _optional_decimal(value) -> Decimal | None:
    if value is None:
        return None
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _decimal(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _read_mark(symbol: str, venue: str) -> Decimal | None:
    import httpx

    try:
        if venue == "mexc_futures":
            response = httpx.get(
                "https://contract.mexc.com/api/v1/contract/ticker",
                params={"symbol": symbol.replace("/", "_")},
                timeout=2.5,
            )
        elif venue == "mexc_spot":
            response = httpx.get(
                "https://api.mexc.com/api/v3/ticker/price",
                params={"symbol": symbol.replace("/", "")},
                timeout=2.5,
            )
        elif venue == "arcus":
            response = httpx.get(
                "https://api.arcus.xyz/v1/markets",
                params={"market": symbol.replace("/", "-")},
                timeout=2.5,
            )
        else:
            return None
        response.raise_for_status()
        return _public_price(response.json(), venue)
    except Exception:
        return None


def _public_price(body, venue: str) -> Decimal | None:
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
