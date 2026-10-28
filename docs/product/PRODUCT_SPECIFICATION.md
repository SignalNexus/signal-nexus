# Signal Nexus Product Specification

For documentation structure and responsibilities, see [../DOCUMENTATION_STRUCTURE.md](../DOCUMENTATION_STRUCTURE.md).

This document describes the product and its value proposition. The Japanese edition is [PRODUCT_SPECIFICATION_JA.md](PRODUCT_SPECIFICATION_JA.md).

## Where the parts run

Deployment topology is defined in Architecture.

In the reference environment, Render receives alerts. Oracle Cloud is the reference place for the virtual machine. Equivalent infrastructure may also be used.

The VM stores records and performs exchange-facing operations.

Discord receives audit copies.

## What is Signal Nexus?

Signal Nexus is the product you run on your own infrastructure to operate TradingView alerts. After an alert arrives, you get four things.

- Trading. The portal shows positions, fills, open orders, and balances at the venues you connected. The screen reads the account. It does not send an order.
- Operational record. The alert is kept as a record of the strategy it used, the plan that was made, and, when you send orders, what the venue did. This is the record. The Analytics screen is a view of it.
- Audit trail. What happened to that alert is kept when the virtual machine is connected. Discord can deliver a copy. A missed delivery does not remove the trail.
- Review. You read Trading, the operational record, and the audit trail, check what the signal did, and decide the next change in how it is run.

With `EXECUTION_MODE` unset, the order is not sent. That mode is `dry_run`. `live` sends orders. The records are kept in either case. This document is not investment advice.

## Product Philosophy

Your funds, your keys, your infrastructure.

Funds stay at your exchange. Exchange API keys stay on infrastructure you run. Signal Nexus does not custody assets. Signal Nexus does not hold either.

## Supported Venues

Current supported execution venues:

- MEXC Spot
- MEXC Futures
- Arcus

## Portal

The portal reads your operation. Nothing on the screen places an order. It has four areas: Dashboard, Trading, Analytics, and Operations. Analytics here is the screen, not the operational record. What each screen shows is the Screen Specification. How they connect is the Screen Relationship Diagram.

### Trading

- Positions. Open positions on the connected venues.
- Trades. Fills already booked.
- Orders. Orders still open at the venue.
- Balances. Balances read from the venue.

### Analytics

- Strategy records. Strategies lists each strategy that has activity in the run.
- Symbol activity. Tickers lists the same run by symbol.
- Operational history. The time-ordered trail of each alert is the audit trail, shown as the Audit Log under Operations. The Analytics screen summarizes the run. It does not replace that trail. The labels on that screen are defined in the Screen Specification.

### Performance

Performance is the Dashboard.

- Summary metrics. Where the run stands today, the risk in open positions, and whether alerts are arriving.
- Historical views. The same run by day, week, month, and year.

The Dashboard reads your own operation. This document does not publish results.

### Backtest Comparison

Backtest Comparison is a view under Analytics.

- Stored reference data. Figures you stored for a strategy. This document does not include them.
- Live vs stored comparison. The live run for that strategy is shown beside the stored figures. The screen does not judge the strategy.

## Operational record

The operational record is what you keep so you can review the run, check it, and change how the signal is run. It is written when `ANALYTICS_API_URL` and `ANALYTICS_API_SECRET` are set. Without them, the webhook can still answer and the record is not stored. The Analytics screen is one view of that record. It is not the record itself.

Review. You look back at which strategy an alert used, whether a plan was made, and, when orders are sent, what happened to the order.

Validate. You check the audit trail for that alert. The check is yours. It is not a statement about how the signal performed. The labels on the Audit Log screen are defined in the Screen Specification.

Improve. You decide the next change in how the signal is run. Signal Nexus keeps the record. It does not choose the change.

The record is not only a copy of the webhook request.

## Discord Notifications

When `DISCORD_WEBHOOK_URL` is set on Render, Discord receives a copy of these audit events. Discord is a delivery destination. The row stays in Postgres on the virtual machine. A missed delivery does not remove the audit. These notices are outside the checks in the README.

- Signal received. The alert arrived and was mapped to a strategy.
- Rejected. The alert failed validation.
- Not sent. The order was left unsent.
- Sell resend skipped. A repeated sell was not sent again.
- Planned. An order was planned. In `dry_run`, this is as far as the order goes.
- Succeeded. The venue accepted the order.
- Failed. The order did not go through.
- Duplicate discarded. The same alert was dropped.

## Audit trail

An audit trail exists for each alert when the virtual machine is connected. The portal shows it as the Audit Log, under Operations. Discord can deliver a copy when `DISCORD_WEBHOOK_URL` is set. A missed delivery does not remove the trail.

A protective exit is an added function that covers sharp price changes between bars, because a TradingView alert is evaluated only when a bar closes. Signal Nexus keeps one stop price and one take-profit price for each strategy. Those prices are set by applying `loss_pct` and `profit_pct` to that strategy's latest entry fill. Every five seconds, the virtual machine reads a fresh public price and closes that strategy's entire remaining quantity with a market order at the first level the price crosses. It does not replace the alert. It limits an unexpected loss, or secures a profit, until the next bar's alert arrives. The exit does not create a `SIGNAL RECEIVED` record. It reuses the existing audit events and remains visible in the Audit Log. Discord receives the same exit copy when Render delivers it.

What the Audit Log screen labels are, and which notices appear there, is defined in the Screen Specification.

## Public vs Private

Platform is Public. The public repository contains the webhook, execution, analytics, portal, and deploy files you run yourself.

Research is Private. How a strategy was found, ranked, or left unpublished is not part of this product description and is not in the public repository.

## Product Lineup

Names only. This document does not set a price. Which product to read, and which regional sales page to open, is [Product Catalog](PRODUCT_CATALOG.md).

- Free. The public platform. You deploy it yourself.
- Starter. The same platform, plus the Buildbook that prepares a new machine and the operator guidance in that playbook. It is not a second program. It does not include a support contract.
- Profit Pack. A research package. The purchase-day snapshot studies net result. Figures are not in this document. Nothing here promises results.
- Volume Pack. A research package. The purchase-day snapshot studies activity and venue participation. Figures are not in this document. Nothing here promises results.
- Complete. Starter together with the two purchase-day packs. It does not add a separate support contract. It is not a higher edition of either pack.
- VenueAdd. The extension for one venue that is not in the public release, after that venue is enabled and documented. Maintenance of that venue stays with the purchaser. It is not a dated research edition. It is not a right to every later venue.
