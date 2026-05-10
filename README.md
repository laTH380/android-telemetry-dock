# Android Telemetry Dock

Android Telemetry Dock は、自宅 PC 上で常駐し、自宅 LAN に戻ってきた既知の Android 端末から ADB 経由でテレメトリを取得して SQLite に保存するローカルサーバーです。

## 主な機能

- `uv` によるローカル常駐起動
- 自宅ネットワーク上の登録済み Android 端末の在宅検出
- 帰宅判定後の ADB 接続
- 拡張可能な Collector インターフェース
- 初期 Collector として `dumpsys usagestats` によるスマホ利用履歴収集
- SQLite への raw payload と正規化データの保存
- 帰宅時収集、在宅中の定期収集、クールダウン、指数バックオフ

## 前提条件

ADB は強力な管理インターフェースです。対象 Android 端末は、事前に Wireless debugging または `adb tcpip` で自宅 PC の ADB 鍵を認証済みにしてください。未認証端末へ勝手に接続することはできません。

利用履歴情報には高いプライバシー性があります。必ず所有者または利用者の明示的な同意がある端末のみ登録してください。

Windows では Android SDK Platform Tools の `adb.exe` を PATH に追加してください。

```powershell
$env:PATH="$env:LOCALAPPDATA\Android\Sdk\platform-tools;$env:PATH"
adb version
```

## セットアップ

```powershell
Copy-Item config.example.yaml config.yaml
New-Item -ItemType Directory -Force data
uv run android-telemetry-dock --once --config config.yaml
```

`config.yaml` の `devices` と `scan.cidr` は自宅 LAN に合わせて編集してください。

## Android 11 以降の Wireless debugging

Wireless debugging のポートは、初回ペアリング用と接続用で異なります。

1. Android の Wireless debugging 画面で「ペア設定コードによるデバイスのペア設定」を開きます。
2. 表示されたペアリング用 IP:ポートで、PC から一度だけ `adb pair` します。
3. ペアリング成功後、Wireless debugging のメイン画面に戻ります。
4. メイン画面の「IP アドレスとポート」に表示される接続用ポートを `config.yaml` の `adb_port` に設定します。

```powershell
adb pair 192.168.1.42:37123
adb connect 192.168.1.42:42193
adb devices
```

`config.yaml` に設定するのは接続用ポートだけです。ペアリング用ポートとペア設定コードは一時的な値なので保存しません。

## ADB固定ポートの初期設定

常時運用では Wireless debugging のランダムな接続用ポートより、USB で一度 `adb tcpip 5555` を有効化して固定ポートにする方が安定します。

1. 端末をUSB接続し、USBデバッグを許可します。
2. 複数デバイスが見える場合はUSB側のシリアルを指定して `tcpip` を実行します。
3. USBを抜き、Wi-Fi経由で `IP:5555` に接続します。
4. `config.yaml` の `adb_port` を `5555` にします。

```powershell
adb devices
adb -s RFCX40MXASN tcpip 5555
adb connect 192.168.1.42:5555
adb devices
```

端末を再起動した場合などは、再度USB接続して `adb tcpip 5555` が必要になることがあります。

初回接続後、アプリ名の表示用メタデータも更新しておくと、タイムラインを人間向け表示名で見られます。

```powershell
uv run android-telemetry-dock --refresh-app-metadata --metadata-limit 25 --config config.yaml
```

## 起動

1回だけ動作確認する場合:

```powershell
uv run android-telemetry-dock --once --config config.yaml
```

常駐起動する場合:

```powershell
uv run android-telemetry-dock --config config.yaml
```

付属スクリプトから起動する場合:

```powershell
.\scripts\start-local.ps1
```

PowerShell を閉じずに運用する場合はこのままで十分です。Windows 起動時に自動実行したい場合は、上記コマンドをタスク スケジューラに登録してください。作業ディレクトリはこのリポジトリのルートにします。

現在の監視状態を確認する場合:

```powershell
uv run android-telemetry-dock --status --config config.yaml
```

## 設定例

