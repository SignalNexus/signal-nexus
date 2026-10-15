# Signal Nexus

Signal Nexus は TradingView の Webhook を受けます。`EXECUTION_MODE` を未設定にすると、プロセスは注文を予定し、送りません。このモードは `dry_run` です。

資金は会場の口座に残します。鍵は自分のインフラに置きます。この手順は、あなたの口座を運用しません。

下の確認が終わるのは、二つの health が `{"status":"ok"}` を返し、`POST /webhook` が `{"status":"dry_run"}` を返したときです。各 health が見るのは、そのプロセスが応答することだけです。Postgres、会場、Discord、Importer は、この確認に含めません。

このファイルに従う人の環境は Windows 11 Home です。Analytics API は、あなたが起動する VM で動きます。その VM は処理を動かす先であり、もう一台のデスクトップではありません。

英語版は `README.md` です。手順は同じです。

## 編集するファイル

編集するのは `config/` です。

| ファイル | 用途 |
| --- | --- |
| `config/venues.yml` | 有効にする会場 |
| `config/strategies.yml` | 戦略 ID、銘柄、`size_quote` |
| `config/strategy_results.yml` | 自分で残すバックテストの数値 |
| `config/month_target.yml` | `month_target_usdt` |
| `config/ops_schedule.yml` | 作業名、開始日、期限 |

`config/strategy_results.yml` は、下の確認には使いません。

## 1. インストール

Python 3.12 を入れます。PowerShell で、このリポジトリのクローンに移動します。

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

## 2. Webhook のプロセス

同じ PowerShell で起動します。

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

もう一つの PowerShell で、同じクローンから確認します。

```powershell
curl.exe -i http://127.0.0.1:8000/health
```

期待するのは HTTP 200 と `{"status":"ok"}` です。

```powershell
curl.exe -i -X POST http://127.0.0.1:8000/webhook `
  -H "Content-Type: application/json" `
  -d "{\"secret\":\"replace-me\",\"strategy_id\":\"btc_long_example\",\"symbol\":\"BTC/USDT\",\"action\":\"BUY\",\"bar_time\":\"2026-10-15T00:00:00Z\",\"client_order_id\":\"btc_long_example_20261015000000_buy\"}"
```

`secret` は、設定した `WEBHOOK_SECRET` と同じ値にします。期待するのは HTTP 200 と `{"status":"dry_run"}` です。

違う `secret` は HTTP 401 と `{"detail":"unauthorized"}` です。`size` または `size_quote` を含む body は HTTP 422 です。

このローカル確認が終わったら、Ctrl+C でプロセスを止めます。

## 3. 自分の Render

このリポジトリの自分のコピーから、自分の Render Web Service を作ります。ホスト名はそのサービスのものであり、このファイルには書きません。

- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- 環境変数: `WEBHOOK_SECRET` に自分の値を置く。この確認では `EXECUTION_MODE` は設定しない。

デプロイする `config/strategies.yml` には、手順 1 で保存した `btc_long_example` が必要です。

`https://<your-host>/health` を開きます。期待するのは `{"status":"ok"}` です。

手順 2 と同じ JSON を `https://<your-host>/webhook` へ送ります。期待するのは `{"status":"dry_run"}` です。

TradingView のアラートの向き先は `https://<your-host>/webhook` です。TradingView からアラートを送ったことは、上の確認に含めません。

## 4. Analytics API

起動する VM でこのリポジトリをクローンし、同じように仮想環境を作り、`requirements.txt` を入れます。そのあと次を実行します。

```bash
python -m app.analytics.api
```

プロセスはポート 8080 で待ちます。その VM で確認します。

```bash
curl -i http://127.0.0.1:8080/health
```

期待するのは HTTP 200 と `{"status":"ok"}` です。この確認は Postgres を開きません。
