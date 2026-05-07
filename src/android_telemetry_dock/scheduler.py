from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import time

from android_telemetry_dock.adb.manager import AdbManager
from android_telemetry_dock.collectors.base import Collector, CollectionResult
from android_telemetry_dock.config import AppConfig
from android_telemetry_dock.presence.devices import Device, DeviceRepository, utc_now
from android_telemetry_dock.presence.scanner import PresenceScanner
from android_telemetry_dock.storage.db import Database

LOGGER = logging.getLogger(__name__)


@dataclass
class DeviceRuntimeState:
    state: str = "absent"
    first_seen_monotonic: float | None = None
    last_seen_monotonic: float | None = None
    last_absent_monotonic: float | None = None
    last_collection_monotonic: float | None = None
    next_retry_monotonic: float = 0
    retry_delay_seconds: int = 30


class Scheduler:
    def __init__(self, config: AppConfig, db: Database, devices: DeviceRepository, scanner: PresenceScanner, adb: AdbManager, collectors: list[Collector]) -> None:
        self.config = config
        self.db = db
        self.devices = devices
        self.scanner = scanner
        self.adb = adb
        self.collectors = collectors
        self.state: dict[str, DeviceRuntimeState] = {}

    def run_forever(self) -> None:
        LOGGER.info("Android Telemetry Dock scheduler started")
        while True:
            self.tick()
            time.sleep(self.config.scan_interval_seconds)

    def tick(self) -> None:
        devices = self.devices.list_enabled()
        results = self.scanner.scan(devices)
        now = time.monotonic()
        for result in results:
            state = self.state.setdefault(result.device.id, DeviceRuntimeState())
            if result.present:
                self.devices.mark_seen(result.device, result.ip_address, "seen", result.details)
                self._handle_present(result.device, state, now)
            else:
                self._handle_absent(result.device, state, now, result.details)

    def _handle_present(self, device: Device, state: DeviceRuntimeState, now: float) -> None:
        if state.state == "absent":
            state.state = "candidate_present"
            state.first_seen_monotonic = now
        state.last_seen_monotonic = now
        state.last_absent_monotonic = None
        confirmed = state.first_seen_monotonic is not None and now - state.first_seen_monotonic >= self.config.presence_confirm_seconds
        if state.state == "candidate_present" and confirmed:
            state.state = "present"
            if self.config.collect_on_arrival:
                self._maybe_collect(device, state, now, reason="arrival")
        elif state.state == "present" and self.config.collect_periodically:
            self._maybe_collect(device, state, now, reason="periodic")

    def _handle_absent(self, device: Device, state: DeviceRuntimeState, now: float, details: str) -> None:
        if state.last_absent_monotonic is None:
            state.last_absent_monotonic = now
        if now - state.last_absent_monotonic >= self.config.absence_confirm_seconds:
            if state.state != "absent":
                self.devices.mark_seen(device, device.ip_address, "absent", details)
            state.state = "absent"
            state.first_seen_monotonic = None
            state.last_seen_monotonic = None
            state.last_collection_monotonic = None
            state.retry_delay_seconds = 30
        elif state.state == "present":
            state.state = "offline"

    def _maybe_collect(self, device: Device, state: DeviceRuntimeState, now: float, reason: str) -> None:
        if now < state.next_retry_monotonic:
            self._record_skipped_jobs(device.id, f"backoff until {state.next_retry_monotonic:.0f}")
            return
        min_interval = self.config.arrival_cooldown_seconds if reason == "arrival" else self.config.periodic_interval_seconds
        if state.last_collection_monotonic is not None and now - state.last_collection_monotonic < min_interval:
            self._record_skipped_jobs(device.id, f"cooldown for {reason}")
            return
        adb_state = self.adb.connect(device)
        if adb_state.state != "device":
            state.next_retry_monotonic = now + state.retry_delay_seconds
            state.retry_delay_seconds = min(state.retry_delay_seconds * 2, 3600)
            self._record_skipped_jobs(device.id, f"adb state {adb_state.state}")
            return
        any_success = False
        for collector in self.collectors:
            if not collector.supports(device):
                self._create_job(device.id, collector.name, "skipped", skip_reason="collector does not support device")
                continue
            job_id = self._create_job(device.id, collector.name, "running")
            try:
                result = collector.collect(device, self.adb)
                self._save_result(job_id, device.id, collector.name, result)
                any_success = any_success or result.status in {"success", "partial_success"}
            except Exception as exc:  # pragma: no cover - defensive for daemon loop
                LOGGER.exception("collector %s failed for %s", collector.name, device.id)
                self._finish_job(job_id, "failed", str(exc))
        if any_success:
            state.last_collection_monotonic = now
            state.retry_delay_seconds = 30
            self.devices.mark_collected(device.id)

    def _record_skipped_jobs(self, device_id: str, reason: str) -> None:
        for collector in self.collectors:
            self._create_job(device_id, collector.name, "skipped", skip_reason=reason)

    def _create_job(self, device_id: str, collector_name: str, status: str, skip_reason: str | None = None) -> int:
        with self.db.connect() as conn:
            cur = conn.execute(
                "INSERT INTO collection_jobs(device_id, collector_name, status, started_at, finished_at, skip_reason) VALUES (?, ?, ?, ?, ?, ?)",
                (device_id, collector_name, status, utc_now(), utc_now() if status == "skipped" else None, skip_reason),
            )
            return int(cur.lastrowid)

    def _finish_job(self, job_id: int, status: str, error_message: str | None = None) -> None:
        self.db.execute("UPDATE collection_jobs SET status=?, finished_at=?, error_message=? WHERE id=?", (status, utc_now(), error_message, job_id))

    def _save_result(self, job_id: int, device_id: str, collector_name: str, result: CollectionResult) -> None:
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO raw_collection_payloads(job_id, device_id, collector_name, collected_at, payload) VALUES (?, ?, ?, ?, ?)",
                (job_id, device_id, collector_name, utc_now(), result.raw_payload),
            )
            for event in result.usage_events:
                conn.execute(
                    "INSERT INTO usage_events(job_id, device_id, package_name, event_type, event_time, duration_ms, raw_line) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (job_id, device_id, event["package_name"], event.get("event_type"), event.get("event_time"), event.get("duration_ms"), event.get("raw_line")),
                )
            for summary in result.app_usage_summaries:
                conn.execute(
                    "INSERT INTO app_usage_summaries(job_id, device_id, package_name, total_time_ms, last_time_used, window_start, window_end, raw_line) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (job_id, device_id, summary["package_name"], summary.get("total_time_ms"), summary.get("last_time_used"), summary.get("window_start"), summary.get("window_end"), summary.get("raw_line")),
                )
            conn.execute("UPDATE collection_jobs SET status=?, finished_at=?, error_message=? WHERE id=?", (result.status, utc_now(), result.error_message, job_id))
