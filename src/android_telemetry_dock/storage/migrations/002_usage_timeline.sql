ALTER TABLE usage_events ADD COLUMN class_name TEXT;
ALTER TABLE usage_events ADD COLUMN task_root_package TEXT;
ALTER TABLE usage_events ADD COLUMN task_root_class TEXT;
ALTER TABLE usage_events ADD COLUMN instance_id TEXT;

CREATE TABLE IF NOT EXISTS app_usage_sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id INTEGER NOT NULL REFERENCES collection_jobs(id),
  device_id TEXT NOT NULL REFERENCES devices(id),
  package_name TEXT NOT NULL,
  class_name TEXT,
  task_root_package TEXT,
  task_root_class TEXT,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  duration_ms INTEGER,
  end_reason TEXT,
  start_event_type TEXT,
  end_event_type TEXT
);

CREATE INDEX IF NOT EXISTS idx_usage_events_device_time ON usage_events(device_id, event_time);
CREATE INDEX IF NOT EXISTS idx_app_usage_sessions_device_start ON app_usage_sessions(device_id, started_at);
CREATE INDEX IF NOT EXISTS idx_app_usage_sessions_package_start ON app_usage_sessions(package_name, started_at);
