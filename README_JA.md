# Signal Nexus

## Signal Nexus とは

Signal Nexus は、第三者へ資金や API キーの管理を委ねることなく、TradingView シグナルを自動化するための基盤です。自分で動かす Webhook の実行フレームワークです。

資金は会場に残ります。鍵は自分のインフラに残ります。`EXECUTION_MODE` を未設定にすると、注文を予定し、送りません。このモードは `dry_run` です。投資助言ではありません。

## 前提

このファイルは、次がすでにあるものとして書きます。導入手順は書きません。

- Windows 11 Home
- Python 3.12（`py -3.12`）
- Git
- GitHub アカウント
- Render アカウント
- シェルで入れる Linux VM

下のコマンドは Windows 11 Home で実行します。Analytics API は Linux VM で動きます。

## クイックスタート

自分のコピーとして clone したこのリポジトリから始めます。編集するのは `config/` だけです。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:WEBHOOK_SECRET = "replace-me"
```

`EXECUTION_MODE` は設定しません。`WEBHOOK_SECRET` は自分の値にします。プレースホルダは使わないでください。

`config/strategies.yml` を次の内容に置き換えます。

```yaml
btc_long_example:
  symbol: BTC/USDT
  size_quote: 10
  side: long
  venue: mexc_spot
```

`size_quote` は注文額で、単位は USDT です。Webhook の body に金額は載せません。

同じ PowerShell で起動します。

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Linux VM では、同じコードの clone から実行します。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m app.analytics.api
```

Analytics API はポート 8080 で待ちます。このプロセスは Postgres を開きません。

## Render への配置

自分の Render Web Service では、次を使います。

- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- 環境変数: `WEBHOOK_SECRET` に自分の値を置く。`EXECUTION_MODE` は設定しない。

デプロイする `config/strategies.yml` には、クイックスタートで保存した `btc_long_example` が必要です。ホスト名はそのサービスのものであり、このファイルには書きません。

## 確認

このファイルの終わりは、次の三つです。

1. Render の `GET /health` が `{"status":"ok"}` を返す。

```powershell
curl.exe -i https://<your-host>/health
```

2. Analytics API の `GET /health` が `{"status":"ok"}` を返す。VM 上で実行します。

```bash
curl -i http://127.0.0.1:8080/health
```

3. `POST /webhook` が `{"status":"dry_run"}` を返す。

```powershell
curl.exe -i -X POST https://<your-host>/webhook `
  -H "Content-Type: application/json" `
  -d "{\"secret\":\"replace-me\",\"strategy_id\":\"btc_long_example\",\"symbol\":\"BTC/USDT\",\"action\":\"BUY\",\"bar_time\":\"2026-10-15T00:00:00Z\",\"client_order_id\":\"btc_long_example_20261015000000_buy\"}"
```

`secret` は `WEBHOOK_SECRET` と同じ値にします。違う `secret` は HTTP 401 と `{"detail":"unauthorized"}` です。`size` または `size_quote` を含む body は HTTP 422 です。

各 health が見るのは、そのプロセスが応答することだけです。Postgres、会場、Discord、Importer は、この確認に含めません。TradingView からアラートを送ったことも、この確認に含めません。

## ドキュメント

Python 3.12 と Git の導入、GitHub アカウント、Render アカウント、Render Web Service、Linux VM、SSH 鍵の作り方は、Signal Nexus Buildbook にあります。VM に Oracle Cloud を使うときのコンソール手順も、そこにあります。このファイルはそれを繰り返しません。
