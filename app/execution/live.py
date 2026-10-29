import time
from datetime import datetime, timezone
from dataclasses import dataclass
from decimal import Decimal
from threading import Lock
from collections.abc import Callable

from app.execution.order_executor import (
    base_amount_for_quote,
    combined_average,
    market_quote,
    orderable_base,
    place_limit_order,
    place_market_order,
    public_order_error,
    settle_limit,
    sized_price,
    top_of_book,
)
from app.execution.positions import (
    RESERVE_USDT,
    exchange_client_order_id,
    free_usdt,
    invalidate,
    load_open_buys,
    mark_sold_exit,
    open_holding,
    remember,
    reduce,
    sold_exit,
)
from app.execution.router import Strategy
from app.notifications.analytics import report_order_link
from app.notifications.discord import order_failed, order_success, send_audit

# These ten send STOP for a stop and SELL for a take-profit.
# The live BTC strategies send SELL for both, so their orders stay market.
RESTING_LIMIT_IDS = frozenset(
    {
        "hype_long_saucer_bottom",
        "eth_long_falling_wedge",
        "eth_long_double_bottom",
        "sol_long_saucer_bottom",
        "eth_long_saucer_bottom",
        "btc_long_triple_bottom_30m",
        "sol_long_falling_wedge",
        "btc_long_falling_wedge_1h",
        "hype_long_ascending_triangle",
        "hype_long_v_bottom",
    }
)

_locks_guard = Lock()
_strategy_locks: dict[str, Lock] = {}
_working: set[str] = set()

MISSING_BUY = "bought quantity missing; no record of this strategy's buy, check MEXC for leftover coins"
WAIT_SECONDS = 5


@dataclass(frozen=True)
class LiveResult:
    status: str
    sent: bool
    reason: str = ""
    resend_skipped: bool = False
    average: float | None = None
    follow_up: Callable[[], None] | None = None
    realized: Decimal | None = None


def clear_live_state() -> None:
    with _locks_guard:
        _working.clear()


def execute_live(
    exchange,
    strategy: Strategy,
    action: str,
    client_order_id: str,
    strategies: dict[str, Strategy],
    exit_bar_close_ms: int | None = None,
    sleeper: Callable[[float], None] = time.sleep,
) -> LiveResult:
    try:
        load_open_buys(exchange, strategies)
    except Exception:
        return LiveResult("not_sent", False, "position history unavailable")
    exchange_id = exchange_client_order_id(
        strategy.strategy_id, client_order_id, action, venue=strategy.venue
    )
    with _strategy_lock(strategy.strategy_id):
        if strategy.strategy_id in _working:
            if action == "BUY":
                return LiveResult("not_sent", False, "entry already working")
            return LiveResult("not_sent", False, "exit already working", resend_skipped=True)
        if action == "BUY":
            return _buy(exchange, strategy, exchange_id, client_order_id, sleeper)
        if action in ("SELL", "STOP"):
            return _sell(
                exchange,
                strategy,
                action,
                exchange_id,
                client_order_id,
                exit_bar_close_ms,
                sleeper,
            )
    raise RuntimeError("unsupported action")


def _strategy_lock(strategy_id: str) -> Lock:
    with _locks_guard:
        lock = _strategy_locks.get(strategy_id)
        if lock is None:
            lock = Lock()
            _strategy_locks[strategy_id] = lock
        return lock


def _uses_resting_limit(strategy_id: str, action: str) -> bool:
    return action != "STOP" and strategy_id in RESTING_LIMIT_IDS


def _below_order_step(exchange, symbol: str, amount: float) -> bool:
    try:
        return orderable_base(exchange, symbol, amount) <= 0
    except Exception:
        return False


