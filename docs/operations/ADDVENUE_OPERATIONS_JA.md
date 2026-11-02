# AddVenue の運用

原文は英語版 [ADDVENUE_OPERATIONS.md](ADDVENUE_OPERATIONS.md) です。

この章は、環境がすでに `venues: []` で成功したあと、manifest に 1 行を足す公開手順です。ライセンスのモデルは [会場ライセンス](VENUE_LICENSE_JA.md) です。workflow の配置は [AddVenue deployment](../architecture/ADDVENUE_DEPLOY_JA.md) です。この章は、Community Deployment Guide の最初の health の経路に、必須の事実を足しません。

lighter は作業例です。必須の導入ではありません。txflow はここでは導入しません。

## 1. この章を始めるとき

環境には、最後に成功した deploy があります。推奨 SHA は決まっています。`venueadd/venues.yaml` はまだ `venues: []` です。`VENUEADD_READ_TOKEN` はまだ未設定です。`SIGNAL_NEXUS_VENUEADD` は未設定です。

[顧客の作成](CUSTOMER_CREATION_JA.md) や最初の [起動の条件](LAUNCH_GATE_JA.md) では、行を足さないでください。

## 2. 1 行

1. 買った会場リポジトリで Read を受けます。
2. [会場ライセンス](VENUE_LICENSE_JA.md) 第 3 節の fine-grained token を作ります。
3. この呼び出し元の `VENUEADD_READ_TOKEN` に置きます。
4. `venueadd/venues.yaml` に 1 件を足します。`import_name`、`repository`、`sha`、`venue_id`、`requirements_file` です。
5. 会場 API の secret は、Analytics API がすでに読む環境ファイルに置きます。workflow はそれらの secret を作りません。
6. `workflow_dispatch` を 1 回実行します。
7. [デプロイの準備](DEPLOYMENT_READINESS_JA.md) の health 確認を繰り返します。log は、その会場リポジトリを名前で示します。install が `SIGNAL_NEXUS_VENUEADD` を立てることがあります。

1 行は 1 会場です。2 つ目の購入は、2 行目と 2 つ目の Read です。

## 3. 作業例としての lighter

買ったパッケージが lighter のとき、記録はそのパッケージの SETUP にある `import_name`、リポジトリ、commit、`venue_id`、`requirements_file` を使います。取得は credential helper とユーザー名 `x-access-token` を使います。その詳細は [トラブルシューティング](TROUBLESHOOTING_JA.md) です。

この章は lighter を必須にしません。会場を一度も買わない環境は、`venues: []` のままです。

## 4. この章がしないこと

txflow は導入しません。health の確認のために会場を入れろとは書きません。パッケージのファイルは AddVenue パッケージに残します。LICENSE、README、SETUP、RELEASE_NOTES です。
