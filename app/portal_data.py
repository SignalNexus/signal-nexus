from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

import yaml

from app.portal_text import remaining_label

ROOT = Path(__file__).resolve().parents[1]
ORDER_QUOTE = Decimal("10")


def read_month_target(path: Path | None = None) -> Decimal | None:
    source = path or ROOT / "config" / "month_target.yml"
    if not source.is_file():
        return None
    loaded = yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        return None
    value = loaded.get("month_target_usdt")
    if isinstance(value, bool) or not isinstance(value, (int, str, Decimal)):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def read_backtests(path: Path | None = None) -> dict[str, dict[str, Decimal | int | str | None]]:
    source = path or ROOT / "config" / "strategy_results.yml"
    if not source.is_file():
        return {}
    loaded = yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        return {}
    strategies = loaded.get("strategies")
    if not isinstance(strategies, dict):
        return {}
    found: dict[str, dict[str, Decimal | int | str | None]] = {}
    for name, raw in strategies.items():
        if not isinstance(name, str):
            continue
        row = _strategy_result(raw)
        if row is not None:
            found[name] = row
    return found


def _strategy_result(raw) -> dict[str, Decimal | int | str | None] | None:
    if not isinstance(raw, dict):
        return None
    trades = raw.get("trades")
    wins = raw.get("wins")
    pnl = raw.get("pnl_usdt")
    start = _as_date(raw.get("start_date"))
    end = _as_date(raw.get("end_date"))
    if isinstance(trades, bool) or not isinstance(trades, int) or trades < 0:
        return None
    if isinstance(wins, bool) or not isinstance(wins, int) or wins < 0:
        return None
    if isinstance(pnl, bool) or not isinstance(pnl, (int, str, Decimal)):
        return None
    if start is None or end is None:
        return None
    try:
        net = Decimal(str(pnl))
    except InvalidOperation:
        return None
    closes = trades
    return {
        "closes": closes,
        "wins": wins,
        "net": net,
        "win_rate": (Decimal(wins) / Decimal(closes)) if closes else None,
        "profit_rate": (net / (Decimal(closes) * ORDER_QUOTE)) if closes else None,
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "days": (end - start).days,
    }


def ops_items(document: dict, today: date) -> list[dict]:
    raw_items = document.get("items") if isinstance(document, dict) else None
    if not isinstance(raw_items, list):
        return []
    visible = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        name = raw.get("name")
        list_from = _as_date(raw.get("list_from"))
        due = _as_date(raw.get("due"))
        if not isinstance(name, str) or list_from is None or due is None:
            continue
        if today < list_from:
            continue
        near_from = due - timedelta(days=3)
        if today > due:
            state = "overdue"
        elif today >= near_from:
            state = "near"
        else:
            state = "listed"
        visible.append(
            {
                "name": name,
                "list_from": list_from.isoformat(),
                "due": due.isoformat(),
                "state": state,
            }
        )
    return visible


_SCHEDULE_RANK = {"Overdue": 0, "Upcoming": 1, "Active": 2, "Pending": 3}


def schedule_items(document: dict, today: date) -> list[dict]:
    raw_items = document.get("items") if isinstance(document, dict) else None
    if not isinstance(raw_items, list):
        return []
    rows = []
    for index, raw in enumerate(raw_items):
        if not isinstance(raw, dict):
            continue
        name = raw.get("name")
        list_from = _as_date(raw.get("list_from"))
        due = _as_date(raw.get("due"))
        if not isinstance(name, str) or list_from is None or due is None:
            continue
        if today > due:
            state = "Overdue"
        elif today >= due - timedelta(days=3):
            state = "Upcoming"
        elif today >= list_from:
            state = "Active"
        else:
            state = "Pending"
        delta = (due - today).days
        rows.append(
            {
                "name": name,
                "list_from": list_from.isoformat(),
                "due": due.isoformat(),
                "state": state,
                "delta": delta,
                "remaining": remaining_label(delta),
                "index": index,
            }
        )
    rows.sort(key=lambda row: (_SCHEDULE_RANK[row["state"]], row["due"], row["index"]))
    return rows


def next_due(rows: list[dict]) -> str | None:
    if not rows:
        return None
    chosen = min(
        rows,
        key=lambda row: (abs(row["delta"]), _SCHEDULE_RANK[row["state"]], row["due"], row["index"]),
    )
    return chosen["name"]


def read_schedule(today: date, path: Path | None = None) -> list[dict] | None:
    source = path or ROOT / "config" / "ops_schedule.yml"
    try:
        loaded = yaml.safe_load(source.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(loaded, dict):
        return None
    return schedule_items(loaded, today)


def read_ops_items(today: date, path: Path | None = None) -> list[dict]:
    source = path or ROOT / "config" / "ops_schedule.yml"
    if not source.is_file():
        return []
    loaded = yaml.safe_load(source.read_text(encoding="utf-8"))
    return ops_items(loaded if isinstance(loaded, dict) else {}, today)


def _as_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None
