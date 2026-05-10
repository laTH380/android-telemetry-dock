package dev.local.androidtelemetrydock;

import android.app.usage.UsageEvents;
import android.app.usage.UsageStatsManager;
import android.content.Context;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.Instant;
import java.util.HashMap;
import java.util.Map;

final class UsagePayloadBuilder {
    private UsagePayloadBuilder() {
    }

    static JSONObject build(Context context, long startMillis, long endMillis) throws Exception {
        UsageStatsManager manager = (UsageStatsManager) context.getSystemService(Context.USAGE_STATS_SERVICE);
        if (manager == null) {
            throw new IllegalStateException("UsageStatsManager unavailable");
        }

        JSONArray eventsJson = new JSONArray();
        JSONArray sessionsJson = new JSONArray();
        UsageEvents events = manager.queryEvents(startMillis, endMillis);
        UsageEvents.Event event = new UsageEvents.Event();
        Map<String, JSONObject> activeSessions = new HashMap<>();
        PackageManager packageManager = context.getPackageManager();

        while (events.hasNextEvent()) {
            events.getNextEvent(event);
            String packageName = event.getPackageName();
            if (packageName == null || packageName.isEmpty()) {
                continue;
            }
            String eventType = eventTypeName(event.getEventType());
            String eventTime = iso(event.getTimeStamp());
            String className = event.getClassName();
            String displayName = displayName(packageManager, packageName);

            JSONObject eventJson = new JSONObject()
                    .put("package_name", packageName)
                    .put("display_name", displayName)
                    .put("event_type", eventType)
                    .put("event_time", eventTime);
            if (className != null) {
                eventJson.put("class_name", className);
            }
            eventsJson.put(eventJson);

            if ("ACTIVITY_RESUMED".equals(eventType)) {
                JSONObject previous = activeSessions.remove(packageName);
                if (previous != null) {
                    closeSession(previous, eventTime, event.getTimeStamp(), "activity_switch", eventType);
                    sessionsJson.put(previous);
                }
                JSONObject session = new JSONObject()
                        .put("package_name", packageName)
                        .put("display_name", displayName)
                        .put("started_at", eventTime)
                        .put("started_at_millis", event.getTimeStamp())
                        .put("start_event_type", eventType);
                if (className != null) {
                    session.put("class_name", className);
                }
                activeSessions.put(packageName, session);
            } else if (("ACTIVITY_PAUSED".equals(eventType) || "ACTIVITY_STOPPED".equals(eventType)) && activeSessions.containsKey(packageName)) {
                JSONObject session = activeSessions.remove(packageName);
                closeSession(session, eventTime, event.getTimeStamp(), eventType.toLowerCase(), eventType);
                sessionsJson.put(session);
            } else if ("SCREEN_NON_INTERACTIVE".equals(eventType)) {
                for (JSONObject session : activeSessions.values()) {
                    closeSession(session, eventTime, event.getTimeStamp(), "screen_non_interactive", eventType);
                    sessionsJson.put(session);
                }
                activeSessions.clear();
            }
        }
        String windowEnd = iso(endMillis);
        for (JSONObject session : activeSessions.values()) {
            closeSession(session, windowEnd, endMillis, "window_end", "WINDOW_END");
            sessionsJson.put(session);
        }

        JSONObject payload = new JSONObject()
                .put("device_id", TelemetrySettings.deviceId(context))
                .put("device_name", TelemetrySettings.deviceName(context))
                .put("collected_at", iso(System.currentTimeMillis()))
                .put("window_start", iso(startMillis))
                .put("window_end", iso(endMillis))
                .put("events", eventsJson)
                .put("sessions", sessionsJson);
        return payload;
    }

    private static void closeSession(JSONObject session, String endedAt, long endedAtMillis, String reason, String eventType) throws Exception {
        long startedAtMillis = session.optLong("started_at_millis", endedAtMillis);
        session.put("ended_at", endedAt)
                .put("duration_ms", Math.max(0L, endedAtMillis - startedAtMillis))
                .put("end_reason", reason)
                .put("end_event_type", eventType)
                .remove("started_at_millis");
    }

    private static String displayName(PackageManager packageManager, String packageName) {
        try {
            ApplicationInfo info = packageManager.getApplicationInfo(packageName, 0);
            CharSequence label = packageManager.getApplicationLabel(info);
            return label != null ? label.toString() : packageName;
        } catch (PackageManager.NameNotFoundException ex) {
            return packageName;
        }
    }

    static String iso(long millis) {
        return Instant.ofEpochMilli(millis).toString();
    }

    private static String eventTypeName(int eventType) {
        switch (eventType) {
            case UsageEvents.Event.ACTIVITY_RESUMED:
                return "ACTIVITY_RESUMED";
            case UsageEvents.Event.ACTIVITY_PAUSED:
                return "ACTIVITY_PAUSED";
            case UsageEvents.Event.ACTIVITY_STOPPED:
                return "ACTIVITY_STOPPED";
            case UsageEvents.Event.SCREEN_INTERACTIVE:
                return "SCREEN_INTERACTIVE";
            case UsageEvents.Event.SCREEN_NON_INTERACTIVE:
                return "SCREEN_NON_INTERACTIVE";
            case UsageEvents.Event.KEYGUARD_HIDDEN:
                return "KEYGUARD_HIDDEN";
            case UsageEvents.Event.KEYGUARD_SHOWN:
                return "KEYGUARD_SHOWN";
            case UsageEvents.Event.USER_INTERACTION:
                return "USER_INTERACTION";
            default:
                return "EVENT_" + eventType;
        }
    }
}
