package net.linspad.atlasphone.running

import net.linspad.atlasphone.running.coach.CoachConfig
import net.linspad.atlasphone.running.coach.CoachEngine
import net.linspad.atlasphone.running.coach.CoachFrequency
import net.linspad.atlasphone.running.coach.CoachInput
import net.linspad.atlasphone.running.coach.CoachInstruction
import net.linspad.atlasphone.running.coach.CoachKind
import net.linspad.atlasphone.running.coach.CoachPlan
import net.linspad.atlasphone.running.coach.CoachSegment
import net.linspad.atlasphone.running.coach.CoachSettings
import net.linspad.atlasphone.running.coach.CoachState
import net.linspad.atlasphone.running.coach.CoachTrigger
import net.linspad.atlasphone.running.coach.SegmentKind
import net.linspad.atlasphone.running.coach.TargetRange
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.Random

/** COACH1 scenarios of 10_test_spec.md. The engine is pure, so every scenario is a table over ticks of CoachInput. */
class CoachEngineTest {
    private val hr = TargetRange(130.0, 145.0)
    private val pace = TargetRange(330.0, 390.0)
    private val cad = TargetRange(165.0, 175.0)
    private val normal = CoachSettings(enabled = true, muted = false, frequency = CoachFrequency.NORMAL)

    private fun seg(kind: SegmentKind, d: Int, hr: TargetRange? = null, pace: TargetRange? = null, cad: TargetRange? = null) = CoachSegment(kind, d, hr, pace, cad)
    private fun plan(vararg s: CoachSegment, triggers: Set<CoachTrigger> = emptySet()) = CoachPlan("p1", "easy_continuous", "T", null, s.toList(), triggers)
    private fun steadyPlan(triggers: Set<CoachTrigger> = emptySet()) = plan(seg(SegmentKind.STEADY, 1800, hr, pace, cad), triggers = triggers)

    /** One reading source per tick; defaults are inside every target. */
    private fun input(t: Double, hr: Double? = 138.0, pace: Double? = 360.0, cad: Double? = 170.0, hrAge: Double? = 1.0, paused: Boolean = false) =
        CoachInput(t, paused, hr, if (hr == null) null else hrAge, pace, cad)

    private class Run(val instructions: List<CoachInstruction>, val state: CoachState)

    /** Ticks t = from..to (1 Hz). [read] builds the input of a tick. */
    private fun run(p: CoachPlan, from: Int, to: Int, settings: CoachSettings = normal, start: CoachState = CoachState.initial(p, from.toDouble()),
                    read: (Double) -> CoachInput): Run {
        var state = start
        val out = ArrayList<CoachInstruction>()
        for (t in from..to) {
            val r = CoachEngine.step(p, state, read(t.toDouble()), settings)
            state = r.state
            r.instruction?.let { out += it }
        }
        return Run(out, state)
    }

    private fun kinds(r: Run) = r.instructions.map { it.kind }
    private fun times(r: Run, k: CoachKind) = r.instructions.filter { it.kind == k }.map { it.activeS }

    @Test fun sustainedDeviationTriggersOneInstructionAndTheToleranceBandNeverStartsATimer() {
        val p = steadyPlan()
        val short = run(p, 100, 113) { input(it, hr = 155.0) }
        assertTrue("14 s of deviation is not sustained", short.instructions.isEmpty())
        val long = run(p, 100, 130) { input(it, hr = 155.0) }
        assertEquals(1, long.instructions.size)
        assertEquals(CoachKind.HR_HIGH, long.instructions[0].kind); assertEquals(115.0, long.instructions[0].activeS, 0.0)
        assertEquals("Your heart rate is above target.", long.instructions[0].text)
        val band = run(p, 100, 300) { input(it, hr = 147.9) }   // 145 + 2.9: inside range + tolerance
        assertTrue(band.instructions.isEmpty()); assertTrue(band.state.devSince.isEmpty())
        val lowSide = run(p, 100, 130) { input(it, hr = 120.0) }
        assertEquals(listOf(CoachKind.HR_LOW), kinds(lowSide))
    }

    @Test fun anInterruptedDeviationRestartsItsTimer() {
        val p = steadyPlan()
        val r = run(p, 100, 120) { t -> input(t, hr = if (t == 110.0) 140.0 else 155.0) }   // one in-range tick restarts the 15 s
        assertTrue(r.instructions.isEmpty())
        val flip = run(p, 100, 125) { t -> input(t, hr = if (t < 110) 155.0 else 120.0) }   // direction flip restarts, too
        assertEquals(listOf(CoachKind.HR_LOW), kinds(flip)); assertEquals(125.0, flip.instructions[0].activeS, 0.0)
    }

