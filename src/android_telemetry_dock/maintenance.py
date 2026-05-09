from __future__ import annotations

from android_telemetry_dock.collectors.usage_history import parse_usage_stats
from android_telemetry_dock.storage.db import Database


def reparse_usage_history_raw_payloads(db: Database) -> int:
    jobs_reparsed = 0
    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT job_id, device_id, payload
            FROM raw_collection_payloads
            WHERE collector_name = ?
            ORDER BY job_id
            """,
            ("usage_history",),
        ).fetchall()
        job_ids = [int(row["job_id"]) for row in rows]
        if job_ids:
            placeholders = ",".join("?" for _ in job_ids)
            conn.execute(f"DELETE FROM usage_events WHERE job_id IN ({placeholders})", job_ids)
            conn.execute(f"DELETE FROM app_usage_sessions WHERE job_id IN ({placeholders})", job_ids)
            conn.execute(f"DELETE FROM app_usage_summaries WHERE job_id IN ({placeholders})", job_ids)

        for row in rows:
            job_id = int(row["job_id"])
            device_id = str(row["device_id"])
            events, sessions, summaries = parse_usage_stats(str(row["payload"]))

            for event in events:
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
                        event["package_name"],
                        event.get("event_type"),
                        event.get("event_time"),
                        event.get("duration_ms"),
                        event.get("raw_line"),
                        event.get("class_name"),
                        event.get("task_root_package"),
                        event.get("task_root_class"),
                        event.get("instance_id"),
                    ),
                )
            for session in sessions:
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
                        session["package_name"],
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
            for summary in summaries:
                conn.execute(
                    """
                    INSERT INTO app_usage_summaries(
                      job_id, device_id, package_name, total_time_ms, last_time_used,
                      window_start, window_end, raw_line
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job_id,
                        device_id,
                        summary["package_name"],
                        summary.get("total_time_ms"),
                        summary.get("last_time_used"),
                        summary.get("window_start"),
                        summary.get("window_end"),
                        summary.get("raw_line"),
                    ),
                )
            jobs_reparsed += 1
    return jobs_reparsed
