# Database Access

Android Telemetry Dock は SQLite にデータを保存します。標準設定では DB ファイルは以下です。

```text
data/android_telemetry_dock.sqlite3
```

## アクセス方法

### Python から確認する

追加ツールなしで確認できます。

```powershell
@'
import sqlite3

c = sqlite3.connect("data/android_telemetry_dock.sqlite3")
print(c.execute("select name from sqlite_master where type='table' order by name").fetchall())
'@ | uv run python -
```

### sqlite3 CLI で確認する

`sqlite3` が入っている環境では直接開けます。

```powershell
sqlite3 data/android_telemetry_dock.sqlite3
```

よく使うコマンド:

```sql
.tables
.schema device_status
.schema app_usage_sessions
.headers on
.mode column
```

## 主要テーブル

### device_status

端末ごとの現在状態サマリです。監視画面やヘルスチェックではまずここを見ます。

```sql
SELECT *
FROM device_status
ORDER BY device_id;
```

主な用途:

- 最後に Android アプリから送信が成功した時刻
- 最後の収集が成功したか
- 最後のエラーやスキップ理由の確認

### collection_jobs

Collector の実行履歴です。

```sql
SELECT id, device_id, collector_name, status, error_message, skip_reason, started_at, finished_at
FROM collection_jobs
ORDER BY id DESC
LIMIT 20;
```

### raw_collection_payloads

Android アプリから受け取った raw JSON です。再パースやデバッグ用に使います。

```sql
SELECT id, job_id, device_id, collector_name, length(payload) AS payload_bytes, collected_at
FROM raw_collection_payloads
ORDER BY id DESC
LIMIT 20;
```

### usage_events

Android アプリから受け取った利用履歴イベントの正規化データです。

```sql
SELECT event_time, event_type, package_name, class_name
FROM usage_events
ORDER BY event_time DESC
LIMIT 50;
```

### app_usage_sessions

アプリ利用区間のタイムラインです。下流で1日の利用履歴を作る場合は主にこのテーブルを使います。

```sql
SELECT package_name, class_name, started_at, ended_at, duration_ms, end_reason
FROM app_usage_sessions
ORDER BY started_at DESC
LIMIT 50;
```

### app_metadata

パッケージ名に対する人間向け表示名です。

```sql
SELECT device_id, package_name, display_name, source, updated_at
FROM app_metadata
ORDER BY display_name;
```

## よく使うSQL

### 現在状態を見る

```sql
SELECT
  d.display_name,
  d.current_ip,
  s.presence_state,
  s.last_ping_status,
  s.last_collection_status,
  s.last_seen_at,
  s.last_collected_at,
  s.last_error_message
FROM devices d
LEFT JOIN device_status s ON s.device_id = d.id
WHERE d.enabled = 1
ORDER BY d.id;
```

### 直近の収集結果を見る

```sql
SELECT device_id, collector_name, status, error_message, skip_reason, started_at, finished_at
FROM collection_jobs
ORDER BY id DESC
LIMIT 10;
```

### 1日のアプリ利用タイムラインを見る

```sql
SELECT package_name, class_name, started_at, ended_at, duration_ms, end_reason
FROM app_usage_sessions
WHERE device_id = 'Mobile-Maruka-S24'
  AND started_at >= '2026-05-08T00:00:00'
  AND started_at < '2026-05-09T00:00:00'
ORDER BY started_at;
```

### 1日のアプリ利用タイムラインを表示名付きで見る

```sql
SELECT
  COALESCE(m.display_name, s.package_name) AS app_name,
  s.package_name,
  s.class_name,
  s.started_at,
  s.ended_at,
  s.duration_ms,
  s.end_reason
FROM app_usage_sessions s
LEFT JOIN app_metadata m
  ON m.device_id = s.device_id
 AND m.package_name = s.package_name
WHERE s.device_id = 'Mobile-Maruka-S24'
  AND s.started_at >= '2026-05-08T00:00:00'
  AND s.started_at < '2026-05-09T00:00:00'
ORDER BY s.started_at;
```

### 1日のアプリ別利用時間を見る

```sql
SELECT
  COALESCE(m.display_name, s.package_name) AS app_name,
  s.package_name,
  COUNT(*) AS session_count,
  ROUND(SUM(s.duration_ms) / 1000.0 / 60.0, 1) AS minutes
FROM app_usage_sessions s
LEFT JOIN app_metadata m
  ON m.device_id = s.device_id
 AND m.package_name = s.package_name
WHERE s.device_id = 'Mobile-Maruka-S24'
  AND s.started_at >= '2026-05-08T00:00:00'
  AND s.started_at < '2026-05-09T00:00:00'
GROUP BY app_name, s.package_name
ORDER BY SUM(s.duration_ms) DESC;
```

### 通知や画面ON/OFFを含むイベント列を見る

```sql
SELECT event_time, event_type, package_name, class_name
FROM usage_events
WHERE device_id = 'Mobile-Maruka-S24'
  AND event_time >= '2026-05-08T00:00:00'
  AND event_time < '2026-05-09T00:00:00'
ORDER BY event_time;
```

## CLI から状態確認する

現在状態だけ見たい場合は SQL を直接書かずに次を使えます。

```powershell
uv run android-telemetry-dock --status --config config.yaml
```

保存済み raw payload から正規化テーブルを作り直す場合:

```powershell
uv run android-telemetry-dock --reparse-raw --config config.yaml
```

アプリの人間向け表示名は Android アプリの送信 payload に含まれ、`app_metadata` に保存されます。

## 注意点

- `data/android_telemetry_dock.sqlite3` は実データを含むため Git 管理しません。
- DB を直接更新する場合は、常駐プロセスを止めてから行ってください。
- 読み取りだけなら常駐中でも基本的に問題ありません。
- `raw_collection_payloads` には利用履歴の生データが入るため、共有やバックアップ先に注意してください。
- スキーマ変更は `src/android_telemetry_dock/storage/migrations/*.sql` で管理します。
