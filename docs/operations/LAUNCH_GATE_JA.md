# 起動の条件

原文は英語版 [LAUNCH_GATE.md](LAUNCH_GATE.md) です。

この章は、基盤の実行を始めてよいリポジトリ状態を固定します。ホスト、データベース、Render のサービスは作りません。`workflow_dispatch` も実行しません。pin、7ファイル、成功の正本は [Community Deployment Guide](../COMMUNITY_DEPLOYMENT_GUIDE_JA.md) です。この章は、必須の事実を足しません。

## 1. 固定するリポジトリ状態

実行の前に、呼び出し元から次を記録します。あとの commit は、新しい条件です。

| 名前 | 必要な状態 |
| --- | --- |
| ブランチ | `main` |
| `core-pin` | この環境が動かす公開 SHA |
| `uses` | 同じ SHA |
| `core_sha` | 同じ SHA |
| `venueadd/venues.yaml` | `venues: []` |
| runtime 7ファイル | commit 済み。`confirm` が受け入れる |
| Actions secrets | [基盤の実行](INFRASTRUCTURE_EXECUTION_JA.md) まで空 |
| Actions variables | その章まで空 |
| `VENUEADD_READ_TOKEN` | 未設定 |

## 2. 固定する runtime のハッシュ

固定した commit の 7つの live ファイルに対する `sha256sum` を記録します。最初の成功した deploy は、deploy log とホスト上で、それらのハッシュと一致します。

## 3. 起動の前提

| 依存 | 必要な状態 |
| --- | --- |
| Linux ホストのアカウント | 運用者が、ガイドの下限を満たすホストを 1 台作れる |
| Render のアカウント | 運用者が、この呼び出し元を読む Web Service を 1 つ作れる |

同じ作業の中で、両方が真である必要があります。第 1 節を記録したあとの阻止は、これだけです。

## 4. 実行の開始

第 3 節が真になったら、ホストから [基盤の実行](INFRASTRUCTURE_EXECUTION_JA.md) に従います。SSH 鍵はその作業で作ります。`DEPLOY_ANALYTICS` は、その章が 1 回の dispatch の直前に立てるまで、未設定のままです。

## 5. 成功

[デプロイの準備](DEPLOYMENT_READINESS_JA.md) 第 3 節が満たされ、推奨 SHA が、その deploy が checkout した公開コア SHA と等しいとき、起動は完了です。

## 6. あとに残す作業

VenueAdd の行は、この環境が `venues: []` で成功したあとまで待ちます。最初の deploy まで、manifest は空のままです。
