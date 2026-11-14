package net.linspad.atlasphone.running

import net.linspad.atlasphone.mobile.audio.BeatScheduler
import net.linspad.atlasphone.mobile.audio.ClickConfig
import net.linspad.atlasphone.mobile.audio.ClickOutput
import net.linspad.atlasphone.mobile.service.QuickAction
import net.linspad.atlasphone.running.metronome.MetronomeConfig
import net.linspad.atlasphone.running.metronome.MetronomeController
import net.linspad.atlasphone.running.metronome.MetronomeMode
import net.linspad.atlasphone.running.metronome.MetronomeTarget
import net.linspad.atlasphone.running.metronome.TargetSmoother
import net.linspad.atlasphone.running.settings.RunSettings
import net.linspad.atlasphone.running.settings.SettingsStore
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class MetronomeTargetTest {
    private val cad = listOf(0.0 to 160.0, 20.0 to 164.0, 40.0 to 168.0, 100.0 to 170.0)   // gap 60..100 m

    @Test fun ghostCadenceLookupInterpolatesAndHonoursGaps() {
        assertEquals(160.0, MetronomeTarget.ghostCadenceAt(cad, 10.0)!!, 1e-9)        // bucket centre
        assertEquals(162.0, MetronomeTarget.ghostCadenceAt(cad, 20.0)!!, 1e-9)        // between two centres
        assertEquals(164.0, MetronomeTarget.ghostCadenceAt(cad, 30.0)!!, 1e-9)
        assertNull("inside the gap", MetronomeTarget.ghostCadenceAt(cad, 80.0))
        assertNull("far before the first bucket", MetronomeTarget.ghostCadenceAt(cad, -25.0))
        assertNull("far after the last bucket", MetronomeTarget.ghostCadenceAt(cad, 400.0))
        assertEquals("edge value within one bucket outside", 160.0, MetronomeTarget.ghostCadenceAt(cad, -5.0)!!, 1e-9)
        assertNull("unknown progress", MetronomeTarget.ghostCadenceAt(cad, null))
        assertNull(MetronomeTarget.ghostCadenceAt(null, 10.0)); assertNull(MetronomeTarget.ghostCadenceAt(emptyList(), 10.0))
    }

    @Test fun rawTargetPerMode() {
        assertNull(MetronomeTarget.rawTarget(MetronomeMode.OFF, 170.0, 160))
        assertEquals(170.0, MetronomeTarget.rawTarget(MetronomeMode.MATCH_GHOST, 170.0, 160)!!, 1e-9)
        assertEquals(173.4, MetronomeTarget.rawTarget(MetronomeMode.ATTACK_102, 170.0, 160)!!, 1e-9)
        assertEquals(160.0, MetronomeTarget.rawTarget(MetronomeMode.MANUAL, 170.0, 160)!!, 1e-9)
        for (g in listOf(90.0, 260.0)) {
            assertNull(MetronomeTarget.rawTarget(MetronomeMode.MATCH_GHOST, g, 160)); assertNull(MetronomeTarget.rawTarget(MetronomeMode.ATTACK_102, g, 160))
        }
        assertNull(MetronomeTarget.rawTarget(MetronomeMode.MATCH_GHOST, null, 160))      // nothing derived from speed
        assertNull(MetronomeTarget.rawTarget(MetronomeMode.ATTACK_102, null, 160))
        assertEquals(160.0, MetronomeTarget.rawTarget(MetronomeMode.MANUAL, null, 160)!!, 1e-9)
    }

    @Test fun smootherNeverJumpsHoldsThenSilencesAndRestarts() {
        val s = TargetSmoother()
        var now = 0L
        assertEquals(170.0, s.update(170.0, now)!!, 1e-9)
        var prev = 170.0
        for (i in 1..15) {
            now += 1000
            val out = s.update(180.0, now)!!
            assertTrue("step $i", Math.abs(out - prev) <= MetronomeConfig.SLEW_SPM_PER_S + 1e-9)
            if (i == 10) assertEquals(180.0, out, 1e-9)
            prev = out
        }
        assertEquals(180.0, prev, 1e-9)
        for (i in 1..10) { now += 1000; assertEquals("held at $i s", 180.0, s.update(null, now)!!, 1e-9) }
        for (i in 11..15) { now += 1000; assertNotNull("still held at $i s", s.update(null, now)) }
        now += 1000
        assertNull("after HOLD_S of absence", s.update(null, now))
        for (i in 1..5) { now += 1000; assertNull(s.update(null, now)) }
        now += 1000
        assertEquals("restarts from the raw value", 175.0, s.update(175.0, now)!!, 1e-9)
    }

    @Test fun modeCycleAndAvailability() {
        var m = MetronomeMode.OFF
        val withGhost = (1..5).map { m = MetronomeTarget.next(m, true); m }
        assertEquals(listOf(MetronomeMode.MATCH_GHOST, MetronomeMode.ATTACK_102, MetronomeMode.MANUAL, MetronomeMode.OFF, MetronomeMode.MATCH_GHOST), withGhost)
        m = MetronomeMode.OFF
        assertEquals(listOf(MetronomeMode.MANUAL, MetronomeMode.OFF, MetronomeMode.MANUAL), (1..3).map { m = MetronomeTarget.next(m, false); m })
        assertEquals("unavailable restored mode", MetronomeMode.OFF, MetronomeTarget.next(MetronomeMode.MATCH_GHOST, false))
    }

    // ── controller with a fake engine ──

    private class FakeEngine : ClickOutput {
        var running = false; var target: Double? = null; var lastVolume = -1f; var starts = 0; var stops = 0
        override fun start(volume: Float): Boolean { running = true; starts++; this.lastVolume = volume; return true }
        override fun setTargetSpm(spm: Double?) { target = spm }
        override fun setVolume(volume: Float) { lastVolume = volume }
        override fun stop() { running = false; target = null; stops++ }
        override fun stateName() = if (running) "RUNNING" else "STOPPED"
    }
    private class MapStore : SettingsStore {
        val map = HashMap<String, String>()
        override fun getString(key: String) = map[key]
        override fun putString(key: String, value: String) { map[key] = value }
    }

    @Test fun controllerDrivesTheEngineAndPersistsSettings() {
        val engine = FakeEngine(); val quick = QuickAction(); val store = MapStore()
        val c = MetronomeController(engine, quick, RunSettings(store))
        c.begin(true, cad)
        assertFalse("OFF by default: engine not started", engine.running)
        assertEquals("Click: Off", quick.label.value)

        assertEquals(MetronomeMode.MATCH_GHOST, c.cycleMode())
        assertTrue(engine.running); assertEquals("Click: Match ghost", quick.label.value)
        assertEquals("MATCH_GHOST", store.map[RunSettings.KEY_METRONOME_MODE])
        var s = c.tick(10.0, false, 0)
        assertEquals(160.0, s.targetSpm!!, 1e-9); assertEquals(160.0, engine.target!!, 1e-9); assertEquals(true, s.ghostHasCadence)
        s = c.tick(10.0, true, 1000)
        assertNull("paused = silence", s.targetSpm); assertNull(engine.target)
        s = c.tick(10.0, false, 2000)
        assertEquals("resumes from the raw target", 160.0, s.targetSpm!!, 1e-9)

        c.setManualSpm(500); assertEquals(230, RunSettings(store).manualCadenceSpm())
        c.setVolume(7f); assertEquals(1f, RunSettings(store).clickVolume(), 0f); assertEquals(1f, engine.lastVolume, 0f)
        c.setMode(MetronomeMode.MANUAL)
        assertEquals(230.0, c.tick(null, false, 3000).targetSpm!!, 1e-9)

        c.stop()
        assertFalse(engine.running); assertNull(quick.label.value)
        c.stop()                                          // idempotent
        assertEquals("MANUAL", store.map[RunSettings.KEY_METRONOME_MODE])
        val again = MetronomeController(FakeEngine(), QuickAction(), RunSettings(store)); again.begin(false, null)
        assertEquals("mode survives a new controller", MetronomeMode.MANUAL, again.currentState().mode)
    }

    @Test fun ghostWithoutCadenceIsReportedAndNeverFallsBackToSpeed() {
        val engine = FakeEngine(); val store = MapStore().also { it.map[RunSettings.KEY_METRONOME_MODE] = "MATCH_GHOST" }
        val c = MetronomeController(engine, QuickAction(), RunSettings(store))
        c.begin(true, null)
        val s = c.tick(50.0, false, 0)
        assertEquals(false, s.ghostHasCadence); assertNull(s.targetSpm); assertNull(engine.target)
        c.selectManual()
        assertEquals(170.0, c.tick(50.0, false, 1000).targetSpm!!, 1e-9)
        // restored ghost mode without ghost session -> OFF
        val free = MetronomeController(FakeEngine(), QuickAction(), RunSettings(store).also { it.setMetronomeMode(MetronomeMode.ATTACK_102) })
        free.begin(false, null)
        assertEquals(MetronomeMode.OFF, free.currentState().mode); assertNull(free.currentState().ghostHasCadence)
    }

    private fun MetronomeController.selectManual() = setMode(MetronomeMode.MANUAL)

    @Test fun audioKeepsItsTimingWhenTheDisplayTickStalls() {
        val engine = FakeEngine(); val c = MetronomeController(engine, QuickAction(), RunSettings(MapStore()))
        c.begin(false, null); c.setMode(MetronomeMode.MANUAL)
        c.tick(null, false, 0)
        val target = engine.target!!
        // 30 s without any tick while the audio thread keeps rendering from the last handed-over target
        val sched = BeatScheduler(ClickConfig.SAMPLE_RATE_HZ, BeatScheduler.renderClick(ClickConfig.SAMPLE_RATE_HZ, ClickConfig.CLICK_MS, ClickConfig.CLICK_FREQ_HZ, ClickConfig.CLICK_PEAK))
        val buf = ShortArray(ClickConfig.SAMPLE_RATE_HZ * ClickConfig.BUFFER_MS / 1000)
        var beats = 0; var frames = 0L
        while (frames < 30L * ClickConfig.SAMPLE_RATE_HZ) { beats += sched.fill(buf, buf.size, engine.target!!); frames += buf.size }
        assertEquals(target * (frames / ClickConfig.SAMPLE_RATE_HZ.toDouble()) / 60.0, beats.toDouble(), 1.5)
    }
}
