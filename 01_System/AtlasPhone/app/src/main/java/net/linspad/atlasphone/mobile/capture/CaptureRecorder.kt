package net.linspad.atlasphone.mobile.capture

import android.util.Log
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import net.linspad.atlasphone.mobile.model.RawHeartRate
import net.linspad.atlasphone.mobile.model.RawLocation
import net.linspad.atlasphone.mobile.model.SampleJson
import net.linspad.atlasphone.mobile.model.Stream

private const val TAG = "CaptureRecorder"

/**
 * Associates the live sensor streams with a capture and persists them in the [CaptureStore].
 * Independent of any UI: it only needs the sample flows, so it works the same from an Activity or a service.
 */
class CaptureRecorder(
    private val store: CaptureStore,
    private val scope: CoroutineScope,
    private val ioDispatcher: CoroutineDispatcher,
    private val locations: Flow<RawLocation>,
    private val heartRates: Flow<RawHeartRate>,
) {
    private val _active = MutableStateFlow<CaptureInfo?>(null)
    /** The capture being recorded (counts refreshed after every stored sample), or null. */
    val active: StateFlow<CaptureInfo?> = _active

    private var jobs: List<Job> = emptyList()
    private val lock = Any()

    /** Starts (or continues, if [captureId] exists) a capture and returns its id. */
    fun start(captureId: String? = null): String = synchronized(lock) {
        check(_active.value == null) { "capture already running" }
        val id = store.createCapture(captureId)
        store.reopenCapture(id)
        _active.value = store.info(id)
        jobs = listOf(
            scope.launch(ioDispatcher) { locations.collect { record(id, Stream.LOCATION, it.timestampMillis) { seq -> SampleJson.location(it, id, seq).toString() } } },
            scope.launch(ioDispatcher) { heartRates.collect { record(id, Stream.HEART_RATE, it.timestampMillis) { seq -> SampleJson.heartRate(it, id, seq).toString() } } },
        )
        id
    }

    /** Stops recording and marks the capture finished. Stored samples are kept. */
    fun stop() = synchronized(lock) {
        val id = _active.value?.id ?: return
        jobs.forEach { it.cancel() }
        jobs = emptyList()
        store.finishCapture(id)
        _active.value = store.info(id)?.let { null } // recording ended
    }

    private fun record(id: String, stream: Stream, ts: Long, payload: (Long) -> String) {
        when (val r = store.append(id, stream, ts, payload)) {
            is AppendResult.Stored -> _active.value = store.info(id)
            AppendResult.Overflow -> { Log.w(TAG, "buffer full for $id, sample refused"); _active.value = store.info(id) }
            AppendResult.UnknownCapture -> Log.e(TAG, "capture $id vanished")
        }
    }
}
