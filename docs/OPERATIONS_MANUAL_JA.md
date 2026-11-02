# Signal Nexus 運用マニュアル

原文は英語版 [OPERATIONS_MANUAL.md](OPERATIONS_MANUAL.md) です。

このファイルは十三章のバインダーです。[Community Deployment Guide](COMMUNITY_DEPLOYMENT_GUIDE_JA.md) の代わりにはなりません。ガイドが、health の確認までの公開の正本です。

README が最初に読む文書です。[ドキュメント体系](DOCUMENTATION_STRUCTURE_JA.md) が役割の索引です。

## 章

| 章 | 文書 | 責務 |
| --- | --- | --- |
| 01 製品運用 | [README](../README_JA.md)、[製品仕様](product/PRODUCT_SPECIFICATION_JA.md)、[製品カタログ](product/PRODUCT_CATALOG_JA.md)、[画面仕様](ui/SCREEN_SPECIFICATION_JA.md)、[画面関係図](ui/SCREEN_RELATIONSHIP_DIAGRAM_JA.md)、[Strategy Integration Guide](integration/STRATEGY_INTEGRATION_GUIDE_JA.md) | 成功確認を満たしたあとの製品、画面、TradingView、日次運用 |
| 02 顧客ライフサイクル | [顧客ライフサイクル](operations/CUSTOMER_LIFECYCLE_JA.md) | 呼び出し元リポジトリ 1つ、pin 1つ、推奨 SHA 1つ、購入まで空の manifest |
| 03 顧客の立ち上げ | [顧客の作成](operations/CUSTOMER_CREATION_JA.md) | template、runtime 7ファイル、`confirm`、`venues: []` |
| 04 基盤の用意 | [基盤の実行](operations/INFRASTRUCTURE_EXECUTION_JA.md) | Linux ホスト、localhost の PostgreSQL 16、Render Web Service、9つの secret、5つの variable |
| 05 デプロイ | [デプロイの準備](operations/DEPLOYMENT_READINESS_JA.md) | `workflow_dispatch` 1回、health、SHA256 7つ |
| 06 会場運用 | [会場ライセンス](operations/VENUE_LICENSE_JA.md)、[AddVenue の運用](operations/ADDVENUE_OPERATIONS_JA.md) | ライセンス、リポジトリアクセス、取得。lighter は作業例であり、必須の導入ではない |
| 07 リリース管理 | [リリース管理](operations/RELEASE_MANAGEMENT_JA.md)、[起動の条件](operations/LAUNCH_GATE_JA.md) | リリースの条件、書き出し、推奨 SHA |
| 08 トラブルシューティング | [トラブルシューティング](operations/TROUBLESHOOTING_JA.md) | ガイドの経路で起きうる失敗 |
| 09 ロールバック | [ロールバック](operations/ROLLBACK_JA.md) | その呼び出し元だけ |
| 10 構成 | [Architecture](architecture/ARCHITECTURE_JA.md)、[AddVenue deployment](architecture/ADDVENUE_DEPLOY_JA.md) | 公開コア、呼び出し元、VenueAdd |
| 11 Starter パッケージ | Starter に含まれる Buildbook | 詳細、チェックリスト、FAQ、画面、失敗を避けるメモ。ガイドが述べない必須の事実はない |
| 12 AddVenue パッケージ | 会場ごとの LICENSE、README、SETUP、RELEASE_NOTES と [AddVenue の運用](operations/ADDVENUE_OPERATIONS_JA.md) | 買った会場 1つ |
| 13 過去の判断 | `business/consideration/design/` | レビューと顧客の証拠。内部。書き出さない |

第 03、04、05、07、09 章は、ガイドが欠く要件を述べません。

## デプロイの読む順

```text
README
  |
  v
COMMUNITY_DEPLOYMENT_GUIDE
  |
  +-- Architecture
  +-- 運用の第 02 章から第 09 章。あとの手順が必要なとき
  +-- Buildbook。任意
```
