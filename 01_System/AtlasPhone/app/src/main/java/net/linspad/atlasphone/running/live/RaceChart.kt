package net.linspad.atlasphone.running.live

import net.linspad.atlasphone.running.ghost.GhostComparison
import net.linspad.atlasphone.running.ghost.GhostProfile

object RaceConfig {
    /** How much gap history the race screen keeps (1-2 minutes). */
    const val GAP_HISTORY_S = 120.0
    /** A route section shorter than this gives no ghost section pace. */
    const val GHOST_SECTION_MIN_M = 15.0
}

/**
 * Pure display derivations for the left race panel (RC1). Gap (seconds) and pace are never put on one axis:
 * the gap history is a series of seconds, paces are two numbers.
 */
object RaceChart {
    /**
     * Ghost pace (s/km) over the route section from [fromProgressM] to [toProgressM] (the section the runner covered in the
     * last RACE_PACE_WINDOW_S): ghost time difference over the same section, via the profile's time-at-progress lookup.
     * Null for a section shorter than GHOST_SECTION_MIN_M, a section the ghost cannot answer, or a ghost that stood still.
     */
    fun ghostSectionPace(profile: GhostProfile, fromProgressM: Double, toProgressM: Double): Double? {
        val dist = toProgressM - fromProgressM
        if (dist < RaceConfig.GHOST_SECTION_MIN_M) return null
        val t0 = GhostComparison.timeAtProgress(profile, fromProgressM) ?: return null
        val t1 = GhostComparison.timeAtProgress(profile, toProgressM) ?: return null
        val dt = t1 - t0
        return if (dt > 0) dt / dist * 1000.0 else null
    }
}
