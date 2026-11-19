import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from app.portal_data import read_roi_bases
from app.portal_text import english, portal_zone, show_text
from app.venues import enabled_venues

_DEX = {"arcus", "lighter", "txflow", "hyperliquid", "paradex", "vertex", "grvt", "qfex", "ondo"}
_LABELS = {
    "mexc_spot": "MEXC Spot",
    "mexc_futures": "MEXC Futures",
    "lighter": "Lighter",
    "arcus": "Arcus",
    "qfex": "QFEX",
    "ondo": "Ondo",
    "txflow": "TxFlow",
}
_COLORS = {
    "mexc_spot": "#80ECFF",
    "mexc_futures": "#5497D5",
    "lighter": "#14F195",
    "arcus": "#9945FF",
    "qfex": "#FBBF24",
    "ondo": "#FFB020",
    "txflow": "#C49BFF",
}
_STRATEGY_COLORS = ("#14F195", "#FF4D6D", "#80ECFF", "#9945FF", "#FBBF24", "#5497D5")
_SCRIPT = Path(__file__).with_name("portal_pnl.js").read_text(encoding="utf-8")
_STYLE = """
.pv { display: grid; gap: 16px; margin-top: 16px; color: #e2e8f0; }
.pv-lockup { display: flex; align-items: center; gap: 12px; min-width: 0; }
.pv-mark { width: 56px; height: 56px; flex: none; border-radius: 14px; object-fit: cover; }
.pv-lockup-name { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.pv-lockup strong { font-size: 18px; letter-spacing: .06em; }
.pv-engine { border: 1px solid rgba(153,69,255,.75); border-radius: 999px; padding: 2px 8px; color: #d7b3ff; font-size: 11px; letter-spacing: .08em; }
.pv-lockup p { margin: 4px 0 0; color: #94a3b8; font-size: 13px; }
.pv-pin { position: sticky; top: var(--pin-h, 0px); z-index: 5; background: #111; }
.pv-rest { position: sticky; top: calc(var(--pin-h, 0px) + var(--pv-pin-h, 0px)); z-index: 5; background: #111; }
.pv button, .pv select { background: transparent; color: inherit; border: 0; padding: 0; font-size: 13px; }
.pv button { cursor: pointer; }
.pv-card { background: #121822; border: 1px solid rgba(148,163,184,.22); border-radius: 16px; padding: 16px; }
.pv-controls { display: grid; gap: 12px; }
.pv-row, .pv-filters, .pv-row-l, .pv-unit, .pv-legend-wrap { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }
.pv-row, .pv-chart-card > header, .pv-bottom > header { justify-content: space-between; }
.pv-seg, .pv-period, .pv-asof { display: inline-flex; align-items: center; gap: 4px; padding: 4px; border: 1px solid rgba(148,163,184,.25); border-radius: 12px; background: #0b0f14; }
.pv-seg button, .pv-period button { border-radius: 8px; padding: 7px 12px; color: #94a3b8; }
.pv-seg button.is-on { color: white; background: linear-gradient(90deg, #9945ff, #7b2cbf); box-shadow: 0 0 16px rgba(153,69,255,.35); }
.pv-seg button.is-usd { color: #14f195; background: rgba(20,241,149,.16); box-shadow: inset 0 0 0 1px rgba(20,241,149,.45); }
.pv-seg button.is-pct { color: #80ecff; background: rgba(128,236,255,.16); box-shadow: inset 0 0 0 1px rgba(128,236,255,.45); }
.pv-period select, .pv-strategy select { color: white; font-weight: 650; padding: 4px 8px; }
.pv-period button { color: #94a3b8; }
.pv-period button:disabled { opacity: .35; cursor: default; }
.pv-period svg, .pv-asof svg, .pv h3 svg, .pv-ico svg { width: 16px; height: 16px; }
.pv-cal { display: inline-flex; align-items: center; gap: 6px; color: #80ecff; }
.pv-asof { gap: 8px; padding: 8px 12px; color: #80ecff; border-color: rgba(128,236,255,.35); background: rgba(128,236,255,.08); }
.pv-dot { width: 8px; height: 8px; border-radius: 99px; background: #14f195; box-shadow: 0 0 0 4px rgba(20,241,149,.15); }
.pv-unit { margin-left: auto; color: #94a3b8; }
.pv-filters { border-top: 1px solid rgba(148,163,184,.16); padding-top: 12px; }
.pv-k { color: #94a3b8; font-size: 12px; }
.pv-pills { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.pv-pills button, .pv-clear { display: inline-flex; align-items: center; gap: 6px; border: 1px solid rgba(148,163,184,.25); border-radius: 8px; padding: 6px 10px; color: #94a3b8; background: #0b0f14; }
.pv-pills button.is-on { color: white; border-color: rgba(128,236,255,.6); background: rgba(128,236,255,.14); }
.pv-pills i { width: 8px; height: 8px; border-radius: 99px; display: inline-block; }
.pv-pills em, .pv-fill em { border-radius: 4px; padding: 1px 5px; font-style: normal; font-size: 9px; font-weight: 700; }
.pv-pills em.dex { color: #14f195; background: rgba(20,241,149,.12); }
.pv-pills em.cex { color: #94a3b8; background: #1e293b; }
.pv-strategy select { border: 1px solid rgba(148,163,184,.25); border-radius: 8px; background: #0b0f14; padding: 6px 10px; }
.pv-strategy { display: inline-flex; align-items: center; gap: 8px; }
.pv-clear { text-decoration: underline; text-underline-offset: 3px; }
.pv-basis, .pv-chart-card p, .pv-bottom p, .pv-kpi p { margin: 0; color: #94a3b8; font-size: 12px; }
.pv-kpis { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; }
.pv-kpi header { display: flex; justify-content: space-between; gap: 8px; color: #94a3b8; font-size: 11px; letter-spacing: .04em; text-transform: uppercase; }
.pv-kpi strong { display: block; margin: 10px 0 8px; font-size: 26px; font-variant-numeric: tabular-nums; }
.pv-ico { display: grid; place-items: center; width: 28px; height: 28px; border-radius: 8px; }
.pv-ico.up { color: #14f195; background: rgba(20,241,149,.12); }
.pv-ico.down, .pv-ico.dd { color: #ff4d6d; background: rgba(255,77,109,.12); }
.pv-ico.vol { color: #c49bff; background: rgba(153,69,255,.16); }
.pv-ico.win { color: #80ecff; background: rgba(128,236,255,.12); }
.pv-ico.pf { color: #14f195; background: rgba(20,241,149,.12); }
.pv h3 { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin: 0; font-size: 16px; }
.pv h3 em, .pv-drawer em { border-radius: 6px; padding: 2px 6px; font-style: normal; font-size: 11px; }
.pv h3 em.venue, .pv-drawer em.venue { color: #80ecff; background: rgba(128,236,255,.12); }
.pv h3 em.strategy, .pv-drawer em.strategy { color: #c49bff; background: rgba(153,69,255,.16); }
.pv-chart-card > header, .pv-bottom > header { display: flex; flex-wrap: wrap; gap: 12px; align-items: flex-start; margin-bottom: 8px; }
.pv-legend { display: flex; gap: 8px; align-items: center; color: #cbd5e1; font-size: 12px; }
.pv-legend i { width: 12px; height: 12px; border-radius: 3px; display: inline-block; }
.pv-legend i.g { background: #14f195; }
.pv-legend i.r { background: #ff4d6d; }
.pv-legend i.p { background: rgba(153,69,255,.55); }
.pv-legend i.line { width: 16px; height: 3px; background: linear-gradient(90deg, #9945ff, #80ecff); }
.pv-plot { position: relative; }
.pv-chart { width: 100%; height: auto; }
.pv-chart .axis { fill: #94a3b8; font-size: 11px; font-family: ui-monospace, monospace; }
.pv-chart .axis.vol { fill: rgba(153,69,255,.85); }
.pv-chart .future { fill: rgba(148,163,184,.08); }
.pv-chart .future-label { fill: #475569; }
.pv-chart .hit { fill: transparent; }
.pv-chart g.is-hot .hit { fill: rgba(148,163,184,.08); }
.pv-chart .pos { fill: url(#pvPos); }
.pv-chart .neg { fill: url(#pvNeg); }
.pv-chart .flat { fill: #475569; }
.pv-chart .vol-bar { fill: rgba(153,69,255,.28); }
.pv-chart .dot { fill: #80ecff; }
.pv-tip { position: absolute; top: 8px; z-index: 3; min-width: 180px; transform: translateX(-50%); padding: 8px 10px; border: 1px solid rgba(148,163,184,.35); border-radius: 12px; background: rgba(15,21,32,.96); pointer-events: none; }
.pv-tip-h, .pv-tip-r, .pv-fill header, .pv-fill p, .pv-month-h, .pv-month-f { display: flex; justify-content: space-between; gap: 12px; }
.pv-tip-h { margin-bottom: 6px; padding-bottom: 4px; border-bottom: 1px solid #1e293b; color: #94a3b8; font-size: 12px; }
.pv-tip-r { font-size: 12px; color: #94a3b8; }
.pv .up { color: #14f195; }
.pv .down { color: #ff4d6d; }
.pv .vol { color: #c49bff; }
.pv .cum { color: #80ecff; }
.pv-dow, .pv-cal-grid, .pv-months { display: grid; gap: 8px; }
.pv-dow, .pv-cal-grid { grid-template-columns: repeat(7, minmax(0, 1fr)); }
.pv-dow { color: #94a3b8; font-size: 11px; font-weight: 700; text-align: center; }
.pv-dow .sun { color: rgba(255,77,109,.8); }
.pv-dow .sat { color: rgba(128,236,255,.8); }
.pv-day, .pv-empty, .pv-month { min-height: 96px; border: 1px solid rgba(148,163,184,.2); border-radius: 12px; background: #0f151f; color: inherit; text-align: left; }
.pv-empty { background: rgba(11,15,20,.4); }
.pv-day { display: flex; flex-direction: column; justify-content: space-between; padding: 8px; }
.pv-day > span, .pv-month-h { display: flex; justify-content: space-between; align-items: center; font-weight: 700; }
.pv-day em, .pv-drawer em.today { background: #80ecff; color: #0b0f14; border-radius: 4px; padding: 1px 4px; font-size: 9px; font-style: normal; }
.pv-day.is-today { box-shadow: 0 0 0 2px #80ecff; }
.pv-day.is-future, .pv-month.is-future { opacity: .45; cursor: default; }
.pv-cell-pnl, .pv-month strong { font-size: 14px; font-variant-numeric: tabular-nums; }
.pv-cell-vol, .pv-cell-n { font-size: 10px; color: #94a3b8; }
.pv-months { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.pv-month { display: flex; flex-direction: column; gap: 6px; padding: 14px; }
.pv-month.up-card { border-color: rgba(20,241,149,.28); background: rgba(20,241,149,.04); }
.pv-month.down-card { border-color: rgba(255,77,109,.28); background: rgba(255,77,109,.04); }
.pv-month strong { font-size: 20px; }
.pv-future-note, .pv-count { border: 1px solid rgba(148,163,184,.25); border-radius: 8px; padding: 4px 8px; color: #cbd5e1; font-size: 12px; }
.pv-table { overflow-x: auto; }
.pv table { width: 100%; border-collapse: collapse; font-size: 13px; }
.pv th, .pv td { padding: 10px 8px; border-bottom: 1px solid rgba(148,163,184,.16); text-align: left; white-space: nowrap; }
.pv th { color: #94a3b8; font-size: 11px; font-weight: 600; text-transform: uppercase; }
.pv td.num, .pv th:nth-child(n+6) { text-align: right; font-variant-numeric: tabular-nums; }
.pv .side { border-radius: 4px; padding: 2px 6px; font-size: 11px; font-weight: 700; }
.pv .side.up { background: rgba(20,241,149,.12); }
.pv .side.down { background: rgba(255,77,109,.12); }
.pv-none, .pv-more { color: #94a3b8; }
.pv-drawer { position: fixed; inset: 0; z-index: 40; display: flex; justify-content: flex-end; background: rgba(0,0,0,.6); }
.pv-drawer aside { width: min(520px, 100%); height: 100%; display: flex; flex-direction: column; background: #121822; border-left: 1px solid rgba(148,163,184,.25); }
.pv-drawer header, .pv-drawer-k { display: flex; justify-content: space-between; gap: 12px; padding: 16px 20px; border-bottom: 1px solid rgba(148,163,184,.2); }
.pv-drawer header button { color: #94a3b8; font-size: 22px; padding: 4px 8px; }
.pv-drawer-k { display: grid; grid-template-columns: repeat(3, 1fr); background: rgba(11,15,20,.6); }
.pv-drawer-k span { display: block; color: #94a3b8; font-size: 11px; }
.pv-fills { overflow: auto; padding: 16px 20px; display: grid; gap: 10px; }
.pv-fill { border: 1px solid rgba(148,163,184,.2); border-radius: 12px; background: #0b0f14; padding: 12px; }
.pv-fill p { margin-top: 8px; font-size: 12px; }
@media (max-width: 1100px) {
  .pv-kpis { grid-template-columns: 1fr 1fr; }
  .pv-months { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 799px) {
  .pv-rest { position: static; }
}
@media (max-width: 720px) {
  .pv-kpis, .pv-months, .pv-cal-grid, .pv-dow { grid-template-columns: 1fr 1fr; }
  .pv-dow, .pv-cal-grid { grid-template-columns: repeat(7, minmax(72px, 1fr)); }
  .pv-bottom { overflow-x: auto; }
}
"""


