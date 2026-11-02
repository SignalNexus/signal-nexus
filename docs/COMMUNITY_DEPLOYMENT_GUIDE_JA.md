# Community Deployment Guide

英語版が正本です。このファイルは [COMMUNITY_DEPLOYMENT_GUIDE.md](COMMUNITY_DEPLOYMENT_GUIDE.md) の日本語版です。

このガイドは、Signal Nexus Community Edition を Health Validation（health の確認）までデプロイするための公開の正本です。技術のある利用者は、`SignalNexus/signal-nexus` と `SignalNexus/signal-nexus-deploy` だけを読んで、Health Validation まで進めます。

[README](../README_JA.md) は最初に読む文書です。[Architecture](architecture/ARCHITECTURE_JA.md) はシステム構成を確認するための文書です。Starter の Buildbook は、本ガイドの詳細版です。チェックリスト、画面例、FAQ、失敗を避けるメモを加えます。本ガイドに無い必須事項は加えません。

## まずやること

このガイドでは、`SignalNexus/signal-nexus-deploy` から作る利用者自身の非公開リポジトリを、呼び出し元リポジトリと呼びます。作業はこの順です。各手順の詳細は、リンク先の節にあります。

1. テンプレートから呼び出し元リポジトリを作る。[第2節](#sec-2)。
2. サンプルから runtime ファイルを七つ配置する。[第3節](#sec-3)。
3. Webhook を受ける Render の Web Service を作る。[第4節](#sec-4)と[第5節](#sec-5)。
4. Linux ホストを準備する。[第4節](#sec-4)。
5. secret と variable を設定する。[第6節](#sec-6)、[第7節](#sec-7)、[第8節](#sec-8)。
6. GitHub Actions の workflow `deploy` を `workflow_dispatch` で起動する。[第9節](#sec-9)。
7. Health Validation を確認する。[第10節](#sec-10)。

あとからの変更も、同じ workflow を使います。[第11節](#sec-11)。

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

webhook はアラートを受けます。Analytics API は運用の記録を保存します。PostgreSQL がそれを保存します。VenueAdd はこの公開コアの外にあります。

手順で例にする Webhook の置き場所は Render の Web Service です。例にするマシンは Linux の VM です。Signal Nexus 自体は、Render でも Linux VM でもありません。デプロイの自動化が前提にするのは、GitHub Actions、`ubuntu` としての SSH、TCP 443 の Caddy、localhost の PostgreSQL、`RENDER_HEALTH_URL` です。

<a id="sec-2"></a>

## 2. Deploy リポジトリ

このガイドでは、テンプレート `SignalNexus/signal-nexus-deploy` から作った利用者自身の非公開リポジトリを、呼び出し元リポジトリと呼びます。コアのソースは `SignalNexus/signal-nexus` に残ります。呼び出し元は、コアを fork しません。

次の三つは、同じ 40 文字の公開 SHA です。

| 名前 | 場所 |
| --- | --- |
| `core-pin` | 呼び出し元のルートのファイル |
| `uses` | `.github/workflows/deploy.yml` |
| `core_sha` | 同じ workflow |

pin job は、それらが違うときに止まります。より新しい公開 SHA に上げるときは、三か所すべてを書き換えます。

最小の SHA は `c301cb2f1d76344bb5126dc57efccd704eb74eb3` です。その commit は、`BUILTIN_VENUES` に `mexc_futures` が含まれるときだけ `deploy.futures_read` を実行します。同じ条件を持つ、より新しい公開コアができたときに置き換えます。

<a id="sec-3"></a>

## 3. 必要な runtime ファイル

初回 deploy の前に、各例を、`.example` を外したパスへコピーします。値は編集してよいです。全項目を変える必要はありません。サンプルの内容は、そのままでも deploy できます。必要なのは、7ファイルが存在し、`confirm` を通ることです。7ファイルとも、中身が必要です。`{}` は拒否されます。

| 例 | 配置するファイル |
| --- | --- |
| `config/examples/locale.yml.example` | `config/locale.yml` |
| `config/examples/month_target.yml.example` | `config/month_target.yml` |
| `config/examples/ops_schedule.yml.example` | `config/ops_schedule.yml` |
| `config/examples/protective_exit.yml.example` | `config/protective_exit.yml` |
| `config/examples/strategies.yml.example` | `config/strategies.yml` |
| `config/examples/strategy_results.yml.example` | `config/strategy_results.yml` |
| `config/examples/venues.yml.example` | `config/venues.yml` |

`locale.yml` は Portal の言語と時計です。`month_target.yml` は月の目標です。`ops_schedule.yml` は運用の予定です。`protective_exit.yml` は protective exit の対応です。`strategies.yml` は registry です。`strategy_results.yml` は結果のラベルです。`venues.yml` は runtime のカタログです。`enabled: false` の会場は、有効な会場に含まれません。

`venueadd/venues.yaml` は、この7ファイルには含まれません。購入まで `venues: []` のままにします。

`confirm` は、runtime の設定ファイルを検証します。検証に失敗した場合、deploy は進みません。例の registry は、編集せずコピーしても、その検証を通ります。

```yaml
example-btc-spot:
  symbol: BTC/USDT
  side: long
  venue: mexc_spot
  size_quote: 10
```

strategy の会場は有効なカタログ行でなければならないので、例では `mexc_spot` が有効です。`mexc_futures` と `arcus` は記載し、`enabled` は false です。

<a id="sec-4"></a>

## 4. インフラの最小要件

| 要素 | 最小 |
| --- | --- |
| Linux ホスト | Canonical Ubuntu 24.04。ユーザー `ubuntu`。`sudo -n` が成功する。ホームは `/home/ubuntu` |
| 開けるポート | GitHub-hosted runner が届く TCP 22。インターネットからの TCP 443。TCP 5432 は閉じる。TCP 80 は閉じる。Caddy は TLS-ALPN |
| PostgreSQL | 初回 deploy が role `signalnexus` と database `signalnexus` を作成します。deploy は Ubuntu 24.04 のパッケージ、PostgreSQL 16 を入れます。localhost で待ち受けます。`pg_hba.conf` は `127.0.0.1/32` を `scram-sha-256` または `md5` で許可します |
| Render | 呼び出し元の branch `main` の Web Service。Webhook を受けます。deploy workflow を起動する前に Live で、`GET /health` が `{"status":"ok"}` |
| Site | `CADDY_SITE_ADDRESS` は `<public-ip>.sslip.io`。ホスト名だけ。`RENDER_HEALTH_URL` は `https://<render-host>/health`。Render 上の `ANALYTICS_API_URL` は、`https://` のあとに site address を続けたもの |
| Fingerprint | Actions の secret は、ed25519 の host key に対する `ssh-keygen -lf` の `SHA256:` のフィールド。秘密鍵にパスフレーズは無い |

Render では、呼び出し元リポジトリの `main` ブランチを接続した Web Service を作成します。このサービスが Webhook を受けます。build と start は第5節のコマンドです。

Oracle の `ap-tokyo-1` にある `VM.Standard.E2.1.Micro` は、例として挙げる shape です。ソフトウェアが動く唯一のホストではありません。コンソールのクリックは Buildbook にあります。

`workflow_dispatch` は、呼び出し元にある GitHub Actions の workflow `deploy` を起動する方法です。その workflow を開き、実行します。画面の画像は要りません。第9節が初回です。第11節が、そのあと毎回です。

<a id="sec-5"></a>

## 5. Build と Start

呼び出し元では、次のコマンドを正本とします。

| | Command |
| --- | --- |
| Build | `bash render-build.sh && pip install -r .core/requirements.txt` |
| Start | `cd .core && uvicorn app.main:app --host 0.0.0.0 --port $PORT` |

`render-build.sh` は `core-pin` を読み、その commit の `SignalNexus/signal-nexus` を `.core/` に取得し、配置先の七ファイルを `.core/config/` へコピーし、ファイルごとに sha256 の行を出します。workflow は build log からその行を読みます。

初回 deploy の前の Render の環境変数:

| 名前 | 値 |
| --- | --- |
| `ANALYTICS_API_URL` | `https://<public-ip>.sslip.io` |
| `ANALYTICS_API_SECRET` | 24 文字以上。GitHub に置く値と同じ |
| `EXECUTION_MODE` | `dry_run` |
| `KILL_SWITCH` | `false` |

`WEBHOOK_SECRET`、`PORTAL_PASSWORD`、`DISCORD_WEBHOOK_URL` は、あとから設定できます。設定した secret が 24 文字未満だと、プロセスは止まります。

<a id="sec-6"></a>

## 6. 必要な secret

最初の `workflow_dispatch` の前に必要:

| Secret | 意味 |
| --- | --- |
| `ANALYTICS_SSH_HOST` | Linux ホストの公開 IPv4 |
| `ANALYTICS_SSH_PRIVATE_KEY` | 鍵ファイル。`BEGIN` から `END` まで |
| `ANALYTICS_SSH_HOST_FINGERPRINT` | `SHA256:` のフィールド |
| `ANALYTICS_API_SECRET` | Render と共有 |
| `ANALYTICS_DB_PASSWORD` | role `signalnexus` のパスワード。Render には置かない |
| `RENDER_HEALTH_URL` | `https://<render-host>/health` |
| `CADDY_SITE_ADDRESS` | ホスト名だけ |
| `RENDER_DEPLOY_HOOK` | Render の Web Service の Deploy Hook URL です。path は `srv-...` で終わります |
| `RENDER_API_KEY` | そのサービス、deploy、build log を読める鍵 |

あとから設定するもの:

| Secret | 時期 |
| --- | --- |
| `VENUEADD_READ_TOKEN` | manifest に行が追加されたとき。`venues: []` では、git の前に処理を終える |
| `ANALYTICS_MEXC_API_KEY`、`ANALYTICS_MEXC_API_SECRET` | `BUILTIN_VENUES` が `mexc_spot` を含むとき |
| `ANALYTICS_MEXC_FUTURES_API_KEY`、`ANALYTICS_MEXC_FUTURES_API_SECRET` | `BUILTIN_VENUES` が `mexc_futures` を含むとき |
| Arcus の address と署名の名前 | `BUILTIN_VENUES` が `arcus` を含むとき |
| `KILL_SWITCH` | flag を true にするときだけ。無い値は false のまま |
| 発注鍵 `MEXC_API_*` と `MEXC_FUTURES_API_*` | `EXECUTION_MODE` を `live` に変更するとき。それまでは `dry_run` で、注文は出ません。最初の health の確認ではありません |

名前だけで、値は書かれていません。置場はテンプレートの `deploy/target.env.example` です。

<a id="sec-7"></a>

## 7. 必要な variable

| Variable | 値 |
| --- | --- |
| `ANALYTICS_SSH_USER` | `ubuntu` |
| `ANALYTICS_CORE_DIRECTORY` | `/home/ubuntu/signal-nexus` |
| `ANALYTICS_VENUE_DIRECTORY` | `/opt/signal-nexus/venueadd` |
| `BUILTIN_VENUES` | `none`、またはこの環境で使う組み込み会場 |
| `DEPLOY_ANALYTICS` | `true`。九つの secret のあと、`workflow_dispatch` の直前 |

<a id="sec-8"></a>

## 8. BUILTIN_VENUES

`none` と空文字は空集合です。futures の読み取りと追加の secret は、その名前が `BUILTIN_VENUES` に含まれるかどうかで決まります。

| 値 | Futures の読み取り | `ANALYTICS_API_SECRET` と `ANALYTICS_DB_PASSWORD` 以外 |
| --- | --- | --- |
| `none` | 実行しない | 無し |
| `mexc_spot` | 実行しない | MEXC spot の読み取りの対 |
| `mexc_futures` | 実行する | MEXC futures の読み取りの対。名前が欠けると deploy は止まる |
| `arcus` | 実行しない | Arcus の address |
| カンマ区切りの集合 | `mexc_futures` が要素のときだけ実行する | 選んだ行をすべて合わせたもの |

Spot の API 鍵が必要かどうかは、`strategies.yml` ではなく、`BUILTIN_VENUES` の設定で決まります。例の registry は、`BUILTIN_VENUES=none` のまま deploy できます。

<a id="sec-9"></a>

## 9. 初回 deploy

1. SHA を書く三か所を、同じ公開 commit に pin します。第2節の最小 SHA と同じか、それより新しい公開 SHA にします。
2. 七つの例を `config/` へコピーします。全項目を編集する必要はありません。`venues: []` と `render-build.sh` と一緒に commit します。
3. Linux ホストを作り、fingerprint を記録します。
4. Render では、呼び出し元リポジトリの `main` ブランチを接続した Web Service を作成します。第5節のコマンドを使います。`GET /health` が `{"status":"ok"}` になるまで待ちます。
5. secret を九つ置き、そのあと variable を五つ置きます。`DEPLOY_ANALYTICS=true` は最後です。
6. GitHub で Actions を開き、workflow `deploy` を開き、`workflow_dispatch` で一度実行します。

deploy は、PostgreSQL が無ければインストールし、`signalnexus` を作り、七ファイルをコピーし、Analytics API を再起動します。`venues: []` では会場リポジトリを fetch しません。

workflow が完了したら、第10節の確認項目を実施します。

<a id="sec-10"></a>

## 10. 成功

| 確認 | 期待 |
| --- | --- |
| Render の `GET /health` | `{"status":"ok"}` |
| Analytics の `GET https://<CADDY_SITE_ADDRESS>/health` | `{"status":"ok"}` |
| 七つの config SHA256 | 呼び出し元のファイル、deploy log、`ANALYTICS_CORE_DIRECTORY/config/` のコピーが一致する |
| `SIGNAL_NEXUS_VENUEADD` | manifest が空のときは、設定しません |
| Venue fetch | ログに、会場リポジトリの名前は出ません |
| Futures の読み取り | `BUILTIN_VENUES=none` のとき、log に `futures read credentials are not configured` は無い |

hash は、配置した七つの path に対して `sha256sum` を実行して計算します。

この節の確認をすべて通した deploy を、成功した deploy と呼びます。その環境で最も新しい成功した deploy を、最後に成功した deploy と呼びます。

<a id="sec-11"></a>

## 11. 二回目以降の deploy

次の変更を行った場合は、deploy workflow を再実行します。

- runtime ファイル
- `core-pin`
- `uses`
- `core_sha`
- Render の環境変数

初回は第9節です。そのあとの変更も、同じ workflow で deploy します。

1. 配置した runtime ファイル七つを更新するか、`core-pin`、`uses`、`core_sha` に新しい公開 SHA を書くか、Render の環境変数を変えます。新しい SHA も、第2節の futures read の条件を含みます。SHA を書く三か所は、同じ値のままです。
2. Render のサービスは、すでに Live です。起動する前に、`GET /health` は `{"status":"ok"}` のままです。
3. GitHub Actions の workflow `deploy` を、`workflow_dispatch` で一度実行します。`DEPLOY_ANALYTICS` は `true` のままです。
4. 第10節の確認を、もう一度行います。
5. その確認が通ったら、この環境の推奨 SHA は、この deploy が使った公開コアの SHA になります。

## 12. 推奨 SHA

推奨 SHA は、その環境の最後に成功した deploy が使った公開コアの SHA です。最初の成功した deploy が、それを決めます。そのあとの成功した deploy は、それを置き換えます。失敗した deploy は置き換えず、前の値も消しません。別の呼び出し元の pin は、別の値です。

最初の成功だけが推奨だと読まないでください。

## 13. Rollback

rollback の対象は、その呼び出し元のリポジトリ、ホスト、Render サービスです。

初回 deploy が失敗したときは、そのリポジトリの `DEPLOY_ANALYTICS` を false にします。`venues: []` と pin は残します。再試行は新しい SSH 鍵と新しい database パスワードを使います。workflow は、Render のサービスを、hook の前に Live だった deploy へ戻します。

更新後の deploy が失敗した場合も、最後に成功した deploy の状態へ戻します。workflow は、Render のサービスを、その実行の前に Live だった deploy へ戻します。この戻しは、初回 deploy だけのものではありません。

この手順では、ほかの呼び出し元のリポジトリは変更しません。

## 14. Starter

| 項目 | このガイド | Buildbook |
| --- | --- | --- |
| 手順の正本 | はい | このガイドに従う |
| 要件とコマンド | 短く書く | 例にした Oracle と Render の画面操作 |
| secret と variable | 名前 | 値を貼り付けるときのチェックリスト |
| registry | 最小の registry 一つ | 注釈付きの例 |
| 成功条件 | 第10節の確認 | 記入例つきの実行記録 |
| rollback | 説明 | 失敗のメモ |

Starter が加えるのは、検証、詳細、チェックリスト、画面、FAQ、失敗のメモです。必須の事実は加えません。
