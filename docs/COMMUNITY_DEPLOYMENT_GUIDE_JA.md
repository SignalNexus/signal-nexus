# Community Deployment Guide

英語版が正本です。日本語版は [COMMUNITY_DEPLOYMENT_GUIDE.md](COMMUNITY_DEPLOYMENT_GUIDE.md) の写しです。

このガイドは、Signal Nexus Community Edition を health の確認まで配備する公開の正本です。技術のある運用者は、`SignalNexus/signal-nexus` と `SignalNexus/signal-nexus-deploy` だけで従えます。

[README](../README_JA.md) は入口です。[Architecture](architecture/ARCHITECTURE_JA.md) は参照です。Starter に含まれる Buildbook は長い形です。詳細、チェックリスト、画面、FAQ、失敗のメモを足します。必須の事実は足しません。

## 1. Deployment の構造

```text
TradingView alert
        |
        v
Render Webhook Service
        |
        | ANALYTICS_API_URL
        v
Analytics API on the Linux host
        |
        v
PostgreSQL on localhost

VenueAdd packages load beside the Analytics API only when the manifest names them.
An empty manifest loads none.
```

webhook はアラートを受けます。Analytics API は運用の記録を保存します。PostgreSQL がそれを永続化します。VenueAdd はこの公開コアの外にあります。

参照する webhook のホストは Render の Web Service です。参照する機械は Linux の VM です。Signal Nexus はその二つの製品ではありません。自動化が要するのは、GitHub Actions、`ubuntu` としての SSH、TCP 443 の Caddy、localhost の PostgreSQL、`RENDER_HEALTH_URL` です。

## 2. Deploy リポジトリ

template `SignalNexus/signal-nexus-deploy` から非公開リポジトリを生成します。コアのソースは `SignalNexus/signal-nexus` に残ります。caller はコアを fork しません。

次の三つは、同じ四十文字の公開 SHA です。

| 名前 | 場所 |
| --- | --- |
| `core-pin` | caller のルートのファイル |
| `uses` | `.github/workflows/deploy.yml` |
| `core_sha` | 同じ workflow |

pin job は、それらが違うときに止まります。より新しいコアは、三か所すべてに書きます。

最小の SHA は `c301cb2f1d76344bb5126dc57efccd704eb74eb3` です。その commit は、`BUILTIN_VENUES` に `mexc_futures` が含まれるときだけ `deploy.futures_read` を実行します。その門を含むより新しい公開コアができたときに置き換えます。

## 3. 必要な runtime ファイル

初回 deploy の前に、各例を実ファイルの名前へコピーして編集します。七つすべてが空であってはなりません。`{}` は拒否されます。

| 例 | 実ファイル |
| --- | --- |
| `config/examples/locale.yml.example` | `config/locale.yml` |
| `config/examples/month_target.yml.example` | `config/month_target.yml` |
| `config/examples/ops_schedule.yml.example` | `config/ops_schedule.yml` |
| `config/examples/protective_exit.yml.example` | `config/protective_exit.yml` |
| `config/examples/strategies.yml.example` | `config/strategies.yml` |
| `config/examples/strategy_results.yml.example` | `config/strategy_results.yml` |
| `config/examples/venues.yml.example` | `config/venues.yml` |

`locale.yml` は Portal の言語と時計です。`month_target.yml` は月の目標です。`ops_schedule.yml` は運用の予定です。`protective_exit.yml` は protective exit の対応です。`strategies.yml` は registry です。`strategy_results.yml` は結果のラベルです。`venues.yml` は runtime のカタログです。`enabled: false` の会場は、有効な集合の外です。

`venueadd/venues.yaml` は七つの一つではありません。購入まで `venues: []` のままにします。

例の registry は、そのままコピーしても有効です。

```yaml
example-btc-spot:
  symbol: BTC/USDT
  side: long
  venue: mexc_spot
  size_quote: 10
```

strategy の会場は有効なカタログ行でなければならないので、例では `mexc_spot` が有効です。`mexc_futures` と `arcus` はあり、無効です。

## 4. Infrastructure の最小

