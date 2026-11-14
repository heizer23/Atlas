package net.linspad.atlasphone.mobile.steps

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.os.SystemClock
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import net.linspad.atlasphone.mobile.model.RawStep
import net.linspad.atlasphone.mobile.permissions.Capability
import net.linspad.atlasphone.mobile.permissions.PermissionManager

/**
 * Step acquisition (Android TYPE_STEP_DETECTOR, one event per step, hardware-batched, works with the screen off).
 * Domain-free like LocationTracker/HeartRateMonitor: no cadence, no run meaning. Sensor callbacks only emit into a
 * buffered flow (never block, never touch the store). Without permission or sensor, [start] returns false and the
 * state says why; it never throws and never blocks a run.
 */
class StepDetector(
    private val context: Context,
    private val permissions: PermissionManager,
    private val log: (String) -> Unit,
) {
    enum class State { STOPPED, LISTENING, NO_SENSOR, NO_PERMISSION }

    companion object {
        /** Batching allowed: timestamps are event time, so a delayed delivery does not shift the step. */
        const val STEP_MAX_REPORT_LATENCY_MS = 1000L

        /** Event time -> UTC epoch ms: now minus how long ago the sensor event happened. Pure, JVM-testable. */
        fun toRaw(eventNanos: Long, nowMillis: Long, nowElapsedNanos: Long): RawStep =
            RawStep(nowMillis - (nowElapsedNanos - eventNanos) / 1_000_000L, eventNanos)
    }

    // Buffer capacity: a slow collector drops the OLDEST step instead of suspending the sensor thread (REL1: lowers
    // cadence confidence at worst, never delays GPS/HR). tryEmit never blocks.
    private val _samples = MutableSharedFlow<RawStep>(extraBufferCapacity = 512, onBufferOverflow = BufferOverflow.DROP_OLDEST)
    val samples: Flow<RawStep> = _samples

    private val _state = MutableStateFlow(State.STOPPED)
    val state: StateFlow<State> = _state

    private var sensorManager: SensorManager? = null
    private val listener = object : SensorEventListener {
        override fun onSensorChanged(event: SensorEvent) {
            _samples.tryEmit(toRaw(event.timestamp, System.currentTimeMillis(), SystemClock.elapsedRealtimeNanos()))
        }
        override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {}
    }

    /** Registers the listener. Idempotent while LISTENING. False (NO_PERMISSION / NO_SENSOR) when impossible. */
    @Synchronized
    fun start(): Boolean {
        if (_state.value == State.LISTENING) return true
        if (!permissions.isGranted(Capability.ACTIVITY_RECOGNITION)) { _state.value = State.NO_PERMISSION; log("Steps: no activity permission"); return false }
        return try {
            val sm = sensorManager ?: (context.getSystemService(Context.SENSOR_SERVICE) as SensorManager).also { sensorManager = it }
            val sensor = sm.getDefaultSensor(Sensor.TYPE_STEP_DETECTOR)
            if (sensor == null) { _state.value = State.NO_SENSOR; log("Steps: no step detector sensor"); return false }
            val ok = sm.registerListener(listener, sensor, SensorManager.SENSOR_DELAY_NORMAL, (STEP_MAX_REPORT_LATENCY_MS * 1000).toInt())
            _state.value = if (ok) State.LISTENING else State.NO_SENSOR
            ok
        } catch (e: Exception) {
            log("Steps: cannot start (${e.message})")
            _state.value = State.NO_SENSOR
            false
        }
    }

    /** Flushes pending batched events, then unregisters. Idempotent. */
    @Synchronized
    fun stop() {
        if (_state.value == State.LISTENING) {
            try { sensorManager?.flush(listener) } catch (e: Exception) { log("Steps: flush failed (${e.message})") }
            try { sensorManager?.unregisterListener(listener) } catch (e: Exception) { log("Steps: unregister failed (${e.message})") }
        }
        _state.value = State.STOPPED
    }
}
