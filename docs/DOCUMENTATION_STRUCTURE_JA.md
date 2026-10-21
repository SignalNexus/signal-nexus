# Signal Nexus ドキュメント体系

他の文書を読む前に、この文書から始めてください。

この文書は Signal Nexus ドキュメント体系の責務を定義する正本です。

各文書は自分の責務だけに集中し、他文書の責務説明を繰り返しません。

原文は英語版 [DOCUMENTATION_STRUCTURE.md](DOCUMENTATION_STRUCTURE.md) です。

## 文書

| 文書 | アクセス | 役割 | 含むもの | 含まないもの |
| --- | --- | --- | --- | --- |
| Architecture | Public | システム構成の正本 | 部品、データの流れ、公開と非公開の境界 | 導入手順、画面の項目、製品の名前一覧 |
| Buildbook | Starter | 構築手順の正本 | アカウント、仮想マシン、secret、デプロイ、確認 | ポータルの画面、戦略のルール、リサーチ |
| Strategy Integration Guide | Public | TradingView 接続の正本 | `strategy_id`、アラートの本文、Webhook の契約 | シグナルのロジック、インジケーターの設計、リサーチ |
| Screen Specification | Public | 画面仕様の正本 | 目的、分かること、表示するもの、各画面からの移動 | API 設計、データベース設計、構築手順 |
| Screen Relationship Diagram | Public | 画面遷移の正本 | 画面のツリーと、画面から画面への移動 | 項目の一覧、構築手順 |
| Product Specification | Public | 製品定義の正本 | 利用者が得るもの、対応する取引所、製品名 | 導入手順、画面の表示名の定義、価格、どの販売ページを開くか |
| Product Catalog | Public | 商品の案内 | 商品の比較、どの課題にどの商品が対応するか、どの地域の販売ページを開くか | 価格、Checkout、決済の手順、製品の定義 |
| README | Public | 公開の入口と、経験のある運用者向けの参照 | Signal Nexus が何か、実行モード、設定、Webhook と戦略の要約、Build と Start、三つの確認 | このファイルの表、導入の教科書、画面仕様 |
| LICENSE | Public | Community Edition のライセンス | 許可、禁止、ブランド、留保された商用の権利 | 取引リスクの叙述、脆弱性の報告手順 |
| DISCLAIMER | Public | Community Edition を提供する条件 | 助言との境界、資産運用をしないこと、利益を保証しないこと、保証、責任、第三者 | 著作権の許諾 |
| RISK_DISCLOSURE | Public | 暗号資産と無期限市場のリスク | 相場、レバレッジ、流動性、清算、会場、契約、基盤、運用、規制、保存された結果が後日と異なりうること | 利益の保証 |
| SECURITY | Public | 脆弱性の報告方針 | 報告方法、範囲、開示、対応 | 報奨金 |

Buildbook は、公開文書のセットに入らない唯一の正本です。Buildbook は Starter に含まれます。

Buildbook は Signal Nexus の利用に必須ではありません。Buildbook は、参照するデプロイを手順どおり作りたい利用者向けの完全ガイドです。README は、公開の入口であり、経験のある運用者向けの参照です。Buildbook は、その参照実装の手順書です。いまのデプロイ自動化が、どのホストでも動くとは定めません。

## 文書の入手

公開文書:

- README
- Architecture
- Strategy Integration Guide
- Screen Specification
- Screen Relationship Diagram
- Product Specification
- Product Catalog
- LICENSE
- DISCLAIMER
- RISK_DISCLOSURE
- SECURITY

Starter の文書:

- Buildbook

商品のまとめ方は、時期とともに変わり得ます。いま提供している商品の定義の正本は [Product Specification](product/PRODUCT_SPECIFICATION.md) です。

## 商品ごとの入手

この節は、いまの商品がどの資料を含むかを記録します。商品の定義は書きません。

商品は独立しています。Complete は、Starter と、同じ日付の Volume Pack と Profit Pack の束です。どちらのパックの上位版でもありません。VenueAdd は、一つの会場の拡張です。その会場の後の保守を含みます。あとから増えるすべての会場の権利ではなく、他の商品も含みません。

