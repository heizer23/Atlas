package net.linspad.atlasphone.running.coach

import kotlin.math.roundToInt

/** COACH1 constants (declared once, tuned after real sessions via this object only; OQ3). Times are seconds of ACTIVE time. */
object CoachConfig {
    const val SUSTAIN_S = 15.0
    const val SETTLE_S = 45.0
    const val HR_TOL_BPM = 3.0
    const val PACE_TOL_S = 10.0
    const val CAD_TOL_SPM = 3.0
    const val HR_STALE_S = 10.0
    const val SEGMENT_WARN_S = 30
    const val GAP_LOW_S = 90.0
    const val GAP_NORMAL_S = 45.0
    const val GAP_HIGH_S = 25.0
    const val KIND_COOLDOWN_MULT = 3.0
    const val MAINTAIN_S = 180.0
    const val MAINTAIN_QUIET_S = 300.0
    const val SENSOR_LOST_S = 20.0
    const val SENSOR_GRACE_S = 30.0
    const val SENSOR_NOTICE_COOLDOWN_S = 300.0
    const val CAD_STEP_MIN = 2
    const val CAD_STEP_MAX = 5
    const val DISPLAY_S = 20
}

enum class CoachFrequency(val label: String) {
    LOW("Low"), NORMAL("Normal"), HIGH("High");

    fun gapS(): Double = when (this) { LOW -> CoachConfig.GAP_LOW_S; NORMAL -> CoachConfig.GAP_NORMAL_S; HIGH -> CoachConfig.GAP_HIGH_S }

    companion object { fun parse(s: String?): CoachFrequency = entries.firstOrNull { it.name == s } ?: NORMAL }
}

enum class CoachKind(val trigger: CoachTrigger) {
    HR_HIGH(CoachTrigger.HR_HIGH), HR_LOW(CoachTrigger.HR_LOW),
    PACE_TOO_FAST(CoachTrigger.PACE_FAST), PACE_TOO_SLOW(CoachTrigger.PACE_SLOW),
    CADENCE_LOW(CoachTrigger.CADENCE_LOW), CADENCE_HIGH(CoachTrigger.CADENCE_HIGH),
    KEEP_RHYTHM(CoachTrigger.KEEP_RHYTHM),
    SEGMENT_START(CoachTrigger.SEGMENT_CHANGE), SEGMENT_SOON(CoachTrigger.SEGMENT_CHANGE),
    SENSOR_LOST_HR(CoachTrigger.SENSOR_LOST), SENSOR_LOST_GPS(CoachTrigger.SENSOR_LOST),
    PLAN_DONE(CoachTrigger.SEGMENT_CHANGE),
}

/** One tick of live data; activeS = elapsed minus completed pauses (OQ2). null = no valid reading, never 0. */
data class CoachInput(
    val activeS: Double,
    val paused: Boolean,
    val hrBpm: Double?,
    val hrAgeS: Double?,
    val paceSPerKm: Double?,
    val cadenceSpm: Double?,
)

/** enabled and frequency are persisted (RunSettings); muted is session-only. */
data class CoachSettings(val enabled: Boolean, val muted: Boolean, val frequency: CoachFrequency)

data class CoachInstruction(val kind: CoachKind, val text: String, val activeS: Double)

data class CoachStepResult(val state: CoachState, val instruction: CoachInstruction?)

