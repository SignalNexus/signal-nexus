# 画面仕様

文書の役割は [../DOCUMENTATION_STRUCTURE_JA.md](../DOCUMENTATION_STRUCTURE_JA.md) にあります。

この文書は、画面仕様の正本です。英語版 [SCREEN_SPECIFICATION.md](SCREEN_SPECIFICATION.md) が原文です。

ポータルは運用を読みます。どの画面からも注文は出せません。この文書に数値は載せません。シグナルの見つけ方も書きません。

ログインは、ポータルの前の門です。五つ目の主な画面ではありません。パスワードが合わないあいだ、四つの画面は出ません。

## 概要

Signal Nexus の主な画面は四つです。

- Dashboard
- Trading
- Analytics
- Operations

Performance は五つ目の画面ではありません。Dashboard で運用を読む名前です。Backtest Comparison も五つ目ではありません。Analytics の中の切り替えです。

## 移動

各画面の節に、その画面から開く先を書いています。つながりの全体は [SCREEN_RELATIONSHIP_DIAGRAM_JA.md](SCREEN_RELATIONSHIP_DIAGRAM_JA.md) です。四つの主な画面は、どのページからでも選べます。Trading、Analytics、Operations の中の切り替えは、その画面の中に留まります。

## Dashboard

目的. いまの運用と、アラートが届いているかを見る。

分かること. 今日の結果が月のどこにあるか、建玉のリスクがどれだけあるか、アラートを受け取れているか、決済が一件以上ある戦略はどれか。

主な部品.

- Today
- Risk Summary
- Operations
- System Health
- PnL
- Strategy Summary

表示するもの.

値の名前のいくつかは、いま画面上では日本語です。この文書が説明する内容は、その名前に対応します。

- Today. 今月ここまでの結果、今月の出来高、月目標、その目標に対する進み、まだ必要な額、月末の着地の見通し。折りたたむと、`venues.yml` で `enabled: true` の会場 id ごとにカードが出ます。MEXC の現物と先物は一枚のカードです。無効な id は出しません。
- Risk Summary. 建玉の数と、含みの結果。折りたたむと、取引所ごとの内訳が出ます。
- Operations. これから先の作業と、期限を過ぎた作業の名前、期限、状態。
- System Health. モード（`dry_run` または `live`）、新しい注文を出せるか、集計が読めるか、取り込みが新しいか、直近のアラートの時刻。
- PnL. 日、週、月、年の確定した結果。折りたたむと、同じ期間を取引所ごとに見ます。
- Strategy Summary. 決済が一件以上ある戦略ごとに、名前、取引所、確定した結果、出来高、プロフィットファクター、回数、勝率。

この文書に、その数値は載せません。集計が無いときは、Today、Risk Summary、PnL、Strategy Summary は出ません。System Health と Operations は残ります。

移動. Risk Summary は Trading の Positions を開きます。Operations は Schedule を開きます。Strategy Summary は Analytics の Strategies を開きます。

## Trading

目的. 接続した取引所の口座を読む。

分かること. 何が建っているか、何が約定したか、どの注文がまだ残っているか、残高がいくら使えるか。

主な部品.

- Positions
- Trades
- Open Orders
- Balances

最初に開くのは Positions です。

表示するもの.

- Positions. 建玉の数と、含みの結果。一行は、一つの戦略と一つの銘柄です。含みの結果、保有時間、残数量、取引所、建てた時刻、直近の価格が出ます。価格が無い行は末尾です。
- Trades. すでに付いた約定です。時刻、戦略、取引所、銘柄、売買、戻った額、使った額、数量です。要約は、当日の約定件数と、未分類の件数です。
- Open Orders. 画面を開いたときに残っていた注文です。残数量、経過時間、戦略、銘柄、売買、注文価格、注文種別、注文数量です。この一覧は保存しない、と画面に出ます。現物は買いと売りの件数、先物はショートとカバーの件数、Arcus と Lighter はロングとショートの件数です。グリッドに出るのは、`enabled: true` の会場 id だけです。
- Balances. 通貨ごとに、合計、使える額、注文に使っている額です。要約は、USDT の合計、使える額、注文中の額、並んでいるコインの数です。Arcus と Lighter は、評価額、使える額、証拠金、建玉数を出します。Lighter の額は、その建て通貨です。

読めなかった取引所は、読めなかったと出します。ゼロにはしません。

移動. 四つの切り替えは Trading の中です。Dashboard、Analytics、Operations は外側の移動のままです。

## Analytics

目的. 運用を戦略ごと、銘柄ごとに読み、実運用を、自分で保存した数値の横に置く。

分かること. 動きのあった戦略と銘柄はどれか、実運用が保存した参照の横でどう並ぶか。画面は戦略の良し悪しを判定しません。

主な部品.

- Strategies
- Tickers
- Backtest Comparison

最初に開くのは Strategies です。決済の無い戦略と銘柄は出しません。

表示するもの.

- Strategies. 動いている戦略の数、結果がプラスの戦略の数、確定した結果の合計、プロフィットファクターの平均。各行は、確定した結果、出来高、プロフィットファクター、利益率、勝率、回数、戦略名、取引所です。
- Tickers. 同じ要約と列を、銘柄ごとに出します。銘柄と一緒に取引所が出ます。
- Backtest Comparison. 比べた戦略の数、実運用のプロフィットファクターの平均、保存した側の平均、差が最も大きい戦略。各行は、利益率、プロフィットファクター、勝率、回数について、実運用と保存した参照を並べ、保存した期間も出します。

この文書に、その数値は載せません。保存した参照は、自分で残したデータです。ここに公開された結果ではありません。

移動. Dashboard の Strategy Summary は、この画面の Strategies を開きます。Trading と Operations は外側の移動のままです。

## Operations

目的. 期限のある作業と、アラートがどう処理されたかの履歴を見る。

分かること. どの作業が近いか、遅れているか。アラートが受信されたか、拒否されたか、見送られたか、成功したか、失敗したか、重複として破棄されたか。

主な部品.

- Schedule
- Audit Log

最初に開くのは Schedule です。

表示するもの.

- Schedule. 作業の数、直近の数、期限超過の数、次の期限。各行は、作業名、開始日、期限、状態、残日数です。状態は、直近、期限超過、進行中、未着手です。
- Audit Log. イベントの数、成功の数、失敗の数、直近の失敗の時刻。各行は、イベント種別、理由、発生時刻、戦略、銘柄、通知の文面です。この画面の表示は、受信、拒否、見送り、成功、失敗、破棄の六つです。計画は、この六つの中にありません。保護決済に受信の行はありません。Latest Alert は変わりません。理由は `protective_exit stop=<stop_price> mark=<trigger_price>` または `protective_exit take_profit=<take_profit_price> mark=<trigger_price>` です。写しは、今の Sent、Not configured、429 paused のままです。

Audit Log は、時刻順の履歴です。Analytics は運用の集計です。この一覧の代わりにはなりません。

移動. Dashboard の Operations は Schedule を開きます。Trading と Analytics は外側の移動のままです。
