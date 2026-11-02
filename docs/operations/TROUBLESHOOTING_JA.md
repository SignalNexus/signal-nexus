# トラブルシューティング

原文は英語版 [TROUBLESHOOTING.md](TROUBLESHOOTING.md) です。

これらのメモは、[Community Deployment Guide](../COMMUNITY_DEPLOYMENT_GUIDE_JA.md) の経路で起きうる失敗を扱います。必須の事実は足しません。コンソールの復旧手順は Buildbook に残します。

## 1. `none` での futures read

`BUILTIN_VENUES=none` は `deploy.futures_read` を実行しません。log に `futures read credentials are not configured` があってはなりません。

その行があるときは、pin が futures read を実行する条件より古いか、`BUILTIN_VENUES` に `mexc_futures` が含まれています。ガイドの最小 SHA を SHA 3つすべてに書くか、futures の読み取りペアを足してから、deploy を 1 回実行します。

## 2. 欠けた、または空の runtime ファイル

7つの live ファイルのどれかが欠けているか空だと、deploy は止まります。`{}` は拒否されます。各 example を `config/<name>` へコピーして commit します。`workflow_dispatch` の前に `confirm` を実行します。

## 3. pin の不一致

`core-pin`、`uses`、`core_sha` が違うと、pin の job は止まります。同じ公開 SHA を 3 か所に書いてください。

## 4. dispatch の前の Render health

Render の `GET /health` が `{"status":"ok"}` でないあいだは、`workflow_dispatch` を始めないでください。Web Service は Live であり、この呼び出し元の `main` に付き、ガイドの Build と Start のコマンドを使います。

24 文字未満の設定済み secret は、処理を止めます。

## 5. runner の Git 認証

GitHub-hosted runner 上の会場取得は、credential helper を使います。ユーザー名は `x-access-token` です。別ホスト向けに残っていた helper は、取得の前に消します。パスワードは `VENUEADD_READ_TOKEN` に置いた token です。

空の manifest は、git の前に戻ります。まだ `venues: []` の最初の deploy を調べるために、token を設定しないでください。

## 6. 失敗した会場取得

token が読めないリポジトリの行は、`venueadd-install` を失敗させます。Analytics API は再起動しません。入っている木はそのままです。

token または行を直してから、deploy を 1 回実行します。半分だけ入った木を無理に入れるために、サービスを手で再起動しないでください。

## 7. `DEPLOY_ANALYTICS` がまだ false

`DEPLOY_ANALYTICS` が未設定または `false` のあいだ、workflow はホストへ deploy しません。先に 9つの secret を設定します。`DEPLOY_ANALYTICS=true` は最後、1 回の dispatch の直前です。
