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
    private static final long LOOKBACK_MS = 60L * 60L * 1000L;

    private TelemetryUploader() {
    }

    static JSONObject upload(Context context) throws Exception {
        if (!hasUsageAccess(context)) {
            throw new IllegalStateException("Usage access is not granted");
        }
        long now = System.currentTimeMillis();
        long start = now - LOOKBACK_MS;
        JSONObject payload = UsagePayloadBuilder.build(context, start, now);
        post(context, payload);
        return payload;
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
