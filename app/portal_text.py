from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

from app.config_dir import config_file

# Japanese wording is the source. It is used only when language is japanese.
# When language is absent, the portal is English.
_EN = {
    "パスワード": "Password",
    "開く": "Sign in",
    "パスワードが違います。": "Incorrect password.",
    "行き先": "Navigation",
    "Trading の切り替え": "Trading sections",
    "Analytics の切り替え": "Analytics sections",
    "Operations の切り替え": "Operations sections",
    "内訳を開く": "Show breakdown",
    "内訳を閉じる": "Hide breakdown",
    "集計": "Summary",
    "実績（USD）": "Actual (USD)",
    "今月の出来高": "Monthly Volume",
    "月目標": "Monthly Target",
    "達成率": "Achievement",
    "残必要額": "Remaining to Target",
    "月末着地予測": "Month-End Forecast",
    "Positions を開く": "View Positions",
    "作業名": "Task",
    "期限": "Due",
    "状態": "Status",
    "期限超過": "Overdue",
    "直近": "Upcoming",
    "Schedule を開く": "View Schedule",
    "モード": "Mode",
    "発注": "Orders",
    "取り込み": "Import",
    "直近のアラート": "Latest Alert",
    "決済が1件以上存在する戦略・未分類のみを表示": "Only strategies and Unclassified entries with at least one closed trade",
    "戦略": "Strategy",
    "実現損益": "Realized PnL",
    "出来高": "Volume",
    "回数": "Trades",
    "勝率": "Win Rate",
    "Strategies を開く": "View Strategies",
    "含み損益": "Unrealized PnL",
    "保有時間": "Time Held",
    "残数量": "Remaining",
    "取得": "Opened",
    "現在価格": "Current Price",
    "建玉はありません": "No open positions",
    "含み損益の小さい順。価格が無い行は末尾。1 行は戦略と銘柄。": "Lowest unrealized PnL first. Rows without a price are last. One row is one strategy and symbol.",
    "当日約定数": "Fills Today",
    "未約定件数": "Open Orders",
    "未約定注文はありません": "No open orders",
    "経過時間": "Elapsed",
    "約定時刻": "Filled At",
    "銘柄": "Symbol",
    "売買": "Side",
    "戻った": "Received Amount",
    "使った": "Spent Amount",
    "数量": "Quantity",
    "注文価格": "Order Price",
    "注文種別": "Order Type",
    "注文数量": "Order Quantity",
    "USDT 合計": "USDT Total",
    "使える": "Available",
    "注文中": "In Orders",
    "コイン数": "Coins",
    "評価額": "Equity",
    "証拠金": "Margin",
    "建玉数": "Open Positions",
    "通貨": "Asset",
    "合計": "Total",
    "利益率": "Return",
    "差": "Gap",
    "BT期間": "BT Period",
    "実現損益の大きい順。同額は PF が高い順。決済が 1 件以上の銘柄だけ。": "Highest realized PnL first. Ties go to the higher Profit Factor. Only symbols with at least one closed trade.",
    "登録された運用作業はありません": "No scheduled tasks",
    "開始日": "Start",
    "残日数": "Days Left",
    "監査イベントはありません": "No audit events",
    "イベント種別": "Event",
    "理由": "Reason",
    "発生時刻": "Time",
    "会場": "Venue",
    "写し": "Copy",
    "送信済み": "Sent",
    "未設定": "Not configured",
    "失敗": "Failed",
}


