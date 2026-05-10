from android_telemetry_dock.config import DeviceConfig
from android_telemetry_dock.collectors.base import CollectionResult
from android_telemetry_dock.presence.devices import DeviceRepository
from android_telemetry_dock.scheduler import Scheduler
from android_telemetry_dock.storage.db import Database


def test_initialize_and_upsert_device(tmp_path):
    db = Database(str(tmp_path / "dock.sqlite3"))
    db.initialize()
    repo = DeviceRepository(db)

    repo.upsert_configured_devices([
        DeviceConfig(id="phone", display_name="Phone", mac_address="aa", ip_address="192.168.1.2", adb_port=5555)
    ])

    devices = repo.list_enabled()
    assert len(devices) == 1
    assert devices[0].id == "phone"
    assert devices[0].serial == "192.168.1.2:5555"
    status = db.fetchall("SELECT device_id, presence_state FROM device_status WHERE device_id = ?", ("phone",))[0]
    assert tuple(status) == ("phone", "unknown")

    repo.upsert_configured_devices([
        DeviceConfig(id="tablet", display_name="Tablet", mac_address="bb", ip_address="192.168.1.3", adb_port=5555)
    ])
    enabled_ids = [device.id for device in repo.list_enabled()]
    assert enabled_ids == ["tablet"]


def test_device_status_updates_monitoring_fields(tmp_path):
    db = Database(str(tmp_path / "dock.sqlite3"))
    db.initialize()
    repo = DeviceRepository(db)
    repo.upsert_configured_devices([
        DeviceConfig(id="phone", display_name="Phone", mac_address="aa", ip_address="192.168.1.2", adb_port=5555)
    ])
    device = repo.list_enabled()[0]

    repo.mark_seen(device, "192.168.1.2", "seen", "ping reply")
    repo.mark_adb_state(device.id, "device", "connected")
    repo.mark_collection_status(device.id, "running")
    repo.mark_collected(device.id)

    status = db.fetchall(
        """
        SELECT presence_state, last_ping_status, adb_state, last_collection_status,
               last_seen_at, last_adb_checked_at, last_collected_at, last_error_message
        FROM device_status WHERE device_id = ?
        """,
        ("phone",),
    )[0]
    assert status["presence_state"] == "present"
    assert status["last_ping_status"] == "success"
    assert status["adb_state"] == "device"
    assert status["last_collection_status"] == "success"
    assert status["last_seen_at"] is not None
    assert status["last_adb_checked_at"] is not None
    assert status["last_collected_at"] is not None
    assert status["last_error_message"] is None


def test_save_result_persists_timeline_events_and_sessions(tmp_path):
    db = Database(str(tmp_path / "dock.sqlite3"))
    db.initialize()
    repo = DeviceRepository(db)
    scheduler = Scheduler.__new__(Scheduler)
    scheduler.db = db
    scheduler.devices = repo

    with db.connect() as conn:
        conn.execute(
            "INSERT INTO devices(id, display_name, current_ip, adb_port) VALUES (?, ?, ?, ?)",
            ("phone", "Phone", "192.168.1.2", 5555),
        )
        job_id = conn.execute(
            "INSERT INTO collection_jobs(device_id, collector_name, status) VALUES (?, ?, ?)",
            ("phone", "usage_history", "running"),
        ).lastrowid

    result = CollectionResult(
        raw_payload="raw",
        usage_events=[
            {
                "package_name": "com.example.app",
                "event_type": "ACTIVITY_RESUMED",
                "event_time": "2026-05-08T19:24:44",
                "class_name": "com.example.MainActivity",
                "task_root_package": "com.example.app",
                "task_root_class": "com.example.MainActivity",
                "instance_id": "123",
                "raw_line": "raw line",
            }
        ],
        app_usage_sessions=[
            {
                "package_name": "com.example.app",
                "class_name": "com.example.MainActivity",
                "task_root_package": "com.example.app",
                "task_root_class": "com.example.MainActivity",
                "started_at": "2026-05-08T19:24:44",
                "ended_at": "2026-05-08T19:25:44",
                "duration_ms": 60000,
                "end_reason": "activity_paused",
                "start_event_type": "ACTIVITY_RESUMED",
                "end_event_type": "ACTIVITY_PAUSED",
            }
        ],
    )

    scheduler._save_result(int(job_id), "phone", "usage_history", result)

    event = db.fetchall("SELECT package_name, event_time, class_name, instance_id FROM usage_events")[0]
    session = db.fetchall("SELECT package_name, started_at, ended_at, duration_ms, end_reason FROM app_usage_sessions")[0]
    assert tuple(event) == ("com.example.app", "2026-05-08T19:24:44", "com.example.MainActivity", "123")
    assert tuple(session) == ("com.example.app", "2026-05-08T19:24:44", "2026-05-08T19:25:44", 60000, "activity_paused")


def test_app_metadata_backfilled_from_usage_events(tmp_path):
    db = Database(str(tmp_path / "dock.sqlite3"))
    db.initialize()
    columns = [row["name"] for row in db.fetchall("PRAGMA table_info(app_metadata)")]
    assert columns == ["device_id", "package_name", "display_name", "source", "first_seen_at", "last_seen_at", "updated_at"]
