# Android Telemetry Dock

Android Telemetry Dock は、自宅 PC 上で常駐するローカル API と、Android 端末側の軽量アプリで構成するスマホ利用履歴収集システムです。

端末側アプリが `UsageStatsManager` で利用履歴を取得し、PC 側 API に送信します。PC 側は受け取った JSON を SQLite に保存し、1日の利用タイムラインを作りやすい形に正規化します。

## 主な機能

- `uv` による PC 側 API のローカル常駐起動
- Android アプリからの利用履歴 push 送信
- `usage_events` へのイベント単位保存
- `app_usage_sessions` へのアプリ利用区間保存
- `app_metadata` へのアプリ表示名保存
- `device_status` / `collection_jobs` による収集状態確認
- raw payload の保存と再パース

## 前提条件

利用履歴情報には高いプライバシー性があります。必ず所有者または利用者の明示的な同意がある端末のみ登録してください。

PC 側:

- Python 3.12+
- `uv`
- Android 端末と同じ LAN から到達できる PC

Android 側:

- Android Studio で `mobile/android` を開いて実行
- アプリに Usage Access を許可
- PC 側 API に到達できるネットワーク

## セットアップ

```powershell
Copy-Item config.example.yaml config.yaml
New-Item -ItemType Directory -Force data
uv run android-telemetry-dock --serve-api --api-host 0.0.0.0 --api-port 8080 --api-token local-token --config config.yaml
```

付属スクリプトから起動する場合:

```powershell
.\scripts\start-local.ps1
```

疎通確認:

```powershell
curl http://127.0.0.1:8080/api/health
```

実機から送る場合は、Android アプリの Server URL に PC の LAN IP を指定します。

```text
http://10.216.78.25:8080
```

エミュレータから PC 上の API へ送る場合は以下を使います。

```text
http://10.0.2.2:8080
```

## Android アプリ

`mobile/android` を Android Studio で開き、`app` を実行します。

アプリ画面で以下を設定します。

- Server URL: `http://<PCのLAN IP>:8080`
- Auth token: PC 側起動時の `--api-token`
- Device ID: DB 上で使う端末ID

その後、`Open usage access settings` から Usage Access を許可します。

手動確認は `Send now`、定期送信は `Schedule every 15 minutes` を押します。定期送信は Android の `JobScheduler` を使うため、実行時刻は端末の省電力制御により多少遅れることがあります。アプリを再インストールした後はジョブ登録が消えるため、再度 `Schedule every 15 minutes` を押してください。

詳細は [docs/mobile-app.md](docs/mobile-app.md) を参照してください。

## 設定例

PC 側 API 運用では、基本的に DB パスだけ設定すれば動きます。

```yaml
database_path: data/android_telemetry_dock.sqlite3
```

## 動作確認

直近の受信結果:

```powershell
uv run python -c "import sqlite3; c=sqlite3.connect('data/android_telemetry_dock.sqlite3'); print(c.execute('select device_id, collector_name, status, error_message, started_at, finished_at from collection_jobs order by id desc limit 5').fetchall())"
```

現在状態:

```powershell
uv run android-telemetry-dock --status --config config.yaml
```

1日のアプリ利用タイムライン:

```powershell
uv run python -c "import sqlite3; c=sqlite3.connect('data/android_telemetry_dock.sqlite3'); print(c.execute(\"select package_name, started_at, ended_at, duration_ms from app_usage_sessions order by started_at desc limit 10\").fetchall())"
```

保存済み raw payload から正規化テーブルを再作成する場合:

```powershell
uv run android-telemetry-dock --reparse-raw --config config.yaml
```

## データ

SQLite DB は `data/android_telemetry_dock.sqlite3` に保存します。

主なテーブル:

- `devices`: 登録端末
- `device_status`: 端末ごとの現在状態サマリ
- `collection_jobs`: 受信・収集ジョブ履歴
- `raw_collection_payloads`: アプリから受け取った raw JSON
- `usage_events`: 利用履歴イベントの正規化保存先
- `app_usage_sessions`: アプリ利用区間のタイムライン保存先
- `app_metadata`: パッケージ名と人間向け表示名の対応

詳細:

- [docs/database-access.md](docs/database-access.md)
- [docs/usage-timeline.md](docs/usage-timeline.md)
- [docs/monitoring.md](docs/monitoring.md)

## 送信タイミング

- `Send now` で未送信分を即時送信
- `Schedule every 15 minutes` で定期送信を登録
- 端末再起動後は `BOOT_COMPLETED` で再スケジュール
- PC API に到達できない場合は失敗として記録され、次回ジョブで再送信
- 端末側は最後に成功した送信範囲を保存し、次回はその続きから1時間単位で追いつき送信
- 未送信分が溜まっていても、毎回直近1時間分は送信
- PC 側 DB は一意インデックスと `INSERT OR IGNORE` で重複イベント・重複セッションを抑止

## セキュリティ運用

- このサーバーは信頼済み自宅 LAN 内でのみ運用してください。
- `--api-token` は端末アプリに設定し、第三者に共有しないでください。
- SQLite DB には利用履歴が保存されるため、OS のアクセス権限、バックアップ先、必要に応じたディスク暗号化を設定してください。

## 廃止した方式

PC から Wireless ADB / `adb tcpip` で端末へ接続して取得する運用は廃止しました。現在の推奨方式は、Android アプリから PC 側 API へ送信する push 型です。
