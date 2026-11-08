package net.linspad.atlasphone.mobile.location

import android.annotation.SuppressLint
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.location.LocationManager
import android.os.Looper
import androidx.core.content.ContextCompat
import androidx.core.location.LocationManagerCompat
import com.google.android.gms.location.LocationAvailability
import com.google.android.gms.location.LocationCallback
import com.google.android.gms.location.LocationRequest
import com.google.android.gms.location.LocationResult
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import net.linspad.atlasphone.mobile.model.RawLocation
import net.linspad.atlasphone.mobile.permissions.Capability
import net.linspad.atlasphone.mobile.permissions.PermissionManager

enum class TrackingState { IDLE, TRACKING, SIGNAL_LOST, SERVICES_DISABLED, NO_PERMISSION, ERROR }

/**
 * GPS acquisition with the Fused Location Provider: ~1 update per second while tracking, nothing while idle.
 * Knows nothing about captures, distance, pace or routes — it only emits fixes.
 */
@SuppressLint("MissingPermission") // checked in start(); SecurityException is also handled
class LocationTracker(
    context: Context,
    private val permissions: PermissionManager,
    private val log: (String) -> Unit,
) {
    private val appContext = context.applicationContext
    private val client = LocationServices.getFusedLocationProviderClient(appContext)
    private val locationManager = appContext.getSystemService(Context.LOCATION_SERVICE) as LocationManager

    private val _state = MutableStateFlow(TrackingState.IDLE)
    val state: StateFlow<TrackingState> = _state

    private val _latest = MutableStateFlow<RawLocation?>(null)
    val latest: StateFlow<RawLocation?> = _latest

    private val _received = MutableStateFlow(0L)
    /** Fixes received since the last start. */
    val received: StateFlow<Long> = _received

    private val _samples = MutableSharedFlow<RawLocation>(extraBufferCapacity = 128)
    val samples: SharedFlow<RawLocation> = _samples

    private var receiverRegistered = false

    private val callback = object : LocationCallback() {
        override fun onLocationResult(result: LocationResult) {
            val now = System.currentTimeMillis()
            for (l in result.locations) {
                val raw = LocationMapper.map(
                    l.time, now, l.latitude, l.longitude,
                    l.hasAccuracy(), l.accuracy, l.hasSpeed(), l.speed, l.hasAltitude(), l.altitude, l.hasBearing(), l.bearing,
                ) ?: continue
                _latest.value = raw
                _received.value = _received.value + 1
                _samples.tryEmit(raw)
            }
            if (_state.value == TrackingState.SIGNAL_LOST) _state.value = TrackingState.TRACKING
        }

        override fun onLocationAvailability(availability: LocationAvailability) {
            if (_state.value == TrackingState.TRACKING && !availability.isLocationAvailable) {
                _state.value = TrackingState.SIGNAL_LOST
                log("GPS signal lost")
            } else if (_state.value == TrackingState.SIGNAL_LOST && availability.isLocationAvailable) {
                _state.value = TrackingState.TRACKING
                log("GPS signal back")
            }
        }
    }

    private val providerReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            if (!isTracking()) return
            if (!servicesEnabled()) {
                _state.value = TrackingState.SERVICES_DISABLED
                log("Location services switched off")
            } else if (_state.value == TrackingState.SERVICES_DISABLED) {
                _state.value = TrackingState.TRACKING
                log("Location services back on")
            }
        }
    }

    fun isTracking(): Boolean = _state.value in setOf(TrackingState.TRACKING, TrackingState.SIGNAL_LOST, TrackingState.SERVICES_DISABLED)

    /** Starts updates. Returns false (and sets a descriptive state) if they cannot start. */
    fun start(): Boolean {
        if (isTracking()) return true
        if (!permissions.isGranted(Capability.LOCATION)) {
            _state.value = TrackingState.NO_PERMISSION
            log("Cannot start GPS: location permission missing")
            return false
        }
        if (!servicesEnabled()) {
            _state.value = TrackingState.SERVICES_DISABLED
            log("Cannot start GPS: location services are off")
            return false
        }
        val request = LocationRequest.Builder(Priority.PRIORITY_HIGH_ACCURACY, 1_000L)
            .setMinUpdateIntervalMillis(500L)
            .setWaitForAccurateLocation(false)
            .build()
        return try {
            _received.value = 0
            _latest.value = null
            client.requestLocationUpdates(request, callback, Looper.getMainLooper())
                .addOnFailureListener { e -> _state.value = TrackingState.ERROR; log("GPS request failed: ${e.message}") }
            registerReceiver()
            _state.value = TrackingState.TRACKING
            log("GPS started")
            true
        } catch (e: SecurityException) {
            _state.value = TrackingState.NO_PERMISSION
            log("GPS start refused: ${e.message}")
            false
        }
    }

    /** Stops updates and releases the provider connection. */
    fun stop() {
        if (_state.value == TrackingState.IDLE) return
        runCatching { client.removeLocationUpdates(callback) }
        unregisterReceiver()
        _state.value = TrackingState.IDLE
        log("GPS stopped")
    }

    private fun servicesEnabled() = LocationManagerCompat.isLocationEnabled(locationManager)

    private fun registerReceiver() {
        if (receiverRegistered) return
        ContextCompat.registerReceiver(
            appContext, providerReceiver, IntentFilter(LocationManager.PROVIDERS_CHANGED_ACTION), ContextCompat.RECEIVER_NOT_EXPORTED,
        )
        receiverRegistered = true
    }

    private fun unregisterReceiver() {
        if (!receiverRegistered) return
        runCatching { appContext.unregisterReceiver(providerReceiver) }
        receiverRegistered = false
    }
}
