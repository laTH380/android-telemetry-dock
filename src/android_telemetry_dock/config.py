from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import os
import importlib
import importlib.util


@dataclass(frozen=True)
class DeviceConfig:
    id: str
    display_name: str
    mac_address: str | None = None
    ip_address: str | None = None
    adb_port: int = 5555
    enabled: bool = True


@dataclass(frozen=True)
class ScanConfig:
    method: str = "ping"
    cidr: str = "192.168.1.0/24"
    timeout_seconds: float = 1.0


@dataclass(frozen=True)
class AppConfig:
    database_path: str = "data/android_telemetry_dock.sqlite3"
    scan_interval_seconds: int = 60
    presence_confirm_seconds: int = 180
    absence_confirm_seconds: int = 600
    arrival_cooldown_seconds: int = 1800
    periodic_interval_seconds: int = 3600
    collect_on_arrival: bool = True
    collect_periodically: bool = True
    scan: ScanConfig = field(default_factory=ScanConfig)
    collectors: dict[str, dict[str, Any]] = field(default_factory=lambda: {"usage_history": {"enabled": True}})
    devices: list[DeviceConfig] = field(default_factory=list)


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes", "on"}


def load_config(path: str | os.PathLike[str] | None = None) -> AppConfig:
    config_path = Path(path or os.environ.get("ATD_CONFIG", "config.yaml"))
    data: dict[str, Any] = {}
    if config_path.exists():
        yaml_spec = importlib.util.find_spec("yaml")
        if yaml_spec is None:
            raise RuntimeError("PyYAML is required to read YAML configuration files")
        yaml = importlib.import_module("yaml")
        with config_path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}

    scan_data = data.get("scan", {}) or {}
    devices = [DeviceConfig(**device) for device in data.get("devices", [])]
    return AppConfig(
        database_path=str(data.get("database_path", "data/android_telemetry_dock.sqlite3")),
        scan_interval_seconds=int(data.get("scan_interval_seconds", 60)),
        presence_confirm_seconds=int(data.get("presence_confirm_seconds", 180)),
        absence_confirm_seconds=int(data.get("absence_confirm_seconds", 600)),
        arrival_cooldown_seconds=int(data.get("arrival_cooldown_seconds", 1800)),
        periodic_interval_seconds=int(data.get("periodic_interval_seconds", 3600)),
        collect_on_arrival=_as_bool(data.get("collect_on_arrival"), True),
        collect_periodically=_as_bool(data.get("collect_periodically"), True),
        scan=ScanConfig(**scan_data),
        collectors=data.get("collectors", {"usage_history": {"enabled": True}}) or {},
        devices=devices,
    )
