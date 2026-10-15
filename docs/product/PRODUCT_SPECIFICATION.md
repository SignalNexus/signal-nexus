# Signal Nexus Product Specification

This document says what Signal Nexus provides. It does not say how to install tools, create accounts, or deploy.

## What is Signal Nexus?

Signal Nexus is a self-hosted workflow for operating TradingView alerts.

A TradingView alert is mapped to a strategy and turned into an execution plan. Analytics keeps a record of that operation. You review the record over time and decide how to run the signal next.

The webhook answers the alert. Analytics is the record you use for review and for the next change you make. It is not only a log of the request.

With `EXECUTION_MODE` unset, the record is kept and the order is not sent. That mode is `dry_run`. Setting `EXECUTION_MODE` to `live` sends orders. This document is not investment advice.

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

The portal is the screen on the same service as the webhook. It reads the operation. It does not place an order for you from the screen.

- Trading. Positions, trades, open orders, and balances.
- Analytics. Strategies and tickers for the run.
- Performance. The dashboard reads how the run is going. It is a view of your own operation.
- Backtest Comparison. The live run sits next to figures you chose to store. This document does not include those figures.

## Analytics

Analytics keeps the operation record: which strategy the alert used, whether a plan was made, and, when you send orders, what happened to the order.

You use that record to review the run over time and to decide the next change in how the signal is operated. The next change is yours.

## Discord Notifications

When `DISCORD_WEBHOOK_URL` is set, audit notifications can be delivered to Discord.

Discord can receive notice that a signal arrived, that it was rejected, that an order was not sent, that an order was planned, that an order succeeded or failed, and that a duplicate was discarded.

Discord is a delivery destination. A missed delivery does not remove the audit record.

## Audit Log

The audit record is stored in Postgres. The portal shows it as the Audit Log.

The record covers receipt, rejection, a skipped order, a planned order, success, failure, and a discarded duplicate. That is the record you review. Discord receives a copy when configured.

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