def _locale_document(path: Path | None = None) -> dict:
    source = path or config_file("locale.yml")
    try:
        loaded = yaml.safe_load(source.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def portal_zone(path: Path | None = None) -> ZoneInfo:
    value = _locale_document(path).get("timezone")
    if isinstance(value, str) and value.strip():
        try:
            return ZoneInfo(value.strip())
        except ZoneInfoNotFoundError:
            return ZoneInfo("Asia/Tokyo")
    return ZoneInfo("Asia/Tokyo")


def portal_language(path: Path | None = None) -> str:
    if _locale_document(path).get("language") == "japanese":
        return "japanese"
    return "english"


def english() -> bool:
    return portal_language() == "english"


def html_lang() -> str:
    return "en" if english() else "ja"


def t(source: str) -> str:
    if not english():
        return source
    return _EN.get(source, source)


def show_text(value: str) -> str:
    if english() and value == "未分類":
        return "Unclassified"
    return value


def count_label(action: str, kind: str) -> str:
    if not english():
        return f"{action}件数"
    noun = "Fills" if kind == "fills" else "Orders"
    return f"{action} {noun}"


def unclassified_count(kind: str) -> str:
    if not english():
        return "未分類件数"
    return "Unclassified Fills" if kind == "fills" else "Unclassified Orders"


def minutes_label(minutes: int) -> str:
    if not english():
        return f"{minutes}分"
    return f"{minutes}m"


def hours_label(hours: int, minutes: int) -> str:
    if not english():
        return f"{hours}時間 {minutes}分"
    return f"{hours}h {minutes}m"


def days_clock_label(days: int, hours: int) -> str:
    if not english():
        return f"{days}日 {hours}時間"
    return f"{days}d {hours}h"


def remaining_label(delta: int) -> str:
    if not english():
        return f"残り{delta}日" if delta >= 0 else f"{-delta}日超過"
    if delta >= 0:
        return f"{delta} days left"
    return f"{-delta} days overdue"


def period_days(days: int) -> str:
    if not english():
        return f"{days:,}日"
    return f"{days:,} days"


def actual_label(unit: str) -> str:
    shown = escape(unit)
    if not english():
        return f"実績（{shown}）"
    return f"Actual ({shown})"


def volume_phrase(amount: str) -> str:
    if not english():
        return f"出来高 {amount}"
    return f"Volume {amount}"


def received_header(code: str) -> str:
    if not english():
        return f"戻った{code}"
    return f"Received {code}"


def spent_header(code: str) -> str:
    if not english():
        return f"使った{code}"
    return f"Spent {code}"


def trade_amounts(received: str, spent: str, quantity: str) -> str:
    if not english():
        return f"戻った {received} · 使った {spent} · 数量 {quantity}"
    return f"Received Amount {received} · Spent Amount {spent} · Quantity {quantity}"


def orders_fetched(when: str) -> str:
    if not english():
        return f"{when} 取得。保存しない。作成時刻の古い順。"
    return f"Fetched {when}. Not stored. Oldest created time first."


def usd_fetched(when: str) -> str:
    if not english():
        return f"{when} 取得。保存しない。単位は USD。"
    return f"Fetched {when}. Not stored. Unit is USD."


def coins_fetched(when: str) -> str:
    if not english():
        return f"{when} 取得。保存しない。コインはコードの昇順。合計が 0 の通貨は出さない。"
    return f"Fetched {when}. Not stored. Coins are sorted by code. Assets with a zero total are hidden."


def due_phrase(due: str) -> str:
    if not english():
        return f"期限 {due}"
    return f"Due {due}"


def starts_phrase(day: str) -> str:
    if not english():
        return f"開始 {day}"
    return f"Starts {day}"


def balance_amounts(free: str, used: str) -> str:
    if not english():
        return f"使える {free} · 注文中 {used}"
    return f"Available {free} · In Orders {used}"


def opened_phrase(stamp: str) -> str:
    if not english():
        return f"取得 {stamp}"
    return f"Opened {stamp}"


def price_phrase(price: str, unit: str) -> str:
    if not english():
        return f"現在価格 {price} {unit}"
    return f"Current Price {price} {unit}"


def rate_meta(profit: str, win: str, count: str) -> str:
    if not english():
        return f"利益率 {profit} · 勝率 {win} · 回数 {count}"
    return f"Return {profit} · Win Rate {win} · Trades {count}"
