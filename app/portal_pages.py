from datetime import datetime, timezone
from decimal import Decimal
from html import escape
from zoneinfo import ZoneInfo

from app.core.config import execution_mode, kill_switch_enabled
from app.venues import is_futures, is_spot, quote_currency
from app.portal_data import next_due, read_schedule
from app.portal_model import (
    audits_view,
    backtest_view,
    ingest_state,
    latest_alert,
    positions_view,
    strategies_view,
    tickers_view,
    trades_view,
)
from app.portal_text import (
    actual_label,
    balance_amounts,
    coins_fetched,
    count_label,
    due_phrase,
    opened_phrase,
    orders_fetched,
    period_days,
    price_phrase,
    rate_meta,
    received_header,
    show_text,
    spent_header,
    starts_phrase,
    t,
    trade_amounts,
    unclassified_count,
    usd_fetched,
    volume_phrase,
)

TOKYO = ZoneInfo("Asia/Tokyo")
# Venue Lifecycle は販売戦略の会場状態に合わせる。MEXC は本番、Arcus は測定と接続の途中、残りは未対応。
VENUE_CARDS = (
    {"name": "MEXC", "status": "Supported", "lines": (("Spot", "mexc_spot"), ("Futures", "mexc_futures"))},
    {"name": "Arcus", "status": "Supported", "lines": (("Perpetual", "arcus"),)},
    {"name": "Hyperliquid", "status": "Planned", "lines": (("Perpetual", "hyperliquid"),)},
    {"name": "Paradex", "status": "Planned", "lines": (("Perpetual", "paradex"),)},
    {"name": "Vertex", "status": "Planned", "lines": (("Perpetual", "vertex"),)},
    {"name": "GRVT", "status": "Planned", "lines": (("Perpetual", "grvt"),)},
)
PENDING_MARK = (
    '<svg class="status-mark" viewBox="0 0 24 24" aria-hidden="true"><g fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M5 22h14M5 2h14"/>'
    '<path d="M17 22v-4.2a2 2 0 0 0-.6-1.4L12 12l-4.4 4.4a2 2 0 0 0-.6 1.4V22"/>'
    '<path d="M7 2v4.2a2 2 0 0 0 .6 1.4L12 12l4.4-4.4a2 2 0 0 0 .6-1.4V2"/>'
    "</g></svg>"
)
NAV = (
    ("dashboard", "Dashboard", "/portal"),
    ("trading", "Trading", "/portal/trading"),
    ("analytics", "Analytics", "/portal/analytics"),
    ("operations", "Operations", "/portal/operations"),
)
STYLE = """
:root {
  --dark: #1c1c1c; --violet: #9945ff; --teal: #14f195; --loss: #ff4d4d;
  --amber: #ffb020; --text: #ffffff; --muted: rgba(255,255,255,.64);
  --line: rgba(255,255,255,.14); --panel: #242424; --down: #5c5c5c;
  --logo: linear-gradient(90deg, #9945ff 0%, #8752f3 24%, #5497d5 46%, #43b4ca 58%, #28e0b9 78%, #14f195 100%);
}
* { box-sizing: border-box; }
body { margin: 0; background: #111; color: var(--text); font-family: "Segoe UI", "Hiragino Sans", sans-serif; font-size: 16px; }
a { color: inherit; text-decoration: none; }
button, select { background: transparent; color: var(--text); border: 1px solid var(--line); font-size: 16px; padding: 8px 14px; }
.shell { background: var(--dark); min-height: 100vh; }
.brand {
  display: inline-block; margin: 0 0 24px; font-size: 22px; font-weight: 700;
  background-image: linear-gradient(90deg, #9945ff 0%, #8752f3 24%, #5497d5 46%, #43b4ca 58%, #28e0b9 78%, #14f195 100%);
  -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; color: transparent;
}
.side { display: none; }
.side a, .tabs a { display: block; padding: 10px 12px; color: var(--muted); }
.side a.brand {
  display: inline-block; padding: 0; color: transparent;
  background-image: linear-gradient(90deg, #9945ff 0%, #8752f3 24%, #5497d5 46%, #43b4ca 58%, #28e0b9 78%, #14f195 100%);
  -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;
}
.side a[aria-current="page"], .tabs a[aria-current="page"] { color: var(--text); background: var(--violet); }
.phone-brand { display: none; }
.title { display: flex; align-items: center; gap: 10px; min-width: 0; }
header { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.header-actions { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.header-actions button, header > form button { white-space: nowrap; }
h2 { margin: 0; font-size: 20px; }
.screen { margin: 8px 0 0; color: var(--muted); font-size: 13px; }
.switch { display: flex; gap: 8px; margin-top: 16px; flex-wrap: wrap; }
.switch a { padding: 8px 12px; color: var(--muted); border: 1px solid var(--line); border-radius: 12px; font-size: 14px; }
.switch a[aria-current="page"] { color: var(--text); background: var(--violet); border-color: var(--violet); }
.tabs {
  display: grid; grid-template-columns: repeat(5, 1fr); position: fixed; left: 0; right: 0; bottom: 0;
  background: var(--dark); border-top: 1px solid var(--line); z-index: 2;
}
.tabs a { text-align: center; font-size: 11px; padding: 12px 2px; }
.main { padding: 16px 16px 84px; min-width: 0; }
.eyebrow { margin: 0 0 10px; color: var(--violet); font-size: 13px; }
.hint { margin: 8px 0 0; color: var(--muted); font-size: 13px; }
.eyebrow + .hint { margin: 0 0 10px; font-size: 11px; }
.block { margin-top: 22px; }
.today, .panel, .summary div, .health div, .periods div, .position, .card {
  background: var(--panel); border: 1px solid var(--line); border-radius: 12px;
}
.today { margin-top: 18px; padding: 20px; border-color: var(--violet); }
.today-grid, .summary, .risk, .health, .periods, .prio { display: grid; gap: 12px; }
.today-grid, .summary, .health, .periods { grid-template-columns: 1fr 1fr; }
.risk { grid-template-columns: 1fr 1fr; }
.hero { grid-column: 1 / -1; }
.metric span, .summary span, .health span, .periods span { display: block; color: var(--muted); font-size: 13px; }
.metric strong, .summary strong, .health strong, .periods strong {
  display: block; margin-top: 6px; font-weight: 600; font-variant-numeric: tabular-nums;
}
.hero strong { font-size: 40px; line-height: 1; letter-spacing: -0.03em; }
.summary { margin-top: 18px; }
.summary div, .risk .metric { padding: 16px; }
.risk .metric { background: var(--panel); border: 1px solid var(--line); border-radius: 12px; }
.summary strong, .risk .metric strong { font-size: 22px; line-height: 1.1; }
.periods div, .health div { padding: 12px; }
.periods strong { font-size: 16px; }
.up { color: var(--teal); }
.down { color: var(--loss); }
.amber { color: var(--amber); }
.buy { color: var(--teal); }
.panel { overflow: hidden; }
.ops b { font-weight: 600; }
.pill { color: var(--text); background: var(--violet); padding: 4px 8px; font-size: 13px; }
.pill.bad { color: var(--loss); background: transparent; border: 1px solid var(--loss); }
.more { display: inline-block; margin: 12px; color: var(--violet); }
.scroll { min-width: 0; overflow-x: auto; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 12px; border-bottom: 1px solid var(--line); text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
th { color: var(--muted); font-weight: 500; font-size: 13px; }
th:first-child, td:first-child { text-align: left; }
table.compare th.identity, table.compare td.identity { text-align: left; }
table.compare th.identity, table.compare th.set { color: var(--violet); }
table.compare th.set, table.compare td.set { border-left: 1px solid var(--line); }
table.compare th.days, table.compare td.days { text-align: left; line-height: 1.35; }
table.compare td.days .range { display: block; color: var(--muted); font-size: 12px; font-weight: 400; }
.wide { display: none; }
.narrow, .list { display: grid; gap: 8px; margin-top: 18px; }
.card, .position { padding: 14px; }
.position { margin: 0; }
.list { gap: 12px; }
.prio { grid-template-columns: 1fr; }
.pnl strong { font-size: 32px; line-height: 1; }
.rate { display: block; margin-top: 6px; font-size: 14px; font-weight: 600; }
.meta, .rule, .empty { color: var(--muted); }
.meta { margin: 10px 0 0; font-size: 13px; line-height: 1.5; }
.rule { margin: 10px 0 0; font-size: 11px; }
.empty { margin: 18px 0 0; }
.card .lead { margin: 0; font-size: 18px; font-weight: 600; }
.card .sub { margin: 4px 0 0; font-size: 22px; font-weight: 600; font-variant-numeric: tabular-nums; }
.card p { margin: 6px 0 0; }
.focus-amber { border-color: var(--amber); }
.focus-loss { border-color: var(--loss); }
.focus-teal { border-color: var(--teal); }
.summary div.focus-violet {
  border: 1px solid transparent;
  background:
    linear-gradient(var(--panel), var(--panel)) padding-box,
    var(--logo) border-box;
}
.summary div.focus-amber { border-color: var(--amber); }
.summary div.focus-loss { border-color: var(--loss); }
.summary div.focus-teal { border-color: var(--teal); }
.edge-amber { border-left: 3px solid var(--amber); }
.edge-loss { border-left: 3px solid var(--loss); }
tr.edge-amber td:first-child { border-left: 3px solid var(--amber); }
tr.edge-loss td:first-child { border-left: 3px solid var(--loss); }
.big { font-size: 20px; }
.pair { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 8px; }
.pair p { margin: 0; }
td.big { font-size: 20px; font-weight: 600; }
.state, .kind { font-size: 18px; font-weight: 600; }
.status-mark, svg.status-mark { width: 1em; height: 1em; vertical-align: -0.15em; font-variant-emoji: text; }
.upcoming { color: var(--amber); }
.overdue { color: var(--loss); }
.active { color: var(--teal); }
.login { max-width: 360px; margin: 15vh auto; padding: 24px; display: grid; gap: 12px; }
.login input { font-size: 16px; padding: 10px; background: var(--dark); color: var(--text); border: 1px solid var(--line); }
@media (min-width: 800px) {
  .shell { display: grid; grid-template-columns: 248px minmax(0, 1fr); }
  .side { display: block; padding: 24px 16px; border-right: 1px solid var(--line); }
  .side a.brand { font-size: 32px; line-height: 1.15; white-space: nowrap; }
  .tabs { display: none; }
  .main { padding: 24px; }
  .today-grid { grid-template-columns: 1.5fr repeat(4, 1fr); align-items: end; }
  .hero { grid-column: auto; }
  .hero strong { font-size: 48px; }
  .health, .periods { grid-template-columns: repeat(5, 1fr); }
  .periods { grid-template-columns: repeat(4, 1fr); }
  .summary.cols-4 { grid-template-columns: repeat(4, 1fr); }
  .summary.cols-5 { grid-template-columns: repeat(5, 1fr); }
  .summary strong, .risk .metric strong { font-size: 32px; }
  .wide { display: block; margin-top: 18px; }
  .narrow { display: none; }
  .prio { grid-template-columns: 1.5fr 1fr 1fr; }
  .pnl strong { font-size: 36px; }
}
@media (max-width: 799px) {
  .phone-brand { display: inline-block; margin: 0; }
  header {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    column-gap: 12px;
    row-gap: 8px;
    overflow: visible;
  }
  .title { display: contents; }
  .phone-brand {
    grid-column: 1 / -1;
    grid-row: 1;
    display: block;
    font-size: 40px;
    line-height: 1.35;
    letter-spacing: -0.03em;
    padding: 0.12em 0 0.28em;
    white-space: nowrap;
    overflow: visible;
    -webkit-box-decoration-break: clone;
    box-decoration-break: clone;
  }
  .title h2 {
    grid-column: 1;
    grid-row: 2;
    font-size: 18px;
    min-width: 0;
  }
  .header-actions, header > form {
    grid-column: 2;
    grid-row: 2;
    justify-self: end;
  }
  .header-actions { gap: 6px; }
  .header-actions button, header > form button { padding: 7px 10px; font-size: 14px; }
  .mark .tip { display: none; }
  .summary.cols-4 strong, .summary.cols-5 strong { font-size: 22px; }
}
button.fold {
  display: flex; justify-content: flex-start; width: 100%; margin: 4px 0 0; padding: 0 0 0 14px;
  border: 0; color: var(--muted); line-height: 0;
}
button.fold svg { width: 16px; height: 16px; display: block; transition: transform 160ms ease; }
button.fold[aria-expanded="true"] svg { transform: rotate(180deg); }
button.fold:hover, button.fold:focus-visible { color: var(--text); }
.band { margin-top: 12px; padding: 14px; border: 1px solid var(--line); border-radius: 12px; }
.band.total {
  border: 1px solid transparent;
  background:
    linear-gradient(var(--dark), var(--dark)) padding-box,
    var(--logo) border-box;
}
.band h3, .subpnl h3, .slim h3 { margin: 0; color: var(--violet); font-size: 13px; font-weight: 600; }
.band > h3, .subpnl > h3 { margin-bottom: 10px; }
.split { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 8px; }
.slim, .subpnl { margin-top: 8px; padding: 8px 14px; border: 1px solid var(--line); border-radius: 10px; }
.slim { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.slim strong { font-size: 18px; font-weight: 600; }
.bits { display: flex; flex-wrap: wrap; gap: 8px 16px; }
.bits span { color: var(--muted); font-size: 12px; }
.bits b { font-weight: 600; }
.subpnl .periods { margin-top: 0; }
.vol { display: block; margin-top: 4px; color: var(--text); font-style: normal; font-weight: 600; }
.venues { margin-left: 12px; }
.venue-head th { color: var(--violet); font-size: 13px; text-align: left; }
.venue-grid { display: grid; grid-template-columns: 1fr; gap: 16px; margin-top: 16px; }
.venue-card {
  min-height: 168px; padding: 22px 22px 18px; background: var(--panel);
  border: 1px solid var(--line); border-radius: 12px;
}
.venue-top { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.venue-card h3 { margin: 0; color: var(--text); font-size: 22px; font-weight: 600; letter-spacing: -0.02em; }
.lifecycle {
  flex-shrink: 0; padding: 4px 10px; border: 1px solid var(--line); border-radius: 999px;
  color: var(--muted); font-size: 12px; letter-spacing: 0.04em;
}
.lifecycle.supported { color: var(--teal); border-color: rgba(20, 241, 149, .45); }
.lifecycle.research { color: #c49bff; border-color: rgba(153, 69, 255, .7); }
.lifecycle.planned { color: var(--muted); }
.lifecycle.deprecated { color: var(--loss); border-color: rgba(255, 77, 77, .5); }
.venue-lines { margin-top: 18px; }
.venue-line {
  display: flex; justify-content: space-between; align-items: baseline; gap: 16px;
  padding: 10px 0; border-top: 1px solid var(--line);
}
.venue-line span { color: var(--muted); font-size: 13px; }
.venue-line strong, .venue-line b { font-size: 18px; font-weight: 600; font-variant-numeric: tabular-nums; }
.venue-card .quiet { margin: 22px 0 0; color: var(--muted); font-size: 14px; }
.venue-block { margin-top: 16px; }
.venue-block .kicker { margin: 0 0 8px; color: var(--violet); font-size: 13px; font-weight: 600; }
.venue-block .periods { margin-top: 0; }
.venue-grid.books { grid-template-columns: 1fr; }
.venue-card .summary { margin-top: 0; }
.venue-block .list, .venue-block .wide, .venue-block .narrow { margin-top: 12px; }
@media (min-width: 800px) {
  .venue-grid { grid-template-columns: 1fr 1fr; gap: 20px; }
  .venue-grid.books { grid-template-columns: 1fr; }
}
@media (max-width: 799px) {
  .split { grid-template-columns: 1fr; }
}
"""


