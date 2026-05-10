from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any

from android_telemetry_dock.adb.manager import AdbManager
from android_telemetry_dock.presence.devices import Device, utc_now
from android_telemetry_dock.storage.db import Database

_PACKAGE_RE = re.compile(r"^package:(?P<package>[^\s]+)")
_MONKEY_LABEL_RE = re.compile(r"^\s*label:\s*(?P<label>.+?)\s*$", re.IGNORECASE)
_AAPT_LABEL_RE = re.compile(r"^application-label(?:-[^:]+)?:'(?P<label>.*)'$")


def upsert_app_metadata_fallback(db: Database, device_id: str, package_names: set[str]) -> None:
    if not package_names:
        return
    now = utc_now()
    with db.connect() as conn:
        for package_name in sorted(package_names):
            if package_name == "android":
                display_name = "Android System"
                source = "built_in"
            else:
                display_name = package_name
                source = "package_name"
            conn.execute(
                """
                INSERT INTO app_metadata(device_id, package_name, display_name, source, first_seen_at, last_seen_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(device_id, package_name) DO UPDATE SET
                  display_name=excluded.display_name,
                  source=excluded.source,
                  last_seen_at=excluded.last_seen_at,
                  updated_at=excluded.updated_at
                """,
                (device_id, package_name, display_name, source, now, now, now),
            )


def refresh_app_metadata(db: Database, device: Device, adb: AdbManager, package_names: set[str], limit: int | None = None) -> int:
    if not device.serial or not package_names:
        return 0
    installed = _installed_packages(device.serial, adb)
    existing = {
        row["package_name"]: row["source"]
        for row in db.fetchall("SELECT package_name, source FROM app_metadata WHERE device_id = ?", (device.id,))
    }
    pending = [
        package_name
        for package_name in sorted(package_names)
        if package_name in installed and existing.get(package_name) != "device_label"
    ]
    if limit is not None:
        pending = pending[:limit]
    now = utc_now()
    updated = 0
    with db.connect() as conn:
        for package_name in pending:
            display_name = _launcher_label(device.serial, adb, package_name) or _apk_label(device.serial, adb, package_name) or package_name
            source = "device_label" if display_name != package_name else "package_name"
            conn.execute(
                """
                INSERT INTO app_metadata(device_id, package_name, display_name, source, first_seen_at, last_seen_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(device_id, package_name) DO UPDATE SET
                  display_name=excluded.display_name,
                  source=excluded.source,
                  last_seen_at=excluded.last_seen_at,
                  updated_at=excluded.updated_at
                """,
                (device.id, package_name, display_name, source, now, now, now),
            )
            if source == "device_label":
                updated += 1
    return updated


def known_package_names(result: Any) -> set[str]:
    packages: set[str] = set()
    for row in [*result.usage_events, *result.app_usage_sessions, *result.app_usage_summaries]:
        if package_name := row.get("package_name"):
            packages.add(str(package_name))
    return packages


def _installed_packages(serial: str, adb: AdbManager) -> set[str]:
    result = adb.shell(serial, "cmd package list packages", timeout_seconds=60)
    packages: set[str] = set()
    for line in result.stdout.splitlines():
        if match := _PACKAGE_RE.match(line.strip()):
            packages.add(match.group("package"))
    return packages


def _launcher_label(serial: str, adb: AdbManager, package_name: str) -> str | None:
    result = adb.shell(serial, f"monkey -p {package_name} -c android.intent.category.LAUNCHER 0", timeout_seconds=15)
    output = result.stdout + result.stderr
    for line in output.splitlines():
        if match := _MONKEY_LABEL_RE.match(line):
            label = match.group("label").strip()
            return label or None
    return None


def _apk_label(serial: str, adb: AdbManager, package_name: str) -> str | None:
    aapt = _find_aapt()
    if not aapt:
        return None
    result = adb.run(["-s", serial, "shell", "pm", "path", package_name], timeout_seconds=30)
    remote_apk = _base_apk_path(result.stdout)
    if not remote_apk:
        return None
    with tempfile.TemporaryDirectory() as temp_dir:
        local_apk = str(Path(temp_dir) / f"{package_name}.apk")
        pull_result = adb.run(["-s", serial, "pull", remote_apk, local_apk], timeout_seconds=120)
        if pull_result.returncode != 0:
            return None
        completed = subprocess.run(
            [aapt, "dump", "badging", local_apk],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        output = completed.stdout.decode("utf-8", errors="replace")
    for line in output.splitlines():
        if match := _AAPT_LABEL_RE.match(line.strip()):
            label = match.group("label").strip()
            return label or None
    return None


def _base_apk_path(output: str) -> str | None:
    paths = [line.removeprefix("package:").strip() for line in output.splitlines() if line.startswith("package:")]
    for path in paths:
        if path.endswith("/base.apk"):
            return path
    return paths[0] if paths else None


def _find_aapt() -> str | None:
    if path := shutil.which("aapt"):
        return path
    local_app_data = Path.home() / "AppData" / "Local"
    build_tools = local_app_data / "Android" / "Sdk" / "build-tools"
    if build_tools.exists():
        candidates = sorted(build_tools.glob("*/aapt.exe"), reverse=True)
        if candidates:
            return str(candidates[0])
    return None
