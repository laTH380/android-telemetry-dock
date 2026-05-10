from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
from typing import Any

from android_telemetry_dock.presence.devices import utc_now
from android_telemetry_dock.storage.db import Database

LOGGER = logging.getLogger(__name__)


def _metadata_update_sql() -> str:
    return """
        INSERT INTO app_metadata(device_id, package_name, display_name, source, first_seen_at, last_seen_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(device_id, package_name) DO UPDATE SET
          display_name=CASE
            WHEN excluded.display_name = excluded.package_name
             AND app_metadata.display_name IS NOT NULL
             AND app_metadata.display_name != ''
             AND app_metadata.display_name != app_metadata.package_name
            THEN app_metadata.display_name
            ELSE excluded.display_name
          END,
          source=CASE
            WHEN excluded.display_name = excluded.package_name
             AND app_metadata.display_name IS NOT NULL
             AND app_metadata.display_name != ''
             AND app_metadata.display_name != app_metadata.package_name
            THEN app_metadata.source
            ELSE excluded.source
          END,
          last_seen_at=excluded.last_seen_at,
          updated_at=excluded.updated_at
        """


class TelemetryApiServer:
    def __init__(self, db: Database, host: str, port: int, auth_token: str | None = None) -> None:
        self.db = db
        self.host = host
        self.port = port
        self.auth_token = auth_token

    def serve_forever(self) -> None:
        db = self.db
        auth_token = self.auth_token

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                if self.path != "/api/health":
                    self._send_json(404, {"error": "not_found"})
                    return
                self._send_json(200, {"status": "ok"})

            def do_POST(self) -> None:  # noqa: N802
                if self.path != "/api/telemetry/usage":
                    self._send_json(404, {"error": "not_found"})
                    return
                if auth_token and self.headers.get("Authorization") != f"Bearer {auth_token}":
                    self._send_json(401, {"error": "unauthorized"})
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    payload = self.rfile.read(length).decode("utf-8")
                    data = json.loads(payload)
                    result = save_mobile_usage_payload(db, data, payload)
                except Exception as exc:  # pragma: no cover - defensive HTTP boundary
                    LOGGER.exception("failed to save mobile usage payload")
                    self._send_json(400, {"error": str(exc)})
                    return
                self._send_json(200, result)

            def log_message(self, format: str, *args: Any) -> None:
                LOGGER.info("%s - %s", self.address_string(), format % args)

            def _send_json(self, status: int, body: dict[str, Any]) -> None:
                encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

        server = ThreadingHTTPServer((self.host, self.port), Handler)
        LOGGER.info("Telemetry API server listening on %s:%s", self.host, self.port)
        server.serve_forever()


def save_mobile_usage_payload(db: Database, data: dict[str, Any], raw_payload: str) -> dict[str, Any]:
    device_id = str(data["device_id"])
    display_name = str(data.get("device_name") or device_id)
    events = list(data.get("events") or [])
    sessions = list(data.get("sessions") or [])
    collected_at = str(data.get("collected_at") or utc_now())
    now = utc_now()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO devices(id, display_name, enabled, updated_at)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(id) DO UPDATE SET
              display_name=excluded.display_name,
              enabled=1,
              updated_at=excluded.updated_at
            """,
            (device_id, display_name, now),
        )
        cur = conn.execute(
            """
            INSERT INTO collection_jobs(device_id, collector_name, status, started_at, finished_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (device_id, "mobile_usage", "success", collected_at, now),
        )
        job_id = int(cur.lastrowid)
        conn.execute(
            """
            INSERT INTO raw_collection_payloads(job_id, device_id, collector_name, collected_at, payload)
            VALUES (?, ?, ?, ?, ?)
            """,
            (job_id, device_id, "mobile_usage", collected_at, raw_payload),
        )
        for event in events:
            package_name = str(event["package_name"])
            display_name_value = str(event.get("display_name") or package_name)
            conn.execute(
                _metadata_update_sql(),
                (device_id, package_name, display_name_value, "mobile", now, now, now),
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO usage_events(
                  job_id, device_id, package_name, event_type, event_time, duration_ms,
                  raw_line, class_name, task_root_package, task_root_class, instance_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    device_id,
                    package_name,
                    event.get("event_type"),
                    event.get("event_time"),
                    event.get("duration_ms"),
                    json.dumps(event, ensure_ascii=False),
                    event.get("class_name"),
                    event.get("task_root_package"),
                    event.get("task_root_class"),
                    event.get("instance_id"),
                ),
            )
        for session in sessions:
            package_name = str(session["package_name"])
            display_name_value = str(session.get("display_name") or package_name)
            conn.execute(
                _metadata_update_sql(),
                (device_id, package_name, display_name_value, "mobile", now, now, now),
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO app_usage_sessions(
                  job_id, device_id, package_name, class_name, task_root_package, task_root_class,
                  started_at, ended_at, duration_ms, end_reason, start_event_type, end_event_type
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    device_id,
                    package_name,
                    session.get("class_name"),
                    session.get("task_root_package"),
                    session.get("task_root_class"),
                    session["started_at"],
                    session.get("ended_at"),
                    session.get("duration_ms"),
                    session.get("end_reason"),
                    session.get("start_event_type"),
                    session.get("end_event_type"),
                ),
            )
        conn.execute(
            """
            INSERT INTO device_status(device_id, last_collection_status, last_collected_at, last_error_message, updated_at)
            VALUES (?, ?, ?, NULL, ?)
            ON CONFLICT(device_id) DO UPDATE SET
              last_collection_status=excluded.last_collection_status,
              last_collected_at=excluded.last_collected_at,
              last_error_message=NULL,
              updated_at=excluded.updated_at
            """,
            (device_id, "success", now, now),
        )
    return {"job_id": job_id, "events": len(events), "sessions": len(sessions)}
