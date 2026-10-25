# Signal Nexus の構成

文書の役割は [../DOCUMENTATION_STRUCTURE_JA.md](../DOCUMENTATION_STRUCTURE_JA.md) にあります。

この文書は、システム構成の正本です。英語版 [ARCHITECTURE.md](ARCHITECTURE.md) が原文です。

## 概要

Signal Nexus は、自分でホストするプラットフォームです。複数の取引所を、一つの運用で扱います。リサーチから発注までを、一つの流れにします。

複数の取引所を、一つのワークフローで運用します。自分のリサーチを持ち込むことも、リサーチのパッケージを使うこともできます。資金は取引所に残ります。鍵は、自分で動かしている環境に残ります。

下の図は、その順で読む物語です。導入手順ではありません。

### 0. 30秒で見る

```mermaid
graph LR
  TV[TradingView]
  SN[Signal Nexus]
  CEX[CEX]
  DEX[DEX]
  UI[Dashboard Analytics Audit]
  TV --> SN
  SN --> CEX
  SN --> DEX
  SN --> UI
```

シグナルは TradingView で作ります。Signal Nexus が、複数の取引所へ実行します。その動きは、一つの運用画面から見ます。

いまの CEX は、MEXC 現物と MEXC 先物です。いまの DEX は Arcus です。

### 1. ひと目で見る

```mermaid
graph TB
  TradingView --> SignalNexus
  SignalNexus --> MEXC
  SignalNexus --> Arcus
  SignalNexus --> Views
  subgraph Views["見る場所"]
    Portal
    Dashboard
    Trade
    Analytics
    Audit
  end
```

現在の発注先は、MEXC 現物、MEXC 先物、Arcus です。公開版に無い会場は、この構成の発注先ではありません。Portal、Dashboard、Trade、Analytics、Audit は、自分の運用を見る場所です。そこから注文は出せません。

### 2. 部品と流れ

```mermaid
graph TD
  TradingView -->|アラート| Webhook
  Webhook -->|アラート| API["Signal Nexus API"]
  API -->|発注| Engine["発注"]
  Engine -->|発注| Adapter["取引所の接続"]
  Adapter -->|発注| Venue["MEXC または Arcus"]
  Engine -->|記録| Database["PostgreSQL"]
  Database -->|記録| Portal
  GitHub -->|載せる| VM["Oracle VM"]
  Render["Render"] --- Webhook
  VM --- Engine
  VM --- Database
```

アラートは TradingView から Render の Webhook へ進みます。`EXECUTION_MODE` が `live` のとき、発注は Oracle の VM から取引所へ続きます。`dry_run` では、取引所の前で止まります。記録は、その VM の PostgreSQL に残ります。Portal はそれを読みます。

### 3. 外と、自分の環境

```mermaid
graph LR
  subgraph Public["自分のホストの外"]
    TradingView
    MEXC
    Arcus
  end
  subgraph Private["自分の環境"]
    OracleVM["Oracle VM"]
    Secrets["秘密"]
    Engine["発注"]
    Database["PostgreSQL"]
  end
  TradingView -->|アラート| OracleVM
  OracleVM -->|注文| MEXC
  OracleVM -->|注文| Arcus
```

資金は取引所に残ります。鍵は、自分で動かしている環境の秘密に残ります。Signal Nexus は、どちらも預かりません。Your funds, your keys, your infrastructure です。

### 4. 同じワークフローの広がり

```mermaid
graph TD
  Core["公開プラットフォーム"]
  Core --- Starter["Starter: Buildbook"]
  Core --- Volume["Volume Pack"]
  Core --- Profit["Profit Pack"]
  Core --- VenueAdd["VenueAdd: 一つの会場"]
```

これらは、同じワークフローに付きます。階段ではありません。

Starter は Buildbook です。その手順書は、参照するデプロイを何も無い状態から再現します。必要なサービスに慣れていれば、公開の README で足ります。

Volume Pack と Profit Pack は、別々のリサーチのパッケージです。リサーチは非公開です。Complete は、Starter と、同じ日付の両方のパッケージの束です。どちらのパッケージの上位版でもなく、VenueAdd も含みません。

