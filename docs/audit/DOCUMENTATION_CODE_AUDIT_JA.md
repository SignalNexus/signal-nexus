# 文書と実装の監査

監査日は 2026-10-16 です。正本は英語版 [DOCUMENTATION_CODE_AUDIT.md](DOCUMENTATION_CODE_AUDIT.md) です。

この文書は、六つの正本とリポジトリの実装がどこで違うかを記録します。正本自体は変えていません。README は監査の対象にしていません。

ここで実行を確認したのは、`GET https://signal-nexus.onrender.com/health` が `{"status":"ok"}` だったことだけです。仮想マシン、Discord への配達、実際の Webhook は呼んでいません。

## 要約

### 一致

Architecture. 分かれ方はコードにある。Render は `app.main` で、`POST /webhook`、`GET /health`、ポータルを動かす。VM 上の Analytics API は `GET /health` と発注の経路を持つ。Postgres を開くのはその API である。GitHub Actions の `analytics-vm` はリポジトリを VM へコピーする。MEXC と Arcus は発注先である。`live` の注文は Render からその API へ渡される。

Buildbook. 公開リポジトリの clone URL、Render の Build と Start、ワークフローのファイル名、そのワークフローが読む secret の名前、`config/strategies.yml` の欄、一つの取引所に対する `POST /webhook` の `{"status":"dry_run"}` は、実装と一致する。

Strategy Integration Guide. `strategy_id`、`symbol`、`action`、`client_order_id`、`WEBHOOK_SECRET` は、`WebhookPayload` と `route()` と一致する。本文の `size` と `size_quote` は HTTP 422 である。秘密が違うと HTTP 401 である。`EXECUTION_MODE` が未設定なら `dry_run` で、注文は出ない。アクションの表は `_accepts` と一致する。

Screen Specification. Dashboard、Trading、Analytics、Operations はある。ブロック、列、Audit Log の六つの表示は `portal_pages.py` と一致する。計画は保存され、その六つには入らない。

Screen Relationship Diagram. ✅ ポータルが画面をまたいで描いているリンクは、Dashboard から Trading の Positions、Analytics の Strategies、Operations の Schedule の三つだけである。

Product Specification. ポータルは注文を出さない。`dry_run` は注文を出さない。Analytics API が設定されていれば、監査の履歴は書かれる。Analytics の画面は、保存された記録そのものではない。

### 差分

#### 1. Discord の写しは送っていない

状態。解消済み。`_DISCORD_POSTS_ENABLED` は `True` です。判断は [CORRECTION_DECISIONS.md](CORRECTION_DECISIONS.md) にあります。待ちが 1 分を超える 429 では、そのプロセスの以降の POST を止め、行には `429 paused` と残します。

| | |
| --- | --- |
| 項目 | Discord への監査の配達 |
| 文書 | Architecture、Buildbook の完了条件、Product Specification |
| 実装 | `app/notifications/discord.py` の `_DISCORD_POSTS_ENABLED` は `True` である。`DISCORD_WEBHOOK_URL` があれば、`discord_copy` は写しを POST する。 |
| 差分 | 通常の配達に差分はない。`retry_after` が 60 秒を超える 429 では、そのプロセスの以降の投稿を止める。 |
| 影響度 | Webhook を入れた人には写しが届く。Discord がそのプロセスを止めているあいだは届かない。 |
| 修正案 | 実施済み。 |

#### 2. Actions には、Buildbook が書いていない停止条件がある

| | |
| --- | --- |
| 項目 | `analytics-vm` が失敗する条件 |
| 文書 | Buildbook 第 5 章の「マシンへ載せる」 |
| 実装 | コピーのあと、`.github/workflows/analytics-vm.yml` は importer のログに `arcus fills ` が出るまで待ち、そのあと `deploy.confirm_arcus_leverage` と `deploy.confirm_mexc_env` を実行する。 |
| 差分 | 手順書は、secret の不足、ホスト鍵の不一致、Render の health が ok でないこと、で止まると書いている。取り込みのログ待ちは、その三つが通ったあとでも失敗にできる。`confirm_arcus_leverage` は HTTP のエラーを表示して終了コード 0 で終わるので、レバレッジの拒否だけではジョブは落ちない。 |
| 影響度 | Major。Actions が赤でも、secret や health の失敗に見える。実際は importer がまだログを出していないことがある。 |
| 修正案 | 取り込みログの待ちを、停止条件として書く。レバレッジのコマンドは状態を表示し、それだけではジョブを失敗にしない、と書く。 |