| 要素 | 最小 |
| --- | --- |
| Linux ホスト | Canonical Ubuntu 24.04。ユーザー `ubuntu`。`sudo -n` が成功する。ホームは `/home/ubuntu` |
| 受信 | GitHub-hosted runner が届く TCP 22。インターネットからの TCP 443。TCP 5432 は閉じる。TCP 80 は閉じる。Caddy は TLS-ALPN |
| PostgreSQL | deploy が Ubuntu 24.04 のパッケージ、PostgreSQL 16 を入れる。localhost で待ち受ける。`pg_hba.conf` は `127.0.0.1/32` を `scram-sha-256` または `md5` で許す。初回 deploy が role `signalnexus` と database `signalnexus` を作る |
| Render | caller リポジトリの branch `main` の Web Service。`workflow_dispatch` の前に Live で、`GET /health` が `{"status":"ok"}` |
| Site | `CADDY_SITE_ADDRESS` は `<public-ip>.sslip.io`。ホスト名だけ。`RENDER_HEALTH_URL` は `https://<render-host>/health`。Render 上の `ANALYTICS_API_URL` は `https://` に site address を足したもの |
| Fingerprint | Actions の secret は、ed25519 の host key に対する `ssh-keygen -lf` の `SHA256:` 欄。秘密鍵にパスフレーズは無い |

Oracle の `ap-tokyo-1` にある `VM.Standard.E2.1.Micro` は参照の shape です。ソフトウェアが動く唯一のホストではありません。コンソールのクリックは Buildbook にあります。

## 5. Build と Start

caller リポジトリに対する正本は、これらの command です。

| | Command |
| --- | --- |
| Build | `bash render-build.sh && pip install -r .core/requirements.txt` |
| Start | `cd .core && uvicorn app.main:app --host 0.0.0.0 --port $PORT` |

`render-build.sh` は `core-pin` を読み、その commit の `SignalNexus/signal-nexus` を `.core/` に取得し、七つの実ファイルを `.core/config/` へコピーし、ファイルごとに sha256 の行を出します。workflow は build log からその行を読みます。

初回 deploy の前の Render の環境変数:

| 名前 | 値 |
| --- | --- |
| `ANALYTICS_API_URL` | `https://<public-ip>.sslip.io` |
| `ANALYTICS_API_SECRET` | 24 文字以上。GitHub に置く値と同じ |
| `EXECUTION_MODE` | `dry_run` |
| `KILL_SWITCH` | `false` |

`WEBHOOK_SECRET`、`PORTAL_PASSWORD`、`DISCORD_WEBHOOK_URL` は待てます。設定した secret が 24 文字未満だと、プロセスは止まります。

## 6. 必要な secret

最初の `workflow_dispatch` の前に必要:

| Secret | 意味 |
| --- | --- |
| `ANALYTICS_SSH_HOST` | Linux ホストの公開 IPv4 |
| `ANALYTICS_SSH_PRIVATE_KEY` | 鍵ファイル。`BEGIN` から `END` まで |
| `ANALYTICS_SSH_HOST_FINGERPRINT` | `SHA256:` の欄 |
| `ANALYTICS_API_SECRET` | Render と共有 |
| `ANALYTICS_DB_PASSWORD` | role `signalnexus` のパスワード。Render には置かない |
| `RENDER_HEALTH_URL` | `https://<render-host>/health` |
| `CADDY_SITE_ADDRESS` | ホスト名だけ |
| `RENDER_DEPLOY_HOOK` | path が `srv-...` で終わる deploy hook |
| `RENDER_API_KEY` | そのサービス、deploy、build log を読める鍵 |

後から置くもの:

| Secret | 時期 |
| --- | --- |
| `VENUEADD_READ_TOKEN` | manifest に行が足されたとき。`venues: []` は git の前に戻る |
| `ANALYTICS_MEXC_API_KEY`、`ANALYTICS_MEXC_API_SECRET` | `BUILTIN_VENUES` が `mexc_spot` を含むとき |
| `ANALYTICS_MEXC_FUTURES_API_KEY`、`ANALYTICS_MEXC_FUTURES_API_SECRET` | `BUILTIN_VENUES` が `mexc_futures` を含むとき |
| Arcus の address と署名の名前 | `BUILTIN_VENUES` が `arcus` を含むとき |
| `KILL_SWITCH` | flag を true にするときだけ。無い値は false のまま |
| 発注鍵 `MEXC_API_*` と `MEXC_FUTURES_API_*` | 後の `live` への切替。最初の health 確認ではない |