    @Test fun noCorrectiveInstructionDuringSettlingPauseMuteOrDisabled() {
        val p = plan(seg(SegmentKind.WARMUP, 60), seg(SegmentKind.STEADY, 600, hr))
        val settle = run(p, 0, 160) { input(it, hr = 170.0) }
        assertEquals("settle time after the segment change", 105.0, times(settle, CoachKind.HR_HIGH).first(), 0.0)
        assertEquals(CoachKind.SEGMENT_START, settle.instructions[0].kind)

        val s = steadyPlan()
        val paused = run(s, 200, 260) { input(200.0, hr = 170.0, paused = true) }
        assertTrue(paused.instructions.isEmpty()); assertTrue("timers cleared", paused.state.devSince.isEmpty())
        val resumed = run(s, 200, 240, start = paused.state) { input(it, hr = 170.0) }
        assertEquals("timers restart after resume", 215.0, times(resumed, CoachKind.HR_HIGH).first(), 0.0)

        val muted = run(s, 100, 400, normal.copy(muted = true)) { input(it, hr = 170.0) }
        assertTrue(muted.instructions.isEmpty())
        val unmuted = run(s, 401, 450, start = muted.state) { input(it, hr = 170.0) }
        assertEquals("after unmute only the live condition speaks", 416.0, unmuted.instructions.first().activeS, 0.0)
        assertTrue(run(s, 100, 400, normal.copy(enabled = false)) { input(it, hr = 170.0) }.instructions.isEmpty())
    }

    @Test fun oneInstructionAtATimeWithPriorityGapAndCooldown() {
        // HR above, pace too fast, cadence too high: all sustained from t = 100
        val r = run(steadyPlan(), 100, 260) { input(it, hr = 160.0, pace = 300.0, cad = 185.0) }
        assertEquals(listOf(CoachKind.HR_HIGH, CoachKind.PACE_TOO_FAST, CoachKind.CADENCE_HIGH, CoachKind.HR_HIGH), kinds(r))
        assertEquals(listOf(115.0, 160.0, 205.0, 250.0), r.instructions.map { it.activeS })
        r.instructions.zipWithNext().forEach { (a, b) -> assertTrue(b.activeS - a.activeS >= CoachFrequency.NORMAL.gapS()) }
        assertEquals("Reduce cadence by 5 steps per minute.", r.instructions[2].text)   // deviation 10 clamped to 5
    }

    @Test fun conflictingPushInstructionsAreSuppressedWhileHeartRateIsHigh() {
        val p = steadyPlan()
        // HR above range while pace is too slow and cadence low
        val r = run(p, 100, 299) { input(it, hr = 160.0, pace = 420.0, cad = 160.0) }
        assertTrue("no speed-up or cadence-up while HR is above range", r.instructions.all { it.kind == CoachKind.HR_HIGH })
        // HR returns to range: the pending push instruction (pace first) can now be issued
        val after = run(p, 300, 360, start = r.state) { input(it, hr = 140.0, pace = 420.0, cad = 160.0) }
        assertEquals(CoachKind.PACE_TOO_SLOW, after.instructions.first().kind)
        assertEquals("Increase cadence by 5 steps per minute.", run(p, 300, 420, start = r.state) { input(it, hr = 140.0, pace = 360.0, cad = 160.0) }.instructions.first().text)
    }

    @Test fun gapsAndCooldownsFollowTheFrequencySetting() {
        val p = steadyPlan()
        val counts = CoachFrequency.entries.associateWith { f ->
            val r = run(p, 100, 1100, normal.copy(frequency = f)) { input(it, hr = 160.0) }
            val times = times(r, CoachKind.HR_HIGH)
            assertEquals("first one after the sustain time", 115.0, times.first(), 0.0)
            times.zipWithNext().forEach { (a, b) -> assertTrue("$f repeat spacing ${b - a}", b - a >= CoachConfig.KIND_COOLDOWN_MULT * f.gapS()) }
            times.size
        }
        assertTrue(counts.getValue(CoachFrequency.LOW) < counts.getValue(CoachFrequency.NORMAL))
        assertTrue(counts.getValue(CoachFrequency.NORMAL) < counts.getValue(CoachFrequency.HIGH))
    }

    private val intervalPlan = plan(seg(SegmentKind.WARMUP, 120), seg(SegmentKind.WORK, 60), seg(SegmentKind.RECOVERY, 60), seg(SegmentKind.WORK, 60), seg(SegmentKind.COOLDOWN, 120))

    @Test fun segmentAnnouncementsAndPlanDone() {
        val r = run(intervalPlan, 0, 440) { input(it, null, null, null) }
        val got = r.instructions.map { it.kind to it.activeS }
        assertEquals(listOf(
            CoachKind.SEGMENT_START to 0.0, CoachKind.SEGMENT_SOON to 90.0, CoachKind.SEGMENT_START to 120.0,
            CoachKind.SEGMENT_SOON to 150.0, CoachKind.SEGMENT_START to 180.0, CoachKind.SEGMENT_SOON to 210.0,
            CoachKind.SEGMENT_START to 240.0, CoachKind.SEGMENT_SOON to 270.0, CoachKind.SEGMENT_START to 300.0,
            CoachKind.SEGMENT_SOON to 390.0, CoachKind.PLAN_DONE to 420.0), got)
        assertEquals("Work interval begins in 30 seconds.", r.instructions[1].text)
        assertEquals("Warm-up.", r.instructions[0].text)
        assertEquals("Session ends in 30 seconds.", r.instructions[9].text)
        // announcements respect the plan's trigger list
        val silent = run(plan(seg(SegmentKind.WARMUP, 120), seg(SegmentKind.WORK, 60), triggers = setOf(CoachTrigger.HR_HIGH)), 0, 200) { input(it, null, null, null) }
        assertTrue(silent.instructions.isEmpty())
    }