def login_page(error: str) -> str:
    notice = f"<p>{escape(error)}</p>" if error else ""
    return f"""
    <main class="login">
      <a class="brand" href="/portal">Signal Nexus</a>
      {notice}
      <form method="post" action="/portal/login">
        <label>{t("パスワード")}<input type="password" name="password" autocomplete="current-password" required></label>
        <button type="submit">{t("開く")}</button>
      </form>
    </main>
    """


def message_page(text: str) -> str:
    return f'<main class="login"><a class="brand" href="/portal">Signal Nexus</a><p>{escape(text)}</p></main>'


def render_dashboard(board: dict | None) -> str:
    now = datetime.now(TOKYO)
    schedule = read_schedule(now.date())
    ops = []
    if schedule:
        ops = [row for row in schedule if row["state"] in {"Upcoming", "Overdue"}]
    parts = [_health(board, now)]
    if board is not None:
        parts.insert(0, _today(board))
        parts.insert(1, _risk(board, now))
    parts.insert(2 if board is not None else 0, _operations(ops))
    if board is not None:
        parts.append(_pnl(board, now))
        parts.append(_strategy_summary(board))
        parts.append(_fold_script())
    actions = _fold_actions() if board is not None else ""
    return _shell("dashboard", "Dashboard", "", "".join(parts), actions=actions)


def render_trading(view: str, board: dict | None, balances, orders, fetched_at: datetime | None) -> str:
    current = view if view in {"positions", "trades", "orders", "balances"} else "positions"
    switch = _switch(
        t("Trading の切り替え"),
        (
            ("positions", "Positions", "/portal/trading"),
            ("trades", "Trades", "/portal/trading?view=trades"),
            ("orders", "Open Orders", "/portal/trading?view=orders"),
            ("balances", "Balances", "/portal/trading?view=balances"),
        ),
        current,
    )
    now = datetime.now(timezone.utc)
    if current == "trades":
        body = _trades(None if board is None else board.get("trades") or [])
    elif current == "orders":
        body = _orders(orders, fetched_at)
    elif current == "balances":
        body = _balances(balances, fetched_at)
    else:
        body = _positions(None if board is None else board.get("positions") or [], now)
    return _shell("trading", "Trading", switch, body)