値の無い名前は、template の `deploy/target.env.example` にあります。

## 7. 必要な variable

| Variable | 値 |
| --- | --- |
| `ANALYTICS_SSH_USER` | `ubuntu` |
| `ANALYTICS_CORE_DIRECTORY` | `/home/ubuntu/signal-nexus` |
| `ANALYTICS_VENUE_DIRECTORY` | `/opt/signal-nexus/venueadd` |
| `BUILTIN_VENUES` | `none`、またはこの deployment が動かす組み込みの集合 |
| `DEPLOY_ANALYTICS` | `true`。九つの secret のあと、一度の dispatch の直前 |

## 8. BUILTIN_VENUES

`none` と空文字は空集合です。futures の読み取りと追加の secret は、所属に従います。

| 値 | Futures の読み取り | `ANALYTICS_API_SECRET` と `ANALYTICS_DB_PASSWORD` 以外 |
| --- | --- | --- |
| `none` | 実行しない | 無し |
| `mexc_spot` | 実行しない | MEXC spot の読み取りの対 |
| `mexc_futures` | 実行する | MEXC futures の読み取りの対。名前が欠けると deploy は止まる |
| `arcus` | 実行しない | Arcus の address |
| カンマ区切りの集合 | `mexc_futures` が要素のときだけ実行する | 選んだ行の和 |

`mexc_spot` を名指しする registry の行だけでは、spot の鍵は必要になりません。必要にするのは variable です。例の registry は `BUILTIN_VENUES=none` で配備できます。

## 9. 初回 deploy

1. 三つの SHA 欄を、同じ公開 commit に pin する。少なくとも第 2 節の最小。
2. 七つの例を `config/` へコピーして編集し、`venues: []` と `render-build.sh` と一緒に commit する。
3. Linux ホストを作り、fingerprint を記録する。
4. 第 5 節の command で Render のサービスを作る。`GET /health` が `{"status":"ok"}` になるまで待つ。
5. secret 九つを置き、そのあと variable 五つを置く。`DEPLOY_ANALYTICS=true` は最後。
6. `deploy` workflow を `workflow_dispatch` で一度実行する。

deploy は、PostgreSQL が無いときに入れ、`signalnexus` を作り、七ファイルをコピーし、Analytics API を再起動します。`venues: []` では会場リポジトリを fetch しません。

## 10. 成功

| 確認 | 期待 |
| --- | --- |
| Render の `GET /health` | `{"status":"ok"}` |
| Analytics の `GET https://<CADDY_SITE_ADDRESS>/health` | `{"status":"ok"}` |
| 七つの config SHA256 | caller のファイル、deploy log、`ANALYTICS_CORE_DIRECTORY/config/` の写しが一致する |
| `SIGNAL_NEXUS_VENUEADD` | manifest が空のあいだは未設定 |
| Venue fetch | log は会場リポジトリを名指ししない |
| Futures の読み取り | `BUILTIN_VENUES=none` のとき、log に `futures read credentials are not configured` は無い |

hash は、七つの実 path に `sha256sum` を実行して計算します。

## 11. 推奨 SHA

その caller について、推奨 SHA は、最初の緑の `deploy` が使った公開コアの SHA です。第 10 節が通ったときの `core-pin` の値です。失敗した実行は、それを未設定のままにします。別の caller の pin は、別の記録です。

## 12. Rollback

rollback が変えるのは、その caller のリポジトリ、その caller のホスト、その caller の Render サービスです。

初回 deploy が失敗したときは、そのリポジトリの `DEPLOY_ANALYTICS` を false にします。`venues: []` と pin は残します。再試行は新しい SSH 鍵と新しい database パスワードを使います。workflow は、Render のサービスを、hook の前に Live だった deploy へ戻します。

この rollback の一部として、別の caller のリポジトリは編集しません。

## 13. Starter

| このガイド | Buildbook |
| --- | --- |
| この経路の正本 | このガイドに従う |
| 短い要件と command | 参照アカウントのコンソールのクリック |
| 名前で示す secret と variable | 貼り付けながらのチェックリスト |
| 最小の registry 一つ | 注釈付きの例 |
| 成功条件 | 記入済みの実行 |
| rollback の一節 | 失敗のメモ |

Starter が足すのは、検証、詳細、チェックリスト、画面、FAQ、失敗のメモです。必須の事実は足しません。
