package dev.local.androidtelemetrydock;

import android.app.AppOpsManager;
import android.app.usage.UsageStats;
import android.app.usage.UsageStatsManager;
import android.content.Context;
import android.os.Process;

import org.json.JSONObject;

import java.io.OutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.List;

final class TelemetryUploader {
    private static final long INITIAL_LOOKBACK_MS = 60L * 60L * 1000L;
    private static final long CHUNK_MS = 60L * 60L * 1000L;
    private static final long OVERLAP_MS = 5L * 60L * 1000L;
    private static final int MAX_CHUNKS_PER_UPLOAD = 24;

    private TelemetryUploader() {
    }

    static JSONObject upload(Context context) throws Exception {
        if (!hasUsageAccess(context)) {
            throw new IllegalStateException("Usage access is not granted");
        }
        long now = System.currentTimeMillis();
        long cursor = startMillis(context, now);
        int chunks = 0;
        int totalEvents = 0;
        int totalSessions = 0;
        long firstWindowStart = cursor;
        long lastWindowEnd = cursor;
        while (cursor < now && chunks < MAX_CHUNKS_PER_UPLOAD) {
            long end = Math.min(cursor + CHUNK_MS, now);
            JSONObject payload = UsagePayloadBuilder.build(context, cursor, end);
            post(context, payload);
            TelemetrySettings.saveLastSuccessfulWindowEndMillis(context, end);
            chunks++;
            totalEvents += payload.getJSONArray("events").length();
            totalSessions += payload.getJSONArray("sessions").length();
            lastWindowEnd = end;
            cursor = end;
        }
        long recentStart = Math.max(0L, now - INITIAL_LOOKBACK_MS);
        boolean recentWindowAlreadyCovered = recentStart >= firstWindowStart && now <= lastWindowEnd;
        if (!recentWindowAlreadyCovered) {
            JSONObject payload = UsagePayloadBuilder.build(context, recentStart, now);
            post(context, payload);
            chunks++;
            totalEvents += payload.getJSONArray("events").length();
            totalSessions += payload.getJSONArray("sessions").length();
        }
        return new JSONObject()
                .put("chunks", chunks)
                .put("total_events", totalEvents)
                .put("total_sessions", totalSessions)
                .put("window_start", UsagePayloadBuilder.iso(firstWindowStart))
                .put("window_end", UsagePayloadBuilder.iso(lastWindowEnd))
                .put("recent_window_sent", true)
                .put("recent_window_extra", !recentWindowAlreadyCovered)
                .put("complete", lastWindowEnd >= now);
    }

    private static long startMillis(Context context, long now) {
        long lastSuccessfulWindowEnd = TelemetrySettings.lastSuccessfulWindowEndMillis(context);
        if (lastSuccessfulWindowEnd <= 0L || lastSuccessfulWindowEnd > now) {
            return now - INITIAL_LOOKBACK_MS;
        }
        return Math.max(0L, lastSuccessfulWindowEnd - OVERLAP_MS);
    }

    static boolean hasUsageAccess(Context context) {
        AppOpsManager appOps = (AppOpsManager) context.getSystemService(Context.APP_OPS_SERVICE);
        if (appOps == null) {
            return false;
        }
        int mode = appOps.checkOpNoThrow(AppOpsManager.OPSTR_GET_USAGE_STATS, Process.myUid(), context.getPackageName());
        if (mode == AppOpsManager.MODE_ALLOWED) {
            return true;
        }
        UsageStatsManager manager = (UsageStatsManager) context.getSystemService(Context.USAGE_STATS_SERVICE);
        if (manager == null) {
            return false;
        }
        long now = System.currentTimeMillis();
        List<UsageStats> stats = manager.queryUsageStats(UsageStatsManager.INTERVAL_DAILY, now - 60L * 60L * 1000L, now);
        return stats != null && !stats.isEmpty();
    }

    private static void post(Context context, JSONObject payload) throws Exception {
        URL url = new URL(TelemetrySettings.serverUrl(context) + "/api/telemetry/usage");
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        connection.setRequestMethod("POST");
        connection.setConnectTimeout(10000);
        connection.setReadTimeout(30000);
        connection.setDoOutput(true);
        connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
        String token = TelemetrySettings.authToken(context);
        if (!token.isEmpty()) {
            connection.setRequestProperty("Authorization", "Bearer " + token);
        }
        byte[] body = payload.toString().getBytes("UTF-8");
        connection.setFixedLengthStreamingMode(body.length);
        try (OutputStream output = connection.getOutputStream()) {
            output.write(body);
        }
        int status = connection.getResponseCode();
        if (status < 200 || status >= 300) {
            throw new IllegalStateException("Upload failed with HTTP " + status + ": " + responseBody(connection));
        }
    }

    private static String responseBody(HttpURLConnection connection) {
        try {
            InputStream stream = connection.getErrorStream();
            if (stream == null) {
                stream = connection.getInputStream();
            }
            if (stream == null) {
                return "";
            }
            byte[] buffer = new byte[4096];
            int read = stream.read(buffer);
            if (read <= 0) {
                return "";
            }
            return new String(buffer, 0, read, "UTF-8");
        } catch (Exception ex) {
            return "";
        }
    }
}
