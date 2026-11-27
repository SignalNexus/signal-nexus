from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from app.venues import is_futures, is_spot


@dataclass(frozen=True)
class FillView:
    trade_id: str
    symbol: str
    side: str
    quantity: Decimal
    quote_spent: Decimal
    quote_received: Decimal
    fee: Decimal
    filled_at: datetime
    strategy_name: str
    client_order_id: str | None
    fill_price: Decimal | None = None
    fee_asset: str | None = None
    venue: str = "mexc_spot"
    exchange_client_order_id: str | None = None


@dataclass(frozen=True)
class ClosedTrade:
    strategy_name: str
    symbol: str
    closed_at: datetime
    quantity: Decimal
    quote_spent: Decimal
    quote_received: Decimal
    venue: str = "mexc_spot"
    final_trade_id: str = ""

    @property
    def realized(self) -> Decimal:
        return self.quote_received - self.quote_spent

    @property
    def win(self) -> bool:
        return self.quote_received > self.quote_spent


@dataclass(frozen=True)
class OpenPosition:
    strategy_name: str
    symbol: str
    quantity: Decimal
    quote_spent: Decimal
    opened_at: datetime
    unrealized: Decimal | None = None
    venue: str = "mexc_spot"
    side: str = ""


class _Lot:
    def __init__(self, quantity: Decimal, quote_spent: Decimal, opened_at: datetime) -> None:
        self.quantity = quantity
        self.quote_spent = quote_spent
        self.opened_at = opened_at


class _Pending:
    def __init__(self, key: str, symbol: str, strategy_name: str, venue: str) -> None:
        self.key = key
        self.symbol = symbol
        self.strategy_name = strategy_name
        self.venue = venue
        self.quantity = Decimal("0")
        self.quote_spent = Decimal("0")
        self.quote_received = Decimal("0")
        self.closed_at: datetime | None = None
        self.final_trade_id = ""

    def _mark_final(self, fill: FillView) -> None:
        self.final_trade_id = fill.trade_id
        if self.closed_at is None or fill.filled_at > self.closed_at:
            self.closed_at = fill.filled_at

    def add(self, fill: FillView, spent: Decimal) -> None:
        self.quantity += fill.quantity
        self.quote_received += fill.quote_received
        self.quote_spent += spent
        self._mark_final(fill)

    def cover(self, fill: FillView, entry: Decimal) -> None:
        self.quantity += fill.quantity
        self.quote_received += entry
        self.quote_spent += fill.quote_spent
        self._mark_final(fill)


def effective_buy_quantity(fill: FillView) -> Decimal:
    base = fill.symbol.split("/", 1)[0].upper()
    asset = (fill.fee_asset or "").upper()
    if asset == base:
        return fill.quantity - fill.fee
    return fill.quantity


def _risex_sides(fills: list[FillView], given: dict[str, str] | None) -> dict[str, str]:
    if given is not None:
        return given
    wanted = [
        fill.exchange_client_order_id
        for fill in fills
        if fill.venue == "risex" and (fill.exchange_client_order_id or "").isdecimal()
    ]
    if not wanted:
        return {}
    try:
        from app.analytics.schema import create_schema, load_risex_reference_sides
        from app.execution.strategy_lots import connect
    except Exception:
        return {}
    connection = connect()
    if connection is None:
        return {}
    try:
        create_schema(connection)
        return load_risex_reference_sides(connection, wanted)
    except Exception:
        return {}
    finally:
        connection.close()


def _arcus_long(rows: list[FillView], risex_sides: dict[str, str] | None = None) -> bool:
    from app.execution.positions import parse_framed_client_order_id

    sides = risex_sides or {}
    for fill in rows:
        if fill.venue not in {"arcus", "lighter", "qfex", "ondo", "risex", "popdex"}:
            return False
        client = fill.exchange_client_order_id or ""
        if fill.venue == "risex" and client.isdecimal():
            if sides.get(client) in {"LONG", "FLAT"}:
                return True
            continue
        framed = parse_framed_client_order_id(client)
        if framed is not None and framed[1] in ("l", "f"):
            return True
        if len(client) == 32 and client[10] in ("l", "f"):
            return True
    return False


