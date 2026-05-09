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
            configured_ids = [device.id for device in configs]
            if configured_ids:
                placeholders = ",".join("?" for _ in configured_ids)
                conn.execute(f"UPDATE devices SET enabled = 0, updated_at = ? WHERE id NOT IN ({placeholders})", (now, *configured_ids))
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
                conn.execute(
                    """
                    INSERT INTO device_status(device_id, presence_state, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(device_id) DO UPDATE SET updated_at=excluded.updated_at
                    """,
                    (device.id, "unknown", now),
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
            presence_state = "present" if event_type == "seen" else event_type
            ping_status = "success" if event_type == "seen" else "failed"
            error_message = None if ping_status == "success" else details
            conn.execute(
                """
                INSERT INTO device_status(device_id, presence_state, last_ping_status, last_seen_at, last_error_message, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(device_id) DO UPDATE SET
                  presence_state=excluded.presence_state,
                  last_ping_status=excluded.last_ping_status,
                  last_seen_at=CASE WHEN excluded.last_ping_status = 'success' THEN excluded.last_seen_at ELSE device_status.last_seen_at END,
                  last_error_message=excluded.last_error_message,
                  updated_at=excluded.updated_at
                """,
                (device.id, presence_state, ping_status, now, error_message, now),
            )

    def mark_collected(self, device_id: str) -> None:
        now = utc_now()
        with self.db.connect() as conn:
            conn.execute("UPDATE devices SET last_collected_at=?, updated_at=? WHERE id=?", (now, now, device_id))
            conn.execute(
                """
                INSERT INTO device_status(device_id, last_collection_status, last_collected_at, last_error_message, updated_at)
                VALUES (?, ?, ?, NULL, ?)
                ON CONFLICT(device_id) DO UPDATE SET
                  last_collection_status=excluded.last_collection_status,
                  last_collected_at=excluded.last_collected_at,
                  last_error_message=NULL,
                  updated_at=excluded.updated_at
                """,
                (device_id, "success", now, now),
            )

    def mark_ping_missed(self, device: Device, presence_state: str, details: str | None = None) -> None:
        now = utc_now()
        self.db.execute(
            """
            INSERT INTO device_status(device_id, presence_state, last_ping_status, last_error_message, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(device_id) DO UPDATE SET
              presence_state=excluded.presence_state,
              last_ping_status=excluded.last_ping_status,
              last_error_message=excluded.last_error_message,
              updated_at=excluded.updated_at
            """,
            (device.id, presence_state, "failed", details, now),
        )

    def mark_adb_state(self, device_id: str, adb_state: str, message: str | None = None) -> None:
        now = utc_now()
        error_message = None if adb_state == "device" else message
        self.db.execute(
            """
            INSERT INTO device_status(device_id, adb_state, last_adb_checked_at, last_error_message, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(device_id) DO UPDATE SET
              adb_state=excluded.adb_state,
              last_adb_checked_at=excluded.last_adb_checked_at,
              last_error_message=excluded.last_error_message,
              updated_at=excluded.updated_at
            """,
            (device_id, adb_state, now, error_message, now),
        )

    def mark_collection_status(self, device_id: str, status: str, message: str | None = None) -> None:
        now = utc_now()
        self.db.execute(
            """
            INSERT INTO device_status(device_id, last_collection_status, last_error_message, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(device_id) DO UPDATE SET
              last_collection_status=excluded.last_collection_status,
              last_error_message=excluded.last_error_message,
              updated_at=excluded.updated_at
            """,
            (device_id, status, message, now),
        )