def render_analytics(view: str, board: dict | None, backtests: dict) -> str:
    current = view if view in {"tickers", "backtest"} else "strategies"
    switch = _switch(
        t("Analytics の切り替え"),
        (
            ("strategies", "Strategies", "/portal/analytics"),
            ("tickers", "Tickers", "/portal/analytics?view=tickers"),
            ("backtest", "Backtest Comparison", "/portal/analytics?view=backtest"),
        ),
        current,
    )
    labels = {
        "strategies": ("Active Strategies", "Profitable Strategies", "Total Realized PnL", "Average PF"),
        "tickers": ("Active Tickers", "Profitable Tickers", "Total Realized PnL", "Average PF"),
        "backtest": ("Compared Strategies", "Live Average PF", "Backtest Average PF", "Largest Gap Strategy"),
    }
    if board is None or (current == "tickers" and board.get("ticker_rows") is None):
        body = _blank_summary(labels[current])
    elif current == "backtest":
        body = _backtests(backtest_view(board["strategy_rows"], backtests))
    elif current == "tickers":
        body = _tickers(tickers_view(board["ticker_rows"]))
    else:
        body = _strategies(strategies_view(board["strategy_rows"]))
    return _shell("analytics", "Analytics", switch, body)


def render_operations(view: str, audits) -> str:
    current = "audit" if view == "audit" else "schedule"
    switch = _switch(
        t("Operations の切り替え"),
        (
            ("schedule", "Schedule", "/portal/operations"),
            ("audit", "Audit Log", "/portal/operations?view=audit"),
        ),
        current,
    )
    if current == "audit":
        body = _audits(audits_view(None if audits is None else audits))
    else:
        today = datetime.now(TOKYO).date()
        body = _schedule(read_schedule(today))
    return _shell("operations", "Operations", switch, body)


def _shell(active: str, title: str, switch: str, body: str, actions: str = "") -> str:
    side = []
    tabs = []
    for key, label, href in NAV:
        current = ' aria-current="page"' if key == active else ""
        side.append(f'<a href="{href}"{current}>{label}</a>')
        tabs.append(f'<a href="{href}"{current}>{label}</a>')
    return f"""
    <div class="shell">
      <nav class="side" aria-label="{t("行き先")}"><a class="brand" href="/portal">Signal Nexus</a>{''.join(side)}</nav>
      <div class="main">
        <header>
          <div class="title"><a class="brand phone-brand" href="/portal">Signal Nexus</a><h2>{escape(title)}</h2></div>
          {actions or '<form method="post" action="/portal/logout"><button type="submit">Logout</button></form>'}
        </header>
        {switch}
        {body}
      </div>
      <nav class="tabs" aria-label="{t("行き先")}">{''.join(tabs)}</nav>
    </div>
    """


_CHEVRON = (
    '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 6 L8 10.5 L12.5 6" fill="none" '
    'stroke="currentColor" stroke-width="1.25" stroke-linecap="round" stroke-linejoin="round"/></svg>'
)


def _fold(body: str) -> str:
    return (
        f'<button type="button" class="fold" aria-expanded="false" aria-label="{t("内訳を開く")}">'
        f"{_CHEVRON}</button>"
        f'<div class="fold-body" hidden>{body}</div>'
    )


def _fold_actions() -> str:
    return (
        '<div class="header-actions">'
        '<button type="button" id="fold-all">Expand all</button>'
        '<form method="post" action="/portal/logout"><button type="submit">Logout</button></form>'
        "</div>"
    )


def _fold_script() -> str:
    script = """
    <script>
    (function () {
      var sections = document.querySelectorAll("[data-fold]");
      var all = document.getElementById("fold-all");
      function mark(section, open) {
        var body = section.querySelector(".fold-body");
        var button = section.querySelector(".fold");
        body.hidden = !open;
        button.setAttribute("aria-expanded", open ? "true" : "false");
        button.setAttribute("aria-label", open ? "内訳を閉じる" : "内訳を開く");
      }
      function everyOpen() {
        return Array.prototype.every.call(sections, function (section) {
          return section.querySelector(".fold").getAttribute("aria-expanded") === "true";
        });
      }
      function label() {
        all.textContent = everyOpen() ? "Collapse all" : "Expand all";
      }
      Array.prototype.forEach.call(sections, function (section) {
        section.querySelector(".fold").addEventListener("click", function () {
          mark(section, this.getAttribute("aria-expanded") !== "true");
          label();
        });
      });
      all.addEventListener("click", function () {
        var open = !everyOpen();
        Array.prototype.forEach.call(sections, function (section) { mark(section, open); });
        label();
      });
    })();
    </script>
    """
    return script.replace("内訳を閉じる", t("内訳を閉じる")).replace("内訳を開く", t("内訳を開く"))


def _switch(label: str, items: tuple, current: str) -> str:
    links = []
    for key, text, href in items:
        mark = ' aria-current="page"' if key == current else ""
        links.append(f'<a href="{href}"{mark}>{text}</a>')
    return f'<nav class="switch" aria-label="{escape(label)}">{"".join(links)}</nav>'


def _today(board: dict) -> str:
    forecast = board["pnl"]["forecast"]
    actual = Decimal(str(forecast["actual"]))
    month = str(forecast.get("month") or "")
    total_volume = _month_volume(board.get("volume"), month)
    return f"""
    <section class="block" data-fold aria-label="Today">
      <p class="eyebrow">Today</p>
      <div class="band total">
        <h3>Total</h3>
        <div class="today-grid">
          <div class="metric hero"><span>{actual_label("USD")}</span><strong class="{_tone(actual)}">{_num(actual, signed=False)}</strong><span>{t("今月の出来高")}</span><b class="vol">{_volume_text(total_volume, "USD")}</b></div>
          <div class="metric"><span>{t("月目標")}</span><strong>{_num(forecast.get("target"))}</strong></div>
          <div class="metric"><span>{t("達成率")}</span><strong class="{_tone(Decimal(str(forecast["achievement"])) if forecast.get("achievement") not in (None, "") else None)}">{_pct(forecast.get("achievement"))}</strong></div>
          <div class="metric"><span>{t("残必要額")}</span><strong>{_num(forecast.get("remaining"))}</strong></div>
          <div class="metric"><span>{t("月末着地予測")}</span><strong>{_num(forecast.get("forecast"))}</strong></div>
        </div>
      </div>
      {_fold(_venue_grid(board, "today", month))}
    </section>
    """


def _risk(board: dict, now: datetime) -> str:
    moment = now.astimezone(timezone.utc)
    rows = board.get("positions") or []
    return f"""
    <section class="block" data-fold aria-label="Risk Summary">
      <p class="eyebrow">Risk Summary</p>
      <div class="band total"><h3>Total</h3>{_risk_cards(positions_view(rows, moment), "USD")}</div>
      {_fold(_venue_grid(board, "risk", "", now=moment))}
      <p class="hint"><a class="more" href="/portal/trading">{t("Positions を開く")}</a></p>
    </section>
    """


def _operations(rows: list[dict]) -> str:
    body = []
    for row in rows:
        if row["state"] == "Overdue":
            state = t("期限超過")
            css = "overdue"
        else:
            state = t("直近")
            css = "upcoming"
        body.append(
            "<tr>"
            f"<td>{escape(row['name'])}</td>"
            f"<td>{escape(row['due'])}</td>"
            f"<td class=\"{css}\">{state}</td>"
            "</tr>"
        )
    return f"""
    <section class="block" aria-label="Operations">
      <p class="eyebrow">Operations</p>
      <div class="panel scroll">
        <table>
          <tr><th>{t("作業名")}</th><th>{t("期限")}</th><th>{t("状態")}</th></tr>
          {''.join(body)}
        </table>
        <a class="more" href="/portal/operations">{t("Schedule を開く")}</a>
      </div>
    </section>
    """


def _health(board: dict | None, now: datetime) -> str:
    mode = execution_mode()
    mode_class = "ok up" if mode == "live" else ""
    order = "Unhealthy" if kill_switch_enabled() else "Healthy"
    order_class = "down" if order == "Unhealthy" else "up"
    if board is None:
        aggregate = "Unhealthy"
        alert = "—"
        ingest = "Unhealthy"
    else:
        aggregate = "Healthy"
        audits = board.get("audits", [])
        found = latest_alert(audits)
        alert = "No Activity" if found is None and audits is not None else ("—" if found is None else found.astimezone(TOKYO).strftime("%Y-%m-%d %H:%M"))
        ingest = ingest_state(board.get("ingest_succeeded_at"), now)
    ingest_class = "down" if ingest == "Unhealthy" else "up"
    return f"""
    <section class="block" aria-label="System Health">
      <p class="eyebrow">System Health</p>
      <div class="health">
        <div><span>{t("モード")}</span><strong class="{mode_class}">{escape(mode)}</strong></div>
        <div><span>{t("発注")}</span><strong class="{order_class}">{order}</strong></div>
        <div><span>{t("集計")}</span><strong class="{"down" if aggregate == "Unhealthy" else "up"}">{aggregate}</strong></div>
        <div><span>{t("取り込み")}</span><strong class="{ingest_class}">{ingest}</strong></div>
        <div><span>{t("直近のアラート")}</span><strong>{escape(alert)}</strong></div>
      </div>
    </section>
    """