| 資料 | Starter | Volume Pack | Profit Pack | Complete | VenueAdd |
| --- | --- | --- | --- | --- | --- |
| Buildbook | ✅ | ❌ | ❌ | ✅ | ❌ |
| リサーチ資料 | ❌ | ✅ | ✅ | ✅ | ❌ |
| 取引所を広げる資料 | ❌ | ❌ | ❌ | ❌ | ✅ |

Complete の Buildbook は、Complete が Starter を含むためです。Volume Pack と Profit Pack は、別のリサーチ資料を含みます。Complete は、同じ日付の両方を含みます。VenueAdd は、その一つの会場を広げる資料と、その会場の後の保守を含みます。

## 商品との関係

README は、公開の入口です。公開文書に、Starter は要りません。Buildbook は Starter の資料です。上の表は、いまの商品の入手を対応づけます。Product Specification が、製品定義の正本です。

## 読み方

Signal Nexus を検討している。

README → Product Specification → Architecture

どの商品を読むか選ぶ。

README → Product Catalog → Product Specification

プラットフォームを理解したい。

README → Architecture → Product Specification

複数の取引所を運用したい。

README → Architecture → Screen Specification

画面の動きを理解したい。

README → Screen Relationship Diagram → Screen Specification

Signal Nexus をデプロイしたい。

まず README を参照してください。

README は、経験のある運用者向けの公開の入口です。デプロイの入口と確認の流れを含みます。

既に必要なサービスや環境構築に慣れている場合は、README だけで十分な場合があります。

ただし、

- アカウント作成
- クラウド構築
- ネットワーク設定
- セキュリティ設定
- シークレット管理
- バックアップ設定
- 動作確認
- 運用上の注意

まで含めた完全な手順が必要な場合は、Starter が必要です。

→ Buildbook

TradingView とつなぎたい。

README → Strategy Integration Guide

## 関係

```mermaid
graph TD
  README --> DOCUMENTATION_STRUCTURE
  DOCUMENTATION_STRUCTURE --> Architecture
  DOCUMENTATION_STRUCTURE --> Buildbook
  DOCUMENTATION_STRUCTURE --> StrategyIntegrationGuide
  DOCUMENTATION_STRUCTURE --> ProductSpecification
  DOCUMENTATION_STRUCTURE --> ProductCatalog
  DOCUMENTATION_STRUCTURE --> UI
  UI --> ScreenSpecification
  UI --> ScreenRelationshipDiagram
```

```text
README
  |
  v
DOCUMENTATION_STRUCTURE
  |
  +-- Architecture
  +-- Buildbook
  +-- Strategy Integration Guide
  +-- Product Specification
  +-- Product Catalog
  +-- UI
        +-- Screen Specification
        +-- Screen Relationship Diagram
```

## 責務の流れ

README は、Signal Nexus が何かを答えます。

Product Specification は、製品が何かを答えます。

Product Catalog は、どの商品を読むか、どの地域の販売ページを開くかを答えます。価格は定めず、決済も受けません。

Architecture は、どう組まれているかを答えます。

Strategy Integration Guide は、TradingView をどうつなぐかを答えます。

README は、公開の入口であり、経験のある運用者向けの参照です。Buildbook は、参照するデプロイを何も無い状態から再現する手順を答えます。Buildbook を読むには、Starter が必要です。Complete は、Starter を含む束です。

Screen Specification は、運用者が何を見るかを答えます。

Screen Relationship Diagram は、運用者がどう移動するかを答えます。

```mermaid
graph TD
  README["README: Signal Nexus とは何か"] --> ProductSpecification["Product Specification: 製品は何か"]
  ProductSpecification --> Architecture["Architecture: どう組まれているか"]
  Architecture --> StrategyIntegrationGuide["Strategy Integration Guide: TradingView をどうつなぐか"]
  StrategyIntegrationGuide --> Buildbook["Buildbook: 参照するデプロイをどう再現するか"]
  Buildbook --> ScreenSpecification["Screen Specification: 運用者は何を見るか"]
  ScreenSpecification --> ScreenRelationshipDiagram["Screen Relationship Diagram: 運用者はどう移動するか"]
```

