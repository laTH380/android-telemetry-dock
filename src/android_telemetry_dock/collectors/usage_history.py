from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from android_telemetry_dock.adb.manager import AdbManager
from android_telemetry_dock.collectors.base import CollectionResult, Collector
from android_telemetry_dock.presence.devices import Device

_PACKAGE_RE = re.compile(r"(?:package|pkg|Package)[:= ]+([A-Za-z0-9_.$-]+)")
_TOTAL_RE = re.compile(r"(?:totalTime(?:InForeground)?|totalTimeForeground|timeUsed)[:= ]+(\d+)")
_LAST_RE = re.compile(r"(?:lastTimeUsed|lastTimeVisible|lastUsed)[:= ]+([^,\s]+(?:\s+[^,\s]+)?)")
_EVENT_RE = re.compile(r"(?:eventType|type)[:= ]+([A-Z_0-9]+)")


class UsageHistoryCollector(Collector):
    name = "usage_history"

    def __init__(self, command: str = "dumpsys usagestats") -> None:
        self.command = command

    def collect(self, device: Device, adb: AdbManager) -> CollectionResult:
        if not device.serial:
            return CollectionResult("", status="failed", error_message="device has no serial")
        result = adb.shell(device.serial, self.command, timeout_seconds=180)
        payload = result.stdout.strip() or result.stderr.strip()
        if result.returncode != 0:
            return CollectionResult(payload, status="failed", error_message=f"ADB shell failed with {result.returncode}")
        events, summaries = parse_usage_stats(payload)
        status = "success" if events or summaries else "partial_success"
        error = None if status == "success" else "raw payload saved, but no usage rows were parsed"
        return CollectionResult(payload, usage_events=events, app_usage_summaries=summaries, status=status, error_message=error)


def parse_usage_stats(payload: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for line in payload.splitlines():
        if not (pkg_match := _PACKAGE_RE.search(line)):
            continue
        package_name = pkg_match.group(1)
        total_match = _TOTAL_RE.search(line)
        event_match = _EVENT_RE.search(line)
        last_match = _LAST_RE.search(line)
        if total_match:
            summaries.append(
                {
                    "package_name": package_name,
                    "total_time_ms": int(total_match.group(1)),
                    "last_time_used": _normalize_time(last_match.group(1)) if last_match else None,
                    "raw_line": line.strip(),
                }
            )
        elif event_match:
            events.append(
                {
                    "package_name": package_name,
                    "event_type": event_match.group(1),
                    "event_time": _normalize_time(last_match.group(1)) if last_match else None,
                    "duration_ms": None,
                    "raw_line": line.strip(),
                }
            )
    return events, summaries


def _normalize_time(value: str) -> str:
    value = value.strip()
    if value.isdigit():
        try:
            return datetime.fromtimestamp(int(value) / 1000).isoformat()
        except (OverflowError, OSError, ValueError):
            return value
    return value
