package net.linspad.atlasphone.running.coach

import net.linspad.atlasphone.mobile.audio.SpeechPort
import net.linspad.atlasphone.running.net.AtlasClient
import net.linspad.atlasphone.running.net.AtlasResult
import net.linspad.atlasphone.running.settings.RunSettings

/** What CoachStrip renders; lastInstruction is cleared DISPLAY_S seconds after it was issued. */
data class CoachUiState(
    val planId: String,
    val planTitle: String,
    val segmentLabel: String?,
    val segmentRemainingS: Int?,
    val lastInstruction: String?,
    val muted: Boolean,
    val speechAvailable: Boolean,
    val cadenceTargetSpm: Double?,
)

/**
 * Owns the coach session of the active run (running meaning on top of the domain-free SpeechPort). RunController creates and drives
 * it: [begin] at run start/recover, [tick] inside the 1 Hz publish, [end] at finish/discard/stopAll. Every exception is caught: the
 * coach disables itself for the session and logs (REL2); it never touches recording or upload. Plan fetching is [refreshPlan], called
 * from the Run home panel only (COACH3), never during a run.
 */
class CoachController(
    private val speech: SpeechPort,
    private val planStore: CoachPlanStore,
    private val settings: RunSettings,
    private val log: (String) -> Unit,
) {
    private val lock = Any()
    private var plan: CoachPlan? = null
    private var state: CoachState? = null
    private var muted = false
    private var lastText: String? = null
    private var lastTextActiveS = 0.0

    /** Plan id of the cached, supported plan when 'Coach this run' is on; null otherwise. */
    fun sessionPlanId(): String? {
        if (!settings.coachEnabled()) return null
        return (planStore.load() as? CoachPlanParse.Ok)?.plan?.planId
    }

    /** Loads the cached plan by id and builds the initial state; false = no coaching (cache missing, other plan or unsupported). */
    fun begin(planId: String, activeS: Double): Boolean = synchronized(lock) {
        end()
        try {
            val parsed = planStore.load() as? CoachPlanParse.Ok ?: return false
            if (parsed.plan.planId != planId) return false
            plan = parsed.plan
            state = CoachState.initial(parsed.plan, activeS)
            muted = false
            lastText = null
            speech.prepare()
            true
        } catch (e: Exception) {
            disable("begin", e)
            false
        }
    }

    /** COACH1 step; speaks a non-null instruction (speech false -> text only). null when there is no session. */
    fun tick(input: CoachInput): CoachUiState? = synchronized(lock) {
        val p = plan ?: return null
        val s = state ?: return null
        try {
            val result = CoachEngine.step(p, s, input, CoachSettings(enabled = true, muted = muted, frequency = settings.coachFrequency()))
            state = result.state
            result.instruction?.let { instruction ->
                lastText = instruction.text
                lastTextActiveS = instruction.activeS
                runCatching { speech.speak(instruction.text) }   // speech failure = text only, never a disabled session
            }
            val shown = lastText?.takeIf { input.activeS - lastTextActiveS <= CoachConfig.DISPLAY_S }
            val idx = p.segmentIndexAt(input.activeS)
            CoachUiState(
                planId = p.planId, planTitle = p.title,
                segmentLabel = idx?.let { p.segments[it].kind.wire.replaceFirstChar { c -> c.uppercase() } },
                segmentRemainingS = idx?.let { (p.segmentStartS(it) + p.segments[it].durationS - input.activeS).toInt().coerceAtLeast(0) },
                lastInstruction = shown, muted = muted, speechAvailable = speech.isAvailable(),
                cadenceTargetSpm = CoachEngine.currentCadenceTarget(p, input.activeS),
            )
        } catch (e: Exception) {
            disable("tick", e)
            null
        }
    }

    /** COACH2 value for MetronomeController.tick; null without a session or a cadence target. */
    fun cadenceTarget(activeS: Double): Double? = synchronized(lock) {
        val p = plan ?: return null
        try { CoachEngine.currentCadenceTarget(p, activeS) } catch (e: Exception) { null }
    }

    /** True when a session is active and any plan segment has a cadence target (offers MetronomeMode.COACH). */
    fun hasCadenceTarget(): Boolean = synchronized(lock) { plan?.segments?.any { it.cadence != null } == true }

    fun hasSession(): Boolean = synchronized(lock) { plan != null }

    fun setMuted(muted: Boolean) = synchronized(lock) {
        this.muted = muted
        if (muted) runCatching { speech.stop() }
    }

    /** Stop speech, drop the session. Idempotent. */
    fun end() = synchronized(lock) {
        plan = null
        state = null
        lastText = null
        muted = false
        runCatching { speech.stop() }
        Unit
    }

    /**
     * Blocking (call from IO): GET next-plan, save or clear the cache per COACH3, return the parse of the resulting cache. On any error
     * the cache is returned unchanged. Never called during a run.
     */
    fun refreshPlan(client: AtlasClient, nowMillis: Long = System.currentTimeMillis()): CoachPlanParse? {
        try {
            when (val r = client.nextCoachPlan()) {
                is AtlasResult.Success -> {
                    val next = r.value
                    if (next.planId == null || next.planJson == null) planStore.clear()
                    else planStore.save(next.planId, next.planJson, nowMillis)
                }
                else -> Unit   // offline or error: keep the cache
            }
        } catch (e: Exception) {
            log("Coach plan refresh failed (${e.javaClass.simpleName})")
        }
        return planStore.load()
    }

    fun cachedPlan(): CoachPlanParse? = planStore.load()

    private fun disable(where: String, e: Exception) {
        log("Coach disabled for this session ($where: ${e.javaClass.simpleName})")
        plan = null
        state = null
        runCatching { speech.stop() }
    }
}
