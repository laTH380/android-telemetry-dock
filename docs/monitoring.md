# Monitoring Data

Android Telemetry Dock は収集履歴とは別に、現在状態を `device_status` に保存します。

## device_status

端末ごとに1行の状態サマリです。モニタリング画面やCLIは、このテーブルを読むだけで現在状態を表示できます。

主なカラム:

- `device_id`: 端末ID
- `presence_state`: `unknown`, `candidate_present`, `present`, `offline`, `absent`
- `last_ping_status`: `success` または `failed`
- `last_seen_at`: 最後に ping が成功した時刻
- `adb_state`: `device`, `disconnected`, `unauthorized`, `offline`, `missing_ip` など
- `last_adb_checked_at`: 最後に ADB 接続状態を確認した時刻
- `last_collection_status`: `success`, `partial_success`, `failed`, `skipped`, `running`
- `last_collected_at`: 最後に Collector が成功または部分成功した時刻
- `last_error_message`: 最後のエラーまたはスキップ理由
- `updated_at`: 状態サマリの最終更新時刻

## 更新タイミング

### 毎 tick

`scan_interval_seconds` ごとに ping を実行し、以下を更新します。

- `presence_state`
- `last_ping_status`
- `last_seen_at`
- `last_error_message`
- `updated_at`

### ADB 接続確認時

収集フェーズに入って `adb connect` を試したとき、以下を更新します。

- `adb_state`
- `last_adb_checked_at`
- `last_error_message`
- `updated_at`

### Collector 実行時

Collector の実行結果に応じて、以下を更新します。

- `last_collection_status`
- `last_collected_at`
- `last_error_message`
- `updated_at`

`last_collected_at` は Collector が `success` または `partial_success` になったときだけ更新します。

## CLI

現在状態を表示します。

```powershell
uv run android-telemetry-dock --status --config config.yaml
```

`adb_state` が `disconnected` の場合は、まず固定ポートへ接続できるか確認します。

```powershell
Test-NetConnection 192.168.1.42 -Port 5555
adb connect 192.168.1.42:5555
```

端末再起動後などに `5555` が閉じている場合は、USB接続して `adb tcpip 5555` を再実行してください。

## 関連する履歴テーブル

`device_status` は現在状態のサマリです。過去の詳細履歴は以下を参照します。

- `device_presence_events`: ping による在宅検出履歴
- `adb_connection_events`: ADB 接続確認履歴
- `collection_jobs`: Collector 実行履歴
