package net.linspad.atlasphone.running.metronome

import net.linspad.atlasphone.mobile.audio.ClickOutput
import net.linspad.atlasphone.mobile.service.QuickAction
import net.linspad.atlasphone.running.settings.RunSettings

/** What the chip renders: targetSpm null = silent; ghostHasCadence null = no ghost session, false = no cadence recorded for it. */
data class MetronomeState(
    val mode: MetronomeMode,
    val targetSpm: Double?,
    val ghostHasCadence: Boolean?,
    val manualSpm: Int,
    val volume: Float,
    val engine: String,
)

/**
 * Owns the metronome of the active run (running meaning on top of the domain-free click engine and QuickAction).
 * RunController drives it: [tick] once per publish (1 Hz) hands the target to the engine atomically; [stop] at Finish Run,
 * legacy finish, discard and stopAll. Mode, manual cadence and volume are persisted through [RunSettings] only.
 */
class MetronomeController(
    private val engine: ClickOutput,
    private val quickAction: QuickAction,
    private val settings: RunSettings,
) {
    private val lock = Any()
    private val smoother = TargetSmoother()
    private var begun = false
    private var engineOn = false
    private var hasGhost = false
    private var hasCoach = false
    private var ghostCadence: List<Pair<Double, Double>>? = null
    private var mode = MetronomeMode.OFF
    private var manualSpm = MetronomeConfig.DEFAULT_MANUAL_SPM
    private var volume = MetronomeConfig.DEFAULT_VOLUME

    /** Run start / recover: restore the persisted mode (unavailable -> OFF), start the engine only when mode != OFF. */
    fun begin(hasGhost: Boolean, ghostCadenceByProgress: List<Pair<Double, Double>>?, hasCoach: Boolean = false) = synchronized(lock) {
        this.hasGhost = hasGhost
        this.hasCoach = hasCoach
        ghostCadence = ghostCadenceByProgress
        manualSpm = settings.manualCadenceSpm()
        volume = settings.clickVolume()
        val restored = settings.metronomeMode()
        val available = MetronomeTarget.availableModes(hasGhost, hasCoach)
        // COACH2: the persisted mode is never COACH; a ghost mode that is unavailable while coaching becomes COACH.
        mode = when {
            restored in available -> restored
            hasCoach && restored in listOf(MetronomeMode.MATCH_GHOST, MetronomeMode.ATTACK_102) -> MetronomeMode.COACH
            else -> MetronomeMode.OFF
        }
        begun = true
        smoother.reset()
        applyEngine()
        publishLabel()
    }

    /** 1 Hz. Paused = silence and smoother reset; otherwise raw target -> smoother -> engine. */
    fun tick(ghostProgressM: Double?, paused: Boolean, nowMillis: Long, coachCadenceSpm: Double? = null): MetronomeState = synchronized(lock) {
        var target: Double? = null
        if (begun && mode != MetronomeMode.OFF) {
            if (paused) {
                smoother.reset()
            } else {
                val raw = MetronomeTarget.rawTarget(mode, MetronomeTarget.ghostCadenceAt(ghostCadence, ghostProgressM), manualSpm, coachCadenceSpm)
                target = smoother.update(raw, nowMillis)
            }
        }
        if (engineOn) engine.setTargetSpm(target)
        state(target)
    }

    fun cycleMode(): MetronomeMode = synchronized(lock) {
        setModeLocked(MetronomeTarget.next(mode, hasGhost, hasCoach))
        mode
    }

    fun setMode(mode: MetronomeMode) = synchronized(lock) { setModeLocked(mode) }

    fun setManualSpm(spm: Int) = synchronized(lock) {
        manualSpm = spm.coerceIn(MetronomeConfig.MIN_TARGET_SPM.toInt(), MetronomeConfig.MAX_TARGET_SPM.toInt())
        settings.setManualCadenceSpm(manualSpm)
    }

    fun setVolume(volume: Float) = synchronized(lock) {
        this.volume = volume.coerceIn(0f, 1f)
        settings.setClickVolume(this.volume)
        if (engineOn) engine.setVolume(this.volume)
    }

    /** Engine stop, QuickAction cleared, smoother reset. Idempotent; the mode stays persisted. */
    fun stop() = synchronized(lock) {
        if (engineOn) engine.stop()
        engineOn = false
        begun = false
        smoother.reset()
        quickAction.set(null, null)
    }

    /** Current state for the chip outside a tick (e.g. right after a tap). */
    fun currentState(): MetronomeState = synchronized(lock) { state(null) }

    private fun setModeLocked(newMode: MetronomeMode) {
        mode = newMode
        if (newMode != MetronomeMode.COACH) settings.setMetronomeMode(newMode)   // COACH is never persisted
        smoother.reset()
        applyEngine()
        publishLabel()
    }

    private fun applyEngine() {
        if (!begun) return
        if (mode == MetronomeMode.OFF) {
            if (engineOn) engine.stop()
            engineOn = false
        } else if (!engineOn) {
            engineOn = engine.start(volume)
        }
        if (engineOn) engine.setTargetSpm(null)   // silent until the next tick hands over a target
    }

    private fun publishLabel() {
        if (begun) quickAction.set("Click: ${mode.label}") { cycleMode() } else quickAction.set(null, null)
    }

    private fun state(target: Double?) = MetronomeState(
        mode, target,
        if (hasGhost) !ghostCadence.isNullOrEmpty() else null,
        manualSpm, volume, engine.stateName(),
    )
}
