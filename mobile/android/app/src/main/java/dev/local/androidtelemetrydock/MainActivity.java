package dev.local.androidtelemetrydock;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.provider.Settings;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONObject;

public class MainActivity extends Activity {
    private TextView statusView;
    private EditText serverUrlView;
    private EditText tokenView;
    private EditText deviceIdView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(buildView());
        loadSettings();
        refreshStatus();
    }

    @Override
    protected void onResume() {
        super.onResume();
        refreshStatus();
    }

    private ScrollView buildView() {
        ScrollView scrollView = new ScrollView(this);
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        int padding = dp(16);
        layout.setPadding(padding, padding, padding, padding);
        scrollView.addView(layout);

        statusView = new TextView(this);
        layout.addView(statusView, matchWrap());

        serverUrlView = field("Server URL");
        tokenView = field("Auth token");
        deviceIdView = field("Device ID");
        layout.addView(serverUrlView, matchWrap());
        layout.addView(tokenView, matchWrap());
        layout.addView(deviceIdView, matchWrap());

        Button saveButton = button("Save settings");
        saveButton.setOnClickListener(v -> {
            TelemetrySettings.save(this, serverUrlView.getText().toString(), tokenView.getText().toString(), deviceIdView.getText().toString());
            refreshStatus();
        });
        layout.addView(saveButton, matchWrap());

        Button usageAccessButton = button("Open usage access settings");
        usageAccessButton.setOnClickListener(v -> startActivity(new Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS)));
        layout.addView(usageAccessButton, matchWrap());

        Button sendButton = button("Send now");
        sendButton.setOnClickListener(v -> sendNow());
        layout.addView(sendButton, matchWrap());

        Button scheduleButton = button("Schedule every 15 minutes");
        scheduleButton.setOnClickListener(v -> {
            TelemetryScheduler.schedule(this);
            TelemetryScheduler.runSoon(this);
            setStatus("Scheduled. The app sends on unmetered network and retries through JobScheduler.");
        });
        layout.addView(scheduleButton, matchWrap());

        return scrollView;
    }

    private void loadSettings() {
        serverUrlView.setText(TelemetrySettings.serverUrl(this));
        tokenView.setText(TelemetrySettings.authToken(this));
        deviceIdView.setText(TelemetrySettings.deviceId(this));
    }

    private void refreshStatus() {
        setStatus("Usage access: " + (TelemetryUploader.hasUsageAccess(this) ? "granted" : "not granted"));
    }

    private void sendNow() {
        TelemetrySettings.save(this, serverUrlView.getText().toString(), tokenView.getText().toString(), deviceIdView.getText().toString());
        setStatus("Sending...");
        new Thread(() -> {
            try {
                JSONObject payload = TelemetryUploader.upload(this);
                int events = payload.getJSONArray("events").length();
                int sessions = payload.getJSONArray("sessions").length();
                runOnUiThread(() -> setStatus("Uploaded events=" + events + " sessions=" + sessions));
            } catch (Exception ex) {
                runOnUiThread(() -> setStatus("Upload failed: " + ex.getMessage()));
            }
        }).start();
    }

    private void setStatus(String status) {
        statusView.setText(status);
    }

    private EditText field(String hint) {
        EditText editText = new EditText(this);
        editText.setHint(hint);
        editText.setSingleLine(true);
        return editText;
    }

    private Button button(String text) {
        Button button = new Button(this);
        button.setText(text);
        return button;
    }

    private LinearLayout.LayoutParams matchWrap() {
        return new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density);
    }
}
