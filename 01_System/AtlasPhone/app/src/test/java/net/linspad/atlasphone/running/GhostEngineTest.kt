package net.linspad.atlasphone.running

import net.linspad.atlasphone.running.ghost.FieldRanking
import net.linspad.atlasphone.running.ghost.GhostCache
import net.linspad.atlasphone.running.ghost.GhostComparison
import net.linspad.atlasphone.running.ghost.GhostPoint
import net.linspad.atlasphone.running.ghost.GhostProfile
import net.linspad.atlasphone.running.ghost.GhostSession
import net.linspad.atlasphone.running.ghost.GhostStatus
import net.linspad.atlasphone.running.ghost.Match
import net.linspad.atlasphone.running.ghost.MovingClock
import net.linspad.atlasphone.running.ghost.ProgressTracker
import net.linspad.atlasphone.running.ghost.RouteGeometry
import net.linspad.atlasphone.running.ghost.RoutePoint
import net.linspad.atlasphone.running.ghost.RouteProjector
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

/**
 * Ghost engine parity with the Python reference (backend/ghost.py): both read the shared fixtures
 * 03_Application/RunningTracker/tests/fixtures/ghost_golden.json (comparison) and ghost_progress_golden.json (progress).
 * Runs under Robolectric because org.json is only available there.
 */
@org.junit.runner.RunWith(org.robolectric.RobolectricTestRunner::class)
@org.robolectric.annotation.Config(sdk = [34])
class GhostEngineTest {
    @get:Rule val tmp = TemporaryFolder()

    private fun fixture(name: String): JSONObject {
        val rel = "03_Application/RunningTracker/tests/fixtures/$name"
        var dir: File? = File("").absoluteFile
        while (dir != null) { File(dir, rel).takeIf { it.exists() }?.let { return JSONObject(it.readText()) }; dir = dir.parentFile }
        error("$name not found above ${File("").absolutePath}")
    }

    private fun profileOf(points: JSONArray) = GhostProfile(
        "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222", 1,
        (0 until points.length()).map { i -> points.getJSONArray(i).let { GhostPoint(it.getDouble(0), it.getDouble(1), if (it.isNull(2)) null else it.getDouble(2)) } },
    )

    private fun geometryOf(g: JSONArray) =
        (0 until g.length()).map { i -> g.getJSONArray(i).let { RoutePoint(it.getDouble(0), it.getDouble(1), it.getDouble(2)) } }

    // ── comparison: golden vectors ──────────────────────────────────────────

    @Test fun comparisonMatchesTheGoldenVectors() {
        val doc = fixture("ghost_golden.json")
        val profile = profileOf(doc.getJSONArray("profile"))
        val cases = doc.getJSONArray("cases")
        for (i in 0 until cases.length()) {
            val c = cases.getJSONObject(i)
            val got = GhostComparison.compare(profile, c.getDouble("my_t"), c.getDouble("my_s"))
            fun check(key: String, actual: Double?) {
                if (c.isNull(key)) assertNull("case $i $key", actual)
                else { assertNotNull("case $i $key", actual); assertEquals("case $i $key", c.getDouble(key), actual!!, 1e-6) }
            }
            check("time_gap_s", got.timeGapS); check("lead_m", got.leadM)
            check("ghost_hr_at_position", got.ghostHrAtPosition); check("ghost_hr_at_time", got.ghostHrAtTime)
            assertEquals("case $i finished", c.getBoolean("ghost_finished"), got.ghostFinished)
        }
    }

    @Test fun flatGhostSectionReturnsTheEarliestTime() {
        val p = GhostProfile("a", "b", 1, listOf(GhostPoint(0.0, 0.0, null), GhostPoint(10.0, 100.0, null), GhostPoint(20.0, 100.0, null), GhostPoint(30.0, 200.0, null)))
        assertEquals(10.0, GhostComparison.timeAtProgress(p, 100.0)!!, 1e-9)
    }

    // ── progress: shared oracle fixture ─────────────────────────────────────

