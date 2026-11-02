# リリース管理

原文は英語版 [RELEASE_MANAGEMENT.md](RELEASE_MANAGEMENT.md) です。

この章は、公開コアの commit を公開する方法と、1つの環境がその commit を取る方法です。pin を動かす運用者の経路は [Community Deployment Guide](../COMMUNITY_DEPLOYMENT_GUIDE_JA.md) 第 11 節です。この章は、その経路に必須の事実を足しません。

## 1. 開発と公開

開発リポジトリは、公開製品ではありません。その `main` への push は Signal Nexus を公開せず、呼び出し元のホストへも deploy しません。

公開は、開発の commit に付ける、`public-` と 11 桁の tag です。書き出しは、公開の木を `SignalNexus/signal-nexus` の `main` へ送ります。`config/` は送りません。公開側の `config/` は sample のままです。

呼び出し元は、公開の `main` を自分では追いません。`core-pin` の commit を動かします。

## 2. リリースの条件

`public-` tag は、その commit が開発の `main` にあり、その commit で次が成功したときだけ許されます。

- ユニットテスト
- 書き出しパスの確認。`config/`、`business/`、secret の拒否を含む
- Actions 上の `render-build.sh`。空でない fixture 7ファイルで、sha256 を 7 行出す
- workflow の変更では、新しい `analytics-deploy.yml` をそれらのテストに照らして読むこと
- 有料会場では、mock による port のテスト。コアの公開に、稼働中の会場は不要

呼び出し元サービスの Render health と、そのホストへの deploy は、その環境の受け入れです。tag は止めません。

## 3. 環境が公開の更新を取る方法

1. 新しい公開 SHA に、ガイドの futures read を実行する条件が残っていることを確認します。
2. その SHA を `core-pin`、`uses`、`core_sha` に書きます。
3. `workflow_dispatch` を 1 回実行します。`DEPLOY_ANALYTICS` は `true` のままです。
4. [デプロイの準備](DEPLOYMENT_READINESS_JA.md) の成功確認を繰り返します。
5. それらが通ったとき、この環境の推奨 SHA は、その公開 SHA になります。

運用者が pin を選んだあと、Signal Nexus は呼び出し元を編集しません。

## 4. 推奨 SHA の規則

推奨 SHA は、その環境で最後に成功した deploy が使った公開コアの SHA です。最初の成功した deploy が決めます。あとの成功した deploy が置き換えます。失敗した deploy は置き換えません。

別の呼び出し元は、別の記録です。

## 5. この章がしないこと

この章はリリースに tag を付けません。書き出しもしません。別環境の pin も動かしません。