def _buy(exchange, strategy: Strategy, exchange_id: str, client_order_id: str, sleeper) -> LiveResult:
    holding = open_holding(strategy.strategy_id)
    dust = (
        holding is not None
        and holding.symbol == strategy.symbol
        and _below_order_step(exchange, strategy.symbol, holding.base_qty)
    )
    if holding is not None and not dust:
        return LiveResult("not_sent", False, "position already open")
    try:
        free = free_usdt(exchange)
    except Exception:
        return LiveResult("not_sent", False, "USDT balance unavailable")
    if free < strategy.size_quote + RESERVE_USDT:
        return LiveResult("not_sent", False, "USDT insufficient")
    if _uses_resting_limit(strategy.strategy_id, "BUY"):
        posted = _post_buy_limit(exchange, strategy, exchange_id)
        if posted is not None:
            order_id, amount, price = posted
            report_order_link(exchange_id, client_order_id)
            _working.add(strategy.strategy_id)
            return LiveResult(
                "accepted",
                True,
                follow_up=lambda: _finish_buy(
                    exchange, strategy, client_order_id, exchange_id, order_id, amount, price, sleeper
                ),
            )
    return _market_buy(exchange, strategy, exchange_id, client_order_id)


def _market_buy(
    exchange,
    strategy: Strategy,
    exchange_id: str,
    client_order_id: str,
    quote: float | None = None,
) -> LiveResult:
    status, filled, average, _gross = place_market_order(
        exchange,
        strategy.symbol,
        "BUY",
        strategy.size_quote if quote is None else quote,
        client_order_id=exchange_id,
    )
    report_order_link(exchange_id, client_order_id)
    if filled <= 0:
        invalidate()
        return LiveResult("order_failed", True, "filled base missing")
    _add_buy(strategy, filled, exchange_id, fill_price=average)
    return LiveResult(status, True, average=average)


def _add_buy(strategy: Strategy, filled: float, order_key: str, fill_price: float | None = None) -> None:
    current = open_holding(strategy.strategy_id)
    bought_at = current.bought_at_ms if current is not None else None
    stored = _store_spot_fill(
        strategy,
        order_key,
        filled,
        closing=False,
        bought_at_ms=bought_at,
        fill_price=fill_price,
    )
    if stored is not None:
        if stored <= 0:
            reduce(strategy.strategy_id, current.base_qty if current is not None else filled)
            return
        remember(strategy.strategy_id, strategy.symbol, stored, bought_at)
        return
    if current is None:
        remember(strategy.strategy_id, strategy.symbol, filled)
        return
    remember(strategy.strategy_id, strategy.symbol, current.base_qty + filled, current.bought_at_ms)


def _store_spot_fill(
    strategy,
    order_key: str,
    filled: float,
    closing: bool,
    bought_at_ms: int | None,
    fill_price: float | None = None,
):
    from decimal import Decimal

    from app.execution.strategy_lots import LotStoreError, configured, note_fill

    if not configured() or not order_key or filled <= 0:
        return None
    when = bought_at_ms
    if when is None:
        when = int(datetime.now(timezone.utc).timestamp() * 1000)
    try:
        quantity = note_fill(
            "mexc_spot",
            order_key,
            strategy.strategy_id,
            closing,
            Decimal(str(filled)),
            symbol=strategy.symbol,
            bought_at_ms=when,
            fill_price=None if fill_price is None else Decimal(str(fill_price)),
            protect=not closing and fill_price not in (None, 0),
        )
    except LotStoreError:
        return None
    return float(quantity)


def _post_buy_limit(exchange, strategy: Strategy, exchange_id: str):
    try:
        bid, ask = top_of_book(exchange, strategy.symbol)
    except Exception:
        return None
    if bid is None or (ask is not None and bid >= ask):
        return None
    amount = base_amount_for_quote(exchange, strategy.symbol, strategy.size_quote, bid)
    if amount <= 0:
        return None
    order_id = place_limit_order(
        exchange, strategy.symbol, "buy", amount, bid, client_order_id=exchange_id
    )
    return order_id, amount, bid


