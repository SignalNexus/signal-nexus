from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.portal_text import days_clock_label, hours_label, minutes_label, portal_zone, t
from app.venues import is_futures, is_spot

AUDIT_LABELS = {
    "order_success": "SUCCESS",
    "signal_received": "RECEIVED",
    "order_not_sent": "SKIPPED",
    "sell_resend_skipped": "SKIPPED",
    "validation_rejected": "REJECTED",
    "order_failed": "FAILED",
    "duplicate_discarded": "DROPPED",
}


def decimal(value) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(str(value))


def moment(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


# 取り込みは 1 分ごと。1 回失敗しても次の成功がこの範囲に入れば Healthy のままにする。
INGEST_HEALTHY_FOR = timedelta(minutes=3)


def ingest_state(succeeded_at: str | None, now: datetime) -> str:
    if not succeeded_at:
        return "Unhealthy"
    if now - moment(succeeded_at) <= INGEST_HEALTHY_FOR:
        return "Healthy"
    return "Unhealthy"


def hold_label(delta: timedelta) -> str:
    total = int(delta.total_seconds())
    if total < 0:
        total = 0
    minutes = total // 60
    if minutes < 60:
        return minutes_label(minutes)
    hours = minutes // 60
    if hours < 24:
        return hours_label(hours, minutes % 60)
    return days_clock_label(hours // 24, hours % 24)


def positions_view(rows: list[dict], now: datetime) -> dict:
    prepared = []
    for row in rows:
        unrealized = decimal(row.get("unrealized"))
        spent = decimal(row.get("quote_spent")) or Decimal("0")
        quantity = decimal(row.get("quantity")) or Decimal("0")
        opened = moment(row["opened_at"])
        price = None
        if unrealized is not None and quantity != 0:
            price = (unrealized + spent) / quantity
        risk = None
        if unrealized is not None and spent != 0:
            risk = unrealized / spent * Decimal("100")
        prepared.append(
            {
                "strategy_name": row.get("strategy_name") or "未分類",
                "symbol": row.get("symbol") or "",
                "venue": row.get("venue") or "mexc_spot",
                "quantity": quantity,
                "unrealized": unrealized,
                "risk": risk,
                "opened_at": opened,
                "hold": hold_label(now - opened),
                "price": price,
                "base": str(row.get("symbol") or "").split("/", 1)[0],
            }
        )
    prepared.sort(key=lambda item: (item["unrealized"] is None, item["unrealized"] or Decimal("0"), item["opened_at"]))
    missing = any(item["unrealized"] is None for item in prepared)
    total = None if missing else sum((item["unrealized"] or Decimal("0") for item in prepared), Decimal("0"))
    if not prepared:
        total = Decimal("0")
    return {"rows": prepared, "count": len(prepared), "total": total}


def strategies_view(rows: list[dict]) -> dict:
    visible = []
    for row in rows:
        count = int(row.get("count") or 0)
        if count < 1:
            continue
        visible.append(
            {
                "strategy_name": row.get("strategy_name") or "未分類",
                "venue": row.get("venue") or "mexc_spot",
                "realized": decimal(row.get("realized")) or Decimal("0"),
                "profit_factor": decimal(row.get("profit_factor")),
                "profit_rate": decimal(row.get("profit_rate")),
                "win_rate": decimal(row.get("win_rate")),
                "count": count,
                "volume": decimal(row.get("volume")) or Decimal("0"),
            }
        )
    visible.sort(
        key=lambda item: (
            -item["realized"],
            item["profit_factor"] is None,
            -(item["profit_factor"] or Decimal("0")),
        )
    )
    factors = [item["profit_factor"] for item in visible if item["profit_factor"] is not None]
    average = (sum(factors, Decimal("0")) / Decimal(len(factors))) if factors else None
    return {
        "rows": visible,
        "active": len(visible),
        "profitable": sum(1 for item in visible if item["realized"] > 0),
        "total": sum((item["realized"] for item in visible), Decimal("0")),
        "average_pf": average,
    }


def tickers_view(rows: list[dict]) -> dict:
    visible = []
    for row in rows:
        count = int(row.get("count") or 0)
        if count < 1:
            continue
        visible.append(
            {
                "symbol": row.get("symbol") or "",
                "venue": row.get("venue") or "mexc_spot",
                "realized": decimal(row.get("realized")) or Decimal("0"),
                "profit_factor": decimal(row.get("profit_factor")),
                "profit_rate": decimal(row.get("profit_rate")),
                "win_rate": decimal(row.get("win_rate")),
                "count": count,
                "volume": decimal(row.get("volume")) or Decimal("0"),
            }
        )
    visible.sort(
        key=lambda item: (
            -item["realized"],
            item["profit_factor"] is None,
            -(item["profit_factor"] or Decimal("0")),
        )
    )
    factors = [item["profit_factor"] for item in visible if item["profit_factor"] is not None]
    average = (sum(factors, Decimal("0")) / Decimal(len(factors))) if factors else None
    return {
        "rows": visible,
        "active": len(visible),
        "profitable": sum(1 for item in visible if item["realized"] > 0),
        "total": sum((item["realized"] for item in visible), Decimal("0")) if visible else Decimal("0"),
        "average_pf": average,
    }


def backtest_view(
    live_rows: list[dict],
    backtests: dict[str, dict],
    futures_names: list[str] | None = None,
) -> dict:
    books = _registered_books() if futures_names is None else [("mexc_futures", name) for name in futures_names]
    live = {}
    for row in live_rows:
        name = row.get("strategy_name")
        if not name:
            continue
        live[(row.get("venue") or "mexc_spot", name)] = row
    futures_keys = []
    seen = set()
    for venue, name in books:
        if not name or name == "未分類" or (venue, name) in seen:
            continue
        seen.add((venue, name))
        futures_keys.append((venue, name))
    for venue, name in sorted(live):
        if name == "未分類" or not is_futures(venue) or (venue, name) in seen:
            continue
        seen.add((venue, name))
        futures_keys.append((venue, name))
    futures_ids = {name for _venue, name in futures_keys}
    compared = []
    for name, back in backtests.items():
        if name == "未分類" or not back or name in futures_ids:
            continue
        matches = [(venue, row) for (venue, strategy_id), row in live.items() if strategy_id == name and is_spot(venue)]
        if len(matches) == 1:
            venue, source = matches[0]
            attached = back
        elif len(matches) == 0:
            venue, source, attached = "mexc_spot", None, back
        else:
            for venue, source in matches:
                compared.append(_spot_comparison(name, venue, source, None))
            continue
        compared.append(_spot_comparison(name, venue, source, attached))
    for venue, name in futures_keys:
        owners = [item for item in futures_keys if item[1] == name]
        attached = backtests.get(name) if len(owners) == 1 else None
        compared.append(_futures_comparison(name, venue, live.get((venue, name)), attached))
    compared.sort(
        key=lambda item: (
            item["rate_diff"] is None,
            item["rate_diff"] if item["rate_diff"] is not None else Decimal("0"),
            item["pf_diff"] is None,
            item["pf_diff"] if item["pf_diff"] is not None else Decimal("0"),
            item["strategy_name"],
            item["venue"],
        )
    )
    live_factors = [item["live_pf"] for item in compared if item["live_pf"] is not None]
    back_factors = [item["back_pf"] for item in compared if item["back_pf"] is not None]
    negative = [item for item in compared if item["rate_diff"] is not None and item["rate_diff"] < 0]
    largest = min(negative, key=lambda item: item["rate_diff"])["strategy_name"] if negative else None
    return {
        "rows": compared,
        "count": len(compared),
        "live_average_pf": _mean(live_factors),
        "back_average_pf": _mean(back_factors),
        "largest_gap": largest,
    }


def _registered_books() -> list[tuple[str, str]]:
    from app.execution.router import load_strategies

    return sorted(
        (deployment.venue, strategy.strategy_id)
        for strategy in load_strategies().values()
        for deployment in strategy.deployments
        if deployment.enabled and is_futures(deployment.venue)
    )


def _spot_comparison(name: str, venue: str, source: dict | None, back: dict | None) -> dict:
    live_rate = decimal(source.get("profit_rate")) if source else None
    live_pf = decimal(source.get("profit_factor")) if source else None
    live_win = decimal(source.get("win_rate")) if source else None
    live_count = int(source["count"]) if source and source.get("count") is not None else None
    back_rate = decimal(back.get("profit_rate")) if back else None
    back_pf = decimal(back.get("profit_factor")) if back and "profit_factor" in back else None
    back_win = decimal(back.get("win_rate")) if back else None
    back_count = back.get("closes") if back else None
    return {
        "strategy_name": name,
        "venue": venue,
        "live_rate": live_rate,
        "back_rate": back_rate,
        "rate_diff": _subtract(live_rate, back_rate, points=True),
        "live_pf": live_pf,
        "back_pf": back_pf,
        "pf_diff": _subtract(live_pf, back_pf, points=False),
        "live_win": live_win,
        "back_win": back_win,
        "win_diff": _subtract(live_win, back_win, points=True),
        "live_count": live_count,
        "back_count": back_count,
        "count_diff": None if live_count is None or back_count is None else live_count - int(back_count),
        "back_days": None if not back else back.get("days"),
        "back_start": None if not back else back.get("period_start"),
        "back_end": None if not back else back.get("period_end"),
    }


def _futures_comparison(name: str, venue: str, source: dict | None, back: dict | None = None) -> dict:
    closed = source is not None and int(source.get("count") or 0) >= 1
    live_rate = decimal(source.get("profit_rate")) if closed else None
    live_pf = decimal(source.get("profit_factor")) if closed else None
    live_win = decimal(source.get("win_rate")) if closed else None
    live_count = int(source["count"]) if closed and source.get("count") is not None else None
    back_rate = decimal(back.get("profit_rate")) if back else None
    back_pf = decimal(back.get("profit_factor")) if back and "profit_factor" in back else None
    back_win = decimal(back.get("win_rate")) if back else None
    back_count = back.get("closes") if back else None
    return {
        "strategy_name": name,
        "venue": venue,
        "live_rate": live_rate,
        "back_rate": back_rate,
        "rate_diff": _subtract(live_rate, back_rate, points=True),
        "live_pf": live_pf,
        "back_pf": back_pf,
        "pf_diff": _subtract(live_pf, back_pf, points=False),
        "live_win": live_win,
        "back_win": back_win,
        "win_diff": _subtract(live_win, back_win, points=True),
        "live_count": live_count,
        "back_count": back_count,
        "count_diff": None if live_count is None or back_count is None else live_count - int(back_count),
        "back_days": None if not back else back.get("days"),
        "back_start": None if not back else back.get("period_start"),
        "back_end": None if not back else back.get("period_end"),
    }


def trades_view(rows: list[dict], today) -> dict:
    ordered = sorted(rows, key=lambda row: (moment(row["filled_at"]), str(row.get("trade_id") or "")), reverse=True)
    prepared = []
    for row in ordered:
        filled = moment(row["filled_at"]).astimezone(portal_zone())
        venue = row.get("venue") or "mexc_spot"
        bought = str(row.get("side") or "").lower() == "buy"
        if is_futures(venue):
            action = "COVER" if bought else "SHORT"
        elif is_spot(venue):
            action = "BUY" if bought else "SELL"
        else:
            action = "BUY" if bought else "SELL"
        prepared.append(
            {
                "trade_id": str(row.get("trade_id") or ""),
                "filled_at": filled,
                "strategy_name": row.get("strategy_name") or "未分類",
                "symbol": row.get("symbol") or "",
                "venue": venue,
                "side": "BUY" if bought else "SELL",
                "action": action,
                "quantity": decimal(row.get("quantity")) or Decimal("0"),
                "quote_spent": decimal(row.get("quote_spent")) or Decimal("0"),
                "quote_received": decimal(row.get("quote_received")) or Decimal("0"),
                "fill_price": decimal(row.get("fill_price")),
                "realized": decimal(row.get("realized")),
                "unclassified": (row.get("strategy_name") or "未分類") == "未分類",
            }
        )
    return {
        "rows": prepared,
        "count": len(prepared),
        "today": sum(1 for item in prepared if item["filled_at"].date() == today),
        "buy": sum(1 for item in prepared if item["side"] == "BUY"),
        "sell": sum(1 for item in prepared if item["side"] == "SELL"),
        "unclassified": sum(1 for item in prepared if item["unclassified"]),
    }


def balances_view(balance: dict) -> dict:
    coins = []
    usdt = {"free": Decimal("0"), "used": Decimal("0"), "total": Decimal("0")}
    for code, row in balance.items():
        if code in {"info", "free", "used", "total", "timestamp", "datetime", "debt"}:
            continue
        if not isinstance(row, dict):
            continue
        free = decimal(row.get("free")) or Decimal("0")
        used = decimal(row.get("used")) or Decimal("0")
        total = free + used
        entry = {"code": str(code), "free": free, "used": used, "total": total}
        if str(code).upper() == "USDT":
            usdt = entry
            continue
        if total > 0:
            coins.append(entry)
    coins.sort(key=lambda item: item["code"])
    return {"usdt": usdt, "coins": coins, "count": len(coins)}


def orders_view(orders: list[dict], codes: dict[str, str], now: datetime) -> dict:
    prepared = []
    for order in orders:
        created = _order_time(order)
        client_id = _client_id(order)
        strategy = _strategy_name(client_id, codes)
        side = _display_side(order)
        amount = decimal(order.get("amount"))
        remaining = decimal(order.get("remaining"))
        if remaining is None and amount is not None:
            filled = decimal(order.get("filled")) or Decimal("0")
            remaining = amount - filled
        prepared.append(
            {
                "created": created,
                "order_id": str(order.get("id") or ""),
                "strategy_name": strategy,
                "symbol": str(order.get("symbol") or ""),
                "side": side,
                "order_type": _order_type(order),
                "price": decimal(order.get("price")),
                "amount": amount,
                "remaining": remaining,
                "elapsed": None if created is None else hold_label(now - created),
                "unclassified": strategy == "未分類",
            }
        )
    prepared.sort(key=lambda item: (item["created"] is None, item["created"] or now, item["order_id"]))
    return {
        "rows": prepared,
        "count": len(prepared),
        "buy": sum(1 for item in prepared if item["side"] == "BUY"),
        "sell": sum(1 for item in prepared if item["side"] == "SELL"),
        "unclassified": sum(1 for item in prepared if item["unclassified"]),
    }


def audits_view(rows: list[dict] | None) -> dict | None:
    if rows is None:
        return None
    ordered = sorted(rows, key=lambda row: moment(row["recorded_at"]), reverse=True)
    prepared = []
    for row in ordered:
        kind = str(row.get("kind") or "")
        label = AUDIT_LABELS.get(kind, kind)
        reason = str(row.get("reason") or "")
        prepared.append(
            {
                "at": moment(row["recorded_at"]).astimezone(portal_zone()),
                "kind": kind,
                "label": label,
                "known": kind in AUDIT_LABELS,
                "reason": reason,
                "strategy": str(row.get("strategy") or ""),
                "symbol": str(row.get("symbol") or ""),
                "edge": label in {"REJECTED", "FAILED"},
                "copy": _discord_copy(row),
            }
        )
    failures = [item["at"] for item in prepared if item["label"] == "FAILED"]
    return {
        "rows": prepared,
        "count": len(prepared),
        "success": sum(1 for item in prepared if item["label"] == "SUCCESS"),
        "failed": sum(1 for item in prepared if item["label"] == "FAILED"),
        "latest_failure": max(failures) if failures else None,
    }


def _discord_copy(row: dict) -> str:
    status = str(row.get("discord_status") or "")
    detail = str(row.get("discord_detail") or "")
    if status == "sent":
        return t("送信済み")
    if status == "not_configured":
        return t("未設定")
    if status == "failed":
        return detail or t("失敗")
    return "—"


def latest_alert(rows: list[dict] | None) -> datetime | None:
    if not rows:
        return None
    received = [moment(row["recorded_at"]) for row in rows if row.get("kind") == "signal_received"]
    if not received:
        return None
    return max(received).astimezone(portal_zone())


def _subtract(left: Decimal | None, right: Decimal | None, points: bool) -> Decimal | None:
    if left is None or right is None:
        return None
    gap = left - right
    if points:
        return gap * Decimal("100")
    return gap


def _mean(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    return sum(values, Decimal("0")) / Decimal(len(values))


def _client_id(order: dict) -> str:
    info = order.get("info") if isinstance(order.get("info"), dict) else {}
    for source in (order, info):
        for key in ("clientOrderId", "origClientOrderId"):
            value = source.get(key)
            if isinstance(value, str) and value:
                return value
    return ""


def _strategy_name(client_id: str, codes: dict[str, str]) -> str:
    if len(client_id) != 32 or client_id[10] not in {"b", "s", "h", "c"}:
        return "未分類"
    return codes.get(client_id[:10], "未分類")


def _display_side(order: dict) -> str:
    client_id = _client_id(order)
    if len(client_id) == 32 and client_id[10] == "h":
        return "SHORT"
    if len(client_id) == 32 and client_id[10] == "c":
        return "COVER"
    return "BUY" if str(order.get("side") or "").lower() == "buy" else "SELL"


def _order_type(order: dict) -> str:
    info = order.get("info") if isinstance(order.get("info"), dict) else {}
    raw = info.get("type") or info.get("orderType") or order.get("type") or ""
    text = str(raw).strip()
    return text.upper() if text else ""


def _order_time(order: dict) -> datetime | None:
    value = order.get("timestamp")
    if value in (None, ""):
        return None
    return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
