package net.linspad.atlasphone.mobile

import android.app.Application
import android.content.Context
import android.content.Intent
import android.util.Log
import androidx.core.content.ContextCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.distinctUntilChanged
import net.linspad.atlasphone.mobile.capture.CaptureRecorder
import net.linspad.atlasphone.mobile.capture.CaptureStore
import net.linspad.atlasphone.mobile.heartrate.HeartRateMonitor
import net.linspad.atlasphone.mobile.location.LocationTracker
import net.linspad.atlasphone.mobile.location.TrackingState
import net.linspad.atlasphone.mobile.permissions.PermissionManager
import net.linspad.atlasphone.mobile.service.RecordingService
import java.time.LocalTime
import java.time.format.DateTimeFormatter

private const val TAG = "MobilePlatform"

/**
 * The Mobile Platform: device capabilities (location, heart rate, permissions) and the capture buffer.
 * Process-wide and independent of any Activity, so acquisition and buffering outlive screens; the
 * [RecordingService] keeps the process alive and in the foreground while something is active.
 * Contains no domain logic (no distance, pace, routes, ghost runner).
 */
class MobilePlatform private constructor(app: Application) {
    val permissions = PermissionManager(app)
    val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    private val _log = MutableStateFlow<List<String>>(emptyList())
    /** Newest first, capped; errors and reconnection events end up here for the diagnostic screen. */
    val eventLog: StateFlow<List<String>> = _log

    fun log(message: String) {
        Log.i(TAG, message)
        val line = LocalTime.now().format(DateTimeFormatter.ofPattern("HH:mm:ss")) + "  " + message
        _log.value = (listOf(line) + _log.value).take(100)
    }

    val location = LocationTracker(app, permissions, ::log)
    val heartRate = HeartRateMonitor(app, permissions, ::log)
    val store = CaptureStore(app)
    val recorder = CaptureRecorder(store, scope, Dispatchers.IO, location.samples, heartRate.samples)

    /** True while GPS tracking, a sensor connection or a capture is running. */
    val active: Flow<Boolean> = combine(location.state, heartRate.state, recorder.active) { loc, hr, cap ->
        loc in setOf(TrackingState.TRACKING, TrackingState.SIGNAL_LOST, TrackingState.SERVICES_DISABLED) ||
            hr in setOf(HeartRateMonitor.State.CONNECTING, HeartRateMonitor.State.CONNECTED, HeartRateMonitor.State.RECONNECTING) ||
            cap != null
    }.distinctUntilChanged()

    /**
     * Starts the foreground service that keeps recording alive with the screen off. Must be called from the
     * foreground (a user action); the service stops itself when nothing is active any more.
     */
    fun ensureForegroundService(context: Context) {
        try {
            ContextCompat.startForegroundService(context, Intent(context, RecordingService::class.java))
        } catch (e: Exception) {
            log("Cannot start foreground service: ${e.message}")
        }
    }

    /** Stops GPS, disconnects the sensor and ends the capture. Stored samples stay in the buffer. */
    fun stopAll() {
        recorder.stop()
        location.stop()
        heartRate.disconnect()
        log("Everything stopped")
    }

    companion object {
        @Volatile private var instance: MobilePlatform? = null

        fun get(context: Context): MobilePlatform =
            instance ?: synchronized(this) {
                instance ?: MobilePlatform(context.applicationContext as Application).also { instance = it }
            }
    }
}
