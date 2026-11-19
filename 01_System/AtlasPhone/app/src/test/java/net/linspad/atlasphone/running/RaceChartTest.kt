package net.linspad.atlasphone.running

import net.linspad.atlasphone.running.ghost.GhostLive
import net.linspad.atlasphone.running.ghost.GhostPoint
import net.linspad.atlasphone.running.ghost.GhostProfile
import net.linspad.atlasphone.running.ghost.GhostReading
import net.linspad.atlasphone.running.ghost.GhostStatus
import net.linspad.atlasphone.running.live.LiveHistory
import net.linspad.atlasphone.running.live.RaceChart
import net.linspad.atlasphone.running.live.RaceDiff
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

    @Test fun racePaceFieldsFlowThroughAndSideChartsNeedAGhost() {
        val h = LiveHistory()
        for (t in 1..200) h.record(metrics(t.toDouble(), race = 240.0, rolling = 250.0), live(t * 4.0, -t / 10.0), ghostProfile = profile)
        val tr = h.snapshot()
        assertEquals(240.0, tr.racePaceSPerKm!!, 0.0)
        assertEquals(250.0, tr.rollingPaceSPerKm!!, 0.0)                 // the 120 s rolling pace is untouched
        assertNotNull(tr.race)
        val none = LiveHistory()
        for (t in 1..60) none.record(metrics(t.toDouble()), live(t * 4.0, 1.0))
        assertNull(none.snapshot().race)
    }

    /** Ghost: 4 m/s (250 s/km) with HR 149 throughout. */
    private val hrGhost = GhostProfile("g", "r", 1, (0..250).map { GhostPoint(it.toDouble(), it * 4.0, 149.0) })

    @Test fun deltasUseTheSpecSignsAndPositionAlignment() {
        val d = RaceDiff()
        // Runner: 4.138 m/s (= 7:15/km is 435 s/km -> 2.2989 m/s). Use 435 s/km vs ghost 250 s/km? Spec example uses 420 ghost: build it.
        val slowGhost = GhostProfile("g", "r", 1, (0..300).map { GhostPoint(it.toDouble(), it * 1000.0 / 420.0, 149.0) })
        val v = 1000.0 / 435.0
        for (t in 0..300) d.add(t.toDouble(), t * v, 142.0)
        val r = d.snapshot(slowGhost)!!
        assertEquals(-7.0, r.hrDelta.last().second!!, 1e-9)          // 142 - 149
        assertEquals(15.0, r.paceDelta.last().second!!, 0.5)         // 7:15 - 7:00, positive = runner slower
    }

    @Test fun distanceGapIsEqualElapsedTimeAndPositiveWhenAhead() {
        val d = RaceDiff()
        for (t in 0..100) d.add(t.toDouble(), t * 4.0 + 30.0, null)    // 30 m ahead of a 4 m/s ghost at every instant
        val r = d.snapshot(hrGhost)!!
        assertEquals(30.0, r.gapM.last().second!!, 1e-6)
        assertNull("no HR recorded: honest gap, not zero", r.hrDelta.last().second)
        for (t in 101..120) d.add(t.toDouble(), 100 * 4.0 + 30.0 - (t - 100) * 0.1, null)   // jitter: position never goes back
        assertTrue(d.snapshot(hrGhost)!!.nowS >= 430.0)
    }

    @Test fun selectingAnotherGhostRederivesEverythingFromTheSameTrail() {
        val d = RaceDiff()
        for (t in 0..100) d.add(t.toDouble(), t * 4.0, 150.0)
        val fast = GhostProfile("f", "r", 1, (0..100).map { GhostPoint(it.toDouble(), it * 5.0, 140.0) })
        assertEquals(0.0, d.snapshot(hrGhost)!!.gapM.last().second!!, 1e-6)
        assertEquals(-100.0, d.snapshot(fast)!!.gapM.last().second!!, 1e-6)     // 100 m behind at t=100
        assertEquals(10.0, d.snapshot(fast)!!.hrDelta.last().second!!, 1e-6)
    }

    @Test fun sessionSelectionSwitchesTheComparedGhostOnly() {
        val route = net.linspad.atlasphone.running.ghost.RouteGeometry("r", "R", 1, 1000.0, false,
            listOf(net.linspad.atlasphone.running.ghost.RoutePoint(52.0, 10.0, 0.0), net.linspad.atlasphone.running.ghost.RoutePoint(52.0 + 1000 / 111194.9266, 10.0, 1000.0)))
        val s = net.linspad.atlasphone.running.ghost.GhostSession(route, hrGhost, 0, listOf(GhostProfile("x", "r", 1, (0..200).map { GhostPoint(it.toDouble(), it * 5.0, 140.0) })))
        for (i in 0..20) s.addFix(i * 1000L, 52.0 + i * 4.0 / 111194.9266, 10.0, 5.0, emptyList())
        assertEquals("g", s.snapshot(20_500).selectedRunId)
        s.select("x"); s.select("nope")
        val live = s.snapshot(20_500)
        assertEquals("x", live.selectedRunId)
        assertEquals(listOf("x"), live.field.filter { it.isMain }.map { it.runId })
        assertEquals(-20.0, live.reading!!.leadM!!, 1.0)
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
