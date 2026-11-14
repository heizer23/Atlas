package net.linspad.atlasphone.running.hr

import kotlin.math.abs
import kotlin.math.max

/** Display smoothing of heart rate (HR2). Default [ROLLING_5S]; chosen by the user, stored locally only. */
enum class HrSmoothingMode {
    RAW, ROLLING_5S, ROLLING_10S;

    companion object {
        val DEFAULT = ROLLING_5S
        fun parse(name: String?): HrSmoothingMode = entries.firstOrNull { it.name == name } ?: DEFAULT
    }
}

/** One raw HR reading (timestamp = sample timestamp, UTC epoch ms). */
data class HrPoint(val tsMillis: Long, val bpm: Int)

/** Display value; [bpm] null = gap (never 0). */
data class SmoothedPoint(val tsMillis: Long, val bpm: Double?)

/** Same names and values as backend/config.py for the validity rule (HR1); the rest is phone-only. */
object HrConfig {
    const val VALID_MIN_BPM = 30
    const val VALID_MAX_BPM = 230
    const val SPIKE_MAX_BPM_PER_S = 40.0
    const val ROLLING_5S_S = 5.0
    const val ROLLING_10S_S = 10.0
    const val RAW_TOLERANCE_S = 2.0
    const val GAP_BREAK_S = 5.0
    const val RECAP_BUCKET_S = 1.0
}

/** Pure, Android-free HR1 validity and HR2 smoothing. Raw samples are never modified. */
object HrSmoothing {
    /**
     * HR1 on time-ordered samples: range check, then the isolated-spike rule (both range-valid neighbours differ by more than
     * the limit; first and last range-valid samples are never spikes). Returns the valid samples unchanged.
     */
    fun validSamples(samples: List<HrPoint>): List<HrPoint> {
        val ranged = samples.filter { it.bpm in HrConfig.VALID_MIN_BPM..HrConfig.VALID_MAX_BPM }.sortedBy { it.tsMillis }
        return ranged.filterIndexed { i, p ->
            if (i == 0 || i == ranged.lastIndex) return@filterIndexed true
            val prev = ranged[i - 1]; val next = ranged[i + 1]
            val dtPrev = max((p.tsMillis - prev.tsMillis) / 1000.0, 1.0)
            val dtNext = max((next.tsMillis - p.tsMillis) / 1000.0, 1.0)
            val spike = abs(p.bpm - prev.bpm) / dtPrev > HrConfig.SPIKE_MAX_BPM_PER_S &&
                abs(p.bpm - next.bpm) / dtNext > HrConfig.SPIKE_MAX_BPM_PER_S
            !spike
        }
    }

    private fun windowS(mode: HrSmoothingMode): Double = when (mode) {
        HrSmoothingMode.RAW -> 0.0
        HrSmoothingMode.ROLLING_5S -> HrConfig.ROLLING_5S_S
        HrSmoothingMode.ROLLING_10S -> HrConfig.ROLLING_10S_S
    }

    /** First index whose timestamp is >= [ms] ([valid] is sorted by time). */
    private fun lowerBound(valid: List<HrPoint>, ms: Long): Int {
        var lo = 0; var hi = valid.size
        while (lo < hi) { val mid = (lo + hi) ushr 1; if (valid[mid].tsMillis < ms) lo = mid + 1 else hi = mid }
        return lo
    }

    /** Mean of valid samples in [fromMs, toMs] (or (fromMs, toMs]); null without a sample. Binary search keeps long runs cheap. */
    private fun meanIn(valid: List<HrPoint>, fromMs: Long, toMs: Long, fromInclusive: Boolean): Double? {
        var i = lowerBound(valid, if (fromInclusive) fromMs else fromMs + 1)
        var sum = 0L; var n = 0
        while (i < valid.size && valid[i].tsMillis <= toMs) { sum += valid[i].bpm; n++; i++ }
        return if (n == 0) null else sum.toDouble() / n
    }

    /**
     * HR2 value at a time: mean of valid samples in the mode's window (trailing (t-n, t] or centered [t-n/2, t+n/2]).
     * RAW = the nearest valid sample within RAW_TOLERANCE_S. Null when no valid sample qualifies (never 0).
     */
    fun valueAt(samples: List<HrPoint>, mode: HrSmoothingMode, atMillis: Long, centered: Boolean): Double? {
        val valid = validSamples(samples)
        if (mode == HrSmoothingMode.RAW) {
            val tol = (HrConfig.RAW_TOLERANCE_S * 1000).toLong()
            return valid.filter { abs(it.tsMillis - atMillis) <= tol }.minByOrNull { abs(it.tsMillis - atMillis) }?.bpm?.toDouble()
        }
        val n = (windowS(mode) * 1000).toLong()
        return if (centered) meanIn(valid, atMillis - n / 2, atMillis + n / 2, true) else meanIn(valid, atMillis - n, atMillis, false)
    }

    /**
     * One point per input sample with a centered window. An invalid sample (0, out of range, isolated spike) is a gap (null)
     * in every mode; RAW keeps a valid sample's own value.
     */
    fun series(samples: List<HrPoint>, mode: HrSmoothingMode): List<SmoothedPoint> {
        val valid = validSamples(samples)
        val validSet = valid.toHashSet()
        val half = (windowS(mode) * 1000).toLong() / 2
        return samples.map { p ->
            when {
                p !in validSet -> SmoothedPoint(p.tsMillis, null)
                mode == HrSmoothingMode.RAW -> SmoothedPoint(p.tsMillis, p.bpm.toDouble())
                else -> SmoothedPoint(p.tsMillis, meanIn(valid, p.tsMillis - half, p.tsMillis + half, true))
            }
        }
    }

    /** True when the time between consecutive samples exceeds GAP_BREAK_S (charts break the line). */
    fun isGap(prevTsMillis: Long, nextTsMillis: Long): Boolean = (nextTsMillis - prevTsMillis) / 1000.0 > HrConfig.GAP_BREAK_S
}