def reconstruct(
    fills: list[FillView], risex_sides: dict[str, str] | None = None
) -> tuple[list[ClosedTrade], list[OpenPosition]]:
    closed, opens, _books = _reconstruct(fills, risex_sides, books=None)
    return closed, opens


def freeze_books(
    fills: list[FillView], cutoff: datetime
) -> tuple[list[ClosedTrade], dict[tuple[str, str, str], tuple[bool, list[_Lot]]]]:
    # 前日より前は、未決済ロットを残して閉じる。増分はそこから続ける。
    prefix = [fill for fill in fills if fill.filled_at < cutoff]
    _closed, _opens, books = _reconstruct(prefix, None, books=None)
    return _closed, books


def replay_books(
    closed_prefix: list[ClosedTrade],
    books: dict[tuple[str, str, str], tuple[bool, list[_Lot]]],
    fills: list[FillView],
) -> tuple[list[ClosedTrade], list[OpenPosition]]:
    closed, opens, _books = _reconstruct(fills, None, books=books)
    merged = [*closed_prefix, *closed]
    merged.sort(key=lambda item: (item.closed_at, item.strategy_name, item.symbol))
    return merged, opens


def _copy_books(
    books: dict[tuple[str, str, str], tuple[bool, list[_Lot]]] | None,
) -> dict[tuple[str, str, str], tuple[bool, list[_Lot]]]:
    if not books:
        return {}
    return {
        key: (short, [_Lot(lot.quantity, lot.quote_spent, lot.opened_at) for lot in lots])
        for key, (short, lots) in books.items()
    }


def _reconstruct(
    fills: list[FillView],
    risex_sides: dict[str, str] | None,
    books: dict[tuple[str, str, str], tuple[bool, list[_Lot]]] | None,
) -> tuple[list[ClosedTrade], list[OpenPosition], dict[tuple[str, str, str], tuple[bool, list[_Lot]]]]:
    risex_sides = _risex_sides(fills, risex_sides)
    grouped: dict[tuple[str, str, str], list[FillView]] = defaultdict(list)
    for fill in fills:
        grouped[(fill.strategy_name, fill.symbol, fill.venue)].append(fill)
    seeds = _copy_books(books)
    closed: list[ClosedTrade] = []
    opens: list[OpenPosition] = []
    kept: dict[tuple[str, str, str], tuple[bool, list[_Lot]]] = {}
    keys = sorted(set(grouped) | set(seeds))
    for strategy_name, symbol, venue in keys:
        rows = sorted(grouped.get((strategy_name, symbol, venue), []), key=lambda item: (item.filled_at, item.trade_id))
        if venue in {"arcus", "lighter", "qfex", "ondo", "risex", "popdex"} and strategy_name == "未分類":
            continue
        if (strategy_name, symbol, venue) in seeds:
            short, lots = seeds[(strategy_name, symbol, venue)]
        else:
            lots = []
            short = is_futures(venue) and not _arcus_long(rows, risex_sides)
        pending: _Pending | None = None
        for fill in rows:
            if short:
                if fill.side == "sell":
                    if fill.quantity > 0:
                        lots.append(_Lot(fill.quantity, fill.quote_received, fill.filled_at))
                    continue
                key = fill.client_order_id or fill.trade_id
                if pending is None or pending.key != key:
                    _flush(closed, pending)
                    pending = _Pending(key, symbol, strategy_name, venue)
                pending.cover(fill, _consume(lots, fill.quantity))
                continue
            if fill.side == "buy":
                net = effective_buy_quantity(fill)
                if net > 0:
                    lots.append(_Lot(net, fill.quote_spent, fill.filled_at))
                continue
            key = fill.client_order_id or fill.trade_id
            if pending is None or pending.key != key:
                _flush(closed, pending)
                pending = _Pending(key, symbol, strategy_name, venue)
            pending.add(fill, _consume(lots, fill.quantity))
        _flush(closed, pending)
        if lots:
            kept[(strategy_name, symbol, venue)] = (short, lots)
            opens.append(
                OpenPosition(
                    strategy_name=strategy_name,
                    symbol=symbol,
                    quantity=sum((lot.quantity for lot in lots), Decimal("0")),
                    quote_spent=sum((lot.quote_spent for lot in lots), Decimal("0")),
                    opened_at=min(lot.opened_at for lot in lots),
                    venue=venue,
                    side="short" if short else "long" if is_futures(venue) else "",
                )
            )
    closed.sort(key=lambda item: (item.closed_at, item.strategy_name, item.symbol))
    return closed, opens, kept


