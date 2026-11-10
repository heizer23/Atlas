package net.linspad.atlasphone.running

import net.linspad.atlasphone.mobile.model.RawHeartRate
import net.linspad.atlasphone.mobile.model.RawLocation
import net.linspad.atlasphone.running.ghost.RoutePoint
import net.linspad.atlasphone.running.live.GapMomentum
import net.linspad.atlasphone.running.live.HrTarget
import net.linspad.atlasphone.running.live.HrZone
import net.linspad.atlasphone.running.live.LocalMap
import net.linspad.atlasphone.running.live.PaceSmoother
import net.linspad.atlasphone.running.live.Trend
import net.linspad.atlasphone.running.live.leadTransition
import net.linspad.atlasphone.running.live.trendOf
import net.linspad.atlasphone.running.metrics.RunMetricsAccumulator
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class LiveInsightsTest {
    @Test fun hrZones() {
        assertEquals(HrZone.NO_SIGNAL, HrTarget.zone(null, 140))
        assertEquals(HrZone.NO_SIGNAL, HrTarget.zone(140, null))
        assertEquals(HrZone.BELOW, HrTarget.zone(134, 140))
        assertEquals(HrZone.NEAR, HrTarget.zone(135, 140))
        assertEquals(HrZone.NEAR, HrTarget.zone(145, 140))
        assertEquals(HrZone.ABOVE, HrTarget.zone(146, 140))
    }

    @Test fun categoryNamesEquivalentEfforts() {
        assertEquals("4 km · HR 140", HrTarget.category(140, 4010.0))
        assertEquals("4.5 km · HR 150", HrTarget.category(150, 4400.0))
        assertEquals("HR 140", HrTarget.category(140, null))
        assertNull(HrTarget.category(null, 4000.0))
    }

    @Test fun momentumOver100mNeedsHistoryAndSigns() {
        val g = GapMomentum()
        g.add(0.0, 0.0, 50.0)
        g.add(10.0, 50.0, 48.0)
        assertNull(g.changeOver100m()) // less than 100 m covered
        g.add(20.0, 100.0, 45.0)
        g.add(30.0, 150.0, 40.0)
        assertEquals(-8.0, g.changeOver100m()!!, 1e-9) // 40 now vs 48 at s = 50
        assertEquals(45.0, g.leadSecondsAgo()!!, 1e-9) // 30 s - 10 s = 20 s -> lead 45
    }

    @Test fun leadTransitionShowsChangeOnlyWhenRoundedValueMoved() {
        assertEquals("50 m ahead → 45 m ahead", leadTransition(50.2, 45.0))
        assertEquals("45 m ahead", leadTransition(45.4, 45.0))
        assertEquals("12 m ahead → 3 m behind", leadTransition(12.0, -3.0))
        assertEquals("45 m ahead", leadTransition(null, 45.0))
    }

    @Test fun trendHasADeadBandAndFlipsWithSide() {
        assertEquals(Trend.STEADY, trendOf(1.5, true))
        assertEquals(Trend.WIDENING, trendOf(6.0, true))
        assertEquals(Trend.CLOSING, trendOf(-6.0, true))
        assertEquals(Trend.CLOSING, trendOf(6.0, false)) // behind, deficit shrinking
        assertEquals(Trend.WIDENING, trendOf(-6.0, false))
        assertNull(trendOf(null, true))
    }

    @Test fun paceSmootherDampensAndRestartsAfterGap() {
        val s = PaceSmoother(0.5)
        assertEquals(300.0, s.update(300.0)!!, 1e-9)
        assertEquals(330.0, s.update(360.0)!!, 1e-9)
        assertNull(s.update(null))
        assertEquals(400.0, s.update(400.0)!!, 1e-9)
    }

    private fun fix(t: Long, lat: Double) = RawLocation(t, lat, 10.0, 5f, null, null, null, null)

    @Test fun rollingPaceUsesLastTwoMinutesAndStaleHrIsNoSignal() {
        val acc = RunMetricsAccumulator(0L)
        // 3 m/s northward for 300 s, a fix per second: 1 deg lat = 111.19 km
        for (i in 0..300) acc.addFix(fix(i * 1000L, 3.0 * i / 111_194.9))
        acc.addHeartRate(RawHeartRate(299_000L, 150, null))
        val live = acc.snapshot(300_500L)
        assertNotNull(live.rollingPaceSPerKm)
        assertEquals(1000.0 / 3.0, live.rollingPaceSPerKm!!, 3.0)
        assertEquals(150, live.currentHr)
        assertNull(acc.snapshot(320_000L).currentHr) // older than the live HR staleness window
    }

    @Test fun rollingPaceIsNullWithoutEnoughMovement() {
        val acc = RunMetricsAccumulator(0L)
        acc.addFix(fix(0, 3.0))
        assertNull(acc.snapshot(1000L).rollingPaceSPerKm)
    }

    private val route = listOf(RoutePoint(50.0, 10.0, 0.0), RoutePoint(50.001, 10.0, 111.19), RoutePoint(50.004, 10.0, 445.0), RoutePoint(50.008, 10.0, 890.0))

    @Test fun localMapCentersOnRunnerAndPlacesGhost() {
        val v = LocalMap.build(route, 200.0, 250.0)
        assertEquals(0.0, v.runner.east, 1e-9)
        val g = v.ghost!!
        assertEquals(50.0, g.north, 1.0) // ghost 50 m further north
        assertEquals(0.0, g.east, 1.0)
        assertTrue(!v.ghostClamped)
        assertEquals(LocalMap.MIN_RADIUS_M, v.radiusM, 1e-9)
        assertTrue(v.route.size >= 2)
    }

    @Test fun localMapClampsAFarGhostToTheEdge() {
        val v = LocalMap.build(route, 100.0, 880.0)
        assertTrue(v.ghostClamped)
        assertEquals(LocalMap.MAX_RADIUS_M, v.radiusM, 1e-9)
        assertTrue(Math.hypot(v.ghost!!.east, v.ghost!!.north) <= v.radiusM)
    }
}
