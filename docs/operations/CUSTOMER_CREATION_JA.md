# 顧客の作成

原文は英語版 [CUSTOMER_CREATION.md](CUSTOMER_CREATION.md) です。

この章は、呼び出し元リポジトリと runtime 7ファイルを作る公開手順です。名前、コマンド、成功条件の正本は [Community Deployment Guide](../COMMUNITY_DEPLOYMENT_GUIDE_JA.md) です。この章は、必須の事実を足しません。

## 1. 呼び出し元リポジトリを作る

1. GitHub で、template `SignalNexus/signal-nexus-deploy` から新しい非公開リポジトリを作ります。
2. template を fork しないでください。template へ push しないでください。
3. `core-pin`、`uses`、`core_sha` が同じ公開 SHA であること、ガイドの最小 SHA 以上であることを確認します。
4. `venueadd/venues.yaml` が `venues: []` であることを確認します。
5. `render-build.sh` があることを確認します。

このリポジトリの所有者は、この環境の運用者です。

## 2. runtime 7ファイルを置く

各 example を live の名前へコピーします。最初の `workflow_dispatch` より前に、live ファイルを commit します。

| Example | Live ファイル |
| --- | --- |
| `config/examples/locale.yml.example` | `config/locale.yml` |
| `config/examples/month_target.yml.example` | `config/month_target.yml` |
| `config/examples/ops_schedule.yml.example` | `config/ops_schedule.yml` |
| `config/examples/protective_exit.yml.example` | `config/protective_exit.yml` |
| `config/examples/strategies.yml.example` | `config/strategies.yml` |
| `config/examples/strategy_results.yml.example` | `config/strategy_results.yml` |
| `config/examples/venues.yml.example` | `config/venues.yml` |

7ファイルとも存在し、中身が必要です。`{}` は拒否されます。`confirm` が検証します。sample の registry は、変えずに commit して構いません。

`venueadd/venues.yaml` は 7ファイルの一つではありません。`venues: []` のままにします。

## 3. あとに残すもの

`VENUEADD_READ_TOKEN` は設定しません。VenueAdd の行は足しません。`BUILTIN_VENUES` がその会場を名前で示さない限り、MEXC や Arcus の secret も設定しません。

9つの secret と 5つの variable は [基盤の実行](INFRASTRUCTURE_EXECUTION_JA.md) まで待ちます。`DEPLOY_ANALYTICS` は、その章が最初の dispatch の直前に立てるまで、未設定のままです。

## 4. 基盤の準備ができた状態

呼び出し元があり、3つの SHA が一致し、7つの live ファイルが commit され、`venues: []` が変わらず、`confirm` が 7ファイルを受け入れるとき、作成は完了です。

ホストと Render Web Service は次の章です。
