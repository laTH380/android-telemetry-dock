from __future__ import annotations

import argparse
import logging

from android_telemetry_dock.adb.manager import AdbManager
from android_telemetry_dock.collectors.registry import build_collectors
from android_telemetry_dock.config import load_config
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect Android telemetry from known home-network devices")
    parser.add_argument("--config", help="Path to YAML config. Defaults to ATD_CONFIG or ./config.yaml")
    parser.add_argument("--once", action="store_true", help="Run one scheduler tick and exit")
    parser.add_argument("--log-level", default="INFO", help="Python logging level")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(name)s %(message)s")
    scheduler = build_scheduler(args.config)
    if args.once:
        scheduler.tick()
    else:
        scheduler.run_forever()


if __name__ == "__main__":
    main()