def final_fill_realized(fills: list[FillView]) -> dict[str, Decimal]:
    closed, _opens = reconstruct(fills)
    return {trade.final_trade_id: trade.realized for trade in closed if trade.final_trade_id}


def realized_for_closing_fill(history: list[FillView], closing: FillView) -> Decimal | None:
    prior = [fill for fill in history if fill.trade_id != closing.trade_id]
    closed, _opens = reconstruct([*prior, closing])
    match = next((trade for trade in closed if trade.final_trade_id == closing.trade_id), None)
    if match is None or match.quote_spent <= 0 or match.quote_received <= 0:
        return None
    return match.realized


LOT_VENUES = {"arcus", "lighter"}


def held_opens(opens: list[OpenPosition], lots: dict[tuple[str, str], Decimal] | None) -> list[OpenPosition]:
    # Fill reconstruction is the ledger. Lots do not hide a leftover short.
    return list(opens)


def reconstructed_open_quantity(fills: list[FillView], venue: str, strategy_id: str) -> Decimal:
    _closed, opens = reconstruct(fills)
    return sum(
        (position.quantity for position in opens if position.venue == venue and position.strategy_name == strategy_id),
        Decimal("0"),
    )


def fill_view_from_row(row: tuple) -> FillView:
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


def mark_opens(opens: list[OpenPosition], prices: dict) -> list[OpenPosition]:
    marked: list[OpenPosition] = []
    for position in opens:
        price = prices.get((position.symbol, position.venue))
        if price is None and is_spot(position.venue):
            price = prices.get(position.symbol)
        if price is None:
            unrealized = None
        elif is_futures(position.venue) and position.side == "long":
            unrealized = price * position.quantity - position.quote_spent
        elif is_futures(position.venue):
            unrealized = position.quote_spent - price * position.quantity
        elif is_spot(position.venue):
            unrealized = price * position.quantity - position.quote_spent
        else:
            unrealized = None
        marked.append(
            OpenPosition(
                strategy_name=position.strategy_name,
                symbol=position.symbol,
                quantity=position.quantity,
                quote_spent=position.quote_spent,
                opened_at=position.opened_at,
                unrealized=unrealized,
                venue=position.venue,
                side=position.side,
            )
        )
    return marked


def strategy_rows(closed: list[ClosedTrade]) -> list[dict]:
    grouped: dict[tuple[str, str], list[ClosedTrade]] = defaultdict(list)
    for trade in closed:
        grouped[(trade.strategy_name, trade.venue)].append(trade)
    return [
        {"strategy_name": name, "venue": venue, **_closed_metrics(grouped[(name, venue)])}
        for name, venue in sorted(grouped)
    ]


def ticker_rows(closed: list[ClosedTrade]) -> list[dict]:
    grouped: dict[tuple[str, str], list[ClosedTrade]] = defaultdict(list)
    for trade in closed:
        grouped[(trade.symbol, trade.venue)].append(trade)
    return [
        {"symbol": symbol, "venue": venue, **_closed_metrics(grouped[(symbol, venue)])}
        for symbol, venue in sorted(grouped)
    ]


def _closed_metrics(trades: list[ClosedTrade]) -> dict:
    spent = sum((trade.quote_spent for trade in trades), Decimal("0"))
    realized = sum((trade.realized for trade in trades), Decimal("0"))
    wins = [trade for trade in trades if trade.win]
    losses = sum((trade.realized for trade in trades if trade.realized < 0), Decimal("0"))
    gains = sum((trade.realized for trade in wins), Decimal("0"))
    count = len(trades)
    return {
        "count": count,
        "realized": realized,
        "quote_spent": spent,
        "win_rate": (Decimal(len(wins)) / Decimal(count)) if count else None,
        "profit_rate": (realized / spent) if spent else None,
        "profit_factor": (gains / abs(losses)) if losses != 0 else None,
        "per_trade": (realized / Decimal(count)) if count else None,
    }


