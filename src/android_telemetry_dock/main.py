from __future__ import annotations

import argparse
import logging

from android_telemetry_dock.adb.manager import AdbManager
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
    DeviceRepository(db).upsert_configured_devices(config.devices)
    rows = db.fetchall(
        """
        SELECT
          d.id,
          d.display_name,
          d.current_ip,
          d.adb_port,
          s.presence_state,
          s.last_ping_status,
          s.last_seen_at,
          s.adb_state,
          s.last_adb_checked_at,
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
        print(f"  endpoint: {row['current_ip']}:{row['adb_port']}")
        print(f"  presence: {row['presence_state'] or 'unknown'} / ping={row['last_ping_status'] or 'unknown'} / last_seen={row['last_seen_at'] or '-'}")
        print(f"  adb: {row['adb_state'] or 'unknown'} / checked={row['last_adb_checked_at'] or '-'}")
        print(f"  collection: {row['last_collection_status'] or 'unknown'} / last_collected={row['last_collected_at'] or '-'}")
        if row["last_error_message"]:
            print(f"  last_error: {row['last_error_message']}")
        print(f"  updated: {row['updated_at'] or '-'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect Android telemetry from known home-network devices")
    parser.add_argument("--config", help="Path to YAML config. Defaults to ATD_CONFIG or ./config.yaml")
    parser.add_argument("--once", action="store_true", help="Run one scheduler tick and exit")
    parser.add_argument("--reparse-raw", action="store_true", help="Rebuild normalized usage tables from saved raw payloads and exit")
    parser.add_argument("--status", action="store_true", help="Print current device monitoring status and exit")
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
    scheduler = build_scheduler(args.config)
    if args.once:
        scheduler.tick()
    else:
        scheduler.run_forever()


if __name__ == "__main__":
    main()
