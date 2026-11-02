# デプロイの準備

原文は英語版 [DEPLOYMENT_READINESS.md](DEPLOYMENT_READINESS.md) です。

この章は、`workflow_dispatch` の直前の公開チェックリストと、そのあとの成功確認です。正本は [Community Deployment Guide](../COMMUNITY_DEPLOYMENT_GUIDE_JA.md) の第 8 節から第 12 節です。この章は、必須の事実を足しません。

## 1. 最初の dispatch の前

すべての行が真である必要があります。

| 確認 | 必要 |
| --- | --- |
| SHA 3つ | 一致。ガイドの最小 SHA 以上 |
| runtime 7ファイル | あり、中身があり、`confirm` が受け入れる |
| Manifest | `venues: []` |
| Linux ホスト | `ubuntu`、`sudo -n`、TCP 22 と 443 |
| Render | Live。`GET /health` が `{"status":"ok"}` |
| 9つの secret | この呼び出し元に設定済み |
| パスと会場の variable 4つ | 設定済み。`BUILTIN_VENUES` が決まっている |
| `DEPLOY_ANALYTICS` | 最後に `true` |
| `VENUEADD_READ_TOKEN` | manifest が空のあいだは未設定 |
| 追加の会場 secret | `BUILTIN_VENUES` がその会場を名前で示すときだけ |

`none` と空文字は、組み込みの空集合です。futures read は、`BUILTIN_VENUES` に `mexc_futures` が含まれるときだけ実行します。

## 2. 最初の dispatch

GitHub で Actions を開き、`deploy` という名前の workflow を開き、`workflow_dispatch` で 1 回実行します。

deploy は、欠けていれば PostgreSQL を入れ、`signalnexus` を作り、7ファイルをコピーし、Analytics API を再起動します。`venues: []` のときは、会場リポジトリを取得しません。

## 3. 成功

次のすべてが満たされたときだけ、この deploy は成功です。

| 確認 | 期待 |
| --- | --- |
| Render `GET /health` | `{"status":"ok"}` |
| Analytics `GET https://<CADDY_SITE_ADDRESS>/health` | `{"status":"ok"}` |
| config の SHA256 7つ | 呼び出し元のファイル、deploy log、`ANALYTICS_CORE_DIRECTORY/config/` のコピーが一致 |
| `SIGNAL_NEXUS_VENUEADD` | manifest が空のあいだは未設定 |
| 会場の取得 | log が会場リポジトリを名前で示さない |
| Futures read | `BUILTIN_VENUES=none` のとき、log に `futures read credentials are not configured` がない |

7つの live パスに対して `sha256sum` で計算します。

この節の確認をすべて通した deploy が、成功した deploy です。その公開コア SHA が、この環境の推奨 SHA になります。

## 4. あとの deploy

7ファイル、SHA 3つ、または Render の環境変数を変えたとき、同じ workflow を実行します。`DEPLOY_ANALYTICS` は `true` のままです。始める前に、Render の `GET /health` はまだ `{"status":"ok"}` です。第 3 節を繰り返します。あとの成功は推奨 SHA を置き換えます。失敗は置き換えません。

失敗は [ロールバック](ROLLBACK_JA.md) です。
