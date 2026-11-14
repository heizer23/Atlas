package net.linspad.atlasphone.running.metronome

import net.linspad.atlasphone.mobile.audio.ClickConfig
import net.linspad.atlasphone.running.cadence.CadenceConfig
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min

enum class MetronomeMode(val label: String) {
    OFF("Off"), MATCH_GHOST("Match ghost"), ATTACK_102("Attack +2%"), MANUAL("Manual");

    companion object {
        fun parse(s: String?): MetronomeMode = entries.firstOrNull { it.name == s } ?: OFF
    }
}

/** MET1 constants. DEFAULT_VOLUME refers to the single declaration in ClickConfig. */
object MetronomeConfig {
    const val SLEW_SPM_PER_S = 1.0
    const val HOLD_S = 15.0
    const val ATTACK_FACTOR = 1.02
    const val MIN_TARGET_SPM = 100.0
    const val MAX_TARGET_SPM = 230.0
    const val DEFAULT_MANUAL_SPM = 170
    const val MANUAL_STEP_SPM = 1
    const val DEFAULT_VOLUME = ClickConfig.DEFAULT_VOLUME
}

/**
 * Smooths the metronome target: first raw value as is, afterwards at most SLEW_SPM_PER_S per elapsed second toward the raw
 * value; raw null holds the last output for HOLD_S, then silence until a raw value returns (which restarts from that value).
 */
class TargetSmoother {
    private var out: Double? = null
    private var lastMillis: Long? = null
    private var rawLostSinceMillis: Long? = null

    fun update(rawTargetSpm: Double?, nowMillis: Long): Double? {
        val dt = lastMillis?.let { max(0.0, (nowMillis - it) / 1000.0) } ?: 0.0
        lastMillis = nowMillis
        if (rawTargetSpm == null) {
            val since = rawLostSinceMillis ?: nowMillis.also { rawLostSinceMillis = it }
            if ((nowMillis - since) / 1000.0 >= MetronomeConfig.HOLD_S) out = null
            return out
        }
        rawLostSinceMillis = null
        val current = out
        out = if (current == null) rawTargetSpm
        else {
            val maxStep = MetronomeConfig.SLEW_SPM_PER_S * dt
            current + (rawTargetSpm - current).coerceIn(-maxStep, maxStep)
        }
        return out
    }

    fun reset() { out = null; lastMillis = null; rawLostSinceMillis = null }
}

object MetronomeTarget {
    /**
     * GB1 lookup: bucket value at the progress, linearly interpolated between neighbouring bucket centres
     * (centre = start + PROGRESS_BUCKET_M / 2). Null for no list, unknown progress, a gap (a neighbour bucket is absent)
     * or a position more than one bucket outside the covered range. Never derived from speed.
     */
    fun ghostCadenceAt(cadenceByProgress: List<Pair<Double, Double>>?, progressM: Double?): Double? {
        if (cadenceByProgress.isNullOrEmpty() || progressM == null) return null
        val w = CadenceConfig.PROGRESS_BUCKET_M
        val byStart = cadenceByProgress.associate { it.first to it.second }
        val first = cadenceByProgress.first().first
        val last = cadenceByProgress.last().first
        if (progressM < first - w || progressM >= last + 2 * w) return null
        val idx = Math.floor(progressM / w) * w                       // bucket start containing the position
        val own = byStart[idx]
        if (own == null) {
            // Within one bucket outside the covered range the edge value counts; an absent bucket in between is a gap.
            return when (idx) { first - w -> byStart[first]; last + w -> byStart[last]; else -> null }
        }
        val centre = idx + w / 2
        val otherStart = if (progressM >= centre) idx + w else idx - w   // neighbour on the side of the position
        val other = byStart[otherStart] ?: return own
        val oc = otherStart + w / 2
        return own + (other - own) * ((progressM - centre) / (oc - centre))
    }

    fun rawTarget(mode: MetronomeMode, ghostCadenceSpm: Double?, manualSpm: Int): Double? {
        val raw = when (mode) {
            MetronomeMode.OFF -> null
            MetronomeMode.MATCH_GHOST -> ghostCadenceSpm
            MetronomeMode.ATTACK_102 -> ghostCadenceSpm?.times(MetronomeConfig.ATTACK_FACTOR)
            MetronomeMode.MANUAL -> manualSpm.toDouble()
        }
        return raw?.takeIf { it >= MetronomeConfig.MIN_TARGET_SPM && it <= MetronomeConfig.MAX_TARGET_SPM }
    }

    fun availableModes(hasGhost: Boolean): List<MetronomeMode> =
        if (hasGhost) listOf(MetronomeMode.OFF, MetronomeMode.MATCH_GHOST, MetronomeMode.ATTACK_102, MetronomeMode.MANUAL)
        else listOf(MetronomeMode.OFF, MetronomeMode.MANUAL)

    fun next(current: MetronomeMode, hasGhost: Boolean): MetronomeMode {
        val modes = availableModes(hasGhost)
        val i = modes.indexOf(current)
        return if (i < 0) MetronomeMode.OFF else modes[(i + 1) % modes.size]
    }
}
