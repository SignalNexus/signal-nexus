# Signal Nexus Strategy Integration Guide

For documentation structure and responsibilities, see [../DOCUMENTATION_STRUCTURE.md](../DOCUMENTATION_STRUCTURE.md).

This document is the canonical TradingView connection guide. The Japanese edition is [STRATEGY_INTEGRATION_GUIDE_JA.md](STRATEGY_INTEGRATION_GUIDE_JA.md).

Finish the Buildbook validation before creating an alert. With `EXECUTION_MODE` unset, a matching alert is recorded as `dry_run` and the order is not sent.

## Scope

This guide explains:

- `strategy_id` mapping
- TradingView alerts
- webhook payloads
- Signal Nexus integration

This guide does not explain:

- signal logic
- indicator design
- strategy research
- trading rules

Platform is public. The payload contract below is part of the platform. Research is private. How a signal is found or ranked is outside this guide.

## 1. The two sides

TradingView decides when to alert. Signal Nexus decides which strategy that alert is, and the order size.

The link is `strategy_id`. The same id is the key in `config/strategies.yml` and the `strategy_id` field in the alert JSON. The alert's `symbol` must be the symbol on that row.

```yaml
btc_long_example:
  symbol: BTC/USDT
  size_quote: 10
  side: long
  venue: mexc_spot
```

`size_quote` is the order amount in USDT. `side` is `long` or `short`. `venue` is `mexc_spot`, `mexc_futures`, or `arcus`. A short row cannot use a spot venue.

## 2. Pine Script

Keep the webhook secret in a TradingView input. Do not commit the value.

The script's job, for Signal Nexus, is to emit one JSON object. The condition that emits it belongs to your script. This guide does not supply that condition.

### 2.1 Example Only

The example below demonstrates only how Signal Nexus expects a payload.

It is not a trading strategy.

Signal generation remains outside this guide.

`btc_long_example` is the validation row from the Buildbook. It is not a Starter benefit, a Profit Pack, a Volume Pack, or research. Replace the id and the symbol with your own row when you leave validation.

```pine
//@version=6
strategy("btc_long_example", overlay=true)
secret = input.string("", "Webhook secret", group="Signal Nexus")
barTime = str.format_time(time, "yyyy-MM-dd'T'HH:mm:ss'Z'", "UTC")
payload(action) =>
    '{"secret":"' + secret + '","strategy_id":"btc_long_example","symbol":"BTC/USDT","action":"' + action + '","bar_time":"' + barTime + '","client_order_id":"btc_long_example_' + barTime + '_' + action + '"}'
// From your own condition, when secret is non-empty:
// alert(payload("BUY"), alert.freq_once_per_bar_close)
```

Add the script to a chart whose symbol matches `symbol`. Create an alert on the strategy with "Any alert() function call". Open the webhook and set the URL to `https://<your-host>/webhook`.

## 3. Alert payload

The body is a JSON object. These fields are required.

| Field | Meaning |
| --- | --- |
| `secret` | The same string as Render `WEBHOOK_SECRET` |
| `strategy_id` | The key in `config/strategies.yml` |
| `symbol` | The `symbol` on that row, such as `BTC/USDT` |
| `action` | One of the actions in the next section |
| `bar_time` | ISO-8601 time, for example `2026-10-16T00:00:00Z` |
| `client_order_id` | An id for this attempt. A repeat of the same id is discarded |

`exit_bar_close` is optional, and only with `SELL` or `STOP`. It is also an ISO-8601 time.

Do not send `size` or `size_quote`. The request is rejected with HTTP 422. The amount stays in `size_quote` on the strategy row.

### Actions

| Row | Actions the deployment accepts |
| --- | --- |
| `side: long` and a spot venue | `BUY`, `SELL`, `STOP` |
| `side: long` and a futures venue | `LONG`, `FLAT` |
| `side: short` and a futures venue | `SHORT`, `COVER` |

Any other action for that row is rejected. One symbol on one venue cannot have both a long row and a short row.

A protective exit is an added function that covers sharp price changes between bars, because a TradingView alert is evaluated only when a bar closes. Signal Nexus keeps one stop price and one take-profit price for each strategy. Those prices are set by applying `loss_pct` and `profit_pct` to that strategy's latest entry fill. Every five seconds, the virtual machine reads a fresh public price and closes that strategy's entire remaining quantity with a market order at the first level the price crosses. It does not replace the alert. It limits an unexpected loss, or secures a profit, until the next bar's alert arrives. The setting is optional in `config/protective_exit.yml` and on the strategy row. The alert does not carry it. `STOP` remains the spot exit action. It does not set a stop price or a take-profit price. A protective exit creates no `SIGNAL RECEIVED` record. A later TradingView exit is still a separate alert.

## 4. How the secret is used

### `WEBHOOK_SECRET`

Purpose. Webhook authentication.

TradingView. The alert JSON field `secret` carries the value. TradingView does not add an authentication header. The webhook URL is `https://<your-host>/webhook`.

Signal Nexus. `POST /webhook` compares the field with the Render environment variable `WEBHOOK_SECRET`. A mismatch is HTTP 401 and `{"detail":"unauthorized"}`.

## 5. What a matching alert becomes

1. The secret matches.
2. `strategy_id` and `symbol` select one row.
3. `action` is legal for that row's side and venue.
4. `client_order_id` has not already been used for that venue.
5. The response is `{"status":"dry_run"}` while `EXECUTION_MODE` is unset. The order is not sent.
6. With `EXECUTION_MODE=live`, the order is sent to `venue` for `size_quote` USDT.

A rejected alert returns HTTP 422 and does not send an order. That is a validation error. Fix the payload or the strategy row, then send a new `client_order_id`.

A repeated `client_order_id` is not a validation error. It returns HTTP 200 and `{"status":"duplicate"}`, and no order is sent.