def _finish_buy(exchange, strategy, client_order_id, exchange_id, order_id, amount, price, sleeper) -> None:
    sleeper(WAIT_SECONDS)
    with _strategy_lock(strategy.strategy_id):
        try:
            net, remaining, limit_average, limit_gross = settle_limit(
                exchange, order_id, strategy.symbol, amount
            )
            fills = [(limit_gross, limit_average)]
            if net > 0:
                _add_buy(strategy, net, exchange_id, fill_price=limit_average)
            status = "closed"
            if remaining > 0:
                remainder_id = exchange_client_order_id(
                    strategy.strategy_id, client_order_id, "BUY", "remainder", strategy.venue
                )
                quoted = market_quote(
                    exchange,
                    strategy.symbol,
                    Decimal(str(remaining)) * Decimal(str(sized_price(exchange, strategy.symbol, price))),
                )
                if quoted is not None:
                    status, extra, market_average, market_gross = place_market_order(
                        exchange,
                        strategy.symbol,
                        "BUY",
                        quoted,
                        client_order_id=remainder_id,
                    )
                    report_order_link(remainder_id, client_order_id)
                    fills.append((market_gross, market_average))
                    if extra > 0:
                        _add_buy(strategy, extra, remainder_id, fill_price=market_average)
                        net += extra
            if net <= 0:
                invalidate()
                send_audit(order_failed(strategy.strategy_id, "filled base missing", venue=strategy.venue))
                return
            send_audit(
                order_success(
                    strategy.strategy_id,
                    strategy.symbol,
                    "BUY",
                    strategy.size_quote,
                    status,
                    combined_average(fills),
                    venue=strategy.venue,
                )
            )
        except Exception as exc:
            invalidate()
            send_audit(order_failed(strategy.strategy_id, public_order_error(exc), venue=strategy.venue))
        finally:
            _working.discard(strategy.strategy_id)


def _sell(
    exchange,
    strategy: Strategy,
    action: str,
    exchange_id: str,
    client_order_id: str,
    exit_bar_close_ms: int | None,
    sleeper,
) -> LiveResult:
    blocked = _sell_block(strategy, exit_bar_close_ms)
    if blocked is not None:
        return blocked
    holding = open_holding(strategy.strategy_id)
    if _below_order_step(exchange, strategy.symbol, holding.base_qty):
        return LiveResult("not_sent", False, "remainder below order step")
    if _uses_resting_limit(strategy.strategy_id, action):
        posted = _post_sell_limit(exchange, strategy, exchange_id, holding.base_qty)
        if posted is not None:
            order_id, amount, _price = posted
            report_order_link(exchange_id, client_order_id)
            _working.add(strategy.strategy_id)
            return LiveResult(
                "accepted",
                True,
                follow_up=lambda: _finish_sell(
                    exchange,
                    strategy,
                    client_order_id,
                    exchange_id,
                    order_id,
                    amount,
                    exit_bar_close_ms,
                    sleeper,
                ),
            )
    return _market_sell(
        exchange,
        strategy,
        exchange_id,
        holding.base_qty,
        client_order_id,
        exit_bar_close_ms,
    )


def _sell_block(strategy: Strategy, exit_bar_close_ms: int | None) -> LiveResult | None:
    holding = open_holding(strategy.strategy_id)
    if holding is None or holding.symbol != strategy.symbol:
        if exit_bar_close_ms is not None and sold_exit(strategy.strategy_id) == exit_bar_close_ms:
            return LiveResult("not_sent", False, "already sold for exit", resend_skipped=True)
        return LiveResult("not_sent", False, MISSING_BUY)
    if exit_bar_close_ms is not None and holding.bought_at_ms >= exit_bar_close_ms:
        return LiveResult(
            "not_sent", False, "newer position kept, bought after exit", resend_skipped=True
        )
    return None


def _market_sell(
    exchange,
    strategy: Strategy,
    exchange_id: str,
    base_amount: float,
    client_order_id: str,
    exit_bar_close_ms: int | None,
) -> LiveResult:
    status, filled, average, _gross = place_market_order(
        exchange,
        strategy.symbol,
        "SELL",
        strategy.size_quote,
        client_order_id=exchange_id,
        base_amount=base_amount,
    )
    report_order_link(exchange_id, client_order_id)
    if filled <= 0:
        invalidate()
        return LiveResult("order_failed", True, "filled base missing")
    _close_buy(strategy, filled, exchange_id)
    if exit_bar_close_ms is not None and open_holding(strategy.strategy_id) is None:
        mark_sold_exit(strategy.strategy_id, exit_bar_close_ms)
    return LiveResult(
        status,
        True,
        average=average,
        realized=_close_realized(strategy, filled, average, client_order_id),
    )


