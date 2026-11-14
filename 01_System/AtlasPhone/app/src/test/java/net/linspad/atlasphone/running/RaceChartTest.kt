package net.linspad.atlasphone.running

import net.linspad.atlasphone.running.ghost.GhostLive
import net.linspad.atlasphone.running.ghost.GhostPoint
import net.linspad.atlasphone.running.ghost.GhostProfile
import net.linspad.atlasphone.running.ghost.GhostReading
import net.linspad.atlasphone.running.ghost.GhostStatus
import net.linspad.atlasphone.running.live.LiveHistory
import net.linspad.atlasphone.running.live.RaceChart
import net.linspad.atlasphone.running.live.RaceConfig
import net.linspad.atlasphone.running.metrics.LiveMetrics
import net.linspad.atlasphone.running.metrics.RunMetricsAccumulator
import net.linspad.atlasphone.mobile.model.RawLocation
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class RaceChartTest {
    /** Ghost at 4 m/s for 250 s (250 s per km). */
    private val profile = GhostProfile("g", "r", 1, (0..250).map { GhostPoint(it.toDouble(), it * 4.0, null) })

    @Test fun ghostSectionPaceIsTheGhostsTimeOverTheSameSection() {
        assertEquals(250.0, RaceChart.ghostSectionPace(profile, 100.0, 180.0)!!, 1e-6)
        assertNull("section shorter than 15 m", RaceChart.ghostSectionPace(profile, 100.0, 110.0))
        assertNull("beyond what the ghost covers", RaceChart.ghostSectionPace(profile, 900.0, 1100.0))
    }

    private fun metrics(t: Double, race: Double? = null, rolling: Double? = null) =
        LiveMetrics(t * 4, 250.0, 250.0, t, t, null, null, 5f, rollingPaceSPerKm = rolling, racePaceSPerKm = race)

    private fun live(progress: Double, gap: Double) = GhostLive(
        GhostStatus.ON_COURSE, "r", GhostReading(gap, null, null, null, false, null), progress, 1000.0)

    @Test fun gapHistoryKeepsTwoMinutesOrderedAndRacePaceFieldsFlowThrough() {
        val h = LiveHistory()
        for (t in 1..200) h.record(metrics(t.toDouble(), race = 240.0, rolling = 250.0), live(t * 4.0, -t / 10.0), ghostProfile = profile)
        val tr = h.snapshot()
        assertTrue(tr.gapSeries.first().first >= 200 - RaceConfig.GAP_HISTORY_S - 1e-9)
        assertEquals(tr.gapSeries.sortedBy { it.first }, tr.gapSeries)
        assertEquals(-20.0, tr.gapSeries.last().second, 1e-9)          // negative = ahead
        assertEquals(240.0, tr.racePaceSPerKm!!, 0.0)
        assertEquals(250.0, tr.rollingPaceSPerKm!!, 0.0)                 // the 120 s rolling pace is untouched
        assertEquals(250.0, tr.ghostSectionPaceSPerKm!!, 1e-6)
    }

    @Test fun noGhostProfileMeansNoSectionPace() {
        val h = LiveHistory()
        for (t in 1..60) h.record(metrics(t.toDouble()), live(t * 4.0, 1.0))
        assertNull(h.snapshot().ghostSectionPaceSPerKm)
        assertNotNull(h.snapshot().gapSeries)
    }

    @Test fun racePaceUsesTheLast20SecondsAndIsNullWithoutMovement() {
        val acc = RunMetricsAccumulator(0)
        assertNull(acc.snapshot(1000).racePaceSPerKm)
        // 4 m/s north for 120 s, one fix per second
        for (s in 0..120) acc.addFix(RawLocation(s * 1000L, 52.0 + 4.0 * s / 111194.9266, 13.0, 5f, null, null, null))
        val m = acc.snapshot(120_500)
        assertEquals(250.0, m.racePaceSPerKm!!, 3.0)
        assertNotNull(m.rollingPaceSPerKm)
        val still = RunMetricsAccumulator(0)
        for (s in 0..30) still.addFix(RawLocation(s * 1000L, 52.0, 13.0, 5f, null, null, null))
        assertNull(still.snapshot(30_500).racePaceSPerKm)
    }
}
