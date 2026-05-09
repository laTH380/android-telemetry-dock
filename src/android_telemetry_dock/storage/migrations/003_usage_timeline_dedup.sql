DELETE FROM usage_events
WHERE id NOT IN (
  SELECT MIN(id)
  FROM usage_events
  GROUP BY
    device_id,
    event_time,
    event_type,
    package_name,
    COALESCE(class_name, ''),
    COALESCE(instance_id, ''),
    COALESCE(raw_line, '')
);

DELETE FROM app_usage_sessions
WHERE id NOT IN (
  SELECT MIN(id)
  FROM app_usage_sessions
  GROUP BY
    device_id,
    package_name,
    started_at,
    COALESCE(ended_at, ''),
    COALESCE(class_name, ''),
    COALESCE(end_reason, '')
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_usage_events_unique_timeline_event
ON usage_events(
  device_id,
  event_time,
  event_type,
  package_name,
  COALESCE(class_name, ''),
  COALESCE(instance_id, ''),
  COALESCE(raw_line, '')
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_app_usage_sessions_unique_interval
ON app_usage_sessions(
  device_id,
  package_name,
  started_at,
  COALESCE(ended_at, ''),
  COALESCE(class_name, ''),
  COALESCE(end_reason, '')
);
