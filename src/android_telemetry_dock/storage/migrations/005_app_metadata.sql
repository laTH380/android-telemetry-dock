CREATE TABLE IF NOT EXISTS app_metadata (
  device_id TEXT NOT NULL REFERENCES devices(id),
  package_name TEXT NOT NULL,
  display_name TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'unknown',
  first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(device_id, package_name)
);

INSERT OR IGNORE INTO app_metadata(device_id, package_name, display_name, source, first_seen_at, last_seen_at, updated_at)
SELECT DISTINCT device_id, package_name, package_name, 'package_name', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM usage_events
WHERE package_name IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_app_metadata_display_name ON app_metadata(display_name);