def _pnl(board: dict, now: datetime) -> str:
    total = _pnl_values(board["pnl"], now, monthly=Decimal(str(board["pnl"]["forecast"]["actual"])))
    cells = "".join(
        f'<div><span>{label}</span><strong class="{_tone(value)}">{_signed(value, "USD")}</strong></div>'
        for label, value in total.items()
    )
    return (
        '<section class="block" data-fold aria-label="PnL"><p class="eyebrow">PnL</p>'
        f'<div class="band total"><h3>Total</h3><div class="periods">{cells}</div></div>'
        + _fold(_venue_grid(board, "pnl", "", now=now))
        + "</section>"
    )


def _strategy_summary(board: dict) -> str:
    rows = board.get("strategy_rows")
    if rows is None:
        rows = []
        for item in board.get("strategies") or []:
            live = item.get("live")
            if live:
                rows.append({**live, "strategy_name": item.get("name")})
    view = strategies_view(rows)
    body = "".join(
        "<tr>"
        f"<td>{escape(show_text(row['strategy_name']))}</td>"
        f"<td>{escape(row.get('venue') or 'mexc_spot')}</td>"
        f"<td class=\"{_tone(row['realized'])}\">{_signed(row['realized'], _unit(row.get('venue')))}</td>"
        f"<td>{_volume_text(row.get('volume') or Decimal('0'), _unit(row.get('venue')))}</td>"
        f"<td class=\"{_pf_tone(row['profit_factor'])}\">{_pf(row['profit_factor'])}</td>"
        f"<td>{row['count']}</td>"
        f"<td>{_pct(row['win_rate'])}</td>"
        "</tr>"
        for row in view["rows"]
    )
    return f"""
    <section class="block" aria-label="Strategy Summary">
      <p class="eyebrow">Strategy Summary</p>
      <p class="hint">{t("決済が1件以上存在する戦略・未分類のみを表示")}</p>
      <div class="panel scroll">
        <table>
          <tr><th>{t("戦略")}</th><th>Venue</th><th>{t("実現損益")}</th><th>{t("出来高")}</th><th>PF</th><th>{t("回数")}</th><th>{t("勝率")}</th></tr>
          {body}
        </table>
        <a class="more" href="/portal/analytics">{t("Strategies を開く")}</a>
      </div>
    </section>
    """


def _positions(rows: list[dict] | None, now: datetime) -> str:
    if rows is None:
        return _blank_summary(("Open Positions", "Unrealized PnL"))
    moment = now.astimezone(timezone.utc)
    total = _position_summary(positions_view(rows, moment), "USD")

    def section(_label: str, _venue_id: str, line_rows: list[dict]) -> str:
        return _position_body(positions_view(line_rows, moment))

    return f'<div class="band total"><h3>Total</h3>{total}</div>' + _trading_grid(rows, section)


def _trades(rows: list[dict] | None) -> str:
    if rows is None:
        return _blank_summary(("Recent Trades", t("当日約定数"), count_label("BUY", "fills"), count_label("SELL", "fills"), unclassified_count("fills")))
    today = datetime.now(TOKYO).date()

    def section(_label: str, venue_id: str, line_rows: list[dict]) -> str:
        return _trade_body(trades_view(line_rows, today), venue_id)

    return _trading_grid(rows, section)


def _trade_cards(view: dict, futures: bool) -> str:
    open_label = count_label("COVER", "fills") if futures else count_label("BUY", "fills")
    close_label = count_label("SHORT", "fills") if futures else count_label("SELL", "fills")
    if futures:
        opens = sum(1 for row in view["rows"] if row["action"] == "COVER")
        closes = sum(1 for row in view["rows"] if row["action"] == "SHORT")
    else:
        opens = view["buy"]
        closes = view["sell"]
    unclassified = ("focus-amber", "amber") if view["unclassified"] else ("", "")
    return _summary(
        (
            ("Recent Trades", str(view["count"]), ""),
            (t("当日約定数"), str(view["today"]), ""),
            (open_label, str(opens), "up" if opens else ""),
            (close_label, str(closes), ""),
            (unclassified_count("fills"), str(view["unclassified"]), unclassified[1]),
        ),
        "cols-5",
        {4: unclassified[0]},
    )


def _trade_body(view: dict, venue_id: str) -> str:
    cards = _trade_cards(view, is_futures(venue_id))
    amount = sum((row["quote_spent"] + row["quote_received"] for row in view["rows"]), Decimal("0"))
    volume = f'<p><b class="vol">{volume_phrase(_volume_text(amount, _unit(venue_id)))}</b></p>'
    money = _unit(venue_id)
    table = []
    cards_html = []
    for row in view["rows"]:
        edge = "edge-amber" if row["unclassified"] else ""
        strategy = f'<span class="amber">{escape(show_text(row["strategy_name"]))}</span>' if row["unclassified"] else escape(show_text(row["strategy_name"]))
        action = row.get("action") or row["side"]
        side = f'<span class="{"buy" if action in {"BUY", "COVER"} else ""}">{escape(action)}</span>'
        when = escape(row["filled_at"].strftime("%Y-%m-%d %H:%M"))
        venue = escape(row.get("venue") or "mexc_spot")
        table.append(
            f'<tr class="{edge}"><td>{when}</td><td>{strategy}</td><td>{venue}</td><td>{escape(row["symbol"])}</td>'
            f"<td>{side}</td><td>{_num(row['quote_received'])}</td><td>{_num(row['quote_spent'])}</td>"
            f"<td>{_qty(row['quantity'])}</td></tr>"
        )
        cards_html.append(
            f'<article class="card {edge}"><p class="lead">{when}</p><p>{strategy}</p>'
            f'<p>{venue} · {escape(row["symbol"])} · {side}</p>'
            f'<p class="meta">{trade_amounts(_num(row["quote_received"]), _num(row["quote_spent"]), _qty(row["quantity"]))}</p></article>'
        )
    return (
        cards
        + volume
        + f'<div class="wide scroll"><table><tr><th>{t("約定時刻")}</th><th>{t("戦略")}</th><th>Venue</th><th>{t("銘柄")}</th><th>{t("売買")}</th>'
        + f"<th>{received_header(escape(money))}</th><th>{spent_header(escape(money))}</th><th>{t('数量')}</th></tr>"
        + "".join(table)
        + "</table></div>"
        + f'<div class="narrow">{"".join(cards_html)}</div>'
    )


def _orders(view: dict | None, fetched_at: datetime | None) -> str:
    if view is None:
        return _blank_summary((t("未約定件数"), count_label("BUY", "orders"), count_label("SELL", "orders"), unclassified_count("orders")))
    if "rows" in view:
        accounts = {"mexc_spot": view, "mexc_futures": None}
    else:
        accounts = {"mexc_spot": view.get("spot"), "mexc_futures": view.get("futures")}
        if "arcus" in view:
            accounts["arcus"] = view.get("arcus")
    return _account_grid(
        accounts,
        lambda _label, venue_id, account: _order_body(account, fetched_at, venue_id),
    )


def _order_body(view: dict | None, fetched_at: datetime | None, venue_id: str) -> str:
    if view is None:
        return '<p class="empty">Unable to retrieve</p>'
    if venue_id == "arcus":
        left_name, right_name = count_label("LONG", "orders"), count_label("SHORT", "orders")
        left = sum(1 for row in view["rows"] if row["side"] == "LONG")
        right = sum(1 for row in view["rows"] if row["side"] == "SHORT")
    elif is_futures(venue_id):
        left_name, right_name = count_label("SHORT", "orders"), count_label("COVER", "orders")
        left = sum(1 for row in view["rows"] if row["side"] == "SHORT")
        right = sum(1 for row in view["rows"] if row["side"] == "COVER")
    else:
        left_name, right_name = count_label("BUY", "orders"), count_label("SELL", "orders")
        left, right = view["buy"], view["sell"]
    unclassified = ("focus-amber", "amber") if view["unclassified"] else ("", "")
    cards = _summary(
        (
            (t("未約定件数"), str(view["count"]), ""),
            (left_name, str(left), "up" if left else ""),
            (right_name, str(right), ""),
            (unclassified_count("orders"), str(view["unclassified"]), unclassified[1]),
        ),
        "cols-4",
        {3: unclassified[0]},
    )
    when = "" if fetched_at is None else escape(fetched_at.astimezone(TOKYO).strftime("%Y-%m-%d %H:%M"))
    rule = f'<p class="rule">{orders_fetched(when)}</p>' if when else ""
    if view["count"] == 0:
        return f"{cards}{rule}<p class=\"empty\">{t('未約定注文はありません')}</p>"
    table = []
    cards_html = []
    for row in view["rows"]:
        edge = "edge-amber" if row["unclassified"] else ""
        strategy = f'<span class="amber">{escape(show_text(row["strategy_name"]))}</span>' if row["unclassified"] else escape(show_text(row["strategy_name"]))
        side = f'<span class="{"buy" if row["side"] in {"BUY", "LONG"} else ""}">{row["side"]}</span>'
        created = "—" if row["created"] is None else escape(row["created"].astimezone(TOKYO).strftime("%Y-%m-%d %H:%M"))
        elapsed = "—" if row["elapsed"] is None else escape(row["elapsed"])
        table.append(
            f'<tr class="{edge}"><td class="big">{_qty(row["remaining"])}</td><td><strong class="big">{elapsed}</strong><br>{created}</td>'
            f"<td>{strategy}</td><td>{escape(row['symbol'])}</td><td>{side}</td><td>{_price(row['price'])}</td>"
            f"<td>{escape(row['order_type'] or '—')}</td><td>{_qty(row['amount'])}</td></tr>"
        )
        cards_html.append(
            f'<article class="card {edge}"><p class="lead">{escape(row["symbol"])} · {side}</p>'
            f'<p class="sub">{_qty(row["remaining"])}</p><p>{elapsed}</p>'
            f'<p class="meta">{strategy} · {created} · {escape(row["order_type"] or "—")} · {_price(row["price"])} · {t("数量")} {_qty(row["amount"])}</p></article>'
        )
    return (
        cards
        + rule
        + f'<div class="wide scroll"><table><tr><th>{t("残数量")}</th><th>{t("経過時間")}</th><th>{t("戦略")}</th><th>{t("銘柄")}</th><th>{t("売買")}</th>'
        + f"<th>{t('注文価格')}</th><th>{t('注文種別')}</th><th>{t('注文数量')}</th></tr>"
        + "".join(table)
        + "</table></div>"
        + f'<div class="narrow">{"".join(cards_html)}</div>'
    )


