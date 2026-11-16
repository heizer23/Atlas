package net.linspad.atlasphone.running

import net.linspad.atlasphone.mobile.audio.ClickOutput
import net.linspad.atlasphone.mobile.audio.SpeechPort
import net.linspad.atlasphone.mobile.service.QuickAction
import net.linspad.atlasphone.running.coach.CoachController
import net.linspad.atlasphone.running.coach.CoachFrequency
import net.linspad.atlasphone.running.coach.CoachInput
import net.linspad.atlasphone.running.coach.CoachPlanParse
import net.linspad.atlasphone.running.coach.CoachPlanStore
import net.linspad.atlasphone.running.metronome.MetronomeController
import net.linspad.atlasphone.running.metronome.MetronomeMode
import net.linspad.atlasphone.running.metronome.MetronomeTarget
import net.linspad.atlasphone.running.net.AtlasClient
import net.linspad.atlasphone.running.net.HttpResponse
import net.linspad.atlasphone.running.net.StreamCountsLocal
import net.linspad.atlasphone.running.settings.RunSettings
import net.linspad.atlasphone.running.settings.SettingsStore
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
import java.io.IOException

/** Coach session wiring (controller, plan cache, metronome COACH mode, RunMeta/finish link) with fakes; no Android audio. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class CoachSessionTest {
    private class MapStore : SettingsStore {
        val map = HashMap<String, String>()
        var failKey: String? = null
        override fun getString(key: String): String? { if (key == failKey) error("boom"); return map[key] }
        override fun putString(key: String, value: String) { map[key] = value }
    }

    private class FakeSpeech(var available: Boolean = true, var throws: Boolean = false) : SpeechPort {
        val spoken = ArrayList<String>(); var stops = 0; var prepares = 0
        override fun prepare() { prepares++ }
        override fun speak(text: String): Boolean { if (throws) error("tts"); if (!available) return false; spoken += text; return true }
        override fun stop() { stops++ }
        override fun isAvailable() = available
    }

    private val planJson = """{"schema_version":1,"type":"easy_continuous","title":"Easy","rationale":null,"target_distance_m":null,"triggers":[],"segments":[
        {"kind":"steady","duration_s":1800,"hr":{"min":130,"max":145},"pace":null,"cadence":{"min":165,"max":175}}]}"""

    private class Rig(val speech: FakeSpeech = FakeSpeech(), val store: MapStore = MapStore(), val planStore: MapStore = MapStore()) {
        val settings = RunSettings(store)
        val cache = CoachPlanStore(planStore)
        val log = ArrayList<String>()
        val coach = CoachController(speech, cache, settings, { log += it })
    }

    private fun rig(speech: FakeSpeech = FakeSpeech()) = Rig(speech).also { it.cache.save("p1", planJson, 1L) }
    private fun hot(t: Double) = CoachInput(t, false, 160.0, 1.0, null, 170.0)

    @Test fun beginTickMuteAndEnd() {
        val r = rig()
        assertEquals("p1", r.coach.sessionPlanId())
        r.settings.setCoachEnabled(false); assertNull("'Coach this run' off", r.coach.sessionPlanId()); r.settings.setCoachEnabled(true)
        assertFalse("wrong plan id", r.coach.begin("other", 0.0)); assertTrue(r.coach.begin("p1", 0.0))
        assertTrue(r.coach.hasCadenceTarget())
        var ui = r.coach.tick(hot(0.0))
        assertEquals("Steady", ui!!.segmentLabel); assertEquals(170.0, ui.cadenceTargetSpm!!, 0.0)
        for (t in 1..60) ui = r.coach.tick(hot(t.toDouble()))
        assertEquals(listOf("Steady pace.", "Your heart rate is above target."), r.speech.spoken)
        assertEquals("shown while fresh", "Your heart rate is above target.", ui!!.lastInstruction)
        ui = r.coach.tick(hot(100.0).copy(hrBpm = 140.0))
        assertNull("cleared after DISPLAY_S", ui!!.lastInstruction)
        r.coach.setMuted(true); assertTrue(r.speech.stops > 0)
        for (t in 101..400) r.coach.tick(hot(t.toDouble()))
        assertEquals("muted: nothing spoken", 2, r.speech.spoken.size)
        assertTrue(r.coach.tick(hot(401.0))!!.muted)
        r.coach.end(); r.coach.end()
        assertNull(r.coach.tick(hot(402.0))); assertFalse(r.coach.hasSession())
    }

    @Test fun speechUnavailableOrThrowingFallsBackToTextOnly() {
        for (speech in listOf(FakeSpeech(available = false), FakeSpeech(throws = true))) {
            val r = rig(speech)
            r.coach.begin("p1", 0.0)
            val ui = r.coach.tick(CoachInput(0.0, false, 138.0, 1.0, null, 170.0))
            assertEquals("Steady pace.", ui!!.lastInstruction)
            assertEquals(speech.available, ui.speechAvailable)
            assertNotNull("session still alive", r.coach.tick(CoachInput(1.0, false, 138.0, 1.0, null, 170.0)))
        }
    }

    @Test fun anEngineExceptionDisablesTheSessionWithoutPropagating() {
        val r = rig()
        r.coach.begin("p1", 0.0)
        assertNotNull(r.coach.tick(hot(0.0)))
        r.store.failKey = RunSettings.KEY_COACH_FREQUENCY      // the tick reads the frequency: now it throws
        assertNull(r.coach.tick(hot(1.0)))
        assertFalse(r.coach.hasSession()); assertTrue(r.log.any { it.contains("Coach disabled") })
        assertNull(r.coach.tick(hot(2.0)))
    }

    @Test fun unsupportedOrMissingPlanIsNotCoached() {
        val r = Rig()
        assertNull(r.coach.sessionPlanId()); assertFalse(r.coach.begin("p1", 0.0))
        r.cache.save("p9", """{"schema_version":2}""", 1L)
        assertNull(r.coach.sessionPlanId()); assertTrue(r.coach.cachedPlan() is CoachPlanParse.Unsupported)
        assertFalse(r.coach.begin("p9", 0.0))
    }

    private class Transport(var respond: () -> HttpResponse) : net.linspad.atlasphone.running.net.HttpTransport {
        override fun execute(request: net.linspad.atlasphone.running.net.HttpRequest) = respond()
    }

    @Test fun refreshKeepsTheCacheOnErrorAndClearsOnNoPlan() {
        val r = rig()
        val t = Transport { throw IOException("offline") }
        val client = AtlasClient("https://atlas.example:8443", { "tok" }, t)
        assertEquals("p1", (r.coach.refreshPlan(client, 5L) as CoachPlanParse.Ok).plan.planId)       // offline: unchanged
        t.respond = { HttpResponse(500, "{}") }
        assertNotNull(r.coach.refreshPlan(client, 6L))                                              // server error: unchanged
        t.respond = { HttpResponse(200, """{"plan_id":"p2","schema_version":1,"plan":$planJson}""") }
        assertEquals("p2", (r.coach.refreshPlan(client, 7L) as CoachPlanParse.Ok).plan.planId)       // new plan replaces
        t.respond = { HttpResponse(200, """{"plan_id":null,"schema_version":null,"plan":null}""") }
        assertNull("null plan clears the cache", r.coach.refreshPlan(client, 8L))
        assertNull(r.coach.cachedPlan())
    }

    // ── metronome COACH mode ──

    private class FakeEngine : ClickOutput {
        var running = false; var target: Double? = null
        override fun start(volume: Float): Boolean { running = true; return true }
        override fun setTargetSpm(spm: Double?) { target = spm }
        override fun setVolume(volume: Float) {}
        override fun stop() { running = false; target = null }
        override fun stateName() = if (running) "RUNNING" else "STOPPED"
    }

    @Test fun metronomeOffersCoachOnlyWithACoachCadenceAndNeverPersistsIt() {
        assertEquals(listOf(MetronomeMode.OFF, MetronomeMode.MATCH_GHOST, MetronomeMode.ATTACK_102, MetronomeMode.MANUAL), MetronomeTarget.availableModes(true))
        assertEquals(listOf(MetronomeMode.OFF, MetronomeMode.MANUAL), MetronomeTarget.availableModes(false))
        assertEquals("ghost modes are not offered while coaching", listOf(MetronomeMode.OFF, MetronomeMode.COACH, MetronomeMode.MANUAL), MetronomeTarget.availableModes(true, true))
        assertEquals(MetronomeMode.MANUAL, MetronomeTarget.next(MetronomeMode.COACH, true, true))
        assertEquals(170.0, MetronomeTarget.rawTarget(MetronomeMode.COACH, 160.0, 150, 170.0)!!, 0.0)
        assertNull("no coach target = silence, never speed derived", MetronomeTarget.rawTarget(MetronomeMode.COACH, 160.0, 150, null))
        assertNull(MetronomeTarget.rawTarget(MetronomeMode.COACH, null, 150, 90.0))                         // outside the range
        assertEquals("COACH is never restored from storage", MetronomeMode.OFF, MetronomeMode.parse("COACH"))

        val store = MapStore(); val engine = FakeEngine()
        store.map[RunSettings.KEY_METRONOME_MODE] = "MATCH_GHOST"
        val c = MetronomeController(engine, QuickAction(), RunSettings(store))
        c.begin(true, listOf(0.0 to 160.0), hasCoach = true)
        assertEquals("a ghost mode becomes COACH while coaching", MetronomeMode.COACH, c.currentState().mode)
        assertEquals("the stored value stays the last non-coach mode", "MATCH_GHOST", store.map[RunSettings.KEY_METRONOME_MODE])
        assertEquals(170.0, c.tick(10.0, false, 0, coachCadenceSpm = 170.0).targetSpm!!, 1e-9)
        assertEquals("segment without a cadence target: held, then silence", 170.0, c.tick(10.0, false, 1000, coachCadenceSpm = null).targetSpm!!, 1e-9)
        assertNull(c.tick(10.0, false, 17_000, coachCadenceSpm = null).targetSpm)
        c.setMode(MetronomeMode.COACH); assertEquals("MATCH_GHOST", store.map[RunSettings.KEY_METRONOME_MODE])
        c.setMode(MetronomeMode.MANUAL); assertEquals("MANUAL", store.map[RunSettings.KEY_METRONOME_MODE])
        val free = MetronomeController(FakeEngine(), QuickAction(), RunSettings(store)); free.begin(false, null)
        assertEquals("without a coach session the Sprint03 rule applies", MetronomeMode.MANUAL, free.currentState().mode)
    }

    // ── RunMeta and the finish body ──

    private fun meta(plan: String?) = RunMeta("r", RunState.PENDING_UPLOAD, null, null, 1_700_000_000_000, 1_700_000_600_000, emptyList(),
        RunSummary(600.0, 590.0, 2000.0, 295.0, 150.0), 0, null, false, coachPlanId = plan)

    @Test fun planLinkSurvivesRestartAndIsSentOnlyWhenSet() {
        assertEquals("p1", RunMeta.fromJson(meta("p1").toJson()).coachPlanId)
        assertNull(RunMeta.fromJson(meta(null).toJson()).coachPlanId)
        val old = JSONObject(meta(null).toJson()).also { it.remove("coachPlanId") }
        assertNull("old metas decode with no plan", RunMeta.fromJson(old.toString()).coachPlanId)

        val bodies = ArrayList<JSONObject>()
        val t = Transport { HttpResponse(200, """{"result":"complete","run_id":"r","verified_counts":{"location":1,"heart_rate":0},"missing_seq_ranges":[],"count_mismatch":[],"high_seq":{"location":1,"heart_rate":0},"contiguous_seq":1}""") }
        val spy = object : net.linspad.atlasphone.running.net.HttpTransport {
            override fun execute(request: net.linspad.atlasphone.running.net.HttpRequest): HttpResponse { bodies += JSONObject(request.body!!); return t.execute(request) }
        }
        val client = AtlasClient("https://atlas.example:8443", { "tok" }, spy)
        client.finish("r", meta(null), StreamCountsLocal(1, 0), 1, 0)
        client.finish("r", meta("p1"), StreamCountsLocal(1, 0), 1, 0)
        assertFalse("omitted, never null", bodies[0].has("coach_plan_id"))
        assertEquals("p1", bodies[1].getString("coach_plan_id"))
    }

    @Test fun settingsKeysDefaultAndRoundTrip() {
        val s = RunSettings(MapStore())
        assertTrue(s.coachEnabled()); assertEquals(CoachFrequency.NORMAL, s.coachFrequency())
        s.setCoachEnabled(false); s.setCoachFrequency(CoachFrequency.HIGH)
        assertFalse(s.coachEnabled()); assertEquals(CoachFrequency.HIGH, s.coachFrequency())
    }
}
