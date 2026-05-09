from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from android_telemetry_dock.adb.manager import AdbManager
from android_telemetry_dock.collectors.base import CollectionResult, Collector
from android_telemetry_dock.presence.devices import Device

_PACKAGE_RE = re.compile(r"(?:package|pkg|Package)[:= ]+([A-Za-z0-9_.$-]+)")
_TOTAL_RE = re.compile(r"(?:totalTime(?:InForeground)?|totalTimeForeground|timeUsed)[:= ]+(\d+)")
_LAST_RE = re.compile(r"(?:lastTimeUsed|lastTimeVisible|lastUsed)[:= ]+([^,\s]+(?:\s+[^,\s]+)?)")
_EVENT_RE = re.compile(r"(?:eventType|type)[:= ]+([A-Z_0-9]+)")
_FIELD_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=(\"[^\"]*\"|[^,\s]+)")


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
        events, sessions, summaries = parse_usage_stats(payload)
        status = "success" if events or sessions or summaries else "partial_success"
        error = None if status == "success" else "raw payload saved, but no usage rows were parsed"
        return CollectionResult(payload, usage_events=events, app_usage_sessions=sessions, app_usage_summaries=summaries, status=status, error_message=error)


def parse_usage_stats(payload: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for line in payload.splitlines():
        line = line.strip()
        if not (pkg_match := _PACKAGE_RE.search(line)):
            continue
        package_name = pkg_match.group(1)
        fields = _parse_fields(line)
        total_match = _TOTAL_RE.search(line)
        event_match = _EVENT_RE.search(line)
        last_match = _LAST_RE.search(line)
        if total_match:
            summaries.append(
                {
                    "package_name": package_name,
                    "total_time_ms": int(total_match.group(1)),
                    "last_time_used": _normalize_time(last_match.group(1)) if last_match else None,
                    "raw_line": line,
                }
            )
        elif event_match:
            events.append(
                {
                    "package_name": package_name,
                    "event_type": event_match.group(1),
                    "event_time": _event_time(fields, last_match),
                    "duration_ms": None,
                    "class_name": fields.get("class"),
                    "task_root_package": fields.get("taskRootPackage"),
                    "task_root_class": fields.get("taskRootClass"),
                    "instance_id": fields.get("instanceId"),
                    "raw_line": line,
                }
            )
    return events, build_app_usage_sessions(events), summaries


def build_app_usage_sessions(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sessions: list[dict[str, Any]] = []
    active: dict[str, Any] | None = None
    timeline = sorted((event for event in events if event.get("event_time")), key=lambda event: event["event_time"])
    for event in timeline:
        event_type = event.get("event_type")
        package_name = event.get("package_name")
        if event_type == "ACTIVITY_RESUMED" and package_name:
            if active is not None:
                sessions.append(_close_session(active, event, "activity_switch"))
            active = _open_session(event)
        elif event_type in {"ACTIVITY_PAUSED", "ACTIVITY_STOPPED"} and active and package_name == active["package_name"]:
            sessions.append(_close_session(active, event, event_type.lower()))
            active = None
        elif event_type == "SCREEN_NON_INTERACTIVE" and active is not None:
            sessions.append(_close_session(active, event, "screen_non_interactive"))
            active = None
    return sessions


def _open_session(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "package_name": event["package_name"],
        "class_name": event.get("class_name"),
        "task_root_package": event.get("task_root_package"),
        "task_root_class": event.get("task_root_class"),
        "started_at": event["event_time"],
        "start_event_type": event.get("event_type"),
    }


def _close_session(active: dict[str, Any], event: dict[str, Any], reason: str) -> dict[str, Any]:
    ended_at = event.get("event_time")
    return {
        **active,
        "ended_at": ended_at,
        "duration_ms": _duration_ms(active.get("started_at"), ended_at),
        "end_reason": reason,
        "end_event_type": event.get("event_type"),
    }


def _duration_ms(started_at: str | None, ended_at: str | None) -> int | None:
    if not started_at or not ended_at:
        return None
    try:
        duration = datetime.fromisoformat(ended_at) - datetime.fromisoformat(started_at)
    except ValueError:
        return None
    return max(0, int(duration.total_seconds() * 1000))


def _parse_fields(line: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for key, value in _FIELD_RE.findall(line):
        fields[key] = value[1:-1] if value.startswith('"') and value.endswith('"') else value
    return fields


def _event_time(fields: dict[str, str], last_match: re.Match[str] | None) -> str | None:
    if value := fields.get("time"):
        return _normalize_time(value)
    if last_match:
        return _normalize_time(last_match.group(1))
    return None


def _normalize_time(value: str) -> str:
    value = value.strip()
    if value.isdigit():
        try:
            return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc).replace(tzinfo=None).isoformat()
        except (OverflowError, OSError, ValueError):
            return value
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return datetime.strptime(value, fmt).isoformat()
        except ValueError:
            continue
    return value