def _balances(view: dict | None, fetched_at: datetime | None) -> str:
    if view is None:
        return _blank_summary((t("USDT 合計"), t("使える"), t("注文中"), t("コイン数")))
    if "usdt" in view and "spot" not in view:
        accounts = {"mexc_spot": view, "mexc_futures": None}
    else:
        accounts = {"mexc_spot": view.get("spot"), "mexc_futures": view.get("futures")}
        if "arcus" in view:
            accounts["arcus"] = view.get("arcus")
    return _account_grid(
        accounts,
        lambda _label, venue_id, account: (
            _arcus_balance_body(account, fetched_at) if venue_id == "arcus" else _balance_body(account, fetched_at)
        ),
    )


def _arcus_balance_body(view: dict | None, fetched_at: datetime | None) -> str:
    if view is None:
        return '<p class="empty">Unable to retrieve</p>'
    cards = _summary(
        (
            (t("評価額"), f"{_num(view.get('equity'))} USD", ""),
            (t("使える"), f"{_num(view.get('free'))} USD", ""),
            (t("証拠金"), f"{_num(view.get('margin'))} USD", ""),
            (t("建玉数"), str(view.get("positions") or 0), ""),
        ),
        "cols-4",
        {0: "focus-violet"},
    )
    when = "" if fetched_at is None else escape(fetched_at.astimezone(TOKYO).strftime("%Y-%m-%d %H:%M"))
    rule = f'<p class="rule">{usd_fetched(when)}</p>' if when else ""
    return f"{cards}{rule}"


def _balance_body(view: dict | None, fetched_at: datetime | None) -> str:
    if view is None:
        return '<p class="empty">Unable to retrieve</p>'
    usdt = view["usdt"]
    cards = _summary(
        (
            (t("USDT 合計"), _num(usdt["total"]), ""),
            (t("使える"), _num(usdt["free"]), ""),
            (t("注文中"), _num(usdt["used"]), ""),
            (t("コイン数"), str(view["count"]), ""),
        ),
        "cols-4",
        {0: "focus-violet"},
    )
    when = "" if fetched_at is None else escape(fetched_at.astimezone(TOKYO).strftime("%Y-%m-%d %H:%M"))
    table = []
    cards_html = []
    for row in view["coins"]:
        table.append(
            f'<tr><td class="asset">{escape(row["code"])}</td><td>{_qty(row["total"])}</td>'
            f'<td>{_qty(row["free"])}</td><td>{_qty(row["used"])}</td></tr>'
        )
        cards_html.append(
            f'<article class="card"><p class="lead">{escape(row["code"])}</p><p class="sub">{_qty(row["total"])}</p>'
            f'<p class="meta">{balance_amounts(_qty(row["free"]), _qty(row["used"]))}</p></article>'
        )
    return (
        cards
        + f'<p class="rule">{coins_fetched(when)}</p>'
        + f'<div class="wide scroll"><table><tr><th>{t("通貨")}</th><th>{t("合計")}</th><th>{t("使える")}</th><th>{t("注文中")}</th></tr>'
        + "".join(table)
        + "</table></div>"
        + f'<div class="narrow">{"".join(cards_html)}</div>'
    )


def _strategies(view: dict) -> str:
    table = [f'<tr><th>{t("実現損益")}</th><th>{t("出来高")}</th><th>PF</th><th>{t("利益率")}</th><th>{t("勝率")}</th><th>{t("回数")}</th><th>{t("戦略")}</th><th>Venue</th></tr>']
    cards_html = []
    for venue, rows in _grouped(view["rows"]):
        table.append(f'<tr class="venue-head"><th colspan="8">{escape(venue)}</th></tr>')
        for row in rows:
            unit = _unit(row.get("venue"))
            table.append(
                "<tr>"
                f"<td class=\"{_tone(row['realized'])}\">{_signed(row['realized'], unit)}</td>"
                f"<td>{_volume_text(row.get('volume') or Decimal('0'), unit)}</td>"
                f"<td class=\"{_pf_tone(row['profit_factor'])}\">{_pf(row['profit_factor'])}</td>"
                f"<td>{_pct(row['profit_rate'])}</td><td>{_pct(row['win_rate'])}</td><td>{row['count']}</td>"
                f"<td>{escape(show_text(row['strategy_name']))}</td><td>{escape(row.get('venue') or 'mexc_spot')}</td></tr>"
            )
            cards_html.append(
                f'<article class="card"><p class="lead">{escape(show_text(row["strategy_name"]))}</p>'
                f'<p class="meta">{escape(venue)}</p>'
                f'<p class="sub {_tone(row["realized"])}">{_signed(row["realized"], unit)}</p>'
                f'<p class="vol">{volume_phrase(_volume_text(row.get("volume") or Decimal("0"), unit))}</p>'
                f'<p class="{_pf_tone(row["profit_factor"])}">PF {_pf(row["profit_factor"])}</p>'
                f'<p class="meta">{rate_meta(_pct(row["profit_rate"]), _pct(row["win_rate"]), str(row["count"]))}</p></article>'
            )
    shown = _book_realized(view["rows"])
    cards = _summary(
        (
            ("Active Strategies", str(view["active"]), ""),
            ("Profitable Strategies", str(view["profitable"]), ""),
            ("Total Realized PnL", _signed(shown, "USD"), _tone(shown)),
            ("Average PF", _pf(view["average_pf"]), _pf_tone(view["average_pf"])),
        ),
        "cols-4",
        {2: "focus-violet", 3: "focus-violet"},
    )
    return (
        cards
        + '<div class="wide scroll"><table>'
        + "".join(table)
        + "</table></div>"
        + f'<div class="narrow">{"".join(cards_html)}</div>'
    )


def _tickers(view: dict) -> str:
    shown = _book_realized(view["rows"])
    cards = _summary(
        (
            ("Active Tickers", str(view["active"]), ""),
            ("Profitable Tickers", str(view["profitable"]), ""),
            ("Total Realized PnL", _signed(shown, "USD"), _tone(shown)),
            ("Average PF", _pf(view["average_pf"]), _pf_tone(view["average_pf"])),
        ),
        "cols-4",
        {2: "focus-violet", 3: "focus-violet"},
    )
    table = [f'<tr><th>Venue</th><th>{t("銘柄")}</th><th>{t("実現損益")}</th><th>{t("出来高")}</th><th>PF</th><th>{t("利益率")}</th><th>{t("勝率")}</th><th>{t("回数")}</th></tr>']
    cards_html = []
    for venue_name, rows in _grouped(view["rows"]):
        table.append(f'<tr class="venue-head"><th colspan="8">{escape(venue_name)}</th></tr>')
        for row in rows:
            link = escape(row["symbol"])
            venue = escape(row.get("venue") or "mexc_spot")
            unit = _unit(row.get("venue"))
            table.append(
                "<tr>"
                f"<td>{venue}</td>"
                f"<td>{link}</td>"
                f'<td class="big {_tone(row["realized"])}">{_signed(row["realized"], unit)}</td>'
                f"<td>{_volume_text(row.get('volume') or Decimal('0'), unit)}</td>"
                f'<td class="big {_pf_tone(row["profit_factor"])}">{_pf(row["profit_factor"])}</td>'
                f"<td>{_pct(row['profit_rate'])}</td><td>{_pct(row['win_rate'])}</td><td>{row['count']}</td>"
                "</tr>"
            )
            cards_html.append(
                f'<article class="card"><p class="lead">{venue} · {link}</p>'
                '<div class="pair">'
                f'<p class="big {_tone(row["realized"])}">{_signed(row["realized"], unit)}</p>'
                f'<p class="big {_pf_tone(row["profit_factor"])}">PF {_pf(row["profit_factor"])}</p>'
                "</div>"
                f'<p class="vol">{volume_phrase(_volume_text(row.get("volume") or Decimal("0"), unit))}</p>'
                f'<p class="meta">{rate_meta(_pct(row["profit_rate"]), _pct(row["win_rate"]), str(row["count"]))}</p>'
                "</article>"
            )
    rule = (
        ""
        if not view["rows"]
        else f'<p class="rule">{t("実現損益の大きい順。同額は PF が高い順。決済が 1 件以上の銘柄だけ。")}</p>'
    )
    return (
        cards
        + '<div class="wide scroll"><table>'
        + "".join(table)
        + "</table></div>"
        + f'<div class="narrow">{"".join(cards_html)}</div>'
        + rule
    )


