# Signal Nexus

## What is Signal Nexus?

Signal Nexus exists so a TradingView alert can become an order plan you keep, without handing your funds or exchange API keys to a third party.

After deployment, that path runs on infrastructure you operate. The webhook answers the alert. Analytics keeps what the alert became, so you can run and review it instead of losing it in the alert log.

Your funds stay at the venue. Your keys stay on your infrastructure. With `EXECUTION_MODE` unset, the plan is kept and the order is not sent. That mode is `dry_run`. It is not investment advice.

## Architecture

A TradingView alert is the entrance. Signal Nexus receives it, resolves `strategy_id` from `config/strategies.yml`, checks the alert, and builds an execution plan. Analytics is not a second webhook. It stores that plan, so each alert stays a record you can operate and review. In `dry_run`, the order is not sent.

```text
TradingView alert
        |
        v
Webhook
        |
        +-- resolve strategy_id
        +-- check the alert
        +-- execution plan
        |
        v
Analytics API
        |
        v
What the alert became
```

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

## Documentation

How to install Python 3.12, Git, and how to create a GitHub account, a Render account, a Render Web Service, a Linux VM, and an SSH key are in the Signal Nexus Buildbook. Oracle Cloud console steps, if you use Oracle for the VM, are there too. This file does not repeat them.