/** Immutable engine memory. Time keys are active seconds. */
data class CoachState(
    val startS: Double,
    val lastSegIdx: Int,
    val startedIdx: Int,
    val warnedIdx: Int,
    val doneEmitted: Boolean,
    val lastSpokenS: Double?,
    val lastSpokenByKind: Map<CoachKind, Double>,
    val devSince: Map<CoachKind, Double>,
    val inRangeSince: Map<String, Double>,
    val invalidSince: Map<String, Double>,
    val lastNoticeS: Map<CoachKind, Double>,
) {
    companion object {
        /** Segments that started before startActiveS count as announced (a recovery mid-plan replays nothing). */
        fun initial(plan: CoachPlan, startActiveS: Double): CoachState {
            val started = plan.segments.indices.lastOrNull { plan.segmentStartS(it) < startActiveS } ?: -1
            return CoachState(
                startS = startActiveS, lastSegIdx = plan.segmentIndexAt(startActiveS) ?: -1,
                startedIdx = started, warnedIdx = started - 1, doneEmitted = startActiveS >= plan.totalS(),
                lastSpokenS = null, lastSpokenByKind = emptyMap(), devSince = emptyMap(), inRangeSince = emptyMap(),
                invalidSince = emptyMap(), lastNoticeS = emptyMap(),
            )
        }
    }
}

/** COACH1 (definition in Sprint04_GhostCoach/10_architecture.json). Pure: no Android, no clock, no I/O, no randomness. */
object CoachEngine {
    private val PRIORITY = listOf(
        CoachKind.HR_HIGH, CoachKind.PACE_TOO_FAST, CoachKind.HR_LOW, CoachKind.PACE_TOO_SLOW, CoachKind.CADENCE_LOW, CoachKind.CADENCE_HIGH,
    )
    private val PUSH = setOf(CoachKind.HR_LOW, CoachKind.PACE_TOO_SLOW, CoachKind.CADENCE_LOW)

    fun currentCadenceTarget(plan: CoachPlan, activeS: Double): Double? {
        val seg = plan.segmentIndexAt(activeS)?.let { plan.segments[it] } ?: return null
        return seg.cadence?.let { (it.lo + it.hi) / 2.0 }
    }

