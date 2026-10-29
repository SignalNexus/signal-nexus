# Signal Nexus 戦略の接続手順

文書の役割は [../DOCUMENTATION_STRUCTURE_JA.md](../DOCUMENTATION_STRUCTURE_JA.md) にあります。

この文書は、TradingView 接続の正本です。英語版 [STRATEGY_INTEGRATION_GUIDE.md](STRATEGY_INTEGRATION_GUIDE.md) が原文です。

アラートを作る前に、Buildbook の確認を終わらせます。`EXECUTION_MODE` を入れていないあいだは、一致したアラートは `dry_run` として残り、注文は出ません。

## 範囲

この文書が説明すること:

- `strategy_id` の対応
- TradingView のアラート
- Webhook の本文
- Signal Nexus への接続

この文書が説明しないこと:

- シグナルのロジック
- インジケーターの設計
- 戦略のリサーチ
- 売買のルール

Platform is Public. 下の本文の契約は、プラットフォーム側です。Research is Private. シグナルをどう見つけ、どう順位を付けるかは、この文書の外です。

## 1. 役割

いつアラートを出すかは TradingView が決めます。そのアラートがどの戦略で、いくら注文するかは Signal Nexus が決めます。

つなぎ目は `strategy_id` です。`config/strategies.yml` のキーと、アラート JSON の `strategy_id` を同じにします。アラートの `symbol` は、その行のシンボルと揃えます。

```yaml
btc_long_example:
  symbol: BTC/USDT
  size_quote: 10
  side: long
  venue: mexc_spot
```

`size_quote` は USDT 建ての注文額です。`side` は `long` または `short` です。`venue` は `mexc_spot`、`mexc_futures`、`arcus` です。`short` の行は、現物には置けません。

## 2. Pine Script

Webhook の秘密は、TradingView の入力欄に入れます。値をリポジトリにコミットしません。

Signal Nexus から見て、スクリプトがすることは JSON を一つ出すことです。いつ出すかは、自分のスクリプトの条件です。この文書はその条件を渡しません。

### 2.1 例だけ

下の例は、Signal Nexus が受け取る本文の形だけを示すものです。

売買の戦略ではありません。

シグナルをどう出すかは、この文書の外です。

`btc_long_example` は、構築手順にある確認用の行です。Starter の特典でも、Profit Pack でも、Volume Pack でも、リサーチでもありません。確認を終えたら、id とシンボルを自分の行に置き換えます。

```pine
//@version=6
strategy("btc_long_example", overlay=true)
secret = input.string("", "Webhook secret", group="Signal Nexus")
barTime = str.format_time(time, "yyyy-MM-dd'T'HH:mm:ss'Z'", "UTC")
payload(action) =>
    '{"secret":"' + secret + '","strategy_id":"btc_long_example","symbol":"BTC/USDT","action":"' + action + '","bar_time":"' + barTime + '","client_order_id":"btc_long_example_' + barTime + '_' + action + '"}'
// 自分の条件から、secret が入っているときだけ:
// alert(payload("BUY"), alert.freq_once_per_bar_close)
```

`symbol` と一致するチャートにスクリプトを足します。アラートは、strategy の「Any alert() function call」で作ります。Webhook を開き、URL を `https://<your-host>/webhook` にします。

## 3. アラートの本文

本文は JSON です。次は必須です。

| 欄 | 意味 |
| --- | --- |
| `secret` | Render の `WEBHOOK_SECRET` と同じ文字列 |
| `strategy_id` | `config/strategies.yml` のキー |
| `symbol` | その行の `symbol`。例は `BTC/USDT` |
| `action` | 次の節のアクション |
| `bar_time` | サーバ時刻との差が `MAX_BAR_AGE_SECONDS` 以内の ISO-8601。既定は 300 秒で、現在より前も後も同じです |
| `client_order_id` | その一回の id。同じ id の再送は破棄される |

`exit_bar_close` は任意で、`SELL` または `STOP` のときだけです。こちらも ISO-8601 の時刻です。

`size` と `size_quote` は送りません。HTTP 422 で拒否されます。金額は戦略の行の `size_quote` に残します。

### アクション

| 行 | 受け付けるアクション |
| --- | --- |
| `side: long` で現物 | `BUY`、`SELL`、`STOP` |
| `side: long` で先物 | `LONG`、`FLAT` |
| `side: short` で先物 | `SHORT`、`COVER` |

それ以外のアクションは、その行では拒否されます。同じ取引所の同じシンボルに、long の行と short の行を同時には置けません。

保護決済は、TradingView のアラートが足の確定時にだけ評価されるため、その間の急な価格変化への対応を補うための付加機能です。Signal Nexus は、戦略ごとにストップ 価格1 つと利食い価格 1 つを持ちます。価格は、その戦略の最新エントリー約定に loss_pct と profit_pct を掛けて決めます。仮想マシンが 5 秒ごとに新しい公開価格を見て、先に割れた方で、その戦略の残数量全体を成行で閉じます。アラートの代わりではなく、次の足のアラートが来るまでに想定外の損失を防ぐ、もしくは利益の確保を行うための保護です。`config/protective_exit.yml` と戦略行の任意の設定で、アラートには載せません。`STOP` は現物の決済アクションのままで、ストップ価格も利食い価格も決めません。保護決済はアラートから始まりません。`SIGNAL RECEIVED` は作りません。その後の TradingView の決済は、別のアラートのままです。

## 4. 秘密の使われ方

### `WEBHOOK_SECRET`

役割は、Webhook の確認です。

TradingView では、アラート JSON の `secret` に値を入れます。TradingView は認証ヘッダを足しません。Webhook URL は `https://<your-host>/webhook` です。

Signal Nexus では、`POST /webhook` がその欄を、Render の環境変数 `WEBHOOK_SECRET` と比べます。違う値は HTTP 401 で、本文は `{"detail":"unauthorized"}` です。

## 5. 一致したアラートのあと

1. secret が一致する。
2. `strategy_id` と `symbol` で行が一つ決まる。
3. `action` が、その行の side と venue で許可されている。
4. その venue で、`client_order_id` がまだ使われていない。
5. `EXECUTION_MODE` が未設定なら、応答は `{"status":"dry_run"}` です。注文は出ません。
6. `EXECUTION_MODE=live` のとき、`venue` へ `size_quote` USDT の注文を出します。

拒否されたアラートは HTTP 422 で、注文は出ません。これは検証のエラーです。本文か戦略の行を直し、`client_order_id` を新しい値にして送ります。

同じ `client_order_id` の再送は、検証のエラーではありません。HTTP 200 と `{"status":"duplicate"}` を返し、注文は出ません。
