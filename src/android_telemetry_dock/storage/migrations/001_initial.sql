CREATE TABLE IF NOT EXISTS devices (
  id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  mac_address TEXT,
  current_ip TEXT,
  adb_port INTEGER NOT NULL DEFAULT 5555,
  enabled INTEGER NOT NULL DEFAULT 1,
  first_seen_at TEXT,
  last_seen_at TEXT,
  last_collected_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS device_presence_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  device_id TEXT NOT NULL REFERENCES devices(id),
  event_type TEXT NOT NULL,
  ip_address TEXT,
  mac_address TEXT,
  detected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  details TEXT
);

CREATE TABLE IF NOT EXISTS adb_connection_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  device_id TEXT NOT NULL REFERENCES devices(id),
  serial TEXT,
  status TEXT NOT NULL,
  message TEXT,
  occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS collection_jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  device_id TEXT NOT NULL REFERENCES devices(id),
  collector_name TEXT NOT NULL,
  status TEXT NOT NULL,
  started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at TEXT,
  error_message TEXT,
  skip_reason TEXT
);

CREATE TABLE IF NOT EXISTS raw_collection_payloads (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id INTEGER NOT NULL REFERENCES collection_jobs(id),
  device_id TEXT NOT NULL REFERENCES devices(id),
  collector_name TEXT NOT NULL,
  collected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS usage_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id INTEGER NOT NULL REFERENCES collection_jobs(id),
  device_id TEXT NOT NULL REFERENCES devices(id),
  package_name TEXT NOT NULL,
  event_type TEXT,
  event_time TEXT,
  duration_ms INTEGER,
  raw_line TEXT
);

CREATE TABLE IF NOT EXISTS app_usage_summaries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id INTEGER NOT NULL REFERENCES collection_jobs(id),
  device_id TEXT NOT NULL REFERENCES devices(id),
  package_name TEXT NOT NULL,
  total_time_ms INTEGER,
  last_time_used TEXT,
  window_start TEXT,
  window_end TEXT,
  raw_line TEXT
);

CREATE INDEX IF NOT EXISTS idx_presence_device_time ON device_presence_events(device_id, detected_at);
CREATE INDEX IF NOT EXISTS idx_jobs_device_status ON collection_jobs(device_id, status);
CREATE INDEX IF NOT EXISTS idx_usage_events_device_package ON usage_events(device_id, package_name);