    @Test fun recoveryMidPlanDoesNotReplayAnnouncements() {
        val r = run(intervalPlan, 250, 440) { input(it, null, null, null) }
        assertEquals(listOf(CoachKind.SEGMENT_SOON, CoachKind.SEGMENT_START, CoachKind.SEGMENT_SOON, CoachKind.PLAN_DONE), kinds(r))
        assertEquals(listOf(270.0, 300.0, 390.0, 420.0), r.instructions.map { it.activeS })
        assertTrue("a plan that is already over stays silent", run(intervalPlan, 500, 520) { input(it, null, null, null) }.instructions.isEmpty())
    }

    @Test fun missingOrStaleSensorsGetOneNoticeAndNoCorrectiveInstruction() {
        val p = steadyPlan()
        val r = run(p, 100, 400) { input(it, hr = null, pace = null, cad = null) }
        assertEquals(listOf(CoachKind.SENSOR_LOST_HR to 120.0, CoachKind.SENSOR_LOST_GPS to 121.0), r.instructions.map { it.kind to it.activeS })
        val stale = run(p, 100, 130) { input(it, hr = 160.0, hrAge = 11.0) }   // older than HR_STALE_S counts as missing
        assertEquals(listOf(CoachKind.SENSOR_LOST_HR), kinds(stale))
        val again = run(p, 100, 440) { input(it, hr = null) }                  // notice cooldown: next HR notice 300 s later
        assertEquals(listOf(120.0, 420.0), times(again, CoachKind.SENSOR_LOST_HR))
        val grace = run(plan(seg(SegmentKind.STEADY, 600, hr)), 0, 60) { input(it, hr = null) }
        assertEquals("not before the grace period", 30.0, times(grace, CoachKind.SENSOR_LOST_HR).first(), 0.0)
        val cadenceOnly = run(p, 100, 400) { input(it, cad = null) }
        assertTrue("missing cadence is silent", cadenceOnly.instructions.none { it.kind == CoachKind.CADENCE_LOW || it.kind == CoachKind.CADENCE_HIGH })
        assertTrue(cadenceOnly.instructions.none { it.kind == CoachKind.SENSOR_LOST_HR || it.kind == CoachKind.SENSOR_LOST_GPS })
    }

    @Test fun keepRhythmIsRare() {
        val p = steadyPlan()
        val r = run(p, 0, 1700) { input(it) }
        assertEquals(listOf(300.0, 600.0, 900.0, 1200.0, 1500.0), times(r, CoachKind.KEEP_RHYTHM))
        assertEquals("Maintain this rhythm.", r.instructions.first { it.kind == CoachKind.KEEP_RHYTHM }.text)
        val off = run(steadyPlan(setOf(CoachTrigger.SEGMENT_CHANGE)), 0, 1700) { input(it) }
        assertTrue(off.instructions.none { it.kind == CoachKind.KEEP_RHYTHM })
        val deviating = run(p, 0, 1700) { input(it, hr = if (it % 400 < 20) 155.0 else 138.0) }
        assertTrue("a sustained condition blocks keep-rhythm at that time", deviating.instructions.none { it.kind == CoachKind.KEEP_RHYTHM && it.activeS % 400 in 0.0..35.0 })
    }

    @Test fun theEngineIsDeterministic() {
        val rnd = Random(42)
        val seq = (0..900).map { t -> input(t.toDouble(), hr = 120.0 + rnd.nextInt(50), pace = 300.0 + rnd.nextInt(120), cad = 150.0 + rnd.nextInt(40),
            hrAge = rnd.nextInt(15).toDouble()) }
        val p = plan(seg(SegmentKind.WARMUP, 120), seg(SegmentKind.STEADY, 900, hr, pace, cad))
        fun play(): Pair<List<CoachInstruction>, CoachState> {
            var s = CoachState.initial(p, 0.0); val out = ArrayList<CoachInstruction>()
            for (i in seq) { val r = CoachEngine.step(p, s, i, normal); s = r.state; r.instruction?.let { out += it } }
            return out to s
        }
        val a = play(); val b = play()
        assertEquals(a.first, b.first); assertEquals(a.second, b.second)
        assertTrue(a.first.isNotEmpty())
    }

    @Test fun cadenceTargetFollowsTheSegment() {
        val p = plan(seg(SegmentKind.WARMUP, 60), seg(SegmentKind.STEADY, 600, cad = cad))
        assertNull(CoachEngine.currentCadenceTarget(p, 10.0))
        assertEquals(170.0, CoachEngine.currentCadenceTarget(p, 100.0)!!, 0.0)
        assertNull("after the plan", CoachEngine.currentCadenceTarget(p, 700.0))
    }
}