#### 3. 同じ `client_order_id` は 422 ではない

| | |
| --- | --- |
| 項目 | 重複したアラート |
| 文書 | Strategy Integration Guide の第 3 節と第 5 節 |
| 実装 | その id がすでに取られていれば、`receive_webhook` は HTTP 200 と `{"status":"duplicate"}` を返す。HTTP 422 は検証である。HTTP 401 は秘密である。 |
| 差分 | 手順は、再送は破棄される、と書いていて、その点は正しい。拒否は HTTP 422、とも書いている。重複の破棄は別のステータスである。 |
| 影響度 | Minor。重複を、検証エラーと読むことがある。 |
| 修正案 | 同じ id は `{"status":"duplicate"}` を返し、注文は出さない、と書く。 |

#### 4. 四つの画面の前にログインがある

| | |
| --- | --- |
| 項目 | ポータルの入口 |
| 文書 | Screen Specification、Screen Relationship Diagram |
| 実装 | `PORTAL_PASSWORD` が空だと `_session_ok` は偽である。`/portal`、`/portal/trading`、`/portal/analytics`、`/portal/operations` は、パスワードが合うまでログイン画面を出す。 |
| 差分 | ログインのあと、四つの画面とツリーは実装どおりである。文書にログイン画面は無い。 |
| 影響度 | Minor。画面の中身は一致する。最初に開くのは、ツリーに無いログインである。 |
| 修正案 | ログインを、Portal の前の門として書く。五つ目の主な画面にはしない。パスワードの置き場所は Buildbook のままにする。 |

#### 5. Dashboard の一部の文言は日本語である

| | |
| --- | --- |
| 項目 | Dashboard の項目名 |
| 文書 | Screen Specification の Dashboard |
| 実装 | 見出しは英語である（`Today`、`Risk Summary`、`PnL`）。値の名前のいくつかは日本語で、`実績（USD）`、`月目標`、`達成率`、`残必要額`、`月末着地予測` を含む。 |
| 差分 | 英語の仕様は、同じ内容を英語で説明している。画面にはその英語の句は無い。 |
| 影響度 | Minor。内容はある。英語の句を見出しとして探すと見つからない。 |
| 修正案 | それらの値の名前は、画面上では日本語である、と書く。 |

#### 6. 運用の記録は、API を接続したときだけ残る

| | |
| --- | --- |
| 項目 | 運用の記録と監査の履歴 |
| 文書 | Product Specification |
| 実装 | `ANALYTICS_API_URL` または `ANALYTICS_API_SECRET` が空のとき、`append_audit` は送らずに戻る。Webhook は `dry_run` を返す。 |
| 差分 | 製品の文は、記録と履歴が残る、と書いている。Buildbook のとおり Render と VM をつないだあとなら、そのとおりである。`WEBHOOK_SECRET` だけの Webhook では残らない。 |
| 影響度 | Minor。文書どおりに構築すれば、両方の変数は入る。製品の文だけを読むと、受け付けたアラートがすべて保存されるように読める。 |
| 修正案 | VM への接続が設定されているとき、記録が残る、と書く。 |

## 見つからなかったもの

Buildbook の別紙に、削除済みの secret 名は無い。`analytics-vm.yml` はある。Render の `GET /health` はあり、確認したホストでは `{"status":"ok"}` だった。例の戦略 `btc_long_example` は、接続手順が書くレジストリの形で受け付けられる。Hyperliquid、Paradex、GRVT は、実行時に有効な発注先ではない。