def _backtests(view: dict) -> str:
    cards = _summary(
        (
            ("Compared Strategies", str(view["count"]), ""),
            ("Live Average PF", _pf(view["live_average_pf"]), _pf_tone(view["live_average_pf"])),
            ("Backtest Average PF", _pf(view["back_average_pf"]), _pf_tone(view["back_average_pf"])),
            ("Largest Gap Strategy", escape(view["largest_gap"] or "—"), ""),
        ),
        "cols-4",
        {3: "focus-violet"},
    )
    table = []
    cards_html = []
    for row in view["rows"]:
        table.append(
            "<tr>"
            f"<td class=\"identity\">{escape(show_text(row['strategy_name']))}</td><td class=\"identity\">{escape(row.get('venue') or 'mexc_spot')}</td>"
            f"<td class=\"set\">{_pct(row['live_rate'])}</td><td>{_pct(row['back_rate'])}</td><td class=\"{_gap_tone(row['rate_diff'], Decimal('2'))}\">{_points(row['rate_diff'])}</td>"
            f"<td class=\"set\">{_pf(row['live_pf'])}</td><td>{_pf(row['back_pf'])}</td><td class=\"{_gap_tone(row['pf_diff'], Decimal('0.20'))}\">{_plain_signed(row['pf_diff'])}</td>"
            f"<td class=\"set\">{_pct(row['live_win'])}</td><td>{_pct(row['back_win'])}</td><td class=\"{_gap_tone(row['win_diff'], Decimal('2'))}\">{_points(row['win_diff'])}</td>"
            f"<td class=\"set\">{_blank_count(row['live_count'])}</td><td>{_blank_count(row['back_count'])}</td><td>{_count_diff(row['count_diff'])}</td>"
            f"{_period_cell(row)}"
            "</tr>"
        )
        cards_html.append(
            f'<article class="card"><p class="lead">{escape(show_text(row["strategy_name"]))}</p>'
            f'<p class="meta">{escape(row.get("venue") or "mexc_spot")} · {escape(_period_text(row))}</p>'
            f'<p class="sub {_gap_tone(row["rate_diff"], Decimal("2"))}">{_points(row["rate_diff"])}</p>'
            f'<p class="meta">{t("利益率")} {_pct(row["live_rate"])} / {_pct(row["back_rate"])}<br>'
            f'PF {_pf(row["live_pf"])} / {_pf(row["back_pf"])} / <span class="{_gap_tone(row["pf_diff"], Decimal("0.20"))}">{_plain_signed(row["pf_diff"])}</span><br>'
            f'{t("勝率")} {_pct(row["live_win"])} / {_pct(row["back_win"])} / <span class="{_gap_tone(row["win_diff"], Decimal("2"))}">{_points(row["win_diff"])}</span><br>'
            f'{t("回数")} {_blank_count(row["live_count"])} / {_blank_count(row["back_count"])} / {_count_diff(row["count_diff"])}</p></article>'
        )
    return (
        cards
        + f'<div class="wide scroll"><table class="compare"><tr><th class="identity">{t("戦略")}</th><th class="identity">Venue</th>'
        + f'<th class="set">{t("利益率")}</th><th>BT</th><th>{t("差")}</th>'
        + f'<th class="set">PF</th><th>BT</th><th>{t("差")}</th><th class="set">{t("勝率")}</th><th>BT</th><th>{t("差")}</th>'
        + f'<th class="set">{t("回数")}</th><th>BT</th><th>{t("差")}</th><th class="days set">{t("BT期間")}</th></tr>'
        + "".join(table)
        + "</table></div>"
        + f'<div class="narrow">{"".join(cards_html)}</div>'
    )


def _schedule(rows: list[dict] | None) -> str:
    if rows is None:
        return _blank_summary(("Operations Tasks", "Upcoming", "Overdue", "Next Due"))
    upcoming = sum(1 for row in rows if row["state"] == "Upcoming")
    overdue = sum(1 for row in rows if row["state"] == "Overdue")
    due = next_due(rows) or "—"
    cards = (
        f'<section class="summary cols-4" aria-label="{t("集計")}">'
        f"<div><span>Operations Tasks</span><strong>{len(rows)}</strong></div>"
        f'<div class="{"focus-amber" if upcoming else ""}"><span class="{"upcoming" if upcoming else ""}">'
        f'<span class="status-mark" aria-hidden="true">◉</span> Upcoming</span>'
        f'<strong class="{"upcoming" if upcoming else ""}">{upcoming}</strong></div>'
        f'<div class="{"focus-loss" if overdue else ""}"><span class="{"overdue" if overdue else ""}">'
        '<span class="status-mark" aria-hidden="true">⚠&#xFE0E;</span> Overdue</span>'
        f'<strong class="{"overdue" if overdue else ""}">{overdue}</strong></div>'
        f"<div><span>Next Due</span><strong>{escape(due)}</strong></div>"
        "</section>"
    )
    if not rows:
        return cards + f'<p class="empty">{t("登録された運用作業はありません")}</p>'
    table = []
    cards_html = []
    for row in rows:
        state = _state(row["state"])
        remain = escape(row["remaining"])
        remain_class = "overdue" if row["state"] == "Overdue" else "upcoming" if row["state"] == "Upcoming" else ""
        table.append(
            f'<tr><td>{escape(row["name"])}</td><td>{escape(row["list_from"])}</td><td>{escape(row["due"])}</td>'
            f'<td class="state">{state}</td><td class="big {remain_class}">{remain}</td></tr>'
        )
        cards_html.append(
            f'<article class="card"><p class="lead">{escape(row["name"])}</p><p class="state">{state}</p>'
            f'<p>{due_phrase(escape(row["due"]))}</p><p class="sub {remain_class}">{remain}</p>'
            f'<p class="meta">{starts_phrase(escape(row["list_from"]))}</p></article>'
        )
    return (
        cards
        + f'<div class="wide scroll"><table><tr><th>{t("作業名")}</th><th>{t("開始日")}</th><th>{t("期限")}</th><th>{t("状態")}</th><th>{t("残日数")}</th></tr>'
        + "".join(table)
        + "</table></div>"
        + f'<div class="narrow">{"".join(cards_html)}</div>'
    )


def _audits(view: dict | None) -> str:
    if view is None:
        return _blank_summary(("Audit Events", "Success", "Failed", "Latest Failure"))
    latest = "—" if view["latest_failure"] is None else escape(view["latest_failure"].strftime("%Y-%m-%d %H:%M"))
    cards = _summary(
        (
            ("Audit Events", str(view["count"]), ""),
            ("Success", str(view["success"]), "up" if view["success"] else ""),
            ("Failed", str(view["failed"]), "down" if view["failed"] else ""),
            ("Latest Failure", latest, ""),
        ),
        "cols-4",
        {1: "focus-teal" if view["success"] else "", 2: "focus-loss" if view["failed"] else ""},
    )
    if view["count"] == 0:
        return cards + f'<p class="empty">{t("監査イベントはありません")}</p>'
    table = []
    cards_html = []
    for row in view["rows"]:
        tone = _audit_class(row["label"])
        edge = "edge-loss" if row["label"] == "FAILED" else "edge-amber" if row["label"] == "REJECTED" else ""
        reason_class = tone if row["edge"] else ""
        reason = "—" if not row["reason"] else escape(row["reason"])
        strategy = "—" if not row["strategy"] else escape(row["strategy"])
        symbol = "—" if not row["symbol"] else escape(row["symbol"])
        when = escape(row["at"].strftime("%Y-%m-%d %H:%M"))
        copy = escape(row["copy"])
        kind = f'<span class="kind {tone}">{_audit_mark(row)}{escape(row["label"])}</span>'
        table.append(
            f'<tr class="{edge}"><td>{kind}</td><td class="big {reason_class}">{reason}</td><td>{when}</td>'
            f"<td>{strategy}</td><td>{symbol}</td><td>{copy}</td></tr>"
        )
        cards_html.append(
            f'<article class="card {edge}"><p>{kind}</p><p class="{reason_class}">{reason}</p>'
            f"<p>{when}</p><p class=\"meta\">{strategy} · {symbol}</p><p>{copy}</p></article>"
        )
    return (
        cards
        + f'<div class="wide scroll"><table><tr><th>{t("イベント種別")}</th><th>{t("理由")}</th><th>{t("発生時刻")}</th><th>{t("戦略")}</th><th>{t("銘柄")}</th><th>{t("写し")}</th></tr>'
        + "".join(table)
        + "</table></div>"
        + f'<div class="narrow">{"".join(cards_html)}</div>'
    )


