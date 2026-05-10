# Mobile Android App

`mobile/android` は Android 端末側で利用履歴を取得し、PC の Android Telemetry Dock API へ送信する軽量アプリです。

現在の推奨構成は、PC から端末へ取りに行く方式ではなく、端末からPCへ送る push 型です。Wireless ADB での収集運用は廃止しました。

## 構成

```text
mobile/android
  app/src/main/java/dev/local/androidtelemetrydock
    MainActivity.java
    UsagePayloadBuilder.java
    TelemetryUploader.java
    TelemetryUploadJobService.java
    TelemetryScheduler.java
```

主な処理:

- `UsageStatsManager` で利用イベントを取得
- `PackageManager` でアプリ表示名を取得
- `app_usage_sessions` 相当の利用区間を端末側で生成
- 未送信分を1時間単位でPC側APIへ JSON POST
- `JobScheduler` で15分周期送信
- 起動後も `BOOT_COMPLETED` で再スケジュール

## PC側APIを起動する

PCのIP例が `10.216.78.25` の場合:

```powershell
uv run android-telemetry-dock --serve-api --api-host 0.0.0.0 --api-port 8080 --api-token local-token --config config.yaml
```

疎通確認:

```powershell
curl http://10.216.78.25:8080/api/health
```

エミュレータからPC上のAPIへ送る場合は、Androidアプリの Server URL に以下を設定します。

```text
http://10.0.2.2:8080
```

実機から送る場合は、PCのLAN IPを使います。

```text
http://10.216.78.25:8080
```

## Androidアプリの設定

アプリ画面で以下を設定します。

- Server URL: `http://10.216.78.25:8080`
- Auth token: `local-token`
- Device ID: `Mobile-Maruka-S24` など、PC側DBで使う端末ID

その後、`Open usage access settings` から Usage Access を許可します。

アプリ表示名を広く取得するため、Manifest では `QUERY_ALL_PACKAGES` を宣言しています。ローカル利用・自分の端末向けの APK として使う前提です。

## 送信タイミング

手動確認:

- `Send now` ボタンで即時送信

定期送信:

- `Schedule every 15 minutes` ボタンで `JobScheduler` を登録
- Android の制約により、実行時刻は厳密な15分ぴったりではありません
- ネットワーク条件は `NETWORK_TYPE_UNMETERED` です
- 対象LANにいない場合はPC APIへ到達できないため失敗し、次回ジョブで再試行します
- 端末側に最後に成功した `window_end` を保存し、次回はその続きから送ります。
- 送信は1時間単位のチャンクに分け、1回の実行では最大24チャンクまで送ります。
- チャンクごとに成功した時点でカーソルを進めます。途中で失敗した場合は、次回そのチャンクから再試行します。
- 境界欠落を避けるため5分重ねて送ります。PC側DBは重複イベント・重複セッションを `INSERT OR IGNORE` と一意インデックスで抑止します。

## ビルド

Android Studio で `mobile/android` を開いて `app` を実行します。

CLIでビルドする場合は JDK と Gradle が必要です。

```powershell
cd mobile/android
gradle :app:assembleDebug
```

このリポジトリには Gradle Wrapper を含めています。Android Studioで開くか、`gradlew` を使ってビルドしてください。

## 送信JSON

```json
{
  "device_id": "Mobile-Maruka-S24",
  "device_name": "SC-51E",
  "collected_at": "2026-05-10T12:00:00Z",
  "window_start": "2026-05-10T11:45:00Z",
  "window_end": "2026-05-10T12:00:00Z",
  "events": [
    {
      "package_name": "com.google.android.youtube",
      "display_name": "YouTube",
      "event_type": "ACTIVITY_RESUMED",
      "event_time": "2026-05-10T11:50:00Z",
      "class_name": "com.google.android.apps.youtube.app.WatchWhileActivity"
    }
  ],
  "sessions": [
    {
      "package_name": "com.google.android.youtube",
      "display_name": "YouTube",
      "started_at": "2026-05-10T11:50:00Z",
      "ended_at": "2026-05-10T11:55:00Z",
      "duration_ms": 300000,
      "end_reason": "activity_paused"
    }
  ]
}
```

PC側では以下に保存します。

- `raw_collection_payloads`
- `usage_events`
- `app_usage_sessions`
- `app_metadata`
- `collection_jobs`