    @Test fun progressMatchesTheSharedOracleFixture() {
        val f = fixture("ghost_progress_golden.json")
        val tracker = ProgressTracker(RouteProjector(geometryOf(f.getJSONArray("geometry"))))
        val start = f.getLong("started_at_ms")
        val pauses = f.getJSONArray("pauses_ms").let { a -> (0 until a.length()).map { i -> a.getJSONArray(i).let { PauseRecord(it.getLong(0), it.getLong(1), 0.0, 0.0) } } }
        val clock = MovingClock(start)
        val got = ArrayList<Pair<Double, Double>>()
        val fixes = f.getJSONArray("fixes")
        for (i in 0 until fixes.length()) {
            val x = fixes.getJSONArray(i)
            val ts = x.getLong(0)
            if (clock.inPause(ts, pauses)) continue
            val acc = if (x.isNull(3)) null else x.getDouble(3)
            val m = tracker.addFix(clock.movingS(ts, pauses), x.getDouble(1), x.getDouble(2), acc)
            if (m is Match.Matched && (got.isEmpty() || m.movingS - got.last().first >= 1.0)) got += m.movingS to m.progressM
        }
        val expected = f.getJSONObject("expected")
        val exp = expected.getJSONArray("profile")
        assertEquals(exp.length(), got.size)
        for (i in 0 until exp.length()) {
            assertEquals("t[$i]", exp.getJSONArray(i).getDouble(0), got[i].first, 0.006)
            assertEquals("s[$i]", exp.getJSONArray(i).getDouble(1), got[i].second, 0.006)
        }
        assertEquals(expected.getInt("matched"), tracker.matched)
        assertEquals(expected.getInt("off_course"), tracker.offCourse)
    }

    // ── session behaviour (live-only rules) ─────────────────────────────────

    private val line = listOf(RoutePoint(53.59, 10.0, 0.0), RoutePoint(53.59 + 1000 / 111194.9266, 10.0, 1000.0))
    private val route = RouteGeometry("22222222-2222-2222-2222-222222222222", "Test line", 1, 1000.0, false, line)
    // ghost: 4 m/s the whole way (250 s for 1 km)
    private val ghost = GhostProfile("11111111-1111-1111-1111-111111111111", route.routeId, 1, (0..250).map { GhostPoint(it.toDouble(), it * 4.0, 140.0) })
    private fun lat(northM: Double) = 53.59 + northM / 111194.9266

    @Test fun sessionWaitsForStartThenComparesThenSuspendsOffCourseAndRecovers() {
        val s = GhostSession(route, ghost, startedAtMillis = 0)
        assertEquals(GhostStatus.WAITING_FOR_START, s.snapshot(0).status)
        // runner at 4.4 m/s: ahead of the 4 m/s ghost
        for (i in 0..20) s.addFix(i * 1000L, lat(i * 4.4), 10.0, 5.0, emptyList())
        val live = s.snapshot(20_500)
        assertEquals(GhostStatus.ON_COURSE, live.status)
        val gap = live.reading!!.timeGapS!!
        assertTrue("ahead means negative gap, was $gap", gap < -1.5 && gap > -2.5)       // 88 m at t=20: ghost needed 22 s
        assertTrue(live.reading!!.leadM!! > 5.0)
        assertEquals(140.0, live.reading!!.ghostHrAtPosition!!, 1e-9)
        // three fixes 200 m east of the route: suspended, no false gap
        for (i in 21..23) s.addFix(i * 1000L, lat(i * 4.4), 10.0 + 200 / 66_000.0, 5.0, emptyList())
        val off = s.snapshot(23_500)
        assertEquals(GhostStatus.OFF_COURSE, off.status); assertNull(off.reading)
        // back on the route: comparison resumes
        s.addFix(24_000, lat(24 * 4.4), 10.0, 5.0, emptyList())
        assertEquals(GhostStatus.ON_COURSE, s.snapshot(24_500).status)
        // GPS silence
        assertEquals(GhostStatus.GPS_LOST, s.snapshot(24_000 + 11_000).status)
    }

    @Test fun pausedTimeCountsForNeitherRunner() {
        val pause = PauseRecord(10_000, 40_000, 10.0, 40.0)
        val s = GhostSession(route, ghost, startedAtMillis = 0)
        for (i in 0..10) s.addFix(i * 1000L, lat(i * 4.0), 10.0, 5.0, listOf(pause.copy(endedAtMillis = null, endedElapsedS = null)))
        for (i in 20..39) s.addFix(i * 1000L, lat(40.0), 10.0, 5.0, listOf(pause))     // inside the pause: ignored
        for (i in 40..50) s.addFix(i * 1000L, lat(40.0 + (i - 40) * 4.0), 10.0, 5.0, listOf(pause))
        val r = s.snapshot(50_500).reading!!
        // 50 s wall - 30 s pause = 20 s moving, 80 m: exactly the ghost's pace -> level
        assertEquals(0.0, r.timeGapS!!, 0.6)
    }