def period_rows(closed: list[ClosedTrade], now: datetime) -> dict[str, list[dict]]:
    today = now.astimezone(timezone.utc).date()
    if closed:
        start = min(trade.closed_at.astimezone(timezone.utc).date() for trade in closed).replace(day=1)
    else:
        start = today.replace(day=1)
    totals: dict[str, dict[str, Decimal]] = {
        "days": defaultdict(lambda: Decimal("0")),
        "weeks": defaultdict(lambda: Decimal("0")),
        "months": defaultdict(lambda: Decimal("0")),
        "years": defaultdict(lambda: Decimal("0")),
    }
    for trade in closed:
        local = trade.closed_at.astimezone(timezone.utc)
        totals["days"][local.date().isoformat()] += trade.realized
        calendar = local.date().isocalendar()
        totals["weeks"][f"{calendar.year}-W{calendar.week:02d}"] += trade.realized
        totals["months"][local.strftime("%Y-%m")] += trade.realized
        totals["years"][str(local.year)] += trade.realized
    months = []
    cursor = start
    while (cursor.year, cursor.month) <= (today.year, today.month):
        key = cursor.strftime("%Y-%m")
        months.append({"period": key, "realized": totals["months"].get(key, Decimal("0"))})
        if cursor.month == 12:
            cursor = cursor.replace(year=cursor.year + 1, month=1)
        else:
            cursor = cursor.replace(month=cursor.month + 1)
    return {
        "days": _labeled(totals["days"]),
        "weeks": _labeled(totals["weeks"]),
        "months": months,
        "years": _labeled(totals["years"]),
    }


def month_forecast(closed: list[ClosedTrade], now: datetime, target: Decimal | None) -> dict:
    today = now.astimezone(timezone.utc).date()
    month_key = today.strftime("%Y-%m")
    actual = sum(
        (
            trade.realized
            for trade in closed
            if trade.closed_at.astimezone(timezone.utc).strftime("%Y-%m") == month_key
        ),
        Decimal("0"),
    )
    elapsed = Decimal(today.day)
    days = Decimal(monthrange(today.year, today.month)[1])
    forecast = actual / elapsed * days
    achievement = None if target is None else actual / target
    remaining = None if target is None else target - actual
    return {
        "month": month_key,
        "target": target,
        "actual": actual,
        "achievement": achievement,
        "remaining": remaining,
        "forecast": forecast,
        "elapsed_days": int(elapsed),
        "days_in_month": int(days),
    }


def _flush(closed: list[ClosedTrade], pending: _Pending | None) -> None:
    if pending is None or pending.closed_at is None:
        return
    closed.append(
        ClosedTrade(
            strategy_name=pending.strategy_name,
            symbol=pending.symbol,
            closed_at=pending.closed_at,
            quantity=pending.quantity,
            quote_spent=pending.quote_spent,
            quote_received=pending.quote_received,
            venue=pending.venue,
            final_trade_id=pending.final_trade_id,
        )
    )


def _consume(lots: list[_Lot], quantity: Decimal) -> Decimal:
    left = quantity
    spent = Decimal("0")
    while left > 0 and lots:
        lot = lots[0]
        take = lot.quantity if lot.quantity <= left else left
        portion = lot.quote_spent * take / lot.quantity
        lot.quote_spent -= portion
        lot.quantity -= take
        spent += portion
        left -= take
        if lot.quantity <= 0:
            lots.pop(0)
    return spent


def _labeled(totals: dict[str, Decimal]) -> list[dict]:
    return [{"period": key, "realized": totals[key]} for key in sorted(totals)]


def fill_notional(fill: FillView) -> Decimal:
    return fill.quote_spent + fill.quote_received