def _summary(items: tuple, columns: str, borders: dict | None = None) -> str:
    borders = borders or {}
    cells = []
    for index, (label, value, css) in enumerate(items):
        border = borders.get(index) or ""
        cells.append(f'<div class="{border}"><span>{escape(label)}</span><strong class="{css}">{value}</strong></div>')
    return f'<section class="summary {columns}" aria-label="{t("集計")}">{"".join(cells)}</section>'


def _blank_summary(labels: tuple) -> str:
    return _summary(tuple((label, "—", "") for label in labels), "cols-4" if len(labels) != 5 else "cols-5")


def _state(name: str) -> str:
    if name == "Overdue":
        return '<span class="overdue"><span class="status-mark" aria-hidden="true">⚠&#xFE0E;</span> Overdue</span>'
    if name == "Upcoming":
        return '<span class="upcoming"><span class="status-mark" aria-hidden="true">◉</span> Upcoming</span>'
    if name == "Active":
        return '<span class="active"><span class="status-mark" aria-hidden="true">✅&#xFE0E;</span> Active</span>'
    return f"<span>{PENDING_MARK} Pending</span>"


def _audit_mark(row: dict) -> str:
    marks = {
        "SUCCESS": "✅&#xFE0E;",
        "RECEIVED": "⬇&#xFE0E;",
        "SKIPPED": "⏭&#xFE0E;",
        "REJECTED": "⚠&#xFE0E;",
        "FAILED": "❌&#xFE0E;",
        "DROPPED": "🗑&#xFE0E;",
    }
    mark = marks.get(row["label"])
    if mark is None:
        return ""
    return f'<span class="status-mark" aria-hidden="true">{mark}</span> '


def _audit_class(label: str) -> str:
    if label == "SUCCESS":
        return "up"
    if label in {"SKIPPED", "REJECTED"}:
        return "amber"
    if label == "FAILED":
        return "down"
    return ""


