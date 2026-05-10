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
