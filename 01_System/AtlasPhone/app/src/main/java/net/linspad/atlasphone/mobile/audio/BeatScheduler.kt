package net.linspad.atlasphone.mobile.audio

import kotlin.math.PI
import kotlin.math.exp
import kotlin.math.sin

/** Constants of the click track (MobilePlatform_API.md). */
object ClickConfig {
    const val SAMPLE_RATE_HZ = 44100
    const val CLICK_MS = 12
    const val CLICK_FREQ_HZ = 1800.0
    /** Fraction of full scale at volume 1.0. */
    const val CLICK_PEAK = 0.5
    const val BUFFER_MS = 20
    /** Default gain 0..1 (very quiet); MetronomeConfig.DEFAULT_VOLUME refers to this single declaration. */
    const val DEFAULT_VOLUME = 0.2f
}

/**
 * Pure, Android-free, sample-accurate beat generator. The interval to the next beat is computed when the previous beat
 * starts, from the CURRENT target (frames = sampleRate * 60 / spm), with the fractional remainder carried, so there is no
 * drift and no timer. Target <= 0 / NaN = silence; the first beat after silence starts immediately.
 */
class BeatScheduler(private val sampleRateHz: Int, private val click: ShortArray) {
    private var untilNextBeat = 0.0     // frames until the next beat starts, measured from the current frame
    private var clickPos = -1           // index inside the click being rendered, -1 = none

    /** Writes [frames] mono PCM16 samples to [out]; returns the number of beats that STARTED inside this buffer. */
    fun fill(out: ShortArray, frames: Int, targetSpm: Double): Int {
        val audible = targetSpm > 0.0 && !targetSpm.isNaN()
        if (!audible) untilNextBeat = 0.0
        val interval = if (audible) sampleRateHz * 60.0 / targetSpm else 0.0
        var beats = 0
        for (i in 0 until frames) {
            if (audible && untilNextBeat < 1.0) {
                clickPos = 0
                beats++
                untilNextBeat += interval
            }
            if (audible) untilNextBeat -= 1.0
            if (clickPos in click.indices) { out[i] = click[clickPos]; clickPos++ } else { out[i] = 0; clickPos = -1 }
        }
        return beats
    }

    companion object {
        /** Short sine burst with exponential decay (starts at zero: no DC step, no pop). */
        fun renderClick(sampleRateHz: Int, clickMs: Int, freqHz: Double, peak: Double): ShortArray {
            val n = sampleRateHz * clickMs / 1000
            val tau = clickMs / 1000.0 / 5.0
            return ShortArray(n) { i ->
                val t = i.toDouble() / sampleRateHz
                (peak * 32767.0 * sin(2 * PI * freqHz * t) * exp(-t / tau)).toInt().toShort()
            }
        }
    }
}
