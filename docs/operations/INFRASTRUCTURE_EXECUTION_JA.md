# 基盤の実行

原文は英語版 [INFRASTRUCTURE_EXECUTION.md](INFRASTRUCTURE_EXECUTION.md) です。

この章は、Linux ホスト、PostgreSQL、Render Web Service、9つの secret、5つの variable の公開手順です。下限と名前の正本は [Community Deployment Guide](../COMMUNITY_DEPLOYMENT_GUIDE_JA.md) の第 4 節から第 7 節です。この章は、必須の事実を足しません。`workflow_dispatch` は始めません。

## 1. Linux ホスト

この呼び出し元だけのための Linux ホストを 1 台作ります。

| 要素 | 下限 |
| --- | --- |
| Image | Canonical Ubuntu 24.04 |
| ユーザー | `ubuntu`、ホーム `/home/ubuntu`、`sudo -n` が成功する |
| 受信 | GitHub-hosted runner から TCP 22。インターネットから TCP 443。TCP 5432 は閉じる。TCP 80 は閉じる |
| TLS | TLS-ALPN の Caddy |
| Fingerprint | Actions の secret は、ed25519 ホスト鍵に対する `ssh-keygen -lf` の `SHA256:` 欄 |
| SSH 鍵 | ed25519。パスフレーズなし |

Oracle `ap-tokyo-1` の `VM.Standard.E2.1.Micro` は、例として挙げる shape です。このソフトウェアを動かせるホストは、それだけではありません。

別ホストの環境ファイルをコピーしないでください。別環境のデータベース dump を戻さないでください。

## 2. PostgreSQL

最初の deploy は、欠けていれば PostgreSQL 16 を入れ、ロール `signalnexus` とデータベース `signalnexus` を作り、localhost で待ち受けます。`pg_hba.conf` は `127.0.0.1/32` を `scram-sha-256` または `md5` で許します。

パスワードはこの環境の `ANALYTICS_DB_PASSWORD` です。Render には保存しません。

## 3. Render Web Service

この呼び出し元の `main` ブランチに接続した Web Service を 1 つ作ります。

| 設定 | 値 |
| --- | --- |
| Build Command | `bash render-build.sh && pip install -r .core/requirements.txt` |
| Start Command | `cd .core && uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| `ANALYTICS_API_URL` | `https://` に `CADDY_SITE_ADDRESS` を続ける |
| `ANALYTICS_API_SECRET` | 24 文字以上。同じ値を GitHub にも置く |
| `EXECUTION_MODE` | `dry_run` |
| `KILL_SWITCH` | `false` |

`workflow_dispatch` の前に、サービスが Live であり、`GET /health` が `{"status":"ok"}` を返すまで待ちます。

`CADDY_SITE_ADDRESS` は `<public-ip>.sslip.io`、ホスト名だけです。`RENDER_HEALTH_URL` は `https://<render-host>/health` です。

## 4. 9つの secret

この呼び出し元の GitHub repository secrets として設定します。最初の dispatch の前に必要です。

| Secret | 意味 |
| --- | --- |
| `ANALYTICS_SSH_HOST` | このホストの公開 IPv4 |
| `ANALYTICS_SSH_PRIVATE_KEY` | 鍵ファイル。`BEGIN` から `END` まで |
| `ANALYTICS_SSH_HOST_FINGERPRINT` | `SHA256:` 欄 |
| `ANALYTICS_API_SECRET` | Render と共有 |
| `ANALYTICS_DB_PASSWORD` | ロール `signalnexus` のパスワード |
| `RENDER_HEALTH_URL` | `https://<render-host>/health` |
| `CADDY_SITE_ADDRESS` | ホスト名だけ |
| `RENDER_DEPLOY_HOOK` | この Web Service の Deploy Hook URL |
| `RENDER_API_KEY` | このサービス、その deploy、その build log を読める鍵 |

別の呼び出し元から secret の値をコピーしないでください。

## 5. 5つの variable

| Variable | 値 |
| --- | --- |
| `ANALYTICS_SSH_USER` | `ubuntu` |
| `ANALYTICS_CORE_DIRECTORY` | `/home/ubuntu/signal-nexus` |
| `ANALYTICS_VENUE_DIRECTORY` | `/opt/signal-nexus/venueadd` |
| `BUILTIN_VENUES` | `none`、またはこの環境が動かす組み込みの集合 |
| `DEPLOY_ANALYTICS` | 9つの secret のあと、1回の dispatch の直前に `true` |

`DEPLOY_ANALYTICS` は最後です。`true` になるまで、workflow を始めないでください。

## 6. 最初の deploy の準備ができた状態

ホストが第 1 節を満たし、Render の `GET /health` が `{"status":"ok"}` であり、9つの secret があり、先の 4つの variable があるとき、基盤の実行は完了です。dispatch そのものは [デプロイの準備](DEPLOYMENT_READINESS_JA.md) です。
