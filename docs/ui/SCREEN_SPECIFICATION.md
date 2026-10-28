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

Displayed information.

Some value labels are currently displayed in Japanese. The information described in this document corresponds to those labels.

- Today. Result for the month so far, month volume, month target, progress against that target, amount still required, and the month-end projection. A fold shows the same block by venue.
- Risk Summary. Count of open positions and unrealized result. A fold shows the same block by venue.
- Operations. Name, due date, and state for tasks that are upcoming or overdue.
- System Health. Mode (`dry_run` or `live`), whether new orders are allowed, whether the aggregate is available, whether ingest is current, and the time of the latest alert.
- PnL. Realized result for the day, the week, the month, and the year. A fold shows the same periods by venue.
- Strategy Summary. For each strategy with at least one close: name, venue, realized result, volume, profit factor, count, and win rate.

This document does not publish those figures. An empty aggregate leaves Today, Risk Summary, PnL, and Strategy Summary off the page. System Health and Operations remain.

Navigation. Risk Summary opens Trading at Positions. Operations opens the Schedule. Strategy Summary opens Analytics at Strategies.

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
- Open Orders. Orders still open when the screen was opened: remaining quantity, age, strategy, symbol, side, price, order type, and original quantity. The screen says the list is not stored. Spot counts buys and sells. Futures counts shorts and covers. Arcus counts longs and shorts.
- Balances. For each currency: total, available, and amount locked in orders. The summary reads the USDT total, what is available, what is in orders, and how many coins are listed.

A venue the screen cannot read shows that the read failed. The screen does not invent a zero.

Navigation. The four switches stay inside Trading. Dashboard, Analytics, and Operations remain in the outer navigation.

## Analytics

Purpose. Read the run by strategy and by symbol, and set the live run next to figures you stored.

What the user can learn. Which strategies and symbols have activity, and how the live run sits beside the stored reference. The screen does not judge the strategy.

Key components.

- Strategies
- Tickers
- Backtest Comparison

The switch starts on Strategies. A strategy or symbol with no closed trades is omitted.

Displayed information.

- Strategies. Summary of how many strategies are active, how many are profitable, total realized result, and average profit factor. Each row: realized result, volume, profit factor, profit rate, win rate, count, strategy name, and venue.
- Tickers. The same summary and columns, grouped by symbol. Venue is shown with the symbol.
- Backtest Comparison. Count of compared strategies, live average profit factor, stored average profit factor, and the strategy with the largest gap. Each row places the live run beside the stored reference for profit rate, profit factor, win rate, and count, plus the stored period.

This document does not include those figures. The stored reference is data you kept. It is not a result published here.

Navigation. Dashboard's Strategy Summary opens this view at Strategies. Trading and Operations remain in the outer navigation.

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
