# Signal Nexus

## What is Signal Nexus?

Signal Nexus is a self-hosted TradingView webhook execution framework.

- Self-hosted
- Dry-run by default
- TradingView integration
- Analytics API
- Venue keys remain under the operator's control
- Funds remain at the venue

Signal Nexus does not custody user funds.

## Architecture

```text
TradingView
    |
    v
Webhook API
    |
    v
Execution engine
    |
    v
Venue
    |
    v
Analytics API
```

TradingView calls the Webhook API. The execution engine plans the order, or sends it when you set `EXECUTION_MODE=live`. The Analytics API is a separate process.

## Quick Start

1. Install dependencies. See [1. Install](#1-install).
2. Set `WEBHOOK_SECRET`. See [1. Install](#1-install).
3. Start the webhook process. See [2. Webhook process](#2-webhook-process).
4. Call `/health`. See [2. Webhook process](#2-webhook-process).
5. Send the sample webhook. See [2. Webhook process](#2-webhook-process).

Expected result:

```json
{"status":"dry_run"}
```

Signal Nexus receives a TradingView webhook. With `EXECUTION_MODE` unset, the process plans the order and does not send it. That mode is `dry_run`.

Your funds stay at the venue. Your keys stay on your infrastructure. This procedure does not operate your account.

The checks below are complete when both health endpoints return `{"status":"ok"}` and `POST /webhook` returns `{"status":"dry_run"}`. Each health check shows only that its process answered. Postgres, a venue, Discord, and the importer are outside these checks.

You follow this file on Windows 11 Home. The Analytics API runs on a VM you start. That VM is the process host, not a second desktop.

## Files you edit

Edit `config/` only.

| File | Purpose |
| --- | --- |
| `config/venues.yml` | Venues that are enabled |
| `config/strategies.yml` | Strategy id, symbol, and `size_quote` |
| `config/strategy_results.yml` | Backtest figures you choose to store |
| `config/month_target.yml` | `month_target_usdt` |
| `config/ops_schedule.yml` | Task name, start date, and due date |

`config/strategy_results.yml` is not part of the checks below.

## 1. Install

Install Python 3.12. In PowerShell, from a clone of this repository:

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

## 2. Webhook process

In the same PowerShell window:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In a second PowerShell window, from the same clone:

```powershell
curl.exe -i http://127.0.0.1:8000/health
```

Expect HTTP 200 and `{"status":"ok"}`.

```powershell
curl.exe -i -X POST http://127.0.0.1:8000/webhook `
  -H "Content-Type: application/json" `
  -d "{\"secret\":\"replace-me\",\"strategy_id\":\"btc_long_example\",\"symbol\":\"BTC/USDT\",\"action\":\"BUY\",\"bar_time\":\"2026-10-15T00:00:00Z\",\"client_order_id\":\"btc_long_example_20261015000000_buy\"}"
```

Use the same secret you set in `WEBHOOK_SECRET`. Expect HTTP 200 and `{"status":"dry_run"}`.

A different `secret` returns HTTP 401 and `{"detail":"unauthorized"}`. A body that contains `size` or `size_quote` returns HTTP 422.

Stop the process with Ctrl+C when you are finished with this local check.

## 3. Your Render service

Create your own Render Web Service from your copy of this repository. The hostname belongs to your service. This file does not name one.

- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Environment: set `WEBHOOK_SECRET` to your secret. Leave `EXECUTION_MODE` unset for this check.

The deployed `config/strategies.yml` must contain `btc_long_example`, as saved in step 1.

Open `https://<your-host>/health`. Expect `{"status":"ok"}`.

Post the same JSON as in step 2 to `https://<your-host>/webhook`. Expect `{"status":"dry_run"}`.

Point a TradingView alert at `https://<your-host>/webhook`. An alert sent from TradingView is not one of the checks above.

## 4. Analytics API

On the VM you start, clone this repository, create a virtual environment, and install `requirements.txt` the same way. Then:

```bash
python -m app.analytics.api
```

The process listens on port 8080. On that VM:

```bash
curl -i http://127.0.0.1:8080/health
```

Expect HTTP 200 and `{"status":"ok"}`. This check does not open Postgres.

## Disclaimer

Signal Nexus is software.

It is not investment advice.

Use at your own risk.

The authors are not responsible for trading losses, exchange failures, or configuration mistakes.

Users are responsible for securing their infrastructure, API keys, and venue accounts.