VenueAdd は、公開版に無い一つの会場を、その会場が有効になり手順が文書になったあとで接続します。その会場の保守は、同じ拡張に残ります。日付のリサーチのパッケージではなく、あとから増えるすべての会場の権利でもありません。

各商品が何を含むかは [Product Specification](../product/PRODUCT_SPECIFICATION_JA.md) が定義します。この節は価格を定めません。

## 分かれているもの

Signal Nexus は、リサーチ、発注、運用、インフラを分けています。

自分のリサーチを持ち込むことも、リサーチのパッケージを使うこともできます。一つのワークフローが、複数の取引所に届きます。発注と記録は、自分でホストします。

## 部品

### TradingView

TradingView は、Render の Webhook URL へ HTTP POST を送ります。本文は JSON です。秘密はその本文に入ります。TradingView は認証ヘッダを付けません。

### Render

Render は Webhook のプロセス（`app.main`）を動かします。`POST /webhook` を受け、`GET /health` に応答します。`EXECUTION_MODE` が未設定のときは、記録の経路は残り、注文は出ません。この状態が `dry_run` です。`live` で注文を出します。Render は Postgres を開きません。

### Analytics API

Analytics API は仮想マシン上で動きます。運用の記録と、注文を出すときの引き渡しを受けます。自身の `GET /health` が示すのは、プロセスが応答したことだけです。

### Postgres

Postgres は、Analytics API と同じ仮想マシンで動きます。待ち受けるのはそのマシンの中で、公開インターネットには出しません。監査の行はここに保存します。Discord への配達は、この行の代わりにはなりません。

### Oracle の VM

仮想マシンは、Analytics API、Postgres、そして MEXC と Arcus への発注を置く場所です。この一連の文書でそのマシンの参照環境にしているのは、Ubuntu を動かす Oracle Cloud です。Render は別のホストです。

### GitHub Actions

ワークフロー `analytics-vm` は、デプロイするリポジトリへの push で動きます。ログインの前に、Render の health と SSH ホスト鍵のフィンガープリントを確認します。そのあと、リポジトリをコピーし、secret のファイルを VM に書きます。

ジョブが動くのは、`github.repository` がワークフローに書いたリポジトリ名と一致するときだけです。公開ソースに入っている名前は例です。自分のデプロイでは、その例を自分の `account/repo` に置き換えます。この比較があるので、ワークフローは別のリポジトリを載せません。

### Discord

Render に `DISCORD_WEBHOOK_URL` があるとき、Discord は監査の通知を受け取ります。Discord は届け先です。記録の正本は Postgres です。

### MEXC

MEXC 現物と MEXC 先物は、いまの発注先です。読み取りキーと発注キーは別で、現物と先物も別です。発注キーは仮想マシンにあります。

### Arcus

Arcus は、いまの発注先です。約定の読み取りは `ANALYTICS_ARCUS_ADDRESS` で、署名しません。注文は `ARCUS_ADDRESS` と `ARCUS_SIGNING_KEY` です。設定は二つです。アドレスが別である必要はありません。一つのウォレットを両方の名前に入れてかまいません。署名鍵が要るのは注文だけです。

## データの流れ

1. TradingView がアラートを Render に送る。
2. Render が `WEBHOOK_SECRET` を確認し、`strategy_id`、`symbol`、`action` を `config/strategies.yml` と照合する。
3. 注文額は、その行の `size_quote` である。アラートの本文に `size` も `size_quote` も無い。
4. `dry_run` では、Render は注文を出さない。
5. `live` では、注文は仮想マシン上の Analytics API を通り、MEXC または Arcus へ出る。
6. 監査の行は Postgres に保存される。Render は写しを Discord へ届けられる。

Render の `GET /health` と Analytics API の `GET /health` は、それぞれ、そのプロセスが応答したことだけを示す。

## 公開と非公開の境界

Platform is Public. 公開リポジトリにあるのは、Webhook、発注、Analytics、ポータル、そして自分で動かすデプロイのワークフローです。

Research is Private. 戦略をどう見つけ、どう順位を付け、なぜ公開しなかったかは、この構成には含まれません。公開リポジトリにもありません。
