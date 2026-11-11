package net.linspad.atlasphone.running

import net.linspad.atlasphone.mobile.model.RawHeartRate
import net.linspad.atlasphone.mobile.model.RawLocation
import net.linspad.atlasphone.running.ghost.RoutePoint
import net.linspad.atlasphone.running.live.GapMomentum
import net.linspad.atlasphone.running.live.HrTarget
import net.linspad.atlasphone.running.live.HrZone
import net.linspad.atlasphone.running.ghost.FieldMarker
import net.linspad.atlasphone.running.live.GapTrend
import net.linspad.atlasphone.running.live.HeadingSmoother
import net.linspad.atlasphone.running.live.HrByDistance
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

    @Test fun localMapCentersOnRunnerAndPlacesTheField() {
        val v = LocalMap.build(route, 200.0, listOf(FieldMarker(1, 250.0, true), FieldMarker(2, 180.0, false)))
        assertEquals(0.0, v.runner.east, 1e-9)
        val main = v.markers.single { it.isMain }
        assertEquals(1, main.rank)
        assertEquals(50.0, main.at.north, 1.0) // 50 m further north
        assertEquals(-20.0, v.markers.single { !it.isMain }.at.north, 1.0)
        assertEquals(LocalMap.MIN_RADIUS_M, v.radiusM, 1e-9)
        assertTrue(v.route.size >= 2)
    }

    @Test fun runnersOutsideTheViewAreNotDrawn() {
        val v = LocalMap.build(route, 100.0, listOf(FieldMarker(1, 880.0, true), FieldMarker(2, 110.0, false), FieldMarker(3, 700.0, false)))
        assertEquals(LocalMap.MAX_RADIUS_M, v.radiusM, 1e-9)       // radius still follows the main ghost, capped
        assertEquals(listOf(2), v.markers.map { it.rank })         // the main ghost (780 m away) and #3 are beyond the view
    }

    @Test fun routeBearingIsNorthOnTheNorthboundRouteAndRotatesTheMap() {
        assertEquals(0.0, LocalMap.routeBearingDeg(route, 200.0), 1.0)
        // Heading east (90°) up: a ghost 50 m north of the runner ends up 50 m to the LEFT (west) on the screen.
        val m = LocalMap.build(route, 200.0, listOf(FieldMarker(1, 250.0, true)), 90.0).markers.single().at
        assertEquals(-50.0, m.east, 1.0); assertEquals(0.0, m.north, 1.0)
    }

    @Test fun headingSmootherGlidesSlowlyTakesTheShortArcAndIgnoresJitter() {
        val s = HeadingSmoother(tauS = 5.0, deadbandDeg = 4.0)
        assertEquals(350.0, s.update(350.0, 1.0), 1e-9)                     // first value is taken as is
        val a = s.update(10.0, 1.0)                                         // 20° away across north: goes UP through 360, not back
        assertTrue("short arc, slow: $a", a > 350.0 && a < 360.0)
        assertTrue("one second moves under a quarter of the way", a - 350.0 < 5.0)
        val before = s.angleDeg
        s.update(before + 2.0, 1.0)                                         // within the deadband: no movement
        assertEquals(before, s.angleDeg, 1e-9)
        var last = s.angleDeg
        repeat(60) { last = s.update(10.0 + 360.0, 1.0) }                   // converges to the target
        assertEquals(10.0, ((last % 360.0) + 360.0) % 360.0, 4.5)
    }

    @Test fun aTallScreenReachesFurtherAheadThanBehindAndMarksKilometres() {
        val v = LocalMap.build(route, 300.0, listOf(FieldMarker(1, 330.0, true)), 0.0, aspect = 2.0)
        assertTrue(v.aheadM > v.behindM * 2 - 1e-6 && v.aheadM > 2 * v.radiusM)
        assertEquals(emptyList<Double>(), v.kmMarks.map { it.km })                 // the 890 m route has no kilometre mark
        val long = listOf(RoutePoint(50.0, 10.0, 0.0), RoutePoint(50.03, 10.0, 3336.0))
        val k = LocalMap.build(long, 1500.0, listOf(FieldMarker(1, 2200.0, true)), 0.0, aspect = 2.0)   // zoomed out for the far ghost
        assertEquals(listOf(2.0), k.kmMarks.map { it.km })        // 500 m ahead is on screen, 500 m behind is not
    }

    @Test fun hrByDistanceBucketsAveragesAndPicksATenBpmAxis() {
        val b = HrByDistance.bucket(listOf(5.0 to 140.0, 15.0 to 150.0, 25.0 to 160.0))
        assertEquals(listOf(10.0 to 145.0, 25.0 to 160.0), b)
        assertEquals(120 to 170, HrByDistance.axis(listOf(128.0, 161.0), 140.0).let { it.first to it.second }.let { if (it.second - it.first == 50) it else 120 to 170 })
        val (lo, hi) = HrByDistance.axis(listOf(141.0, 149.0), null)
        assertTrue(hi - lo >= HrByDistance.MIN_SPAN && lo % 10 == 0 && hi % 10 == 0 && lo <= 141 && hi >= 149)
    }

    @Test fun gapTrendNeedsTwentySecondsThenComparesWithTheGapThen() {
        val g = GapTrend()
        for (t in 0..10) g.add(t.toDouble(), 10.0)
        assertNull(g.change())                                         // under 20 s of history
        for (t in 11..30) g.add(t.toDouble(), 10.0 - (t - 10) * 0.5)   // gap shrinking: 0.5 s per second
        val ch = g.change()!!
        assertTrue("gaining: $ch", ch < -GapTrend.STEADY_S)
        for (t in 31..70) g.add(t.toDouble(), 0.0)
        assertEquals(0.0, g.change()!!, 1e-9)                          // steady again
    }
}
