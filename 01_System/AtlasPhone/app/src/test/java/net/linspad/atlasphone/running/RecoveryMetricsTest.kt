package net.linspad.atlasphone.running

import net.linspad.atlasphone.running.hr.HrPoint
import net.linspad.atlasphone.running.recap.RecoveryConfig
import net.linspad.atlasphone.running.recap.RecoveryMetrics
import net.linspad.atlasphone.running.recap.RecoverySummary
import net.linspad.atlasphone.running.recap.RecoveryTracker
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.File
import java.time.Instant

/** One case of tests/fixtures/recovery_golden.json (the same file pytest reads). */
class GoldenCase(val name: String, val trainingEndMillis: Long, val points: List<HrPoint>, val expected: JSONObject) {
    val validCount: Int get() = expected.getInt("valid_count")
}

object RecoveryGolden {
    private fun file(): File {
        val rel = "03_Application/RunningTracker/tests/fixtures/recovery_golden.json"
        var dir: File? = File("").absoluteFile
        while (dir != null) { File(dir, rel).takeIf { it.exists() }?.let { return it }; dir = dir.parentFile }
        error("recovery_golden.json not found above ${File("").absolutePath}")
    }

    private val doc = JSONObject(file().readText())
    val tolerance: Double = doc.getDouble("tolerance")
    val runFinishedAtMillis: Long = Instant.parse(doc.getString("run_finished_at")).toEpochMilli()

    fun cases(): List<GoldenCase> {
        val arr = doc.getJSONArray("cases")
        return (0 until arr.length()).map { i ->
            val c = arr.getJSONObject(i)
            val pts = c.getJSONArray("points").let { a ->
                (0 until a.length()).map { j -> a.getJSONArray(j).let { HrPoint(runFinishedAtMillis + Math.round(it.getDouble(0) * 1000.0), it.getInt(1)) } }
            }
            GoldenCase(c.getString("name"), runFinishedAtMillis + Math.round(c.getDouble("training_end_s") * 1000.0), pts, c.getJSONObject("expected"))
        }
    }
}

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class RecoveryMetricsTest {
    private fun close(name: String, expected: JSONObject, key: String, actual: Double?) {
        if (expected.isNull(key)) assertNull("$name $key", actual)
        else { assertNotNull("$name $key", actual); assertEquals("$name $key", expected.getDouble(key), actual!!, RecoveryGolden.tolerance) }
    }

    @Test fun phoneAndServerAgreeOnTheGoldenVectors() {
        for (c in RecoveryGolden.cases()) {
            val r = RecoveryMetrics.compute(c.points, RecoveryGolden.runFinishedAtMillis, c.trainingEndMillis)
            close(c.name, c.expected, "hr_end", r.hrEnd); close(c.name, c.expected, "hr_60", r.hr60); close(c.name, c.expected, "hr_120", r.hr120)
            close(c.name, c.expected, "hrr60", r.hrr60); close(c.name, c.expected, "hrr120", r.hrr120)
        }
    }

    @Test fun nothingIsZeroWhenNotComputable() {
        val r = RecoveryMetrics.compute(emptyList(), 1_000_000, 2_000_000)
        assertEquals(RecoverySummary(null, null, null, null, null), r)
    }

    // ── RecoveryTracker ──

    private val t0 = 1_700_000_000_000L
    private fun bpmAt(t: Int) = if (t <= 0) 170 else 170 - t / 4 // same shape as the golden "normal_recovery" case

    @Test fun trackerFillsHrr60AndHrr120OnlyOnceTheirWindowsAreComplete() {
        val tracker = RecoveryTracker(t0, (-3..0).map { HrPoint(t0 + it * 1000L, bpmAt(it)) })
        var fed = 0
        fun snapshotAt(sec: Int): net.linspad.atlasphone.running.recap.RecoveryLive {
            while (fed < sec) { fed++; tracker.addHeartRate(HrPoint(t0 + fed * 1000L, bpmAt(fed))) }
            return tracker.snapshot(t0 + sec * 1000L)
        }
        val at30 = snapshotAt(30).summary
        assertEquals(170.0, at30.hrEnd!!, 0.01); assertNull(at30.hr60); assertNull(at30.hrr60); assertNull(at30.hr120)
        val at65 = snapshotAt(65).summary
        assertEquals(155.0, at65.hr60!!, 0.01); assertEquals(15.0, at65.hrr60!!, 0.01); assertNull(at65.hr120); assertNull(at65.hrr120)
        val live125 = snapshotAt(125)
        assertEquals(140.0, live125.summary.hr120!!, 0.01); assertEquals(30.0, live125.summary.hrr120!!, 0.01)
        assertEquals(125.0, live125.secondsSinceRunEnd, 1e-9)
        assertEquals(bpmAt(125), live125.lastHr)
        assertFalse(live125.reminderDue)
        assertFalse(snapshotAt(899).reminderDue)
        assertTrue(snapshotAt(901).reminderDue) // 15 minutes
    }

    @Test fun trackerWithoutReadingsShowsNoValues() {
        val tracker = RecoveryTracker(t0, emptyList())
        val live = tracker.snapshot(t0 + 70_000)
        assertNull(live.lastHr)
        assertEquals(RecoverySummary(null, null, null, null, null), live.summary)
        tracker.addHeartRate(HrPoint(t0 + 1000, 0)) // a 0 reading is kept raw but is never shown as a value
        assertNull(tracker.snapshot(t0 + 2000).lastHr)
        assertEquals(RecoveryConfig.REMINDER_MS, 900_000L)
    }
}
