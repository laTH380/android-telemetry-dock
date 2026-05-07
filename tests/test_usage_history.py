from android_telemetry_dock.collectors.usage_history import parse_usage_stats


def test_parse_usage_stats_summaries_and_events():
    payload = """
    package=com.example.app totalTimeInForeground=12345 lastTimeUsed=1710000000000
    pkg=com.example.other eventType=MOVE_TO_FOREGROUND lastTimeUsed=1710000001000
    """

    events, summaries = parse_usage_stats(payload)

    assert summaries == [
        {
            "package_name": "com.example.app",
            "total_time_ms": 12345,
            "last_time_used": "2024-03-09T16:00:00",
            "raw_line": "package=com.example.app totalTimeInForeground=12345 lastTimeUsed=1710000000000",
        }
    ]
    assert events[0]["package_name"] == "com.example.other"
    assert events[0]["event_type"] == "MOVE_TO_FOREGROUND"
