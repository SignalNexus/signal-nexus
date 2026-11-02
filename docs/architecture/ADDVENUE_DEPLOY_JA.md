# AddVenue の配備

このファイルは英語版の日本語版です。正本は [ADDVENUE_DEPLOY.md](ADDVENUE_DEPLOY.md) です。

公開コアに、有料会場のパッケージは含まれません。呼び出し元リポジトリが、core の commit、manifest のパス、SSH のホスト、SSH の利用者、コアのディレクトリ、会場のディレクトリを渡します。共有 workflow には、それらの値を書きません。manifest があるとき、その実行はそこに書いた commit だけを導入します。

## Manifest

配備先ごとに `venueadd/venues.yaml` を一つ置きます。このパスは公開の書き出しには入りません。形の見本は [venues.example.yaml](../../deploy/venueadd/venues.example.yaml) です。

レコードにあるのは `import_name`、`repository`、`sha`、`venue_id`、`requirements_file` だけです。Python の版、秘密の名前、検証コマンド、配備方法、SSH、サービス管理は書きません。

ファイルが無い、または会場が空なら、AddVenue は導入しません。

## リポジトリのアクセス

有料会場のリポジトリは非公開です。顧客は、購入した各リポジトリの Read を持つ outside collaborator であり、公開元の組織のメンバーではありません。顧客は fine-grained personal access token を一つ作ります。resource owner は、会場リポジトリを持つ組織です。権限は Contents: Read です。リポジトリの範囲は、その顧客がすでに読めるリポジトリに従います。

token は、その顧客の deploy リポジトリの secret にだけ置きます。呼び出し元は、それを `venueadd_read_token` として渡します。Signal Nexus は token を保持せず、公開コアにも入れません。

空の manifest は、token が無くても完了します。token が読めないリポジトリの行は、`venueadd-install` を失敗させます。`analytics-deploy` は、その job が成功したあとだけ Analytics API を再起動します。失敗した取得は、導入済みのツリーを変えません。

返金は、manifest の行を外して deploy を一度実行します。apply は、manifest がもう指定しない会場ディレクトリを削除します。そのあと、公開元が Read を外します。行が残ったまま Read を外すと、次の deploy は再起動の前に失敗します。

## workflow の分担

`venueadd-install` は、固定した commit を取得し、一つの lock を解き、本番のローダーで確認します。SSH、サービスファイル、再起動は行いません。

呼び出し元が、リポジトリの変数と secret を `analytics-deploy` へ渡します。lock またはローダーが失敗したときは、再起動まで進みません。会場ディレクトリは、呼び出し元の `venue_directory` です。

## 依存の解決

`uv` が、Core の `requirements.txt`、各会場の固定 commit にある `requirements_file`、[constraints.txt](../../deploy/venueadd/constraints.txt) を一度に解きます。制約は `urllib3==2.8.0` です。

例外は [exceptions.yml](../../deploy/venueadd/exceptions.yml) だけです。いま入っているのは、`lighter-sdk` 1.1.8 が宣言する `urllib3` の上限を外すことです。そのパッケージは、その宣言なしで導入します。解いた lock には `urllib3==2.8.0` が残ります。会場の manifest から例外は足せません。解が無いとき、環境変数も再起動も変わりません。

## Rollback

manifest の `sha` を前の commit に戻し、`analytics-vm` を再実行します。`/opt/signal-nexus/venueadd/<import 名>/` はその commit の内容に置き換わります。`uv pip sync` は lock にある配布物だけを残し、それ以外を消します。例外のパッケージは、外した宣言なしで導入します。戻す前の commit が足した依存は残りません。

## この実行がしないこと

会場の API 秘密は、Analytics API がすでに読んでいる環境ファイルに残します。この workflow は秘密を作りません。新しいマシンには、Arcus と MEXC の鍵と同じように、それらの秘密が先に要ります。

導入先は、呼び出し元が渡した SSH のホストです。コンテナイメージは作らず、2 台目も設定しません。次の実行の前に、呼び出し元のリポジトリへ `DEPLOY_ANALYTICS`、`ANALYTICS_SSH_USER`、`ANALYTICS_CORE_DIRECTORY`、`ANALYTICS_VENUE_DIRECTORY` を設定します。