def _post_sell_limit(exchange, strategy: Strategy, exchange_id: str, amount: float):
    try:
        bid, ask = top_of_book(exchange, strategy.symbol)
    except Exception:
        return None
    if ask is None or (bid is not None and ask <= bid):
        return None
    order_id = place_limit_order(
        exchange, strategy.symbol, "sell", amount, ask, client_order_id=exchange_id
    )
    return order_id, amount, ask


def _close_buy(strategy: Strategy, sold: float, order_key: str) -> None:
    current = open_holding(strategy.strategy_id)
    stored = _store_spot_fill(
        strategy,
        order_key,
        sold,
        closing=True,
        bought_at_ms=None if current is None else current.bought_at_ms,
    )
    if stored is None:
        reduce(strategy.strategy_id, sold)
        return
    if current is None or stored <= 0:
        reduce(strategy.strategy_id, current.base_qty if current is not None else sold)
        return
    remember(strategy.strategy_id, current.symbol, stored, current.bought_at_ms)


def _finish_sell(
    exchange, strategy, client_order_id, exchange_id, order_id, amount, exit_bar_close_ms, sleeper
) -> None:
    sleeper(WAIT_SECONDS)
    with _strategy_lock(strategy.strategy_id):
        try:
            _net, remaining, limit_average, limit_gross = settle_limit(
                exchange, order_id, strategy.symbol, amount
            )
            fills = [(limit_gross, limit_average)]
            sold = amount - remaining
            if sold > 0:
                _close_buy(strategy, sold, exchange_id)
            status = "closed"
            extra = 0.0
            if remaining > 0:
                remainder_id = exchange_client_order_id(
                    strategy.strategy_id, client_order_id, "SELL", "remainder", strategy.venue
                )
                status, extra, market_average, market_gross = place_market_order(
                    exchange,
                    strategy.symbol,
                    "SELL",
                    strategy.size_quote,
                    client_order_id=remainder_id,
                    base_amount=remaining,
                )
                report_order_link(remainder_id, client_order_id)
                fills.append((market_gross, market_average))
                if extra > 0:
                    _close_buy(strategy, extra, remainder_id)
            if sold <= 0 and extra <= 0:
                invalidate()
                send_audit(order_failed(strategy.strategy_id, "filled base missing", venue=strategy.venue))
                return
            if exit_bar_close_ms is not None and open_holding(strategy.strategy_id) is None:
                mark_sold_exit(strategy.strategy_id, exit_bar_close_ms)
            send_audit(
                order_success(
                    strategy.strategy_id,
                    strategy.symbol,
                    "SELL",
                    strategy.size_quote,
                    status,
                    combined_average(fills),
                    venue=strategy.venue,
                    realized=_close_realized(
                        strategy,
                        _base_filled(sold, extra),
                        combined_average(fills),
                        client_order_id,
                    ),
                )
            )
        except Exception as exc:
            invalidate()
            send_audit(order_failed(strategy.strategy_id, public_order_error(exc), venue=strategy.venue))
        finally:
            _working.discard(strategy.strategy_id)


def _base_filled(*amounts) -> Decimal:
    total = Decimal("0")
    for amount in amounts:
        if isinstance(amount, Decimal):
            total += amount
        else:
            total += Decimal(str(amount or 0))
    return total


def _close_realized(strategy: Strategy, quantity, price, client_order_id: str) -> Decimal | None:
    from app.analytics.history import closing_realized_pnl

    return closing_realized_pnl(
        strategy_name=strategy.strategy_id,
        symbol=strategy.symbol,
        venue=strategy.venue,
        trade_id=f"notify:{client_order_id}",
        side="sell",
        quantity=quantity,
        price=price,
        client_order_id=client_order_id,
    )