def render_pnl_vol(trades: list[dict] | None) -> str:
    if trades is None:
        return '<p class="empty">Unable to retrieve</p>'
    payload = _payload(trades)
    blob = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")
    return f'<section class="pv"><style>{_STYLE}</style><div id="pv-mount"></div><script type="application/json" id="pv-data">{blob}</script><script>{_SCRIPT}</script></section>'


def _payload(rows: list[dict]) -> dict:
    trades = _trades(rows)
    now = datetime.now(timezone.utc)
    zone = portal_zone()
    return {
        "now": now.isoformat(),
        "asOf": now.astimezone(zone).strftime("%Y/%m/%d %H:%M"),
        "zone": "UTC",
        "bases": [
            {
                "start": row["start"].isoformat(),
                "end": row["end"].isoformat(),
                "capital": float(row["capital"]),
            }
            for row in read_roi_bases()
        ],
        "venues": _venues(trades),
        "strategies": _strategies(trades),
        "trades": trades,
        "copy": _copy(),
    }


def _trades(rows: list[dict]) -> list[dict]:
    enabled = _enabled_ids()
    prepared = []
    for row in rows:
        venue = str(row.get("venue") or "mexc_spot")
        if enabled is not None and venue not in enabled:
            continue
        filled = row.get("filled_at")
        if not filled:
            continue
        realized = row.get("realized")
        pnl = None if realized in (None, "") else format(_decimal(realized), "f")
        side = str(row.get("side") or "").lower()
        if pnl is None:
            position = "LONG" if side == "buy" else "SHORT"
        else:
            position = "LONG" if side == "sell" else "SHORT"
        prepared.append(
            {
                "id": str(row.get("trade_id") or ""),
                "ts": str(filled),
                "strategy": show_text(str(row.get("strategy_name") or "未分類")),
                "pair": str(row.get("symbol") or ""),
                "side": position,
                "venue": venue,
                "volume": format(_decimal(row.get("quote_spent")) + _decimal(row.get("quote_received")), "f"),
                "pnl": pnl,
            }
        )
    return prepared


