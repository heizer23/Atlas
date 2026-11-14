package net.linspad.atlasphone.running

import net.linspad.atlasphone.running.ghost.FieldRanking
import net.linspad.atlasphone.running.ghost.GhostPoint
import net.linspad.atlasphone.running.ghost.GhostProfile
import net.linspad.atlasphone.running.ghost.GhostSession
import net.linspad.atlasphone.running.ghost.RouteGeometry
import net.linspad.atlasphone.running.ghost.RoutePoint
import net.linspad.atlasphone.running.recap.FinishStandings
import net.linspad.atlasphone.running.ui.achievements
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** ST1: standing and achievements from real data only. Route 1000 m; ghosts run at constant speed. */
class FinishStandingTest {
    private fun profile(id: String, secs: Int) = GhostProfile(id, "route", 1, (0..secs).map { GhostPoint(it.toDouble(), it * 1000.0 / secs, null) })
    private val a = profile("a", 100)
    private val b = profile("b", 120) // main ghost
    private val c = profile("c", 140)
    private val field = listOf(a, b, c)

    private fun done(myT: Double, previous: String? = null, f: List<GhostProfile> = field) =
        FinishStandings.compute(b, f, previous, myT, 1000.0, 1000.0)

    @Test fun fasterThanAllGhostsIsFirstWithEveryoneOvertaken() {
        val s = done(90.0)
        assertEquals(1, s.position); assertEquals(3, s.fieldSize); assertEquals(3, s.overtaken)
        assertTrue(s.routeCompleted); assertEquals(90.0, s.routeTimeS!!, 0.0)
        assertTrue(s.rivalBeaten); assertEquals(30.0, s.rivalMarginS!!, 1e-9); assertEquals(120.0, s.rivalTimeS, 0.0)
        assertTrue(s.personalRecord)
    }

    @Test fun betweenGhostsAndSlowerThanAll() {
        val mid = done(110.0)
        assertEquals(2, mid.position); assertEquals(2, mid.overtaken); assertTrue(mid.rivalBeaten); assertEquals(10.0, mid.rivalMarginS!!, 1e-9)
        assertFalse(mid.personalRecord)
        val last = done(150.0)
        assertEquals(4, last.position); assertEquals(0, last.overtaken)
        assertFalse(last.rivalBeaten); assertEquals(30.0, last.rivalMarginS!!, 1e-9); assertFalse(last.personalRecord)
    }

    @Test fun tieWithTheFastestGhostFavoursTheRunner() {
        val s = done(100.0)
        assertEquals(1, s.position)
        assertTrue("a tie with the fastest ghost still gives a personal record (ties favour the runner)", s.personalRecord)
    }

    @Test fun incompleteRouteUsesTheLivePositionMechanism() {
        val s = FinishStandings.compute(b, field, null, 55.0, 500.0, 1000.0)
        assertFalse(s.routeCompleted); assertNull(s.routeTimeS)
        assertEquals(2, s.position)            // only "a" (550 m at 55 s) is ahead of 500 m
        assertEquals(2, s.overtaken)
        assertTrue(s.rivalBeaten); assertEquals(5.0, s.rivalMarginS!!, 1e-6)
        assertFalse("never a personal record on an incomplete route", s.personalRecord)
        assertNull(s.beatPreviousRun)
    }

    @Test fun previousRunFactsRequireItsCachedProfile() {
        val faster = done(110.0, previous = "c")
        assertEquals(true, faster.beatPreviousRun); assertEquals(3, faster.previousRunRank)
        val slower = done(110.0, previous = "a")
        assertEquals(false, slower.beatPreviousRun); assertEquals(1, slower.previousRunRank)
        val uncached = done(110.0, previous = "not-cached")
        assertNull(uncached.beatPreviousRun); assertNull(uncached.previousRunRank)
        assertNull(done(110.0, previous = null).beatPreviousRun)
        assertEquals(listOf("Faster than your previous run on this route", "Your previous run on this route ranks 3"), achievements(faster).drop(0).filter { !it.startsWith("Personal") })
        assertTrue(achievements(uncached).isEmpty())
    }

    @Test fun emptyFieldAndDuplicateMainAreHandled() {
        val alone = done(90.0, f = emptyList())
        assertEquals(1, alone.fieldSize); assertEquals(1, alone.position)
        assertEquals(3, done(90.0, f = listOf(a, b, b, c)).fieldSize) // main deduplicated by run id
    }

    @Test fun noStandingWithoutAMatchedFixAndFieldRankingIsUnchanged() {
        val line = listOf(RoutePoint(53.59, 10.0, 0.0), RoutePoint(53.59 + 1000 / 111194.9266, 10.0, 1000.0))
        val route = RouteGeometry("route", "Line", 1, 1000.0, false, line)
        val s = GhostSession(route, b, 0, field)
        assertNull(s.finalStanding(null))
        for (i in 0..20) s.addFix(i * 1000L, 53.59 + i * 4.4 / 111194.9266, 10.0, 5.0, emptyList())
        assertNotNull(s.finalStanding(null))
        assertEquals(mapOf("a" to 1, "b" to 2, "c" to 3), FieldRanking.ranks(field))
    }
}