def volume_rows(fills: list[FillView], now: datetime) -> dict[str, list[dict]]:
    today = now.astimezone(timezone.utc).date()
    if fills:
        start = min(fill.filled_at.astimezone(timezone.utc).date() for fill in fills).replace(day=1)
    else:
        start = today.replace(day=1)
    totals: dict[str, dict[str, Decimal]] = {
        "days": defaultdict(lambda: Decimal("0")),
        "weeks": defaultdict(lambda: Decimal("0")),
        "months": defaultdict(lambda: Decimal("0")),
        "years": defaultdict(lambda: Decimal("0")),
    }
    for fill in fills:
        local = fill.filled_at.astimezone(timezone.utc)
        amount = fill_notional(fill)
        totals["days"][local.date().isoformat()] += amount
        calendar = local.date().isocalendar()
        totals["weeks"][f"{calendar.year}-W{calendar.week:02d}"] += amount
        totals["months"][local.strftime("%Y-%m")] += amount
        totals["years"][str(local.year)] += amount
    months = []
    cursor = start
    while (cursor.year, cursor.month) <= (today.year, today.month):
        key = cursor.strftime("%Y-%m")
        months.append({"period": key, "volume": totals["months"].get(key, Decimal("0"))})
        if cursor.month == 12:
            cursor = cursor.replace(year=cursor.year + 1, month=1)
        else:
            cursor = cursor.replace(month=cursor.month + 1)
    return {
        "days": [{"period": key, "volume": totals["days"][key]} for key in sorted(totals["days"])],
        "weeks": [{"period": key, "volume": totals["weeks"][key]} for key in sorted(totals["weeks"])],
        "months": months,
        "years": [{"period": key, "volume": totals["years"][key]} for key in sorted(totals["years"])],
    }


def volume_rows_from_daily(rows: list[tuple], now: datetime) -> dict[str, list[dict]]:
    today = now.astimezone(timezone.utc).date()
    totals: dict[str, dict[str, Decimal]] = {
        "days": defaultdict(lambda: Decimal("0")),
        "weeks": defaultdict(lambda: Decimal("0")),
        "months": defaultdict(lambda: Decimal("0")),
        "years": defaultdict(lambda: Decimal("0")),
    }
    start = today.replace(day=1)
    for day, _venue, amount in rows:
        if day < start:
            start = day.replace(day=1)
        totals["days"][day.isoformat()] += Decimal(amount)
        calendar = day.isocalendar()
        totals["weeks"][f"{calendar.year}-W{calendar.week:02d}"] += Decimal(amount)
        totals["months"][day.strftime("%Y-%m")] += Decimal(amount)
        totals["years"][str(day.year)] += Decimal(amount)
    months = []
    cursor = start
    while (cursor.year, cursor.month) <= (today.year, today.month):
        key = cursor.strftime("%Y-%m")
        months.append({"period": key, "volume": totals["months"].get(key, Decimal("0"))})
        if cursor.month == 12:
            cursor = cursor.replace(year=cursor.year + 1, month=1)
        else:
            cursor = cursor.replace(month=cursor.month + 1)
    return {
        "days": [{"period": key, "volume": totals["days"][key]} for key in sorted(totals["days"])],
        "weeks": [{"period": key, "volume": totals["weeks"][key]} for key in sorted(totals["weeks"])],
        "months": months,
        "years": [{"period": key, "volume": totals["years"][key]} for key in sorted(totals["years"])],
    }


def attach_notional(rows: list[dict], totals: dict[tuple[str, str], Decimal], *, by: str) -> list[dict]:
    attached = []
    for row in rows:
        key = (row["strategy_name"] if by == "strategy" else row["symbol"], row["venue"])
        attached.append({**row, "volume": totals.get(key, Decimal("0"))})
    return attached


def attach_volumes(rows: list[dict], fills: list[FillView], *, by: str) -> list[dict]:
    totals: dict[tuple[str, str], Decimal] = defaultdict(lambda: Decimal("0"))
    for fill in fills:
        name = fill.strategy_name or "未分類"
        if by == "strategy" and name == "未分類":
            continue
        key = (name if by == "strategy" else fill.symbol, fill.venue)
        totals[key] += fill_notional(fill)
    attached = []
    for row in rows:
        key = (row["strategy_name"] if by == "strategy" else row["symbol"], row["venue"])
        attached.append({**row, "volume": totals.get(key, Decimal("0"))})
    return attached
