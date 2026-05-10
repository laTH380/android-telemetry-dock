from __future__ import annotations

import argparse
import logging

from android_telemetry_dock.adb.manager import AdbManager
from android_telemetry_dock.api_server import TelemetryApiServer
from android_telemetry_dock.collectors.app_metadata import refresh_app_metadata
from android_telemetry_dock.collectors.registry import build_collectors
from android_telemetry_dock.config import load_config
from android_telemetry_dock.maintenance import reparse_usage_history_raw_payloads
from android_telemetry_dock.presence.devices import DeviceRepository
from android_telemetry_dock.presence.scanner import PresenceScanner
from android_telemetry_dock.scheduler import Scheduler
from android_telemetry_dock.storage.db import Database


def build_scheduler(config_path: str | None = None) -> Scheduler:
    config = load_config(config_path)
    db = Database(config.database_path)
    db.initialize()
    devices = DeviceRepository(db)
    devices.upsert_configured_devices(config.devices)
    scanner = PresenceScanner(config.scan)
    adb = AdbManager(db)
    collectors = build_collectors(config.collectors)
    return Scheduler(config, db, devices, scanner, adb, collectors)


def print_device_status(config_path: str | None = None) -> None:
    config = load_config(config_path)
    db = Database(config.database_path)
    db.initialize()
    rows = db.fetchall(
        """
        SELECT
          d.id,
          d.display_name,
          d.current_ip,
          s.presence_state,
          s.last_ping_status,
          s.last_seen_at,
          s.last_collection_status,
          s.last_collected_at,
          s.last_error_message,
          s.updated_at
        FROM devices d
        LEFT JOIN device_status s ON s.device_id = d.id
        WHERE d.enabled = 1
        ORDER BY d.id
        """
    )
    if not rows:
        print("No devices registered.")
        return
    for row in rows:
        print(f"{row['id']} ({row['display_name']})")
        if row["current_ip"]:
            print(f"  endpoint: {row['current_ip']}")
        if row["presence_state"] or row["last_ping_status"] or row["last_seen_at"]:
            print(f"  presence: {row['presence_state'] or 'unknown'} / ping={row['last_ping_status'] or 'unknown'} / last_seen={row['last_seen_at'] or '-'}")
        print(f"  collection: {row['last_collection_status'] or 'unknown'} / last_collected={row['last_collected_at'] or '-'}")
        if row["last_error_message"]:
            print(f"  last_error: {row['last_error_message']}")
        print(f"  updated: {row['updated_at'] or '-'}")


def refresh_metadata(config_path: str | None = None, limit: int = 25) -> None:
    config = load_config(config_path)
    db = Database(config.database_path)
    db.initialize()
    devices = DeviceRepository(db)
    devices.upsert_configured_devices(config.devices)
    adb = AdbManager(db)
    package_rows = db.fetchall(
        """
        SELECT package_name
        FROM app_usage_sessions
        GROUP BY package_name
        ORDER BY SUM(duration_ms) DESC
        """
    )
    package_names = {row["package_name"] for row in package_rows}
    for device in devices.list_enabled():
        count = refresh_app_metadata(db, device, adb, package_names, limit=limit if limit > 0 else None)
        logging.getLogger(__name__).info("refreshed %s app display names for %s", count, device.id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Receive Android telemetry from the mobile app and store it in SQLite")
    parser.add_argument("--config", help="Path to YAML config. Defaults to ATD_CONFIG or ./config.yaml")
    parser.add_argument("--once", action="store_true", help="Run one scheduler tick and exit")
    parser.add_argument("--reparse-raw", action="store_true", help="Rebuild normalized usage tables from saved raw payloads and exit")
    parser.add_argument("--refresh-app-metadata", action="store_true", help="Refresh app display names from device APK metadata and exit")
    parser.add_argument("--metadata-limit", type=int, default=25, help="Maximum packages to inspect when refreshing app metadata. Use 0 for all.")
    parser.add_argument("--status", action="store_true", help="Print current device monitoring status and exit")
    parser.add_argument("--serve-api", action="store_true", help="Run local HTTP API for mobile telemetry uploads")
    parser.add_argument("--api-host", default="0.0.0.0", help="Host for --serve-api")
    parser.add_argument("--api-port", type=int, default=8080, help="Port for --serve-api")
    parser.add_argument("--api-token", help="Bearer token required by --serve-api")
    parser.add_argument("--log-level", default="INFO", help="Python logging level")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if args.status:
        print_device_status(args.config)
        return
    if args.reparse_raw:
        config = load_config(args.config)
        db = Database(config.database_path)
        db.initialize()
        count = reparse_usage_history_raw_payloads(db)
        logging.getLogger(__name__).info("reparsed %s usage_history raw payloads", count)
        return
    if args.refresh_app_metadata:
        refresh_metadata(args.config, args.metadata_limit)
        return
    if args.serve_api:
        config = load_config(args.config)
        db = Database(config.database_path)
        db.initialize()
        TelemetryApiServer(db, args.api_host, args.api_port, args.api_token).serve_forever()
        return
    scheduler = build_scheduler(args.config)
    if args.once:
        scheduler.tick()
    else:
        scheduler.run_forever()


if __name__ == "__main__":
    main()