def _by_asset_class(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    spot = [row for row in rows if is_spot(row.get("venue") or "mexc_spot")]
    futures = [row for row in rows if is_futures(row.get("venue") or "mexc_spot")]
    return spot, futures


def _venue_grid(board: dict, kind: str, month: str, now: datetime | None = None) -> str:
    positions = board.get("positions") or []
    visible = []
    for card in VENUE_CARDS:
        booked = any(_venue_booked(board, venue_id, positions) for _label, venue_id in card["lines"])
        if card["status"] == "Planned" and not booked:
            continue
        visible.append(_venue_card(board, card, kind, month, positions, now))
    return f'<div class="venue-grid">{"".join(visible)}</div>'


def _venue_card(board: dict, card: dict, kind: str, month: str, positions: list[dict], now: datetime | None) -> str:
    status = card["status"]
    active = status == "Supported" or any(_venue_booked(board, venue_id, positions) for _label, venue_id in card["lines"])
    body = _venue_body(board, card, kind, month, positions, now) if active else '<p class="quiet">No Activity</p>'
    return (
        '<article class="venue-card">'
        f'<div class="venue-top"><h3>{escape(card["name"])}</h3>'
        f'<span class="lifecycle {escape(status.lower())}">{escape(status)}</span></div>'
        f"{body}</article>"
    )


def _venue_body(board: dict, card: dict, kind: str, month: str, positions: list[dict], now: datetime | None) -> str:
    if kind == "today":
        lines = []
        volume = Decimal("0")
        for label, venue_id in card["lines"]:
            amount = _venue_month(board, venue_id, month)
            volume += _month_volume(_venue_volume(board, venue_id), month)
            lines.append(
                f'<div class="venue-line"><span>{escape(label)}</span>'
                f'<strong class="{_tone(amount)}">{_num(amount, signed=False)} USD</strong></div>'
            )
        lines.append(
            f'<div class="venue-line"><span>Month Volume</span><b class="vol">{_volume_text(volume, "USD")}</b></div>'
        )
        return f'<div class="venue-lines">{"".join(lines)}</div>'
    if kind == "risk":
        moment = now or datetime.now(timezone.utc)
        lines = []
        for label, venue_id in card["lines"]:
            view = positions_view(_named(positions, venue_id), moment)
            total = view["total"]
            text = f"0.00 USD" if total == 0 else _signed(total, "USD")
            lines.append(
                f'<div class="venue-line"><span>{escape(label)} · Open {view["count"]}</span>'
                f'<strong class="{_tone(total)}">{text}</strong></div>'
            )
        return f'<div class="venue-lines">{"".join(lines)}</div>'
    blocks = []
    for label, venue_id in card["lines"]:
        values = _pnl_values(_venue_pnl(board, venue_id), now or datetime.now(timezone.utc))
        cells = "".join(
            f'<div><span>{period}</span><strong class="{_tone(amount)}">{_signed(amount, "USD")}</strong></div>'
            for period, amount in values.items()
        )
        blocks.append(f'<div class="venue-block"><p class="kicker">{escape(label)}</p><div class="periods">{cells}</div></div>')
    return "".join(blocks)


def _venue_booked(board: dict, venue_id: str, positions: list[dict]) -> bool:
    if any((row.get("venue") or "") == venue_id for row in positions):
        return True
    pnl = _venue_pnl(board, venue_id)
    volume = _venue_volume(board, venue_id) or {}
    for key in ("days", "weeks", "months", "years"):
        for row in pnl.get(key) or []:
            if Decimal(str(row.get("realized") or "0")) != 0:
                return True
        for row in volume.get(key) or []:
            if Decimal(str(row.get("volume") or "0")) != 0:
                return True
    return False


def _unit(venue: str | None) -> str:
    return quote_currency(venue or "mexc_spot")


def _volume_text(value, unit: str) -> str:
    if value is None:
        return "—"
    return f"{_num(value)} {escape(unit)}"


def _volume_period(rows, key: str) -> Decimal:
    for row in rows or []:
        if row.get("period") == key:
            return Decimal(str(row.get("volume") or "0"))
    return Decimal("0")


def _month_volume(bundle, month: str) -> Decimal:
    if not isinstance(bundle, dict):
        return Decimal("0")
    return _volume_period(bundle.get("months"), month)


def _volume_values(bundle, now: datetime) -> dict[str, Decimal]:
    if not isinstance(bundle, dict):
        bundle = {}
    local = now.astimezone(TOKYO)
    week = local.isocalendar()
    return {
        "Daily": _volume_period(bundle.get("days"), local.date().isoformat()),
        "Weekly": _volume_period(bundle.get("weeks"), f"{week.year}-W{week.week:02d}"),
        "Monthly": _volume_period(bundle.get("months"), local.strftime("%Y-%m")),
        "Annually": _volume_period(bundle.get("years"), str(local.year)),
    }


def _class_volume(board: dict, asset_class: str) -> dict | None:
    found = (board.get("volume_by_asset_class") or {}).get(asset_class)
    return found if isinstance(found, dict) else None


def _venue_volume(board: dict, venue: str) -> dict | None:
    found = (board.get("volume_by_venue") or {}).get(venue)
    return found if isinstance(found, dict) else None


def _venue_pnl(board: dict, venue: str) -> dict:
    found = (board.get("pnl_by_venue") or {}).get(venue)
    return found if isinstance(found, dict) else {}


def _venue_month(board: dict, venue: str, month: str) -> Decimal:
    return _period_value(_venue_pnl(board, venue).get("months"), month)


def _for_venue(rows: list[dict], venue_id: str) -> list[dict]:
    return [row for row in rows if (row.get("venue") or "mexc_spot") == venue_id]


def _card_shell(card: dict, body: str) -> str:
    status = card["status"]
    return (
        '<article class="venue-card">'
        f'<div class="venue-top"><h3>{escape(card["name"])}</h3>'
        f'<span class="lifecycle {escape(status.lower())}">{escape(status)}</span></div>'
        f"{body}</article>"
    )


def _trading_grid(rows: list[dict], section) -> str:
    cards = []
    for card in VENUE_CARDS:
        booked = any(_for_venue(rows, venue_id) for _label, venue_id in card["lines"])
        if card["status"] == "Planned" and not booked:
            continue
        if card["status"] == "Supported" or booked:
            body = "".join(
                f'<div class="venue-block"><p class="kicker">{escape(label)}</p>'
                + section(label, venue_id, _for_venue(rows, venue_id))
                + "</div>"
                for label, venue_id in card["lines"]
            )
        else:
            body = '<p class="quiet">No Activity</p>'
        cards.append(_card_shell(card, body))
    return f'<div class="venue-grid books">{"".join(cards)}</div>'


def _account_grid(accounts: dict, section) -> str:
    cards = []
    for card in VENUE_CARDS:
        if card["status"] == "Planned":
            continue
        if card["status"] != "Supported":
            cards.append(_card_shell(card, '<p class="quiet">No Activity</p>'))
            continue
        body = "".join(
            f'<div class="venue-block"><p class="kicker">{escape(label)}</p>'
            + (
                '<p class="quiet">No Activity</p>'
                if venue_id not in accounts
                else section(label, venue_id, accounts.get(venue_id))
            )
            + "</div>"
            for label, venue_id in card["lines"]
        )
        cards.append(_card_shell(card, body))
    return f'<div class="venue-grid books">{"".join(cards)}</div>'


def _named(rows: list[dict], venue: str) -> list[dict]:
    return [row for row in rows if (row.get("venue") or "") == venue]


def _book_realized(rows: list[dict]) -> Decimal:
    return sum((row["realized"] for row in rows), Decimal("0"))


def _grouped(rows: list[dict]) -> list[tuple[str, list[dict]]]:
    present = {row.get("venue") or "mexc_spot" for row in rows}

    def rank(venue: str) -> tuple:
        if is_spot(venue):
            return (0, venue)
        if quote_currency(venue) == "USDT":
            return (1, 0 if venue == "mexc_futures" else 1, venue)
        return (2, venue)

    return [
        (venue, [row for row in rows if (row.get("venue") or "mexc_spot") == venue])
        for venue in sorted(present, key=rank)
    ]


def _slim_actual(title: str, value: Decimal, volume: Decimal = Decimal("0"), unit: str = "USDT") -> str:
    return (
        f'<div class="slim"><h3>{escape(title)}</h3>'
        f'<div class="metric"><span>{actual_label(unit)}</span><strong class="{_tone(value)}">{_num(value, signed=False)}</strong>'
        f'<span>{t("今月の出来高")}</span><b class="vol">{_volume_text(volume, unit)}</b></div></div>'
    )


def _class_month(board: dict, asset_class: str, month: str, fallback: Decimal) -> Decimal:
    bundle = _class_pnl(board, asset_class)
    if bundle is None:
        return fallback
    return _period_value(bundle.get("months"), month)


def _class_pnl(board: dict, asset_class: str) -> dict | None:
    found = (board.get("pnl_by_asset_class") or {}).get(asset_class)
    return found if isinstance(found, dict) else None


def _risk_cards(view: dict, unit: str = "USD") -> str:
    total = view["total"]
    text = f"0.00 {unit}" if total == 0 else _signed(total, unit)
    return (
        '<div class="risk">'
        f'<div class="metric"><span>Open Positions</span><strong>{view["count"]}</strong></div>'
        f'<div class="metric"><span>Unrealized PnL</span><strong class="{_tone(total)}">{text}</strong></div>'
        "</div>"
    )


def _risk_slim(title: str, view: dict, unit: str = "USD") -> str:
    total = view["total"]
    text = f"0.00 {unit}" if total == 0 else _signed(total, unit)
    return (
        f'<div class="slim"><h3>{title}</h3><div class="bits">'
        f"<span>Open <b>{view['count']}</b></span>"
        f'<span>Unrealized <b class="{_tone(total)}">{text}</b></span>'
        "</div></div>"
    )


def _pnl_values(pnl: dict, now: datetime, monthly: Decimal | None = None) -> dict[str, Decimal]:
    local = now.astimezone(TOKYO)
    week = local.isocalendar()
    if monthly is None:
        monthly = _period_value(pnl.get("months"), local.strftime("%Y-%m"))
    return {
        "Daily": _period_value(pnl.get("days"), local.date().isoformat()),
        "Weekly": _period_value(pnl.get("weeks"), f"{week.year}-W{week.week:02d}"),
        "Monthly": monthly,
        "Annually": _period_value(pnl.get("years"), str(local.year)),
    }


def _pnl_line(title: str, values: dict[str, Decimal], volumes: dict[str, Decimal] | None = None, unit: str = "USDT") -> str:
    volumes = volumes or {}
    cells = "".join(
        f'<div><strong class="{_tone(value)}">{_signed(value, unit)}</strong>'
        f'<b class="vol">{_volume_text(volumes.get(label, Decimal("0")), unit)}</b></div>'
        for label, value in values.items()
    )
    return f'<div class="subpnl"><h3>{escape(title)}</h3><div class="periods">{cells}</div></div>'


def _position_summary(view: dict, unit: str = "USD") -> str:
    total = view["total"]
    return _summary(
        (
            ("Open Positions", str(view["count"]), ""),
            ("Unrealized PnL", f"0.00 {unit}" if total == 0 else _signed(total, unit), _tone(total)),
        ),
        "cols-2",
    )


def _position_body(view: dict) -> str:
    rows = []
    for row in view["rows"]:
        unit = _unit(row.get("venue"))
        rows.append(
            "<article class=\"position\">"
            "<div class=\"prio\">"
            f"<div class=\"metric pnl\"><span>{t('含み損益')}</span><strong class=\"{_tone(row['unrealized'])}\">{_signed(row['unrealized'], unit)}</strong>"
            f"<span class=\"rate {_tone(row['risk'])}\">{_risk_text(row['risk'])}</span></div>"
            f"<div class=\"metric hold\"><span>{t('保有時間')}</span><strong>{escape(row['hold'])}</strong></div>"
            f"<div class=\"metric qty\"><span>{t('残数量')}</span><strong>{_qty(row['quantity'])} {escape(row['base'])}</strong></div>"
            "</div>"
            f"<p class=\"meta\">{escape(show_text(row['strategy_name']))} · {escape(row['symbol'])} · {escape(row.get('venue') or 'mexc_spot')} · "
            f"{opened_phrase(escape(row['opened_at'].astimezone(TOKYO).strftime('%Y-%m-%d %H:%M')))} · "
            f"{price_phrase(_price(row['price']), escape(unit))}</p></article>"
        )
    empty = "" if rows else f'<p class="empty">{t("建玉はありません")}</p>'
    return (
        _position_summary(view, "USD")
        + f'<p class="rule">{t("含み損益の小さい順。価格が無い行は末尾。1 行は戦略と銘柄。")}</p>'
        + f'<div class="list">{"".join(rows)}</div>{empty}'
    )


def _period_value(rows, key: str) -> Decimal:
    for row in rows or []:
        if row.get("period") == key:
            return Decimal(str(row.get("realized") or "0"))
    return Decimal("0")


def _tone(value: Decimal | None) -> str:
    if value is None or value == 0:
        return ""
    return "up" if value > 0 else "down"


def _pf_tone(value: Decimal | None) -> str:
    if value is None:
        return ""
    if value >= Decimal("1.5"):
        return "up"
    if value < Decimal("1"):
        return "down"
    return ""


def _gap_tone(value: Decimal | None, band: Decimal) -> str:
    if value is None or abs(value) < band:
        return ""
    return "up" if value > 0 else "down"


def _num(value, signed: bool = False) -> str:
    if value in (None, ""):
        return "—"
    number = Decimal(str(value))
    if signed:
        return _signed(number)
    return escape(f"{number:,.2f}")


def _signed(value: Decimal | None, suffix: str = "") -> str:
    if value is None:
        return "—"
    text = f"{value:,.2f}" if value <= 0 else f"+{value:,.2f}"
    if suffix:
        text = f"{text} {suffix}"
    return escape(text)


def _pct(value) -> str:
    if value in (None, ""):
        return "—"
    return escape(f"{Decimal(str(value)) * Decimal('100'):,.2f}%")


def _pf(value: Decimal | None) -> str:
    if value is None:
        return "—"
    return escape(f"{value:,.2f}")


def _points(value: Decimal | None) -> str:
    if value is None:
        return "—"
    return escape(f"{value:+.1f}pt")


def _plain_signed(value: Decimal | None) -> str:
    if value is None:
        return "—"
    return escape(f"{value:+.2f}")


def _count_diff(value) -> str:
    if value is None:
        return "—"
    return escape(f"{int(value):+d}")


def _period_text(row: dict) -> str:
    days = row.get("back_days")
    start = row.get("back_start")
    end = row.get("back_end")
    if days is None and not start:
        return "—"
    label = "—" if days is None else period_days(int(days))
    if start and end:
        return f"{label} · {start}–{end}"
    return label


def _period_cell(row: dict) -> str:
    days = row.get("back_days")
    start = row.get("back_start")
    end = row.get("back_end")
    if days is None and not (start and end):
        return '<td class="days set">—</td>'
    label = "—" if days is None else escape(period_days(int(days)))
    span = f'<span class="range">{escape(str(start))}–{escape(str(end))}</span>' if start and end else ""
    return f'<td class="days set">{label}{span}</td>'


def _blank_count(value) -> str:
    if value is None:
        return "—"
    return escape(str(value))


def _qty(value) -> str:
    if value is None:
        return "—"
    text = format(Decimal(str(value)), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return escape(text or "0")


def _price(value) -> str:
    if value is None:
        return "—"
    number = Decimal(str(value))
    if number == number.to_integral():
        return escape(f"{number:,.0f}")
    text = f"{number:,.8f}".rstrip("0").rstrip(".")
    return escape(text)


def _risk_text(value: Decimal | None) -> str:
    if value is None:
        return "—"
    return escape(f"({value:+,.2f}%)")
