from __future__ import annotations

from android_telemetry_dock.collectors.base import Collector
from android_telemetry_dock.collectors.usage_history import UsageHistoryCollector


def build_collectors(config: dict[str, dict]) -> list[Collector]:
    collectors: list[Collector] = []
    usage_config = config.get("usage_history", {}) or {}
    if usage_config.get("enabled", True):
        collectors.append(UsageHistoryCollector(command=usage_config.get("command", "dumpsys usagestats")))
    return collectors
