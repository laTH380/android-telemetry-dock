# Monitoring Data

Android Telemetry Dock は収集履歴とは別に、現在状態を `device_status` に保存します。

現在の運用では Android アプリが PC 側 API へ送信するため、主に「最後に送信できたか」「最後のエラーは何か」を見ます。

## device_status

端末ごとに1行の状態サマリです。モニタリング画面やCLIは、このテーブルを読むだけで現在状態を表示できます。

主なカラム:

- `device_id`: 端末ID
- `last_collection_status`: `success`, `partial_success`, `failed`, `skipped`, `running`
- `last_collected_at`: 最後に受信・保存が成功した時刻
- `last_error_message`: 最後のエラーまたはスキップ理由
- `updated_at`: 状態サマリの最終更新時刻

旧 ADB 収集用の互換カラムとして `presence_state`, `last_ping_status`, `adb_state`, `last_adb_checked_at` も残っています。Android アプリ送信運用では通常使いません。

## 更新タイミング

### Android アプリから送信されたとき

PC 側 API が `/api/telemetry/usage` を受信し、DB 保存に成功すると以下を更新します。

- `last_collection_status`
- `last_collected_at`
- `last_error_message`
- `updated_at`

`last_collected_at` は保存が成功したときに更新されます。

### 送信に失敗したとき

Android アプリが PC 側 API に到達できない場合、PC 側 DB は更新されません。端末側のアプリ画面に送信エラーが表示されます。

PC 側 API までは届いたが保存で失敗した場合は、`collection_jobs` と `device_status.last_error_message` を確認します。

## CLI

現在状態を表示します。

```powershell
uv run android-telemetry-dock --status --config config.yaml
```

直近の受信履歴:

```sql
SELECT device_id, collector_name, status, error_message, started_at, finished_at
FROM collection_jobs
ORDER BY id DESC
LIMIT 20;
```

## 関連する履歴テーブル

`device_status` は現在状態のサマリです。過去の詳細履歴は以下を参照します。

- `collection_jobs`: 受信・保存ジョブ履歴
- `raw_collection_payloads`: Android アプリから受け取った raw JSON
- `usage_events`: 利用履歴イベント
- `app_usage_sessions`: アプリ利用区間
