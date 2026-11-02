# 顧客ライフサイクル

原文は英語版 [CUSTOMER_LIFECYCLE.md](CUSTOMER_LIFECYCLE.md) です。

この章は、1つのデプロイ環境の公開モデルです。デプロイそのものの手順は [Community Deployment Guide](../COMMUNITY_DEPLOYMENT_GUIDE_JA.md) です。この章は、必須の事実を足しません。

## 1. 1つの環境

1つの環境は、`SignalNexus/signal-nexus-deploy` から作る、1つの非公開の呼び出し元リポジトリです。そのリポジトリが、1つの pin、1つの推奨 SHA、1つの Linux ホスト、1つの Render Web Service、購入まで空の会場 manifest を持ちます。

公開コアは `SignalNexus/signal-nexus` に残ります。呼び出し元はコアを fork しません。

## 2. 1つの pin

次の 3 つは、同じ 40 文字の公開 SHA です。

| 名前 | 場所 |
| --- | --- |
| `core-pin` | 呼び出し元のルートにあるファイル |
| `uses` | `.github/workflows/deploy.yml` |
| `core_sha` | 同じ workflow |

3 つが違うと、pin の job は止まります。新しいコアは、3 か所すべてに書きます。最小の SHA は、Community Deployment Guide の値です。

## 3. 1つの推奨 SHA

推奨 SHA は、その環境で最後に成功した deploy が使った公開コアの SHA です。最初の成功した deploy が決めます。あとの成功した deploy が置き換えます。失敗した deploy は置き換えず、前の値も消しません。

別の呼び出し元は、別の記録です。その pin やその推奨 SHA を、この環境へコピーしないでください。

## 4. 購入まで空の manifest

会場を買うまで、`venueadd/venues.yaml` は `venues: []` のままです。空のリストは VenueAdd パッケージを読み込まず、`VENUEADD_READ_TOKEN` も不要です。

`config/venues.yml` は runtime のカタログです。購入リストではありません。カタログで組み込み会場を有効にするかは、`BUILTIN_VENUES` の判断であり、VenueAdd の購入ではありません。

## 5. この章がしないこと

この章は、リポジトリ、ホスト、Render のサービスを作りません。それらの手順は [顧客の作成](CUSTOMER_CREATION_JA.md)、[基盤の実行](INFRASTRUCTURE_EXECUTION_JA.md)、[起動の条件](LAUNCH_GATE_JA.md) です。
