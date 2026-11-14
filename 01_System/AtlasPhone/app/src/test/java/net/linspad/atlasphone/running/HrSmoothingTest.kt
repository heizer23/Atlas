package net.linspad.atlasphone.running

import net.linspad.atlasphone.running.hr.HrConfig
import net.linspad.atlasphone.running.hr.HrPoint
import net.linspad.atlasphone.running.hr.HrSmoothing
import net.linspad.atlasphone.running.hr.HrSmoothingMode
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** HR1 validity (shared oracle recovery_golden.json) and HR2 display smoothing. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class HrSmoothingTest {
    private val base = 1_700_000_000_000L
    private fun p(tS: Int, bpm: Int) = HrPoint(base + tS * 1000L, bpm)

    @Test fun validityMatchesTheGoldenVectors() {
        for (c in RecoveryGolden.cases()) {
            assertEquals(c.name, c.validCount, HrSmoothing.validSamples(c.points).size)
        }
    }

    /** 140 bpm every second from 0 to 40 s, with a 0, a 250, an isolated 190 spike and a 12 s gap (20..31 missing). */
    private fun artifactSeries(): List<HrPoint> =
        (0..40).filter { it !in 20..31 }.map { t -> p(t, when (t) { 5 -> 0; 10 -> 250; 15 -> 190; else -> 140 }) }

    @Test fun smoothingNeverTurnsMissingIntoZero() {
        val input = artifactSeries()
        val copy = input.toList()
        for (mode in HrSmoothingMode.entries) {
            val out = HrSmoothing.series(input, mode)
            assertEquals(input.size, out.size)
            for (point in out) {
                val t = ((point.tsMillis - base) / 1000).toInt()
                if (t in listOf(5, 10, 15)) assertNull("$mode t=$t is a gap, not a number", point.bpm)
                else assertEquals("$mode t=$t", 140.0, point.bpm!!, 1e-9) // edges use only the readings that exist
            }
        }
        assertEquals("raw values are unchanged", copy, input)
        // the 12 s gap (20..31 s missing): no value inside it in any mode (RAW needs a reading within 2 s, rolling one in its window)
        for (mode in HrSmoothingMode.entries) {
            assertNull("$mode trailing at 29 s", HrSmoothing.valueAt(input, mode, base + 29_000, centered = false))
            assertNull("$mode centered at 26 s", HrSmoothing.valueAt(input, mode, base + 26_000, centered = true))
        }
        assertTrue(HrSmoothing.isGap(base + 19_000, base + 32_000))
        assertFalse(HrSmoothing.isGap(base + 1_000, base + 2_000))
    }

    @Test fun artifactsAreOnlyInvalidForTheSmoothedSeries() {
        val valid = HrSmoothing.validSamples(artifactSeries())
        assertEquals(artifactSeries().size - 3, valid.size)
        assertTrue(valid.none { it.bpm == 0 || it.bpm == 250 || it.bpm == 190 })
    }

    @Test fun trailingAndCenteredWindowsDifferOnlyByPlacement() {
        val ramp = (0..30).map { t -> p(t, 100 + t) } // +1 bpm per second
        val at = base + 10_000
        assertEquals(110.0, HrSmoothing.valueAt(ramp, HrSmoothingMode.ROLLING_5S, at, centered = true)!!, 1e-9)   // [7.5, 12.5] -> 8..12
        assertEquals(108.0, HrSmoothing.valueAt(ramp, HrSmoothingMode.ROLLING_5S, at, centered = false)!!, 1e-9)  // (5, 10] -> 6..10
        assertEquals(110.0, HrSmoothing.valueAt(ramp, HrSmoothingMode.RAW, at, centered = false)!!, 1e-9)
        assertEquals(105.5, HrSmoothing.valueAt(ramp, HrSmoothingMode.ROLLING_10S, at, centered = false)!!, 1e-9) // (0, 10] -> 1..10
        // edge: the window at the start only uses the readings that exist
        assertEquals(101.0, HrSmoothing.valueAt(ramp, HrSmoothingMode.ROLLING_5S, base, centered = true)!!, 1e-9) // 0, 1, 2 -> 101
    }

    @Test fun rawSeriesKeepsValidValuesAndSettingParsesWithFallback() {
        val out = HrSmoothing.series(artifactSeries(), HrSmoothingMode.RAW)
        assertEquals(140.0, out.first { it.tsMillis == base }.bpm!!, 0.0)
        assertNotNull(HrConfig.VALID_MIN_BPM)
        assertEquals(HrSmoothingMode.ROLLING_5S, HrSmoothingMode.parse(null))
        assertEquals(HrSmoothingMode.ROLLING_5S, HrSmoothingMode.parse("bogus"))
        assertEquals(HrSmoothingMode.ROLLING_10S, HrSmoothingMode.parse("ROLLING_10S"))
    }
}
