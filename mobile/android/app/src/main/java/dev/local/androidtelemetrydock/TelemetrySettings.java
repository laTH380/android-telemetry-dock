package dev.local.androidtelemetrydock;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.Build;
import android.provider.Settings;

final class TelemetrySettings {
    private static final String PREFS = "telemetry_dock";
    private static final String SERVER_URL = "server_url";
    private static final String AUTH_TOKEN = "auth_token";
    private static final String DEVICE_ID = "device_id";
    private static final String LAST_SUCCESSFUL_WINDOW_END_MS = "last_successful_window_end_ms";
    private static final String LAST_UPLOAD_STATUS = "last_upload_status";

    private TelemetrySettings() {
    }

    static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    static String serverUrl(Context context) {
        return prefs(context).getString(SERVER_URL, "http://10.216.78.25:8080");
    }

    static String authToken(Context context) {
        return prefs(context).getString(AUTH_TOKEN, "");
    }

    static String deviceId(Context context) {
        String fallback = Settings.Secure.getString(context.getContentResolver(), Settings.Secure.ANDROID_ID);
        return prefs(context).getString(DEVICE_ID, fallback != null ? fallback : "android-device");
    }

    static String deviceName(Context context) {
        String name = Settings.Global.getString(context.getContentResolver(), Settings.Global.DEVICE_NAME);
        if (name == null || name.trim().isEmpty()) {
            return Build.MODEL;
        }
        return name.trim();
    }

    static void save(Context context, String serverUrl, String authToken, String deviceId) {
        prefs(context).edit()
                .putString(SERVER_URL, trimTrailingSlash(serverUrl))
                .putString(AUTH_TOKEN, authToken)
                .putString(DEVICE_ID, deviceId)
                .apply();
    }

    static long lastSuccessfulWindowEndMillis(Context context) {
        return prefs(context).getLong(LAST_SUCCESSFUL_WINDOW_END_MS, 0L);
    }

    static void saveLastSuccessfulWindowEndMillis(Context context, long windowEndMillis) {
        prefs(context).edit()
                .putLong(LAST_SUCCESSFUL_WINDOW_END_MS, windowEndMillis)
                .apply();
    }

    static String lastUploadStatus(Context context) {
        return prefs(context).getString(LAST_UPLOAD_STATUS, "never");
    }

    static void saveLastUploadStatus(Context context, String status) {
        prefs(context).edit()
                .putString(LAST_UPLOAD_STATUS, status)
                .apply();
    }

    private static String trimTrailingSlash(String value) {
        String trimmed = value.trim();
        while (trimmed.endsWith("/")) {
            trimmed = trimmed.substring(0, trimmed.length() - 1);
        }
        return trimmed;
    }
}
