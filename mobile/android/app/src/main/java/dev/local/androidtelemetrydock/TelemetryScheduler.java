package dev.local.androidtelemetrydock;

import android.app.job.JobInfo;
import android.app.job.JobScheduler;
import android.content.ComponentName;
import android.content.Context;

final class TelemetryScheduler {
    static final int JOB_ID = 10242;
    private static final long FIFTEEN_MINUTES_MS = 15L * 60L * 1000L;

    private TelemetryScheduler() {
    }

    static void schedule(Context context) {
        ComponentName component = new ComponentName(context, TelemetryUploadJobService.class);
        JobInfo jobInfo = new JobInfo.Builder(JOB_ID, component)
                .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY)
                .setPersisted(true)
                .setPeriodic(FIFTEEN_MINUTES_MS)
                .build();
        JobScheduler scheduler = (JobScheduler) context.getSystemService(Context.JOB_SCHEDULER_SERVICE);
        if (scheduler != null) {
            scheduler.schedule(jobInfo);
        }
    }

    static void runSoon(Context context) {
        ComponentName component = new ComponentName(context, TelemetryUploadJobService.class);
        JobInfo jobInfo = new JobInfo.Builder(JOB_ID + 1, component)
                .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY)
                .setOverrideDeadline(1L)
                .build();
        JobScheduler scheduler = (JobScheduler) context.getSystemService(Context.JOB_SCHEDULER_SERVICE);
        if (scheduler != null) {
            scheduler.schedule(jobInfo);
        }
    }
}