    fun step(plan: CoachPlan, state: CoachState, input: CoachInput, settings: CoachSettings): CoachStepResult {
        val active = input.activeS
        val idx = plan.segmentIndexAt(active)

        // (0) silent states: timers cleared; markers still advance while disabled or muted so nothing stale is announced later.
        if (input.paused || !settings.enabled) return CoachStepResult(silent(plan, state, active, idx, advance = !input.paused), null)
        if (settings.muted) return CoachStepResult(silent(plan, state, active, idx, advance = true), null)
        if (idx == null) {
            if (state.doneEmitted || active < 0) return CoachStepResult(silent(plan, state, active, idx, advance = true), null)
            val done = if (plan.enabled(CoachTrigger.SEGMENT_CHANGE)) CoachInstruction(CoachKind.PLAN_DONE, "Session complete.", active) else null
            return CoachStepResult(speak(silent(plan, state, active, idx, advance = true), done), done)
        }

        val seg = plan.segments[idx]
        val segStart = plan.segmentStartS(idx)
        val segElapsed = active - segStart
        val changed = idx != state.lastSegIdx

        // (2) boundary events (not gated by the frequency gap)
        var startedIdx = state.startedIdx
        var warnedIdx = state.warnedIdx
        var boundary: CoachInstruction? = null
        if (idx > startedIdx) {
            startedIdx = idx
            if (plan.enabled(CoachTrigger.SEGMENT_CHANGE)) boundary = CoachInstruction(CoachKind.SEGMENT_START, startText(seg.kind), active)
        }
        val remaining = segStart + seg.durationS - active
        if (boundary == null && idx > warnedIdx && remaining <= CoachConfig.SEGMENT_WARN_S && seg.durationS >= 2 * CoachConfig.SEGMENT_WARN_S) {
            warnedIdx = idx
            if (plan.enabled(CoachTrigger.SEGMENT_CHANGE)) boundary = CoachInstruction(CoachKind.SEGMENT_SOON, soonText(plan, idx), active)
        }

        // (4) deviations per dimension. A new segment has new targets, so timers restart there.
        val hrValid = input.hrBpm != null && input.hrAgeS != null && input.hrAgeS <= CoachConfig.HR_STALE_S
        val dev = mutableMapOf<CoachKind, Double>()        // kind -> amount beyond the range edge
        val evaluated = mutableSetOf<String>()             // dimensions with a target and a valid reading
        val inBand = mutableSetOf<String>()                // evaluated dimensions inside range +/- tolerance
        fun eval(dim: String, target: TargetRange?, value: Double?, valid: Boolean, tol: Double, high: CoachKind, low: CoachKind) {
            if (target == null || !valid || value == null) return
            evaluated += dim
            when {
                value - target.hi > tol -> dev[high] = value - target.hi
                target.lo - value > tol -> dev[low] = target.lo - value
                else -> inBand += dim
            }
        }
        eval("hr", seg.hr, input.hrBpm, hrValid, CoachConfig.HR_TOL_BPM, CoachKind.HR_HIGH, CoachKind.HR_LOW)
        // pace: a larger value is slower, so "high" = too slow
        eval("pace", seg.pace, input.paceSPerKm, input.paceSPerKm != null, CoachConfig.PACE_TOL_S, CoachKind.PACE_TOO_SLOW, CoachKind.PACE_TOO_FAST)
        eval("cadence", seg.cadence, input.cadenceSpm, input.cadenceSpm != null, CoachConfig.CAD_TOL_SPM, CoachKind.CADENCE_HIGH, CoachKind.CADENCE_LOW)

        val prevDev = if (changed) emptyMap() else state.devSince
        val prevInRange = if (changed) emptyMap() else state.inRangeSince
        var devSince = dev.keys.associateWith { prevDev[it] ?: active }
        val inRangeSince = inBand.associateWith { prevInRange[it] ?: active }
        val invalidSince = buildMap<String, Double> {
            if (seg.hr != null && !hrValid) put("hr", state.invalidSince["hr"] ?: active)
            if (seg.pace != null && input.paceSPerKm == null) put("pace", state.invalidSince["pace"] ?: active)
        }
        fun sustained(k: CoachKind) = devSince[k]?.let { active - it >= CoachConfig.SUSTAIN_S } == true

        val gap = settings.frequency.gapS()
        var lastSpokenS = state.lastSpokenS
        val lastByKind = state.lastSpokenByKind.toMutableMap()
        val lastNotice = state.lastNoticeS.toMutableMap()
        var spoken: CoachInstruction? = boundary

        // (3), (5), (6) corrective instructions
        if (spoken == null && segElapsed >= CoachConfig.SETTLE_S) {
            val easeSustained = sustained(CoachKind.HR_HIGH) || sustained(CoachKind.PACE_TOO_FAST)
            // The per-kind cooldown is part of eligibility, so a kind that spoke recently does not starve the next priority.
            val chosen = PRIORITY.firstOrNull { k ->
                sustained(k) && plan.enabled(k.trigger) &&
                    !(k in PUSH && easeSustained) && !(k == CoachKind.PACE_TOO_SLOW && sustained(CoachKind.HR_HIGH)) &&
                    (lastByKind[k]?.let { active - it >= CoachConfig.KIND_COOLDOWN_MULT * gap } != false)
            }
            if (chosen != null && (lastSpokenS == null || active - lastSpokenS >= gap)) {
                spoken = CoachInstruction(chosen, correctiveText(chosen, dev[chosen] ?: 0.0), active)
                devSince = devSince + (chosen to active)   // must re-sustain before a repeat
            }
        }

        // (8) sensors that are needed by the current segment but missing
        if (spoken == null && active >= CoachConfig.SENSOR_GRACE_S && plan.enabled(CoachTrigger.SENSOR_LOST)) {
            for ((dim, kind) in listOf("hr" to CoachKind.SENSOR_LOST_HR, "pace" to CoachKind.SENSOR_LOST_GPS)) {
                val since = invalidSince[dim] ?: continue
                if (active - since >= CoachConfig.SENSOR_LOST_S && lastNotice[kind]?.let { active - it >= CoachConfig.SENSOR_NOTICE_COOLDOWN_S } != false) {
                    spoken = CoachInstruction(kind, if (kind == CoachKind.SENSOR_LOST_HR) "Heart rate signal lost." else "GPS signal lost.", active)
                    lastNotice[kind] = active
                    break
                }
            }
        }

        // (7) keep rhythm: rare
        if (spoken == null && plan.enabled(CoachTrigger.KEEP_RHYTHM) && PRIORITY.none { sustained(it) } &&
            inRangeSince.isNotEmpty() && inRangeSince.size == evaluated.size &&
            inRangeSince.values.all { active - it >= CoachConfig.MAINTAIN_S } &&
            active - (lastSpokenS ?: state.startS) >= CoachConfig.MAINTAIN_QUIET_S
        ) spoken = CoachInstruction(CoachKind.KEEP_RHYTHM, "Maintain this rhythm.", active)

        if (spoken != null) {
            lastSpokenS = active
            lastByKind[spoken.kind] = active
        }
        val next = state.copy(
            lastSegIdx = idx, startedIdx = startedIdx, warnedIdx = warnedIdx, lastSpokenS = lastSpokenS,
            lastSpokenByKind = lastByKind, devSince = devSince, inRangeSince = inRangeSince, invalidSince = invalidSince,
            lastNoticeS = lastNotice,
        )
        return CoachStepResult(next, spoken)
    }