def _venues(trades: list[dict]) -> list[dict]:
    enabled = _enabled_ids()
    if enabled is None:
        ids = []
        for trade in trades:
            if trade["venue"] not in ids:
                ids.append(trade["venue"])
    else:
        ids = list(enabled)
    rows = [{"id": "ALL", "label": "All Venues" if english() else "すべての取引所", "type": None, "color": "#94a3b8"}]
    for venue in ids:
        rows.append(
            {
                "id": venue,
                "label": _LABELS.get(venue, venue),
                "type": "DEX" if venue in _DEX else "CEX",
                "color": _COLORS.get(venue, "#94a3b8"),
            }
        )
    return rows


def _strategies(trades: list[dict]) -> list[dict]:
    names = sorted({trade["strategy"] for trade in trades if trade["strategy"]})
    rows = [{"id": "ALL", "label": "All Strategies" if english() else "すべての戦略", "color": "#94a3b8"}]
    for index, name in enumerate(names):
        rows.append({"id": name, "label": name, "color": _STRATEGY_COLORS[index % len(_STRATEGY_COLORS)]})
    return rows


def _enabled_ids() -> list[str] | None:
    try:
        return list(enabled_venues())
    except (OSError, ValueError):
        return None


def _decimal(value) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    return Decimal(str(value))


