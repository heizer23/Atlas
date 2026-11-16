package net.linspad.atlasphone.running

import net.linspad.atlasphone.running.coach.CoachPlanParse
import net.linspad.atlasphone.running.coach.CoachPlanStore
import net.linspad.atlasphone.running.coach.CoachTrigger
import net.linspad.atlasphone.running.coach.SegmentKind
import net.linspad.atlasphone.running.coach.parseCoachPlan
import net.linspad.atlasphone.running.settings.SettingsStore
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.File

/** PLAN1 parity with the backend: both read 03_Application/RunningTracker/tests/fixtures/coach_plan_golden.json. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class CoachPlanTest {
    private fun goldenFile(): File {
        val rel = "03_Application/RunningTracker/tests/fixtures/coach_plan_golden.json"
        var dir: File? = File("").absoluteFile
        while (dir != null) { File(dir, rel).takeIf { it.exists() }?.let { return it }; dir = dir.parentFile }
        error("coach_plan_golden.json not found above ${File("").absolutePath}")
    }

    private val golden = JSONObject(goldenFile().readText())

    @Test fun goldenCasesParseAsTheServerSaysWhereThePhoneChecksAnything() {
        val cases = golden.getJSONArray("cases")
        var checked = 0
        for (i in 0 until cases.length()) {
            val c = cases.getJSONObject(i)
            val result = parseCoachPlan("p", c.get("plan").toString())
            when (c.getString("phone")) {
                "ok" -> assertTrue(c.getString("name") + " -> " + result, result is CoachPlanParse.Ok)
                "unsupported" -> assertEquals(c.getString("name"), 2, (result as CoachPlanParse.Unsupported).schemaVersion)
                "invalid" -> assertTrue(c.getString("name") + " -> " + result, result is CoachPlanParse.Invalid)
                else -> error("unknown phone expectation")
            }
            checked++
        }
        assertEquals(cases.length(), checked)
    }

    @Test fun validPlansKeepTheirShape() {
        val easy = (0 until golden.getJSONArray("cases").length()).map { golden.getJSONArray("cases").getJSONObject(it) }
            .first { it.getString("name") == "valid_easy_continuous" }
        val plan = (parseCoachPlan("p1", easy.get("plan").toString()) as CoachPlanParse.Ok).plan
        assertEquals(2400, plan.totalS())
        assertEquals(listOf(SegmentKind.WARMUP, SegmentKind.STEADY, SegmentKind.COOLDOWN), plan.segments.map { it.kind })
        val steady = plan.segments[1]
        assertEquals(130.0, steady.hr!!.lo, 0.0); assertEquals(145.0, steady.hr!!.hi, 0.0)
        assertEquals(330.0, steady.pace!!.lo, 0.0); assertEquals(390.0, steady.pace!!.hi, 0.0)
        assertNull(plan.segments[0].hr)
        assertEquals(setOf(CoachTrigger.HR_HIGH, CoachTrigger.SEGMENT_CHANGE), plan.triggers)
        assertTrue("explicit triggers restrict", !plan.enabled(CoachTrigger.CADENCE_LOW))
    }

    @Test fun emptyTriggersMeanAllAndSegmentBoundariesAreHalfOpen() {
        val json = """{"schema_version":1,"type":"recovery","title":"T","triggers":[],"segments":[
            {"kind":"warmup","duration_s":60,"hr":null,"pace":null,"cadence":null},
            {"kind":"steady","duration_s":120,"hr":null,"pace":null,"cadence":null}]}"""
        val plan = (parseCoachPlan("p", json) as CoachPlanParse.Ok).plan
        assertTrue(CoachTrigger.entries.all { plan.enabled(it) })
        assertEquals(180, plan.totalS())
        assertEquals(0, plan.segmentIndexAt(0.0)); assertEquals(0, plan.segmentIndexAt(59.9))
        assertEquals(1, plan.segmentIndexAt(60.0)); assertEquals(1, plan.segmentIndexAt(179.9))
        assertNull(plan.segmentIndexAt(180.0)); assertNull(plan.segmentIndexAt(-1.0))
        assertEquals(60, plan.segmentStartS(1))
    }

    private class MapStore : SettingsStore {
        val map = HashMap<String, String>()
        override fun getString(key: String) = map[key]
        override fun putString(key: String, value: String) { map[key] = value }
    }

    @Test fun planStoreRoundTripClearAndUnsupported() {
        val store = MapStore(); val cache = CoachPlanStore(store)
        assertNull(cache.load())
        val json = """{"schema_version":1,"type":"recovery","title":"T","segments":[{"kind":"steady","duration_s":600,"hr":null,"pace":null,"cadence":null}]}"""
        cache.save("p1", json, 1234L)
        assertEquals("p1", (cache.load() as CoachPlanParse.Ok).plan.planId)
        assertEquals(1234L, cache.fetchedAtMillis())
        cache.save("p2", """{"schema_version":2}""", 5L)
        assertEquals(2, (cache.load() as CoachPlanParse.Unsupported).schemaVersion)
        cache.clear()
        assertNull(cache.load())
    }
}
