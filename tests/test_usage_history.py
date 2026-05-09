from android_telemetry_dock.collectors.usage_history import parse_usage_stats


def test_parse_usage_stats_summaries_and_events():
    payload = """
    package=com.example.app totalTimeInForeground=12345 lastTimeUsed=1710000000000
    pkg=com.example.other eventType=MOVE_TO_FOREGROUND lastTimeUsed=1710000001000
    """

    events, sessions, summaries = parse_usage_stats(payload)

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
    assert events[0]["event_time"] == "2024-03-09T16:00:01"
    assert sessions == []


def test_parse_usage_stats_builds_timeline_sessions():
    payload = """
    time="2026-05-08 19:24:44" type=ACTIVITY_RESUMED package=com.example.maps class=com.example.MapsActivity instanceId=204 taskRootPackage=com.example.maps taskRootClass=com.example.MapsActivity flags=0x0
    time="2026-05-08 19:26:57" type=ACTIVITY_PAUSED package=com.example.maps class=com.example.MapsActivity instanceId=204 taskRootPackage=com.example.maps taskRootClass=com.example.MapsActivity flags=0x0
    time="2026-05-08 19:29:25" type=ACTIVITY_RESUMED package=com.example.chat class=com.example.ChatActivity instanceId=205 taskRootPackage=com.example.chat taskRootClass=com.example.ChatActivity flags=0x0
    time="2026-05-08 19:30:00" type=SCREEN_NON_INTERACTIVE package=android flags=0x0
    """

    events, sessions, summaries = parse_usage_stats(payload)

    assert summaries == []
    assert events[0]["event_time"] == "2026-05-08T19:24:44"
    assert events[0]["class_name"] == "com.example.MapsActivity"
    assert sessions == [
        {
            "package_name": "com.example.maps",
            "class_name": "com.example.MapsActivity",
            "task_root_package": "com.example.maps",
            "task_root_class": "com.example.MapsActivity",
            "started_at": "2026-05-08T19:24:44",
            "start_event_type": "ACTIVITY_RESUMED",
            "ended_at": "2026-05-08T19:26:57",
            "duration_ms": 133000,
            "end_reason": "activity_paused",
            "end_event_type": "ACTIVITY_PAUSED",
        },
        {
            "package_name": "com.example.chat",
            "class_name": "com.example.ChatActivity",
            "task_root_package": "com.example.chat",
            "task_root_class": "com.example.ChatActivity",
            "started_at": "2026-05-08T19:29:25",
            "start_event_type": "ACTIVITY_RESUMED",
            "ended_at": "2026-05-08T19:30:00",
            "duration_ms": 35000,
            "end_reason": "screen_non_interactive",
            "end_event_type": "SCREEN_NON_INTERACTIVE",
        },
    ]
