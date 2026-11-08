package net.linspad.atlasphone.mobile.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.launch
import net.linspad.atlasphone.R
import net.linspad.atlasphone.mobile.MobilePlatform
import net.linspad.atlasphone.mobile.diagnostics.MobileTestActivity
import net.linspad.atlasphone.mobile.permissions.Capability

/**
 * Foreground service that keeps the process alive and eligible for location/Bluetooth while the screen is off.
 * It owns no sensors: the modules live in [MobilePlatform]. It starts with the first activity, shows a persistent
 * notification with a Stop action, and ends itself shortly after everything became inactive.
 *
 * NOT yet verified on a device with the screen locked (see Sprint01_MobilePlatform acceptance criteria).
 */
class RecordingService : Service() {
    companion object {
        const val ACTION_STOP = "net.linspad.atlasphone.mobile.STOP"
        private const val CHANNEL_ID = "mobile_recording"
        private const val NOTIFICATION_ID = 4711
        private const val WAKE_LOCK_MAX_MS = 4 * 60 * 60 * 1000L
        private const val IDLE_GRACE_MS = 3_000L
    }

    private var job: Job? = null
    private var wakeLock: PowerManager.WakeLock? = null
    private val platform by lazy { MobilePlatform.get(this) }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            platform.stopAll()
            stopSelf()
            return START_NOT_STICKY
        }
        createChannel()
        if (!enterForeground()) { stopSelf(); return START_NOT_STICKY }
        acquireWakeLock()
        if (job == null) job = platform.scope.launch { watch() }
        return START_NOT_STICKY // sensors are not restarted blindly after a kill; the capture buffer keeps what was stored
    }

    private suspend fun watch() {
        var idleSince: Long? = null
        combine(platform.location.state, platform.heartRate.state, platform.heartRate.latest, platform.recorder.active, platform.active) { loc, hr, last, cap, active ->
            Status(active, "GPS ${loc.name.lowercase()} · HR ${last?.bpm?.let { "$it bpm" } ?: hr.name.lowercase()}" +
                (cap?.let { " · capture ${it.locationCount + it.heartRateCount} samples" } ?: ""))
        }.collect { status ->
            notify(status.text)
            if (status.active) idleSince = null
            else {
                val since = idleSince ?: System.currentTimeMillis().also { idleSince = it }
                delay(IDLE_GRACE_MS)
                if (System.currentTimeMillis() - since >= IDLE_GRACE_MS && !isActive()) { stopSelf() }
            }
        }
    }

    private data class Status(val active: Boolean, val text: String)

    private fun isActive(): Boolean {
        val loc = platform.location.isTracking()
        val hr = platform.heartRate.isActive()
        return loc || hr || platform.recorder.active.value != null
    }

    private fun enterForeground(): Boolean {
        var types = 0
        if (Build.VERSION.SDK_INT >= 29) {
            if (platform.permissions.isGranted(Capability.LOCATION)) types = types or ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION
            if (Build.VERSION.SDK_INT >= 31 && platform.permissions.isGranted(Capability.BLUETOOTH)) types = types or ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE
            if (types == 0) { platform.log("Foreground service not started: no location/Bluetooth permission"); return false }
        }
        return try {
            ServiceCompat.startForeground(this, NOTIFICATION_ID, buildNotification("starting…"), types)
            true
        } catch (e: Exception) {
            platform.log("Foreground service refused: ${e.message}")
            false
        }
    }

    private fun buildNotification(text: String): Notification {
        val open = PendingIntent.getActivity(this, 0, Intent(this, MobileTestActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
        val stop = PendingIntent.getService(
            this, 1, Intent(this, RecordingService::class.java).setAction(ACTION_STOP), PendingIntent.FLAG_IMMUTABLE,
        )
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle("AtlasPhone is recording sensors")
            .setContentText(text)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setContentIntent(open)
            .addAction(0, "Stop", stop)
            .build()
    }

    private fun notify(text: String) {
        (getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).notify(NOTIFICATION_ID, buildNotification(text))
    }

    private fun createChannel() {
        if (Build.VERSION.SDK_INT < 26) return
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.createNotificationChannel(NotificationChannel(CHANNEL_ID, "Sensor recording", NotificationManager.IMPORTANCE_LOW))
    }

    private fun acquireWakeLock() {
        if (wakeLock?.isHeld == true) return
        val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
        wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "AtlasPhone:recording").apply { acquire(WAKE_LOCK_MAX_MS) }
    }

    override fun onDestroy() {
        job?.cancel()
        job = null
        wakeLock?.let { if (it.isHeld) it.release() }
        wakeLock = null
        super.onDestroy()
    }
}
