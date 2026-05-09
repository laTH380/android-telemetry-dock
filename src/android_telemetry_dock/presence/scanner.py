from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import platform
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

from android_telemetry_dock.config import ScanConfig
from android_telemetry_dock.presence.devices import Device


@dataclass(frozen=True)
class PresenceResult:
    device: Device
    present: bool
    ip_address: str | None
    details: str


class PresenceScanner:
    def __init__(self, config: ScanConfig) -> None:
        self.config = config

    def scan(self, devices: list[Device]) -> list[PresenceResult]:
        return [self._check_device(device) for device in devices]

    def _check_device(self, device: Device) -> PresenceResult:
        candidates = [device.ip_address] if device.ip_address else []
        if not candidates:
            return PresenceResult(device, False, None, "no ip address configured or learned")
        for ip_address in candidates:
            if ip_address and self._ping(ip_address):
                return PresenceResult(device, True, ip_address, "ping reply")
        return PresenceResult(device, False, device.ip_address, "no ping reply")

    def _ping(self, ip_address: str) -> bool:
        system = platform.system().lower()
        timeout = max(1, int(self.config.timeout_seconds))
        if system == "windows":
            command = ["ping", "-n", "1", "-w", str(timeout * 1000), ip_address]
        else:
            timeout_flag = "-t" if system == "darwin" else "-W"
            command = ["ping", "-c", "1", timeout_flag, str(timeout), ip_address]
        result = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0

    def scan_cidr(self) -> list[str]:
        network = ipaddress.ip_network(self.config.cidr, strict=False)
        addresses = [str(ip) for ip in network.hosts()]
        found: list[str] = []
        with ThreadPoolExecutor(max_workers=64) as executor:
            future_map = {executor.submit(self._ping, ip): ip for ip in addresses}
            for future in as_completed(future_map):
                if future.result():
                    found.append(future_map[future])
        return sorted(found)
