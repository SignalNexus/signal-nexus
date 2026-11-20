# Screen Specification

For documentation structure and responsibilities, see [../DOCUMENTATION_STRUCTURE.md](../DOCUMENTATION_STRUCTURE.md).

This document is the canonical screen specification. The Japanese edition is [SCREEN_SPECIFICATION_JA.md](SCREEN_SPECIFICATION_JA.md).

The portal reads the operation. No screen places an order. This document does not publish figures, and it does not describe how a signal is found.

Login is the gate in front of the portal. It is not a fifth primary view. With no matching password, the four views are not shown.

## Overview

Signal Nexus provides four primary views.

- Dashboard
- Trading
- Analytics
- Operations

Performance is not a fifth view. It is the Dashboard reading of the run. Backtest Comparison is not a fifth view. It is a switch inside Analytics.

## Navigation

Each screen below says where it sends you. The map of those links, and the tree of views, is [SCREEN_RELATIONSHIP_DIAGRAM.md](SCREEN_RELATIONSHIP_DIAGRAM.md). The four primary views stay available from every screen. A switch inside Trading, Analytics, or Operations stays inside that view.

## Pinned headers and pages

While a page scrolls, the block named here stays at the top.

- Dashboard. The Total band of Today.
- Positions. Total. The Trading switch scrolls away.
- Trades. For the venue that is open: its summary, volume, the fold button, the pager, and the table header.
- PnL・Vol. Period, unit, and venue. On a wide screen the strategy filter and the ROI basis stay as well.
- Strategies, Backtest Comparison, and Audit Log. The switch, the summary, and the table header.
- Schedule. The switch only.

Trades shows 20 rows per venue on a page. The Audit Log shows 100. The pager sits above and below the list and is hidden when the list fits on one page. A summary counts every row, not only the rows on the page. Strategies and Backtest Comparison are not paged.

## Dashboard

Purpose. See the run as it stands now, and whether alerts are arriving.

What the user can learn. Where today's result sits against the month, how much open-position risk is on, whether the service is receiving alerts, and which strategies have already closed at least one trade.

Key components.

- Today
- Risk Summary
- Operations
- System Health
- PnL
- Strategy Summary
- PnL・Vol

Displayed information.

Some value labels are currently displayed in Japanese. The information described in this document corresponds to those labels.

- Today. Result for the month so far, month volume, month target, progress against that target, amount still required, and the month-end projection. A fold shows one card for each venue id with `enabled: true` in `venues.yml`. MEXC Spot and MEXC Futures share one card. A disabled id is omitted.
- Risk Summary. Count of open positions and unrealized result. A fold shows the same block by venue.
- Operations. Name, due date, and state for tasks that are upcoming or overdue.
- System Health. Mode (`dry_run` or `live`), whether new orders are allowed, whether the aggregate is available, whether ingest is current, and the time of the latest alert.
- PnL. Realized result for the day, the week, the month, and the year. A fold shows the same periods by venue.
- Strategy Summary. For each strategy with at least one close: name, venue, realized result, volume, profit factor, count, and win rate.
- PnL・Vol. A link to Analytics at PnL・Vol. Days are cut in UTC, the same as PnL.

This document does not publish those figures. An empty aggregate leaves Today, Risk Summary, PnL, Strategy Summary, and PnL・Vol off the page. System Health and Operations remain.

Navigation. Risk Summary opens Trading at Positions. Operations opens the Schedule. Strategy Summary opens Analytics at Strategies. PnL・Vol opens Analytics at PnL・Vol.

## Trading

Purpose. Read the account at the venues you connected.

What the user can learn. What is open, what has filled, which orders are still resting, and what balances are available.

Key components.

- Positions
- Trades
- Open Orders
- Balances

The switch starts on Positions.

Displayed information.

- Positions. Count of open positions and unrealized result. Each row is one strategy and symbol: unrealized result, hold time, remaining quantity, venue, open time, and last price. Rows with no price sit at the end.
- Trades. Fills already booked: time, strategy, venue, symbol, side, quote received, quote spent, and quantity. The summary counts today's fills and unclassified rows.
- Open Orders. Orders still open when the screen was opened: remaining quantity, age, strategy, symbol, side, price, order type, and original quantity. The screen says the list is not stored. Spot counts buys and sells. Futures counts shorts and covers. Arcus and Lighter count longs and shorts. The grid lists only venue ids with `enabled: true`.
- Balances. For each currency: total, available, and amount locked in orders. The summary reads the USDT total, what is available, what is in orders, and how many coins are listed. Arcus and Lighter show equity, available balance, margin, and the open-position count. Lighter's amounts use its quote.

