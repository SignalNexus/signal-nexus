# Signal Nexus

## Signal Nexus とは

Signal Nexus は、TradingView のアラートを、自分の環境で運用するためのソフトウェアです。資金も、取引所の API キーも、第三者には渡しません。

アラートは戦略に割り当てられ、発注の計画になります。Analytics には、その運用の記録が残ります。あとから見返し、シグナルの動かし方を自分で直せます。次に何を変えるかは、自分で決めます。

資金は、使っている取引所の口座に残ります。API キーは、自分の環境に残ります。`EXECUTION_MODE` を設定しないあいだは、記録は残り、注文は出ません。この状態が `dry_run` です。投資助言ではありません。

## 構成

入口は TradingView のアラートです。Signal Nexus が受け取り、`config/strategies.yml` の戦略に割り当て、内容を確認し、発注の計画を作ります。Analytics は、Webhook の控えではありません。運用の記録として残り、あとから見返し、動かし方を直すために使います。`dry_run` では、注文は出ません。

```text
TradingView のアラート
        |
        v
Signal Nexus
        |
        +-- 戦略への割り当て
        +-- 発注の計画
        |
        v
Analytics の記録
        |
        v
見返し、運用を直す
```

## 前提

このファイルは、次がすでに揃っている前提で書かれています。インストール方法は書きません。

- Windows 11 Home
- Python 3.12（`py -3.12`）
- Git
- GitHub アカウント
- Render アカウント
- ログインできる Linux の VM

下のコマンドは Windows 11 Home で実行します。Analytics API は Linux の VM で動きます。

## クイックスタート

自分用に clone したこのリポジトリから始めます。書き換えてよいのは `config/` だけです。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:WEBHOOK_SECRET = "replace-me"
```

`EXECUTION_MODE` は設定しないでください。`WEBHOOK_SECRET` は、自分で決めた値にします。例の `replace-me` は、そのまま使わないでください。

`config/strategies.yml` を次の内容に置き換えます。

```yaml
btc_long_example:
  symbol: BTC/USDT
  size_quote: 10
  side: long
  venue: mexc_spot
```

`size_quote` は、USDT 建ての注文額です。Webhook の本文に金額は入れません。

同じ PowerShell で、次を起動します。

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Linux の VM では、同じコードを clone してから実行します。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m app.analytics.api
```

Analytics API はポート 8080 で待ち受けます。この確認では Postgres は使いません。

## Render への配置

自分の Render Web Service には、次を設定します。

- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- 環境変数: `WEBHOOK_SECRET` に、自分で決めた値を入れる。`EXECUTION_MODE` は入れない。

デプロイする `config/strategies.yml` には、クイックスタートで保存した `btc_long_example` を含めてください。URL のホスト名は、そのサービスに表示されたものを使います。このファイルには書きません。

## 確認

このファイルの完了は、次の三つです。

1. Render の `GET /health` が `{"status":"ok"}` になる。

```powershell
curl.exe -i https://<your-host>/health
```

2. Analytics API の `GET /health` が `{"status":"ok"}` になる。VM の中で実行します。

```bash
curl -i http://127.0.0.1:8080/health
```

3. `POST /webhook` が `{"status":"dry_run"}` になる。

```powershell
curl.exe -i -X POST https://<your-host>/webhook `
  -H "Content-Type: application/json" `
  -d "{\"secret\":\"replace-me\",\"strategy_id\":\"btc_long_example\",\"symbol\":\"BTC/USDT\",\"action\":\"BUY\",\"bar_time\":\"2026-10-15T00:00:00Z\",\"client_order_id\":\"btc_long_example_20261015000000_buy\"}"
```

`secret` は、設定した `WEBHOOK_SECRET` と同じ値にしてください。違う値は HTTP 401 で、本文は `{"detail":"unauthorized"}` です。本文に `size` または `size_quote` があると、HTTP 422 です。

health が示すのは、そのプロセスが応答したことだけです。Postgres、取引所、Discord、Importer は、この確認の対象外です。TradingView から実際にアラートを送ることも、対象外です。

## ドキュメント

Python 3.12 や Git のインストール、GitHub アカウント、Render アカウント、Render Web Service、Linux の VM、SSH 鍵の作り方は、Signal Nexus Buildbook にあります。VM を Oracle Cloud で作る場合の画面操作も、そこです。このファイルでは繰り返しません。
