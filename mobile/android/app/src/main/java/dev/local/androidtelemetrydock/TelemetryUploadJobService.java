package dev.local.androidtelemetrydock;

import android.app.job.JobParameters;
import android.app.job.JobService;

public class TelemetryUploadJobService extends JobService {
    @Override
    public boolean onStartJob(JobParameters params) {
        new Thread(() -> {
            boolean retry = false;
            try {
                org.json.JSONObject summary = TelemetryUploader.upload(this);
                TelemetrySettings.saveLastUploadStatus(this, "background success chunks=" + summary.optInt("chunks") + " recent=" + summary.optBoolean("recent_window_sent") + " complete=" + summary.optBoolean("complete") + " at " + UsagePayloadBuilder.iso(System.currentTimeMillis()));
            } catch (Exception ex) {
                TelemetrySettings.saveLastUploadStatus(this, "background failed: " + ex.getMessage() + " at " + UsagePayloadBuilder.iso(System.currentTimeMillis()));
                retry = true;
            }
            jobFinished(params, retry);
        }).start();
        return true;
    }

    @Override
    public boolean onStopJob(JobParameters params) {
        return true;
    }
}
