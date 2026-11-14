package net.linspad.atlasphone.running

import net.linspad.atlasphone.mobile.audio.BeatScheduler
import net.linspad.atlasphone.mobile.audio.ClickConfig
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class BeatSchedulerTest {
    private val sr = ClickConfig.SAMPLE_RATE_HZ
    private val click = BeatScheduler.renderClick(sr, ClickConfig.CLICK_MS, ClickConfig.CLICK_FREQ_HZ, ClickConfig.CLICK_PEAK)

    /** Renders [seconds] at [spm] in buffers of [bufferFrames]; returns the audio. */
    private fun render(seconds: Int, spm: Double, bufferFrames: Int): ShortArray {
        val s = BeatScheduler(sr, click); val out = ShortArray(seconds * sr)
        var pos = 0
        while (pos < out.size) {
            val n = minOf(bufferFrames, out.size - pos)
            val buf = ShortArray(n); s.fill(buf, n, spm); buf.copyInto(out, pos); pos += n
        }
        return out
    }

    /** Frame index of every beat start (first non-zero sample after silence). */
    private fun beatStarts(a: ShortArray): List<Int> {
        val starts = ArrayList<Int>(); var quiet = true
        for (i in a.indices) {
            if (a[i].toInt() != 0 && quiet) { starts.add(i); quiet = false }
            if (i >= click.size && a[i].toInt() == 0 && a[i - 1].toInt() == 0) quiet = true
        }
        return starts
    }

    @Test fun oneMinuteHasExactlyTheTargetBeatsWithoutDrift() {
        for (spm in listOf(150.0, 170.0, 180.0)) {
            val audio = render(60, spm, 441)
            val beats = beatStarts(audio)
            assertEquals("count at $spm", spm, beats.size.toDouble(), 1.0)
            val interval = sr * 60.0 / spm
            // The click's first sample is 0 (sine start), so the first audible sample is one frame after the beat start.
            beats.forEachIndexed { k, f -> assertTrue("beat $k at $spm drifts", Math.abs(f - 1 - k * interval) < 1.5) }
        }
    }

    @Test fun bufferSizeDoesNotChangeTheAudio() {
        assertTrue(render(20, 173.4, 441).contentEquals(render(20, 173.4, 4410)))
    }

    @Test fun targetChangeAffectsOnlyTheIntervalAfterTheNextBeat() {
        val s = BeatScheduler(sr, click)
        val a = ShortArray(sr * 5); s.fill(a, a.size, 120.0)          // 0.5 s interval; the next beat falls on the first frame of b
        val b = ShortArray(sr * 5); s.fill(b, b.size, 180.0)
        val starts = beatStarts(b)
        assertTrue("the already scheduled beat keeps its place", starts.first() <= 2)
        assertEquals("the interval after it uses the new target", sr * 60.0 / 180.0, (starts[1] - starts[0]).toDouble(), 1.5)
    }

    @Test fun noTargetIsSilenceAndTheFirstBeatAfterSilenceIsImmediate() {
        val s = BeatScheduler(sr, click)
        val silent = ShortArray(sr); assertEquals(0, s.fill(silent, silent.size, 0.0)); assertTrue(silent.all { it.toInt() == 0 })
        val next = ShortArray(441); assertEquals(1, s.fill(next, next.size, 170.0))
        assertTrue("click starts within the first frames", next.take(5).any { it.toInt() != 0 })
    }

    @Test fun clickIsQuiet() {
        val peak = render(5, 170.0, 441).maxOf { Math.abs(it.toInt()) }
        assertTrue(peak <= ClickConfig.CLICK_PEAK * 32767 + 1)
        assertTrue(peak > 1000)
    }
}
