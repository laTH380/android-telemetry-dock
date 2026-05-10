package dev.local.androidtelemetrydock;

import android.app.job.JobParameters;
import android.app.job.JobService;

public class TelemetryUploadJobService extends JobService {
    @Override
    public boolean onStartJob(JobParameters params) {
        new Thread(() -> {
            boolean retry = false;
            try {
                TelemetryUploader.upload(this);
            } catch (Exception ignored) {
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
