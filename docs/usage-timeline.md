# Usage Timeline Data

Android Telemetry Dock は `dumpsys usagestats` の出力を、再処理用の raw payload と、下流で扱いやすい正規化済みデータの両方として保存します。

## 保存レイヤー

### raw_collection_payloads

ADB から取得した `dumpsys usagestats` の出力を、そのまま `payload` に保存します。

用途:

- パーサー改善後の再パース
- 端末や Android バージョンごとの出力差分調査
- 正規化データに欠落があった場合の確認

### usage_events

`dumpsys usagestats` の各イベント行を正規化して保存します。

主なカラム:

- `device_id`: 端末ID
- `package_name`: アプリのパッケージ名
- `event_type`: `ACTIVITY_RESUMED`, `ACTIVITY_PAUSED`, `SCREEN_INTERACTIVE` など
- `event_time`: イベント発生時刻。`time="YYYY-MM-DD HH:MM:SS"` または `lastTimeUsed` から生成
- `class_name`: Activity class
- `task_root_package`: task root package
- `task_root_class`: task root class
- `instance_id`: Android が出力する Activity instance ID
- `raw_line`: 元の1行

通知、画面ON/OFF、ロック解除、アプリ状態遷移などのイベント単位のタイムラインにはこのテーブルを使います。

### app_usage_sessions

アプリ利用タイムライン用の派生テーブルです。`usage_events` からアプリが前面に出ていた区間を生成します。

主なカラム:

- `device_id`: 端末ID
- `package_name`: 利用されたアプリのパッケージ名
- `class_name`: 開始時点の Activity class
- `started_at`: 利用開始時刻
- `ended_at`: 利用終了時刻
- `duration_ms`: 利用時間
- `end_reason`: 終了理由
- `start_event_type`: 通常は `ACTIVITY_RESUMED`
- `end_event_type`: `ACTIVITY_PAUSED`, `ACTIVITY_STOPPED`, `SCREEN_NON_INTERACTIVE` など

## セッション生成ルール

現在の実装では、以下のルールで `app_usage_sessions` を生成します。

1. `ACTIVITY_RESUMED` で新しいセッションを開始します。
2. 同じ `package_name` の `ACTIVITY_PAUSED` または `ACTIVITY_STOPPED` でセッションを終了します。
3. 別アプリの `ACTIVITY_RESUMED` が来た場合、直前のセッションを `activity_switch` として終了し、新しいセッションを開始します。
4. `SCREEN_NON_INTERACTIVE` が来た場合、開いているセッションを `screen_non_interactive` として終了します。

## 1日のタイムライン例

アプリ利用区間:

```sql
SELECT package_name, class_name, started_at, ended_at, duration_ms, end_reason
FROM app_usage_sessions
WHERE device_id = 'Mobile-Maruka-S24'
  AND started_at >= '2026-05-08T00:00:00'
  AND started_at < '2026-05-09T00:00:00'
ORDER BY started_at;
```

画面ON/OFFや通知を含むイベント列:

```sql
SELECT event_time, event_type, package_name, class_name
FROM usage_events
WHERE device_id = 'Mobile-Maruka-S24'
  AND event_time >= '2026-05-08T00:00:00'
  AND event_time < '2026-05-09T00:00:00'
ORDER BY event_time;
```

## 注意点

- `event_time` は端末が出力した時刻を正規化した値です。`time="YYYY-MM-DD HH:MM:SS"` 形式の場合はタイムゾーンなしのローカル時刻として保存します。
- Android やメーカーの実装差により、イベント種別や行の形式は変わる可能性があります。
- raw payload は残しているため、パーサー改善後に再パースできます。
