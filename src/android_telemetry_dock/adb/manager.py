from __future__ import annotations

from dataclasses import dataclass
import subprocess
from typing import Sequence

from android_telemetry_dock.presence.devices import Device, utc_now
from android_telemetry_dock.storage.db import Database


@dataclass(frozen=True)
class AdbResult:
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class AdbDeviceState:
    serial: str
    state: str
    message: str | None = None


class AdbManager:
    def __init__(self, db: Database, adb_path: str = "adb", timeout_seconds: int = 30) -> None:
        self.db = db
        self.adb_path = adb_path
        self.timeout_seconds = timeout_seconds

    def run(self, args: Sequence[str], timeout_seconds: int | None = None) -> AdbResult:
        completed = subprocess.run(
            [self.adb_path, *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds or self.timeout_seconds,
            check=False,
        )
        stdout = completed.stdout.decode("utf-8", errors="replace") if completed.stdout else ""
        stderr = completed.stderr.decode("utf-8", errors="replace") if completed.stderr else ""
        return AdbResult(completed.returncode, stdout, stderr)

    def connect(self, device: Device) -> AdbDeviceState:
        if not device.serial:
            self.record_event(device.id, None, "failed", "device has no IP address")
            return AdbDeviceState("", "missing_ip", "device has no IP address")
        result = self.run(["connect", device.serial])
        state = self.get_state(device.serial)
        status = "connected" if state == "device" else state
        message = (result.stdout + result.stderr).strip()
        self.record_event(device.id, device.serial, status, message)
        return AdbDeviceState(device.serial, state, message)

    def devices(self) -> list[AdbDeviceState]:
        result = self.run(["devices"])
        states: list[AdbDeviceState] = []
        for line in result.stdout.splitlines()[1:]:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 2:
                states.append(AdbDeviceState(parts[0], parts[1]))
        return states

    def get_state(self, serial: str) -> str:
        for device in self.devices():
            if device.serial == serial:
                return device.state
        return "disconnected"

    def shell(self, serial: str, command: str, timeout_seconds: int = 120) -> AdbResult:
        return self.run(["-s", serial, "shell", command], timeout_seconds=timeout_seconds)

    def record_event(self, device_id: str, serial: str | None, status: str, message: str | None) -> None:
        self.db.execute(
            "INSERT INTO adb_connection_events(device_id, serial, status, message, occurred_at) VALUES (?, ?, ?, ?, ?)",
            (device_id, serial, status, message, utc_now()),
        )
