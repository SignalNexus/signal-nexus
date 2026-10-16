# レビュー指摘の対応

原文は英語版 [REVIEW_FEEDBACK_ACTIONS.md](REVIEW_FEEDBACK_ACTIONS.md) です。2026-10-16 のレビュー記録であり、利用者向けの手順ではありません。

日本語版は確認用です。英語の本文が固まるまで、全文の訳し直しはしていません。

| 指摘 | 判断 | 対応 | 優先度 | 状態 |
| --- | --- | --- | --- | --- |
| `BUILDBOOK_JA` が未完成の訳に読める | 英語版を正本にする。この回では日本語の全文を磨かない | `BUILDBOOK_JA.md` の冒頭で、画面単位の手順は英語版を見るようにした。全文の書き直しは待つ | P4 | 方針として完了 |
| Buildbook 冒頭の README についての文を消す | 読む人の役に立たない | `BUILDBOOK.md` と `BUILDBOOK_JA.md` から削除した | P1 | 完了 |
| 冒頭の「`SignalNexus/signal-nexus` へは push しない」が唐突 | リポジトリの手順へ移す | 英語版と日本語版の両方で移した | P1 | 完了 |
| 他文書の紹介が繰り返される | 紹介は一箇所 | 英語版と日本語版の両方で、一段落にまとめた | P1 | 完了 |
| 「本流 / Advanced notes」の文が分かりにくい | Main Flow と Advanced Notes に分け、Main Flow だけで構築できると書く | 英語版と日本語版の両方で置き換えた | P1 | 完了 |
| GitHub、Render、Oracle、Discord に画面の順が要る | 英語版に置く。クリック順は Advanced Notes でよい | `BUILDBOOK.md` に追加した | P1 | 完了 |
| TradingView の無料プランと Webhook | Basic では戦略の Webhook を送れない。二要素認証が必要。ポートは 80 と 443。有料プランの上限は変わる | `BUILDBOOK.md` の TradingView の Advanced Notes に表を置いた。料金ページで確認する、と書いた | P1 | 完了 |
| Render と GitHub の接続順 | Dashboard、New、Web Service、GitHub 接続、リポジトリ選択 | `BUILDBOOK.md` の Render の Advanced Notes に追加した | P1 | 完了 |
| 東京を推奨する | 動作を確認した地域は Japan East（`ap-tokyo-1`）。別の地域では、東京で通る Arcus の呼び出しが拒否されることがある | `BUILDBOOK.md` に書いた | P1 | 完了 |
| インスタンスの前に VCN、サブネット、セキュリティ規則を作る | 必要な順である | `BUILDBOOK.md` に書いた。ウィザード、自分の IP からの TCP 22、インターネットからの TCP 443、5432 は開けない | P1 | 完了 |
| Postgres を毎日 03:00 にバックアップし、4 世代を残して回す | デプロイのスクリプトはこの作業を入れない。手順書が、自分で足すと書く | `BUILDBOOK.md` に手作業として書いた。既存のワークフローだとは書いていない | P1 | 完了 |
| Oracle の入力欄 | VCN とインスタンスの手順と同じ | `BUILDBOOK.md` に書いた | P1 | 完了 |
| `CADDY_SITE_ADDRESS` を説明する | ホスト名だけ。GitHub の secret に置き、`/home/ubuntu/site.env` に書き、Caddy が使う。`https://` を付けるのは `ANALYTICS_API_URL` だけ | `BUILDBOOK.md` に書いた | P1 | 完了 |
| 「アカウントを作る」だけでは名前が分からない | MEXC、Rabby、Arcus と書く | `BUILDBOOK.md` に書いた | P1 | 完了 |
| MEXC と Arcus の紹介リンクを、変わることがあると注記して足す | 2026-10-16 に渡された URL を使う。TradingView の料金リンクも含む。変わることがあると書く | `BUILDBOOK.md` と `BUILDBOOK_JA.md` に足した | P1 | 完了 |
| Arcus の Advanced Notes に Robinhood Chain と、署名のガス代 | ガスが要るのは API キーの発行時で、チェーンは Robinhood Chain。そのキーで発注するときにはガスは要らない | 英語版と日本語版に書いた | P1 | 完了 |
| 最初から `<account>/<repo>` を使い、個人のリポジトリ名を出さない | 比較そのものは残す。特定の人のリポジトリ名は教えない | `BUILDBOOK.md` と `BUILDBOOK_JA.md` を更新した | P1 | 完了 |
| `arcus-region-probe.yml` はこの読者向けではない | Buildbook から外す。ワークフローのファイルは消さない | 英語版と日本語版の両方から外した | P1 | 完了 |
| Render ができる前に `RENDER_HEALTH_URL` は分からない | 先にコードを push し、Render のサービスを作り、secret を保存し、Actions をやり直す | `BUILDBOOK.md` の順を変えた | P1 | 完了 |
| 確認コマンドの実行場所を書く | 三つの確認は Ubuntu のシェル | `BUILDBOOK.md` に書いた | P1 | 完了 |
| Architecture の日本語版の ASCII 図が読みにくい | Mermaid を使う。図の正本は英語版なので、両方を変える | `ARCHITECTURE.md` と `ARCHITECTURE_JA.md` に Mermaid を足した | P2 | 完了 |
| Arcus の読み取りアドレスと発注アドレスは別か | 設定は二つ。読み取りは `ANALYTICS_ARCUS_ADDRESS` で、署名しない。発注は `ARCUS_ADDRESS` と `ARCUS_SIGNING_KEY`。同じアドレスを両方に入れてよい | `ARCHITECTURE.md`、`ARCHITECTURE_JA.md`、`BUILDBOOK.md` を直した | P2 | 完了 |
| 製品仕様の日本語版に概要と目次が要る | 足す。二つ目の構成説明にはしない | `PRODUCT_SPECIFICATION_JA.md` に足した | P3 | 完了 |
| 「どこで動くか」が Architecture の繰り返し | 日本語版から繰り返す文を外す | Architecture の日本語版への一文に替えた | P3 | 完了 |
| 日本語の文章品質 | この回ではやらない | 英語版が固まるまで後回し | P4 | 後回し |
