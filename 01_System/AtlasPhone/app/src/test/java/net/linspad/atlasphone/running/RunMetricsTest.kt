package net.linspad.atlasphone.running

import net.linspad.atlasphone.mobile.model.RawHeartRate
import net.linspad.atlasphone.mobile.model.RawLocation
import net.linspad.atlasphone.running.metrics.RunMetrics
import net.linspad.atlasphone.running.metrics.RunMetricsAccumulator
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.File
import java.time.Instant

/**
 * Algorithm A1 parity with the backend: both read 03_Application/RunningTracker/tests/fixtures/metrics_golden.json.
 * The expected values in that file are analytic (northward route at constant speed), not produced by either implementation.
 * org.json needs the Robolectric runtime in JVM tests.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class RunMetricsTest {
    private class Case(val name: String, val startedAt: Long, val locations: List<RawLocation>, val heartRates: List<RawHeartRate>,
                       val pauses: List<PauseRecord>, val expected: JSONObject)

    private fun goldenFile(): File {
        val rel = "03_Application/RunningTracker/tests/fixtures/metrics_golden.json"
        var dir: File? = File("").absoluteFile
        while (dir != null) { File(dir, rel).takeIf { it.exists() }?.let { return it }; dir = dir.parentFile }
        error("metrics_golden.json not found above ${File("").absolutePath}")
    }

    private val doc = JSONObject(goldenFile().readText())
    private val tol = doc.getJSONObject("tolerances")
    private fun millis(s: String) = Instant.parse(s).toEpochMilli()
    private fun JSONObject.dbl(k: String): Double? = if (isNull(k)) null else getDouble(k)

    private fun cases(): List<Case> {
        val arr = doc.getJSONArray("cases")
        return (0 until arr.length()).map { i ->
            val c = arr.getJSONObject(i)
            val locs = c.getJSONArray("locations").let { a ->
                (0 until a.length()).map { j ->
                    val l = a.getJSONObject(j)
                    RawLocation(millis(l.getString("timestamp")), l.getDouble("latitude"), l.getDouble("longitude"),
                        l.dbl("accuracyMeters")?.toFloat(), null, null, null,
                        if (l.isNull("elapsedRealtimeNanos")) null else l.getLong("elapsedRealtimeNanos"))
                }
            }
            val hrs = c.getJSONArray("heart_rates").let { a ->
                (0 until a.length()).map { j -> a.getJSONObject(j).let { RawHeartRate(millis(it.getString("timestamp")), it.getInt("bpm"), null) } }
            }
            val pauses = c.getJSONArray("pauses").let { a ->
                (0 until a.length()).map { j -> a.getJSONObject(j).let { PauseRecord(millis(it.getString("started_at")), millis(it.getString("ended_at")), 0.0, 0.0) } }
            }
            Case(c.getString("name"), millis(c.getString("started_at")), locs, hrs, pauses, c.getJSONObject("expected"))
        }
    }

    private fun assertClose(msg: String, expected: Double?, actual: Double?, tolerance: Double) {
        if (expected == null) { assertNull("$msg should be null", actual); return }
        assertNotNull("$msg should not be null", actual)
        assertEquals(msg, expected, actual!!, tolerance)
    }

    @Test fun nativeMetricsMatchGoldenVectors() {
        val all = cases()
        assertEquals(7, all.size)
        for (c in all) {
            val finished = c.startedAt + 3_600_000
            val summary = RunMetrics.summarize(c.locations, c.heartRates, c.pauses, c.startedAt, finished)
            assertClose("${c.name} distance", c.expected.getDouble("distance_m"), summary.distanceM, tol.getDouble("distance_m"))
            assertClose("${c.name} avg hr", c.expected.dbl("avg_hr"), summary.avgHr, tol.getDouble("hr"))

            val splits = RunMetrics.splits(c.locations, c.heartRates, c.pauses)
            val want = c.expected.getJSONArray("splits")
            assertEquals("${c.name} split count", want.length(), splits.size)
            for (i in splits.indices) {
                val w = want.getJSONObject(i)
                assertEquals(w.getInt("km"), splits[i].km)
                assertEquals(w.getBoolean("partial"), splits[i].partial)
                assertClose("${c.name} split $i distance", w.getDouble("distance_m"), splits[i].distanceM, tol.getDouble("distance_m"))
                assertClose("${c.name} split $i duration", w.getDouble("duration_s"), splits[i].durationS, tol.getDouble("duration_s"))
                assertClose("${c.name} split $i pace", w.getDouble("pace_s_per_km"), splits[i].paceSPerKm, tol.getDouble("pace_s_per_km"))
                assertClose("${c.name} split $i hr", w.dbl("avg_hr"), splits[i].avgHr, tol.getDouble("hr"))
            }
        }
    }

    @Test fun incrementalAccumulatorAgreesWithBatchSummarize() {
        for (c in cases()) {
            val acc = RunMetricsAccumulator(c.startedAt, c.pauses)
            c.locations.forEach(acc::addFix)
            c.heartRates.forEach(acc::addHeartRate)
            val batch = RunMetrics.summarize(c.locations, c.heartRates, c.pauses, c.startedAt, c.startedAt + 3_600_000)
            assertEquals("${c.name} distance", batch.distanceM, acc.distanceM, 1e-9)
            assertEquals("${c.name} splits", RunMetrics.splits(c.locations, c.heartRates, c.pauses).size, acc.splits().size)
        }
    }

    @Test fun livePauseHandlingMatchesRecordedPauses() {
        // Same as route_with_pause, but the pause is entered through pause()/resume() while fixes arrive in order.
        val c = cases().first { it.name == "route_with_pause" }
        val acc = RunMetricsAccumulator(c.startedAt)
        val p = c.pauses.single()
        for (fix in c.locations) {
            if (fix.timestampMillis == p.startedAtMillis) acc.pause(p.startedAtMillis)
            if (fix.timestampMillis == p.endedAtMillis) acc.resume(p.endedAtMillis!!)
            acc.addFix(fix)
        }
        assertEquals(952.0, acc.distanceM, 0.5)
    }

    @Test fun liveSnapshotShowsSmoothedAndAveragePace() {
        val c = cases().first { it.name == "clean_route" }
        val acc = RunMetricsAccumulator(c.startedAt)
        c.locations.forEach(acc::addFix)
        c.heartRates.forEach(acc::addHeartRate)
        val snap = acc.snapshot(c.startedAt + 600_000)
        assertEquals(250.0, snap.currentPaceSPerKm!!, 0.5)
        assertEquals(600.0 / 2.396, snap.avgPaceSPerKm!!, 0.5) // average on moving time: 600 s / 2.396 km
        assertEquals(160, snap.currentHr)
        assertEquals(5.0f, snap.lastAccuracyM)
        assertEquals(600.0, snap.movingS, 1e-6)
    }

    @Test fun noPaceWhileStaleOrPaused() {
        val c = cases().first { it.name == "gps_only_run" }
        val acc = RunMetricsAccumulator(c.startedAt)
        c.locations.forEach(acc::addFix)
        assertNull(acc.snapshot(c.startedAt + 300_000 + 60_000).currentPaceSPerKm) // no fix for a minute
        acc.pause(c.startedAt + 301_000)
        assertNull(acc.snapshot(c.startedAt + 302_000).currentPaceSPerKm)
        assertEquals(301.0, acc.snapshot(c.startedAt + 302_000).movingS, 0.01)
    }

    @Test fun fixesWithoutAccuracyOrWithPoorAccuracyAreIgnored() {
        val acc = RunMetricsAccumulator(0)
        acc.addFix(RawLocation(1000, 52.0, 13.0, null, null, null, null))
        acc.addFix(RawLocation(2000, 52.0, 13.0, 80f, null, null, null))
        assertEquals(0.0, acc.distanceM, 0.0)
        assertTrue(acc.splits().isEmpty())
    }
}
