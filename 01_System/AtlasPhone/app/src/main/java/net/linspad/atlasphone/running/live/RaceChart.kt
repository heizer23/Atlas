package net.linspad.atlasphone.running.live

import net.linspad.atlasphone.running.ghost.GhostComparison
import net.linspad.atlasphone.running.ghost.GhostProfile

object RaceConfig {
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

/** The three side-chart series against the selected ghost, by route position s (metres). Null y = honest gap (no line drawn). */
class RaceDiffSeries(
    /** Runner minus ghost progress at equal elapsed time, metres; + = runner ahead. */
    val gapM: List<Pair<Double, Double?>>,
    /** Runner HR minus ghost HR at the same route position, bpm. */
    val hrDelta: List<Pair<Double, Double?>>,
    /** Runner pace minus ghost pace over the same route section, s/km; negative = runner faster. */
    val paceDelta: List<Pair<Double, Double?>>,
    /** Route position the runner is at now; the series only reach this far (no future comparison). */
    val nowS: Double,
)

/**
 * Runner trail (moving s, route position, smoothed HR) for the side charts. Everything is derived from the trail and the
 * selected ghost's profile, so switching ghost re-derives all three series at once. Display only, in memory.
 * Equal elapsed time -> [RaceDiffSeries.gapM]; equal route position -> hrDelta and paceDelta.
 */
class RaceDiff {
    private val ts = ArrayList<Double>()
    private val ss = ArrayList<Double>()
    private val hrs = ArrayList<Double?>()

    /** Position never goes backwards (GPS jitter / a short wrong-way step is held at the best position reached). */
    fun add(t: Double, s: Double, hr: Double?) {
        if (ts.isNotEmpty() && (t <= ts.last())) return
        val pos = if (ss.isEmpty()) s else maxOf(s, ss.last())
        ts.add(t); ss.add(pos); hrs.add(hr)
    }

    /** Runner moving time at route position [s]; null outside what was covered. */
    private fun timeAt(s: Double): Double? {
        if (ss.isEmpty() || s < ss.first() || s > ss.last()) return null
        var lo = 0; var hi = ss.size
        while (lo < hi) { val mid = (lo + hi) ushr 1; if (ss[mid] < s) lo = mid + 1 else hi = mid }
        if (ss[lo] == s) return ts[lo]
        val a = lo - 1
        return ts[a] + (ts[lo] - ts[a]) * (s - ss[a]) / (ss[lo] - ss[a])
    }

    fun snapshot(profile: GhostProfile): RaceDiffSeries? {
        if (ss.size < 2) return null
        val now = ss.last()
        val from = (now - SPAN_M).coerceAtLeast(ss.first())
        val gap = ArrayList<Pair<Double, Double?>>(); val dHr = ArrayList<Pair<Double, Double?>>(); val dPace = ArrayList<Pair<Double, Double?>>()
        // One pass over the trail: mean gap and mean HR per bucket.
        var i = ss.indexOfFirst { it >= from }.coerceAtLeast(0)
        var b = Math.floor(from / STEP_M).toInt()
        val lastB = Math.floor(now / STEP_M).toInt()
        while (b <= lastB) {
            var gSum = 0.0; var gN = 0; var hSum = 0.0; var hN = 0
            while (i < ss.size && ss[i] < (b + 1) * STEP_M) {
                gSum += ss[i] - GhostComparison.progressNow(profile, ts[i]); gN++
                hrs[i]?.let { hSum += it; hN++ }
                i++
            }
            val mid = ((b + 0.5) * STEP_M).coerceIn(from, now)
            if (gN > 0) {
                gap.add(mid to gSum / gN)
                val ghostHr = GhostComparison.hrAtProgress(profile, mid)
                dHr.add(mid to if (hN > 0 && ghostHr != null) hSum / hN - ghostHr else null)
                dPace.add(mid to paceDelta(profile, mid))
            }
            b++
        }
        return RaceDiffSeries(gap, dHr, dPace, now)
    }

    private fun paceDelta(profile: GhostProfile, mid: Double): Double? {
        val a = mid - PACE_SECTION_M; val z = mid
        val t0 = timeAt(a) ?: return null
        val t1 = timeAt(z) ?: return null
        val dt = t1 - t0
        if (dt <= 0) return null
        val mine = dt / (z - a) * 1000.0
        if (mine > MAX_PACE_S_PER_KM) return null          // standing still: no pace, not a huge number
        val ghost = RaceChart.ghostSectionPace(profile, a, z) ?: return null
        return mine - ghost
    }

    companion object {
        const val STEP_M = 20.0
        /** The side charts show the last kilometre of the route. */
        const val SPAN_M = 1000.0
        /** Pace over the 60 m just covered = about 15 s at running pace (the 10-20 s window of the spec), by position not clock. */
        const val PACE_SECTION_M = 60.0
        const val MAX_PACE_S_PER_KM = 1200.0
    }
}
