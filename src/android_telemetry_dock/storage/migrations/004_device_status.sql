CREATE TABLE IF NOT EXISTS device_status (
  device_id TEXT PRIMARY KEY REFERENCES devices(id),
  presence_state TEXT NOT NULL DEFAULT 'unknown',
  last_ping_status TEXT,
  last_seen_at TEXT,
  adb_state TEXT,
  last_adb_checked_at TEXT,
  last_collection_status TEXT,
  last_collected_at TEXT,
  last_error_message TEXT,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO device_status(
  device_id,
  presence_state,
  last_seen_at,
  last_collected_at,
  updated_at
)
SELECT
  id,
  CASE WHEN last_seen_at IS NULL THEN 'unknown' ELSE 'present' END,
  last_seen_at,
  last_collected_at,
  updated_at
FROM devices;

UPDATE device_status
SET last_collection_status = 'success'
WHERE last_collected_at IS NOT NULL
  AND last_collection_status IS NULL;