```yaml
database_path: data/android_telemetry_dock.sqlite3
scan_interval_seconds: 60
presence_confirm_seconds: 180
absence_confirm_seconds: 600
arrival_cooldown_seconds: 1800
periodic_interval_seconds: 3600
collect_on_arrival: true
collect_periodically: true
scan:
  method: ping
  cidr: 192.168.1.0/24
  timeout_seconds: 1.0
collectors:
  usage_history:
    enabled: true
    command: dumpsys usagestats
    raw_retention_days: 90
devices:
  - id: my-phone
    display_name: My Android Phone
    mac_address: aa:bb:cc:dd:ee:ff
    ip_address: 192.168.1.42
    # Wireless debugging のメイン画面に表示される接続用ポート。
    # ペア設定コード画面に出る一時的なペアリング用ポートではありません。
    adb_port: 5555
    enabled: true
```

## 動作確認

ADB 接続確認:

```powershell
adb connect 192.168.1.42:5555
adb devices
```

収集確認:

```powershell
uv run android-telemetry-dock --once --config config.yaml
uv run python -c "import sqlite3; c=sqlite3.connect('data/android_telemetry_dock.sqlite3'); print(c.execute('select device_id, status, error_message, skip_reason from collection_jobs order by id desc limit 5').fetchall())"
```

保存済み raw payload から正規化テーブルを再作成する場合:

```powershell
uv run android-telemetry-dock --reparse-raw --config config.yaml
```

## タイムラインデータ

`dumpsys usagestats` の raw payload は `raw_collection_payloads` に保存し、イベント単位の正規化データは `usage_events`、アプリ利用区間は `app_usage_sessions` に保存します。

詳細は [docs/usage-timeline.md](docs/usage-timeline.md) を参照してください。

## モニタリングデータ

端末ごとの現在状態は `device_status` に保存します。ping の最終状態、ADB 接続状態、最後の収集状態、最後のエラーを1行で確認できます。

詳細は [docs/monitoring.md](docs/monitoring.md) を参照してください。

## DBアクセス

SQLite DB は `data/android_telemetry_dock.sqlite3` に保存します。主要テーブル、確認用SQL、CLIでの見方は [docs/database-access.md](docs/database-access.md) を参照してください。

## 取得タイミング

1. 端末が ping に応答すると `candidate_present` になります。
2. `presence_confirm_seconds` の間、継続して検出されると帰宅済み `present` と判定します。
3. `collect_on_arrival` が有効なら、帰宅判定直後に ADB 接続して有効な Collector を実行します。
4. 取得後は `arrival_cooldown_seconds` の間、同一端末の重複取得を抑止します。
5. `collect_periodically` が有効なら、在宅中に `periodic_interval_seconds` ごとに再取得します。
6. ADB 接続失敗時は 30 秒から最大 1 時間まで指数バックオフします。
7. `absence_confirm_seconds` の間、検出できない状態が続くと `absent` に戻します。

## SQLite スキーマ

初期マイグレーションでは以下のテーブルを作成します。

- `devices`: 登録端末、現在 IP、ADB ポート、最終検出・最終収集時刻
- `device_presence_events`: 検出・不在イベント履歴
- `device_status`: 端末ごとの現在状態サマリ
- `adb_connection_events`: ADB 接続結果
- `collection_jobs`: Collector 実行・スキップ・失敗履歴
- `raw_collection_payloads`: ADB から取得した生データ
- `usage_events`: 利用履歴イベントの正規化保存先
- `app_usage_sessions`: アプリ利用区間のタイムライン保存先
- `app_metadata`: パッケージ名と人間向け表示名の対応
- `app_usage_summaries`: アプリ別利用サマリーの正規化保存先

## Collector の追加

新しい情報を収集する場合は `src/android_telemetry_dock/collectors/base.py` の `Collector` を継承し、`collect()` で `CollectionResult` を返します。その後、`collectors/registry.py` に登録し、`config.yaml` の `collectors` で有効化してください。

## セキュリティ運用

- ADB 鍵と Wireless debugging のペアリング情報は共有しないでください。
- このサーバーは信頼済み自宅 LAN 内でのみ運用してください。
- SQLite DB には利用履歴が保存されるため、OS のアクセス権限、バックアップ先、必要に応じたディスク暗号化を設定してください。
