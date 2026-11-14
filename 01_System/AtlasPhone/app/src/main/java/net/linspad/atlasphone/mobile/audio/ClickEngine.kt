package net.linspad.atlasphone.mobile.audio

import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioTrack
import android.os.Process
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import java.util.concurrent.atomic.AtomicLong

/** What a metronome needs from a click track; [ClickEngine] is the Android implementation, tests use a fake. */
interface ClickOutput {
    fun start(volume: Float): Boolean
    fun setTargetSpm(spm: Double?)
    fun setVolume(volume: Float)
    fun stop()
    /** Engine state name for display (STOPPED / RUNNING / ERROR). */
    fun stateName(): String
}

/**
 * A quiet click track on its own audio thread (domain-free). Streaming AudioTrack fed by [BeatScheduler]; the target
 * and volume are atomics read by the thread, so stalls in the UI or the 1 Hz publish cannot change click timing.
 * Requests NO audio focus: it mixes with music/podcasts and never pauses them. Never touches location/HR/capture.
 */
class ClickEngine(private val log: (String) -> Unit) : ClickOutput {
    enum class State { STOPPED, RUNNING, ERROR }

    private val _state = MutableStateFlow(State.STOPPED)
    val state: StateFlow<State> = _state

    private val targetBits = AtomicLong(NONE)
    private val volumeBits = AtomicLong(java.lang.Double.doubleToRawLongBits(ClickConfig.DEFAULT_VOLUME.toDouble()))
    @Volatile private var thread: Thread? = null
    @Volatile private var running = false

    /** Creates the track and the thread; starts silent. Idempotent. */
    @Synchronized
    override fun start(volume: Float): Boolean {
        if (running) return true
        setVolume(volume)
        targetBits.set(NONE)
        val frames = ClickConfig.SAMPLE_RATE_HZ * ClickConfig.BUFFER_MS / 1000
        val track = try {
            val min = AudioTrack.getMinBufferSize(ClickConfig.SAMPLE_RATE_HZ, AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_16BIT)
            AudioTrack.Builder()
                .setAudioAttributes(AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION).build())
                .setAudioFormat(AudioFormat.Builder().setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                    .setSampleRate(ClickConfig.SAMPLE_RATE_HZ).setChannelMask(AudioFormat.CHANNEL_OUT_MONO).build())
                .setTransferMode(AudioTrack.MODE_STREAM)
                .setBufferSizeInBytes(maxOf(min, frames * 2 * 4))
                .build()
        } catch (e: Exception) {
            log("Click: cannot create audio track (${e.message})")
            _state.value = State.ERROR
            return false
        }
        running = true
        _state.value = State.RUNNING
        thread = Thread({ loop(track, frames) }, "ClickEngine").also { it.start() }
        return true
    }

    private fun loop(track: AudioTrack, frames: Int) {
        try {
            Process.setThreadPriority(Process.THREAD_PRIORITY_URGENT_AUDIO)
            val scheduler = BeatScheduler(
                ClickConfig.SAMPLE_RATE_HZ,
                BeatScheduler.renderClick(ClickConfig.SAMPLE_RATE_HZ, ClickConfig.CLICK_MS, ClickConfig.CLICK_FREQ_HZ, ClickConfig.CLICK_PEAK),
            )
            val buffer = ShortArray(frames)
            var appliedVolume = -1.0
            track.play()
            while (running) {
                val volume = java.lang.Double.longBitsToDouble(volumeBits.get())
                if (volume != appliedVolume) { track.setVolume(volume.toFloat()); appliedVolume = volume }
                val bits = targetBits.get()
                scheduler.fill(buffer, frames, if (bits == NONE) 0.0 else java.lang.Double.longBitsToDouble(bits))
                if (track.write(buffer, 0, frames) < 0) throw IllegalStateException("audio write failed")
            }
        } catch (e: Exception) {
            log("Click: audio error (${e.message})")
            _state.value = State.ERROR
        } finally {
            running = false
            try { track.stop() } catch (_: Exception) {}
            track.release()
        }
    }

    /** Atomic hand-off; null = silence. Any thread, never blocks. */
    override fun setTargetSpm(spm: Double?) { targetBits.set(if (spm == null) NONE else java.lang.Double.doubleToRawLongBits(spm)) }

    /** 0..1 gain applied through AudioTrack.setVolume by the audio thread. */
    override fun setVolume(volume: Float) { volumeBits.set(java.lang.Double.doubleToRawLongBits(volume.coerceIn(0f, 1f).toDouble())) }

    /** Stops the thread and releases the track. Idempotent. */
    @Synchronized
    override fun stop() {
        running = false
        thread?.let { try { it.join(500) } catch (_: InterruptedException) {} }
        thread = null
        targetBits.set(NONE)
        if (_state.value == State.RUNNING) _state.value = State.STOPPED
    }

    override fun stateName(): String = _state.value.name

    private companion object { const val NONE = Long.MIN_VALUE }
}
