package net.linspad.atlasphone.running

import net.linspad.atlasphone.running.cadence.CadenceEstimator
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

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
/** CAD1 parity with the backend: both read 03_Application/RunningTracker/tests/fixtures/cadence_golden.json. */
class CadenceEstimatorTest {
    private fun goldenFile(): File {
        val rel = "03_Application/RunningTracker/tests/fixtures/cadence_golden.json"
        var dir: File? = File("").absoluteFile
        while (dir != null) { File(dir, rel).takeIf { it.exists() }?.let { return it }; dir = dir.parentFile }
        error("cadence_golden.json not found above ${File("").absolutePath}")
    }

    private val golden = JSONObject(goldenFile().readText())
    private val tolSpm = golden.getJSONObject("tolerance").getDouble("spm") + 1e-9
    private val tolConf = golden.getJSONObject("tolerance").getDouble("conf") + 1e-9
    private fun longs(a: JSONArray) = (0 until a.length()).map { a.getLong(it) }
    private fun case(name: String): JSONObject = (0 until golden.getJSONArray("cases").length()).map { golden.getJSONArray("cases").getJSONObject(it) }.first { it.getString("name") == name }
    private val start = 1_700_000_000_000L

    private fun run(c: JSONObject) = CadenceEstimator.series(
        longs(c.getJSONArray("steps_ms")).map { start + it },
        (0 until c.getJSONArray("pauses_ms").length()).map { c.getJSONArray("pauses_ms").getJSONArray(it).let { p -> (start + p.getLong(0)) until (start + p.getLong(1)) } },
        start, start + c.getLong("end_ms"),
    )

    @Test fun everyGoldenVectorMatchesTheServer() {
        val cases = golden.getJSONArray("cases")
        assertTrue(cases.length() >= 10)
        for (i in 0 until cases.length()) {
            val c = cases.getJSONObject(i)
            val got = run(c); val exp = c.getJSONArray("expected")
            assertEquals(c.getString("name"), exp.length(), got.size)
            for (k in got.indices) {
                val e = exp.getJSONArray(k)
                assertEquals(c.getString("name") + " t", e.getDouble(0), got[k].tSeconds, 1e-9)
                assertEquals(c.getString("name") + " spm", e.getDouble(1), got[k].spm, tolSpm)
                assertEquals(c.getString("name") + " conf", e.getDouble(2), got[k].conf, tolConf)
            }
        }
    }

    @Test fun gapsAreAbsentNeverZero() {
        val stop = run(case("stop_then_run"))
        assertTrue(stop.none { it.tSeconds == 25.0 } && stop.all { it.spm > 0 })
        assertTrue(run(case("irregular_stumbling")).isEmpty())
        assertTrue(run(case("sparse_three_intervals")).isEmpty())
    }

    @Test fun atIsDeterministicAndNullWithoutSteps() {
        val steps = longs(case("steady_170").getJSONArray("steps_ms")).map { start + it }.filter { it <= start + 30_000 }
        val a = CadenceEstimator.at(steps, emptyList(), start + 30_000)
        assertNotNull(a)
        assertEquals(170.0, a!!.spm, tolSpm)
        assertEquals(a, CadenceEstimator.at(steps, emptyList(), start + 30_000))
        assertNull(CadenceEstimator.at(emptyList(), emptyList(), start))
        assertNull("a stop longer than the gap limit gives no value", CadenceEstimator.at(steps, emptyList(), start + 40_000))
    }
}
