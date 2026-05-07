from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from android_telemetry_dock.config import DeviceConfig
from android_telemetry_dock.storage.db import Database


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Device:
    id: str
    display_name: str
    mac_address: str | None
    ip_address: str | None
    adb_port: int
    enabled: bool = True

    @property
    def serial(self) -> str | None:
        if not self.ip_address:
            return None
        return f"{self.ip_address}:{self.adb_port}"


class DeviceRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def upsert_configured_devices(self, configs: list[DeviceConfig]) -> None:
        now = utc_now()
        with self.db.connect() as conn:
            for device in configs:
                conn.execute(
                    """
                    INSERT INTO devices(id, display_name, mac_address, current_ip, adb_port, enabled, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                      display_name=excluded.display_name,
                      mac_address=excluded.mac_address,
                      current_ip=COALESCE(excluded.current_ip, devices.current_ip),
                      adb_port=excluded.adb_port,
                      enabled=excluded.enabled,
                      updated_at=excluded.updated_at
                    """,
                    (device.id, device.display_name, device.mac_address, device.ip_address, device.adb_port, int(device.enabled), now),
                )

    def list_enabled(self) -> list[Device]:
        rows = self.db.fetchall("SELECT * FROM devices WHERE enabled = 1 ORDER BY id")
        return [Device(row["id"], row["display_name"], row["mac_address"], row["current_ip"], row["adb_port"], bool(row["enabled"])) for row in rows]

    def mark_seen(self, device: Device, ip_address: str | None, event_type: str = "seen", details: str | None = None) -> None:
        now = utc_now()
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE devices SET current_ip=COALESCE(?, current_ip), first_seen_at=COALESCE(first_seen_at, ?), last_seen_at=?, updated_at=? WHERE id=?",
                (ip_address, now, now, now, device.id),
            )
            conn.execute(
                "INSERT INTO device_presence_events(device_id, event_type, ip_address, mac_address, detected_at, details) VALUES (?, ?, ?, ?, ?, ?)",
                (device.id, event_type, ip_address or device.ip_address, device.mac_address, now, details),
            )

    def mark_collected(self, device_id: str) -> None:
        now = utc_now()
        self.db.execute("UPDATE devices SET last_collected_at=?, updated_at=? WHERE id=?", (now, now, device_id))
