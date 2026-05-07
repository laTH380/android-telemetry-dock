from android_telemetry_dock.config import DeviceConfig
from android_telemetry_dock.presence.devices import DeviceRepository
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