    private fun speak(state: CoachState, instruction: CoachInstruction?): CoachState =
        if (instruction == null) state else state.copy(lastSpokenS = instruction.activeS, lastSpokenByKind = state.lastSpokenByKind + (instruction.kind to instruction.activeS))

    /** Timers cleared; with advance the announcement markers move to the present so nothing stale is spoken later. */
    private fun silent(plan: CoachPlan, state: CoachState, active: Double, idx: Int?, advance: Boolean): CoachState {
        val cleared = state.copy(devSince = emptyMap(), inRangeSince = emptyMap(), invalidSince = emptyMap())
        if (!advance) return cleared
        val reached = idx ?: plan.segments.lastIndex
        return cleared.copy(
            lastSegIdx = idx ?: state.lastSegIdx,
            startedIdx = maxOf(state.startedIdx, reached), warnedIdx = maxOf(state.warnedIdx, reached),
            doneEmitted = state.doneEmitted || idx == null && active >= plan.totalS(),
        )
    }

    private fun label(kind: SegmentKind) = when (kind) {
        SegmentKind.WARMUP -> "Warm-up"; SegmentKind.STEADY -> "Steady pace"; SegmentKind.WORK -> "Work interval"
        SegmentKind.RECOVERY -> "Recovery interval"; SegmentKind.COOLDOWN -> "Cool-down"
    }

    private fun startText(kind: SegmentKind) = "${label(kind)}."

    private fun soonText(plan: CoachPlan, idx: Int): String =
        plan.segments.getOrNull(idx + 1)?.let { "${label(it.kind)} begins in ${CoachConfig.SEGMENT_WARN_S} seconds." }
            ?: "Session ends in ${CoachConfig.SEGMENT_WARN_S} seconds."

    private fun correctiveText(kind: CoachKind, deviation: Double): String {
        val step = deviation.roundToInt().coerceIn(CoachConfig.CAD_STEP_MIN, CoachConfig.CAD_STEP_MAX)
        return when (kind) {
            CoachKind.HR_HIGH -> "Your heart rate is above target."
            CoachKind.HR_LOW -> "Your heart rate is below target."
            CoachKind.PACE_TOO_FAST -> "Reduce your pace slightly."
            CoachKind.PACE_TOO_SLOW -> "Pick up your pace slightly."
            CoachKind.CADENCE_LOW -> "Increase cadence by $step steps per minute."
            CoachKind.CADENCE_HIGH -> "Reduce cadence by $step steps per minute."
            else -> error("not a corrective kind")
        }
    }
}
