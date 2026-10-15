# Signal Nexus Product Specification

This document says what Signal Nexus provides. It does not say how to install tools, create accounts, or deploy.

## What is Signal Nexus?

Signal Nexus is the product you run on your own infrastructure to operate TradingView alerts. After an alert arrives, you get four things.

- Trading. The portal shows positions, fills, open orders, and balances at the venues you connected. The screen reads the account. It does not send an order.
- Analytics. The alert is kept as a record of the strategy it used, the plan that was made, and, when you send orders, what the venue did.
- Audit. Postgres keeps what happened to that alert. Discord can deliver a copy. A missed delivery does not remove the record.
- Review. You read Trading, Analytics, and the audit, check what the signal did, and decide the next change in how it is run.

With `EXECUTION_MODE` unset, the order is not sent. That mode is `dry_run`. `live` sends orders. The records are kept in either case. This document is not investment advice.

## Product Philosophy

Your funds, your keys, your infrastructure.

Funds stay at your exchange. Exchange API keys stay on infrastructure you run. Signal Nexus does not hold either.

## Supported Venues

Current venues have an order path:

- MEXC Spot
- MEXC Futures
- Arcus

Planned venues are not an order path yet:

- Hyperliquid
- Paradex
- GRVT

## Portal

The portal is the screen on the same service as the webhook. It has four areas: Dashboard, Trading, Analytics, and Operations. It reads the operation. Nothing on the screen places an order.

### Trading

- Positions. Open positions on the connected venues.
- Trades. Fills already booked.
- Orders. Orders still open at the venue.
- Balances. Balances read from the venue.

### Analytics

- Strategy records. Strategies lists each strategy that has activity in the run.
- Symbol activity. Tickers lists the same run by symbol.
- Operational history. The time-ordered trail of each alert is the Audit Log, under Operations. The Analytics views summarize the run. They do not replace that trail.

### Performance

Performance is the Dashboard.

- Summary metrics. Where the run stands today, the risk in open positions, and whether alerts are arriving.
- Historical views. The same run by day, week, month, and year.

The Dashboard reads your own operation. This document does not publish results.

### Backtest Comparison

Backtest Comparison is a view under Analytics.

- Stored reference data. Figures you stored for a strategy. This document does not include them.
- Live vs stored comparison. The live run for that strategy is shown beside the stored figures. The screen does not judge the strategy.

## Analytics

Analytics keeps the operation so you can review it, check it, and change how the signal is run.

Review. You look back at which strategy an alert used, whether a plan was made, and, when orders are sent, what happened to the order.

Validate. You check the trail for that alert: received, rejected, left unsent, planned, succeeded, failed, or discarded as a duplicate. The check is yours. It is not a statement about how the signal performed.

Improve. You decide the next change in how the signal is run. Signal Nexus keeps the record. It does not choose the change.

The record is not only a copy of the webhook request.

## Discord Notifications

When `DISCORD_WEBHOOK_URL` is set, Discord receives a copy of these audit events. Discord is a delivery destination. A missed delivery does not remove the audit. These notices are outside the checks in the README.

- Signal received. The alert arrived and was mapped to a strategy.
- Rejected. The alert failed validation.
- Not sent. The order was left unsent.
- Sell resend skipped. A repeated sell was not sent again.
- Planned. An order was planned. In `dry_run`, this is as far as the order goes.
- Succeeded. The venue accepted the order.
- Failed. The order did not go through.
- Duplicate discarded. The same alert was dropped.

## Audit Log

The audit record is stored in Postgres. The portal shows it as the Audit Log, under Operations.

Postgres keeps receipt, rejection, an order left unsent, a skipped sell resend, a planned order, success, failure, and a discarded duplicate.

The screen uses six labels: received, rejected, skipped, success, failed, and dropped. A planned order is stored, and Discord can deliver it. Planned is not one of those six labels.

That stored trail is what you review. Discord receives a copy when `DISCORD_WEBHOOK_URL` is set.

## Public vs Private

Platform is Public. The public repository contains the webhook, execution, analytics, portal, and deploy files you run yourself.

Research is Private. How a strategy was found, ranked, or left unpublished is not part of this product description and is not in the public repository.

## Product Lineup

Names only. This document does not set a price.

- Free. The public platform. You deploy it yourself.
- Starter. The same platform, plus the Buildbook that prepares a new machine, and a place to ask questions. It is not a second program.
- Profit Pack. A purchase-day set of strategies read for net result. Results are not in this document.
- Volume Pack. A purchase-day set of strategies read for activity you choose to continue. Results are not in this document.
- Complete. Starter together with the two purchase-day packs. It does not add a separate support contract.
- Alpha. Later venue adapters that are not in the public platform, after that venue is enabled and documented.
- Beta. Alpha, plus later updates of the strategy packs during the membership. How strategies are chosen is not included.
