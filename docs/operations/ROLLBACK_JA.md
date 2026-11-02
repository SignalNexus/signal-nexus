# ロールバック

原文は英語版 [ROLLBACK.md](ROLLBACK.md) です。

この章は [Community Deployment Guide](../COMMUNITY_DEPLOYMENT_GUIDE_JA.md) 第 13 節を展開します。必須の事実は足しません。ロールバックが変えるのは、その呼び出し元、そのホスト、その Render のサービスだけです。

## 1. ロールバックとは

[デプロイの準備](DEPLOYMENT_READINESS_JA.md) の成功確認が失敗したときが、ロールバックです。推奨 SHA は置き換えません。前の推奨 SHA は残ります。

このロールバックの一部として、別の呼び出し元を編集しないでください。

## 2. 最初の deploy の失敗

環境には、最後に成功した deploy がありません。

1. その呼び出し元の `DEPLOY_ANALYTICS` を `false` にします。
2. `venues: []` と SHA 3つはそのままにします。
3. workflow は、hook の前に Live だった deploy へ Render のサービスを戻します。
4. 再試行は、新しい SSH 鍵と新しいデータベースパスワードを使います。新しい fingerprint を記録します。`ANALYTICS_SSH_PRIVATE_KEY`、`ANALYTICS_SSH_HOST_FINGERPRINT`、`ANALYTICS_DB_PASSWORD` を置き換えます。
5. 置き換えた secret は [基盤の実行](INFRASTRUCTURE_EXECUTION_JA.md) へ戻り、そのあと [デプロイの準備](DEPLOYMENT_READINESS_JA.md) へ進みます。

## 3. あとの deploy の失敗

環境には、最後に成功した deploy があります。

1. 7つの runtime ファイル、または SHA 3つを、最後に成功した deploy へ戻します。
2. `workflow_dispatch` を 1 回実行します。`DEPLOY_ANALYTICS` は `true` のままです。
3. workflow は、失敗した実行の前に Live だった deploy へ Render のサービスを戻します。
4. 成功確認を繰り返します。推奨 SHA は、あとの更新で確認が再び通るまで、最後に成功した値のままです。

同じコア SHA のまま会場を戻すときは、manifest の `sha` を前の commit にし、deploy を 1 回実行します。`ANALYTICS_VENUE_DIRECTORY/<import_name>/` の木は、その commit に置き換わります。

## 4. 範囲

| 範囲に入るもの | 範囲に入らないもの |
| --- | --- |
| この呼び出し元 | 別の呼び出し元 |
| このホスト | 別のホスト |
| この Render Web Service | 別の Render サービス |
| この環境の推奨 SHA | 公開 tag、または別環境の pin |
