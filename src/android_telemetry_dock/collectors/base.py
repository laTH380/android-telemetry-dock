from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from android_telemetry_dock.adb.manager import AdbManager
from android_telemetry_dock.presence.devices import Device


@dataclass(frozen=True)
class CollectionResult:
    raw_payload: str
    usage_events: list[dict[str, Any]] = field(default_factory=list)
    app_usage_summaries: list[dict[str, Any]] = field(default_factory=list)
    status: str = "success"
    error_message: str | None = None


class Collector(ABC):
    name: str

    def supports(self, device: Device) -> bool:
        return device.enabled and device.serial is not None

    @abstractmethod
    def collect(self, device: Device, adb: AdbManager) -> CollectionResult:
        raise NotImplementedError