A venue the screen cannot read shows that the read failed. The screen does not invent a zero.

Navigation. The four switches stay inside Trading. Dashboard, Analytics, and Operations remain in the outer navigation.

## Analytics

Purpose. Read the realized result and volume over time, read the run by strategy, and set the live run next to figures you stored.

What the user can learn. How the result and volume move by hour, day, and month, which strategies have activity, and how the live run sits beside the stored reference. The screen does not judge the strategy.

Key components.

- PnL・Vol
- Strategies
- Backtest Comparison

The switch starts on PnL・Vol. A strategy with no closed trades is omitted from Strategies.

Displayed information.

- PnL・Vol. The header shows the Signal Nexus mark beside SIGNAL NEXUS, QUANT ENGINE, and "Automated Strategy P&L & Volume Analytics".
  - Period. Daily is the last 24 hours by hour. Weekly is the last 7 days by day. Both are rolling windows, not the UTC day and ISO week of Dashboard PnL. Monthly, the default, is one month by day. Annually is one year by month. Monthly and Annually move to the previous or next period and pick a year and month. A later period cannot be opened.
  - Unit. $ (USD) or % (ROI).
  - Filters. All Venues and each venue id with `enabled: true`, each marked CEX or DEX, and a strategy filter. Fills on a disabled venue are not counted.
  - Summary. Net P&L, Total Volume, Win Rate, Profit Factor, and Max Drawdown.
  - Chart. P&L bars and volume, with either a cumulative P&L line or a volume axis. Hovering a bar shows that period's values.
  - Below the chart. Monthly shows a calendar, and a day opens its closed trades. Annually shows one card per month, and a month opens Monthly. Daily and Weekly list closed trades, newest first, up to 100.
  - Days are cut in UTC, the same as Dashboard PnL.
  - ROI. Each fill's realized result is divided by the capital in `roi_basis.yml` for that fill's UTC date. Volume stays in USD. Without the file, the screen says the ROI basis is not set.
- Strategies. Summary of how many strategies are active, how many are profitable, total realized result, and average profit factor. Each row: realized result, volume, profit factor, profit rate, win rate, count, strategy name, and venue.
- Backtest Comparison. Count of compared strategies, live average profit factor, stored average profit factor, and the strategy with the largest gap. Each row places the live run beside the stored reference for profit rate, profit factor, win rate, and count, plus the stored period.

This document does not include those figures. The stored reference is data you kept. It is not a result published here.

Navigation. Dashboard's Strategy Summary opens this view at Strategies. Dashboard's PnL・Vol block opens it at PnL・Vol. Trading and Operations remain in the outer navigation.

## Operations

Purpose. See the work that is due, and the trail of what happened to each alert.

What the user can learn. Which tasks are coming up or late, and whether an alert was received, rejected, skipped, filled, failed, or dropped as a duplicate.

Key components.

- Schedule
- Audit Log

The switch starts on Schedule.

Displayed information.

- Schedule. Count of tasks, how many are upcoming, how many are overdue, and the next due date. Each row: task name, start date, due date, state, and days remaining. States are upcoming, overdue, active, and pending.
- Audit Log. Count of events, count of successes, count of failures, and the time of the latest failure. Each row: event type, reason, time, strategy, symbol, and the text of the notice. The labels on this screen are received, rejected, skipped, success, failed, and dropped. A planned order is not one of those labels. A protective exit has no received row. Latest Alert does not change. The reason shows `protective_exit stop=<stop_price> mark=<trigger_price>` or `protective_exit take_profit=<take_profit_price> mark=<trigger_price>`. The copy column keeps the existing Sent, Not configured, and 429 paused results.

The Audit Log is the time-ordered trail. Analytics summarizes the run. It does not replace this list.

Navigation. Dashboard's Operations block opens Schedule. Trading and Analytics remain in the outer navigation.
