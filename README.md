# Signal Nexus

## What is Signal Nexus?

Signal Nexus helps traders operate a self-hosted TradingView automation workflow, without handing funds or exchange API keys to a third party.

A TradingView alert is mapped to a strategy and turned into an execution plan. Analytics keeps a record of that operation, so you can review it over time and improve how the signal is run. You choose the next change.

Your funds stay at your exchange. Your keys stay on your infrastructure. With `EXECUTION_MODE` unset, the record is kept and the order is not sent. That mode is `dry_run`. It is not investment advice.

## Architecture

A TradingView alert enters Signal Nexus. It is mapped to a strategy in `config/strategies.yml`, checked, and turned into an execution plan. Analytics keeps that record so the operation can be reviewed and improved later. It is not only a log of the webhook. In `dry_run`, the order is not sent.

```text
TradingView alert
        |
        v
Signal Nexus
        |
        +-- strategy mapping
        +-- execution planning
        |
        v
Analytics record
        |
        v
Review and improve
```

## Capabilities

- TradingView webhook intake
- Strategy mapping
- Execution planning
- Analytics records you can review and improve from
- Discord audit notifications
- Self-hosted deployment

## Supported Venues

Current:

- MEXC Spot
- MEXC Futures
- Arcus

Planned:

- Hyperliquid
- Paradex
- GRVT

A planned venue is not an order path yet.

## Environment Variables

These names belong to this repository. This file does not say how to create the values.

| Variable | Required | Purpose |
| --- | --- | --- |
| `WEBHOOK_SECRET` | Required | Authenticate webhook requests |
| `DISCORD_WEBHOOK_URL` | Recommended | Deliver audit notifications to Discord |
| `EXECUTION_MODE` | Optional | Unset means `dry_run`. `live` sends orders |

## Notifications

Audit notifications can be delivered to Discord through `DISCORD_WEBHOOK_URL`. Discord is a delivery destination. The audit record itself stays in Postgres.

## Prerequisites

This file assumes the following already exist. It does not install them.

- Windows 11 Home
- Python 3.12 (`py -3.12`)
- Git
- GitHub account
- Render account
- A Linux VM with a shell

You run the commands below on Windows 11 Home. The Analytics API runs on the Linux VM.

## Quick Start

Start from a clone of your copy of this repository. Edit `config/` only.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:WEBHOOK_SECRET = "replace-me"
```

Leave `EXECUTION_MODE` unset. Choose your own `WEBHOOK_SECRET`. Do not reuse the placeholder.

Replace `config/strategies.yml` with:

```yaml
btc_long_example:
  symbol: BTC/USDT
  size_quote: 10
  side: long
  venue: mexc_spot
```

`size_quote` is the order amount in USDT. The webhook body does not carry an amount.

In the same PowerShell window:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

On the Linux VM, from a clone of the same code:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m app.analytics.api
```

The Analytics API listens on port 8080. This process does not open Postgres.

## Render Deployment

On your Render Web Service, use:

- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Environment: set `WEBHOOK_SECRET` to your secret. Leave `EXECUTION_MODE` unset.

The deployed `config/strategies.yml` must contain `btc_long_example`, as saved in Quick Start. The hostname belongs to your service. This file does not name one.

## Validation

These three results are the end of this file.

1. Render `GET /health` returns `{"status":"ok"}`.

```powershell
curl.exe -i https://<your-host>/health
```

2. Analytics API `GET /health` returns `{"status":"ok"}`. On the VM:

```bash
curl -i http://127.0.0.1:8080/health
```

3. `POST /webhook` returns `{"status":"dry_run"}`.

```powershell
curl.exe -i -X POST https://<your-host>/webhook `
  -H "Content-Type: application/json" `
  -d "{\"secret\":\"replace-me\",\"strategy_id\":\"btc_long_example\",\"symbol\":\"BTC/USDT\",\"action\":\"BUY\",\"bar_time\":\"2026-10-15T00:00:00Z\",\"client_order_id\":\"btc_long_example_20261015000000_buy\"}"
```

Use the same secret as `WEBHOOK_SECRET`. A different secret returns HTTP 401 and `{"detail":"unauthorized"}`. A body that contains `size` or `size_quote` returns HTTP 422.

Each health check shows only that its process answered. Postgres, a venue, Discord, and the importer are outside these checks. An alert sent from TradingView is not one of them.

## Learn More

For the portal, what analytics shows, which audits are kept, the public and private boundary, and the product names, see [docs/product/PRODUCT_SPECIFICATION.md](docs/product/PRODUCT_SPECIFICATION.md).

Installing Python, Git, GitHub, Render, a Linux VM, or SSH is in the Signal Nexus Buildbook. This file does not repeat those steps.
