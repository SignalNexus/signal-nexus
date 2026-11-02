# 会場ライセンスとリポジトリアクセス

原文は英語版 [VENUE_LICENSE.md](VENUE_LICENSE.md) です。

この章は、有料会場 1 つの公開ライセンスとアクセスのモデルです。デプロイの配置は [AddVenue deployment](../architecture/ADDVENUE_DEPLOY_JA.md) です。最初の health の経路に会場は不要です。[Community Deployment Guide](../COMMUNITY_DEPLOYMENT_GUIDE_JA.md) は、購入まで `venues: []` のままにします。この章は、その経路に必須の事実を足しません。

## 1. 購入が意味すること

VenueAdd は、1つの会場の拡張であり、その同じ会場のあとの保守を含みます。あとのすべての会場への権利ではありません。Starter、Volume Pack、Profit Pack も含みません。

公開コアに、有料の会場パッケージは入りません。

## 2. Manifest

1つの環境に、`venueadd/venues.yaml` は 1 つです。1件は `import_name`、`repository`、`sha`、`venue_id`、`requirements_file` を持ちます。Python の版、secret、検証コマンド、deploy のモード、SSH の対象、サービスマネージャは書きません。

空のファイル、または `venues: []` は、パッケージを入れず、token も不要です。

## 3. リポジトリアクセス

有料の会場リポジトリは非公開のままです。呼び出し元の運用者は、買った各リポジトリの外部 collaborator で Read を持ち、公開組織のメンバーではありません。

その運用者が、fine-grained の personal access token を 1 つ作ります。resource owner は、会場リポジトリを持つ組織です。権限は Contents: Read です。リポジトリアクセスは、その運用者がすでに読めるリポジトリに従います。

token は、その呼び出し元の `VENUEADD_READ_TOKEN` にだけ置きます。公開コアには入りません。Signal Nexus はコピーを持ちません。

## 4. 取得

呼び出し元の workflow は、token を `venueadd_read_token` として渡します。token が読めないリポジトリの行は、`venueadd-install` を失敗させます。`analytics-deploy` は、その job が成功したあとだけ Analytics API を再起動するので、失敗した取得は、入っている木を変えません。

空の manifest は、git の前に戻ります。

## 5. 返金

manifest の行を外し、deploy を 1 回実行します。適用の手順は、manifest がもう名前を示さない会場ディレクトリを削除します。公開側はそのあと、Read の付与を外します。行が残ったまま Read を外すと、次の deploy は再起動の前に失敗します。