def _copy() -> dict:
    if english():
        return {
            "frames": {"Daily": "Daily", "Weekly": "Weekly", "Monthly": "Monthly", "Annually": "Annually"},
            "venues": "Venues",
            "strategy": "Strategy",
            "unit": "Unit",
            "clear": "Clear filters",
            "asOfBasis": "As-of window:",
            "last24": "Last 24 hours",
            "last7": "Last 7 days",
            "previous": "Previous period",
            "next": "Next period",
            "roiBasis": "ROI uses {amount} from {start} to {end}. Days follow UTC, the same cut as dashboard PnL.",
            "roiMore": "Other ranges apply on their own dates.",
            "roiMissing": "No ROI range covers today. Set start, end, and capital_usd in roi_basis.yml.",
            "roiNone": "ROI basis is not set. Add roi_basis.yml.",
            "net": "Net P&L",
            "totalVolume": "Total Volume",
            "winRate": "Win Rate",
            "profitFactor": "Profit Factor",
            "maxDD": "Max Drawdown",
            "maxDDHint": "Largest peak-to-trough decline in this period",
            "avgTrade": "Avg/Trade",
            "avgWin": "W",
            "avgLoss": "L",
            "perDay": "d",
            "perMonth": "mo",
            "monthToDate": "Month to date (through day {day})",
            "selectedMonth": "Selected month",
            "yearToDate": "Year to date (through month {month})",
            "selectedYear": "Selected year",
            "rollingDay": "Rolling 24 hours",
            "rollingWeek": "Rolling 7 days",
            "monthTitle": "{year}-{month} daily P&L and volume",
            "yearTitle": "{year} monthly P&L and volume",
            "dayTitle": "P&L and volume by hour, last 24 hours",
            "weekTitle": "P&L and volume by day, last 7 days",
            "chartHint": "Hover a bar for period P&L, volume, and cumulative P&L.",
            "yearHint": "Open a month to see its days.",
            "overlayPnl": "P&L + cumulative",
            "overlayVol": "P&L + volume axis",
            "profit": "Profit",
            "loss": "Loss",
            "volKey": "Vol",
            "cumKey": "Cumulative",
            "calendarTitle": "{year}-{month} daily P&L and volume",
            "calendarHint": "Each cell shows that day's P&L, volume, and closed trades.",
            "futureDays": "Later days are still ahead",
            "futureMonth": "Ahead",
            "yearList": "{year} by month",
            "details": "Open",
            "dayList": "Closed trades, last 24 hours",
            "weekList": "Closed trades, last 7 days",
            "listHint": "As of",
            "executions": "closed trades",
            "filledAt": "Filled",
            "pair": "Pair",
            "side": "Side",
            "volume": "Volume",
            "realized": "Realized P&L",
            "trades": "trades",
            "noTrades": "No closed trades for this filter.",
            "showing": "Showing {shown} of {total}",
            "periodPnl": "Period P&L",
            "cumulative": "Cumulative P&L",
            "dayPnl": "Day P&L",
            "dayVol": "Day volume",
            "winLoss": "Wins / losses",
            "drawerHint": "Closed trades",
            "close": "Close",
            "weekdays": ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"],
            "monthShort": "{month}",
        }
    return {
        "frames": {"Daily": "Daily", "Weekly": "Weekly", "Monthly": "Monthly", "Annually": "Annually"},
        "venues": "取引所",
        "strategy": "戦略",
        "unit": "表示単位",
        "clear": "フィルターをすべて解除",
        "asOfBasis": "参照時点起点:",
        "last24": "直近24時間",
        "last7": "直近7日間",
        "previous": "前の期間",
        "next": "次の期間",
        "roiBasis": "ROI は {start} から {end} まで {amount} です。日付の区切りは Dashboard の PnL と同じ UTC です。",
        "roiMore": "ほかの期間は、その日付の基準資金を使います。",
        "roiMissing": "今日を含む ROI の期間がありません。roi_basis.yml に start、end、capital_usd を書いてください。",
        "roiNone": "ROI の基準資金が未設定です。roi_basis.yml を追加してください。",
        "net": "Net P&L (純損益)",
        "totalVolume": "Total Volume (取引高)",
        "winRate": "Win Rate (勝率)",
        "profitFactor": "Profit Factor (PF)",
        "maxDD": "Max Drawdown",
        "maxDDHint": "期間内の最大資産下落幅",
        "avgTrade": "Avg/Trade",
        "avgWin": "W",
        "avgLoss": "L",
        "perDay": "d",
        "perMonth": "mo",
        "monthToDate": "当月進行中 ({day}日時点)",
        "selectedMonth": "選択した月",
        "yearToDate": "年間累計 ({month}月時点)",
        "selectedYear": "選択した年",
        "rollingDay": "直近24時間ローリング",
        "rollingWeek": "直近7日間ローリング",
        "monthTitle": "{year}年{month}月 日次損益 & ボリューム推移",
        "yearTitle": "{year}年 月次損益 & ボリューム推移",
        "dayTitle": "直近24時間 時間帯別損益 & ボリューム推移",
        "weekTitle": "直近7日間 日別損益 & ボリューム推移",
        "chartHint": "棒にカーソルを合わせると期間損益・取引Vol・累積損益を確認できます。",
        "yearHint": "月を開くと、その月の日次へ移動します。",
        "overlayPnl": "P&L + 累積ライン",
        "overlayVol": "P&L + Volume軸",
        "profit": "利益",
        "loss": "損失",
        "volKey": "Vol",
        "cumKey": "累積",
        "calendarTitle": "{year}年{month}月 日次損益 & ボリュームカレンダー",
        "calendarHint": "各セルに日次損益、取引Vol、約定数を表示します。",
        "futureDays": "本日より先は未確定",
        "futureMonth": "未到達",
        "yearList": "{year}年 月別パフォーマンス & ボリューム",
        "details": "詳細",
        "dayList": "直近24時間の決済トレード",
        "weekList": "直近7日間の決済トレード",
        "listHint": "参照時点",
        "executions": "件",
        "filledAt": "約定日時",
        "pair": "ペア",
        "side": "サイド",
        "volume": "取引 Vol",
        "realized": "実現損益",
        "trades": "trades",
        "noTrades": "該当条件の決済トレードはありません。",
        "showing": "{shown} / {total} 件を表示",
        "periodPnl": "期間損益",
        "cumulative": "累積損益",
        "dayPnl": "日次純損益",
        "dayVol": "日次取引 Vol",
        "winLoss": "勝敗内訳",
        "drawerHint": "日次トレード詳細",
        "close": "閉じる",
        "weekdays": ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"],
        "monthShort": "{month}月",
    }
