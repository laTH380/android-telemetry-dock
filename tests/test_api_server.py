import json

from android_telemetry_dock.api_server import save_mobile_usage_payload
from android_telemetry_dock.storage.db import Database


def test_save_mobile_usage_payload(tmp_path):
    db = Database(str(tmp_path / "dock.sqlite3"))
    db.initialize()
    payload = {
        "device_id": "phone",
        "device_name": "Phone",
        "collected_at": "2026-05-10T12:00:00Z",
        "events": [
            {
                "package_name": "com.example.app",
                "display_name": "Example",
                "event_type": "ACTIVITY_RESUMED",
                "event_time": "2026-05-10T11:50:00Z",
                "class_name": "com.example.MainActivity",
            }
        ],
        "sessions": [
            {
                "package_name": "com.example.app",
                "display_name": "Example",
                "started_at": "2026-05-10T11:50:00Z",
                "ended_at": "2026-05-10T11:55:00Z",
                "duration_ms": 300000,
                "end_reason": "activity_paused",
                "start_event_type": "ACTIVITY_RESUMED",
                "end_event_type": "ACTIVITY_PAUSED",
            }
        ],
    }

    result = save_mobile_usage_payload(db, payload, json.dumps(payload))

    assert result["events"] == 1
    assert result["sessions"] == 1
    assert db.fetchall("SELECT display_name, source FROM app_metadata WHERE package_name = ?", ("com.example.app",))[0][:] == ("Example", "mobile")
    assert db.fetchall("SELECT status FROM collection_jobs")[0][0] == "success"
    assert db.fetchall("SELECT package_name FROM app_usage_sessions")[0][0] == "com.example.app"


def test_package_name_fallback_does_not_overwrite_existing_display_name(tmp_path):
    db = Database(str(tmp_path / "dock.sqlite3"))
    db.initialize()
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO devices(id, display_name, enabled, updated_at) VALUES (?, ?, 1, ?)",
            ("phone", "Phone", "2026-05-10T10:00:00Z"),
        )
        conn.execute(
            """
            INSERT INTO app_metadata(device_id, package_name, display_name, source, first_seen_at, last_seen_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("phone", "com.example.app", "Example", "manual", "2026-05-10T10:00:00Z", "2026-05-10T10:00:00Z", "2026-05-10T10:00:00Z"),
        )
    payload = {
        "device_id": "phone",
        "device_name": "Phone",
        "collected_at": "2026-05-10T12:00:00Z",
        "events": [
            {
                "package_name": "com.example.app",
                "display_name": "com.example.app",
                "event_type": "ACTIVITY_RESUMED",
                "event_time": "2026-05-10T11:50:00Z",
            }
        ],
        "sessions": [],
    }

    save_mobile_usage_payload(db, payload, json.dumps(payload))

    row = db.fetchall("SELECT display_name, source FROM app_metadata WHERE package_name = ?", ("com.example.app",))[0]
    assert row[:] == ("Example", "manual")