    @Test fun fieldIsRankedByFinishingTimeAndPositionCountsRunnersAhead() {
        fun at(id: String, mps: Double, secs: Int) = GhostProfile(id, route.routeId, 1, (0..secs).map { GhostPoint(it.toDouble(), it * mps, null) })
        val fast = at("a", 5.0, 200)          // finishes in 200 s
        val slow = at("c", 2.5, 400)          // 400 s
        val field = listOf(slow, fast, ghost) // ghost (main) = 4 m/s, 250 s
        assertEquals(mapOf("a" to 1, ghost.runId to 2, "c" to 3), FieldRanking.ranks(field))
        val s = GhostSession(route, ghost, 0, listOf(slow, fast, ghost))
        for (i in 0..20) s.addFix(i * 1000L, lat(i * 4.4), 10.0, 5.0, emptyList())      // me: 88 m at t=20
        val live = s.snapshot(20_500)
        assertEquals(3, live.fieldSize)
        assertEquals(mapOf(1 to 100.0, 2 to 80.0, 3 to 50.0), live.field.associate { it.rank to it.progressM })
        assertEquals(listOf(2), live.field.filter { it.isMain }.map { it.rank })
        assertEquals(2, live.position)        // only the 5 m/s runner is ahead of me
        assertEquals(2, live.mainRank)
    }

    @Test fun progressNowHoldsAtTheEndsOfAProfile() {
        assertEquals(0.0, GhostComparison.progressNow(ghost, -5.0), 1e-9)
        assertEquals(400.0, GhostComparison.progressNow(ghost, 100.5), 1e-9 + 2.0)
        assertEquals(1000.0, GhostComparison.progressNow(ghost, 999.0), 1e-9)
    }

    @Test fun fixWithPoorAccuracyIsIgnored() {
        val t = ProgressTracker(RouteProjector(line))
        assertEquals(Match.Ignored, t.addFix(1.0, lat(10.0), 10.0, 80.0))
        assertNull(t.lastProgressM)
    }

    // ── cache ───────────────────────────────────────────────────────────────

    @Test fun cacheRoundTripReadinessAndPathSafety() {
        val cache = GhostCache(tmp.newFolder("ghost"))
        assertFalse(cache.isReady(route.routeId, ghost.runId))
        cache.saveRoute(route); cache.saveProfile(ghost)
        assertTrue(cache.isReady(route.routeId, ghost.runId))
        assertEquals(route.points, cache.route(route.routeId)!!.points)
        assertEquals(ghost.points.size, cache.profile(ghost.runId)!!.points.size)
        // a profile for another route/version is not "ready"
        cache.saveProfile(ghost.copy(runId = "33333333-3333-3333-3333-333333333333", geometryVersion = 2))
        assertFalse(cache.isReady(route.routeId, "33333333-3333-3333-3333-333333333333"))
        // ids that are not UUIDs can never become paths
        assertThrows(IllegalArgumentException::class.java) { cache.route("../../etc/passwd") }
        // a corrupt file is "missing", not a crash
        File(tmp.root, "ghost/route-${route.routeId}.json").writeText("{not json")
        assertNull(cache.route(route.routeId))
    }

    @Test fun runMetaKeepsRouteAndGhostAndOldJsonStillLoads() {
        val m = RunMeta("c", RunState.PREPARED, "S", "t", 0, null, emptyList(), null, 0, null, false, route.routeId, ghost.runId)
        val back = RunMeta.fromJson(m.toJson())
        assertEquals(route.routeId, back.routeId); assertEquals(ghost.runId, back.ghostRunId)
        val old = JSONObject(m.toJson()).apply { remove("routeId"); remove("ghostRunId") }.toString()
        assertNull(RunMeta.fromJson(old).routeId); assertNull(RunMeta.fromJson(old).ghostRunId)
    }
}
