from android_telemetry_dock.config import load_config


def test_load_config_defaults_when_file_missing(tmp_path):
    config = load_config(tmp_path / "missing.yaml")
    assert config.database_path == "/data/android_telemetry_dock.sqlite3"
    assert config.collectors["usage_history"]["enabled"] is True
