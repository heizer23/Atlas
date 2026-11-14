package net.linspad.atlasphone.running.cadence

import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sqrt

/** CAD1 constants: same names and values as the backend CAD_* constants (parity: tests/fixtures/cadence_golden.json). */
object CadenceConfig {
    const val MIN_SPM = 100.0
    const val MAX_SPM = 230.0
    const val WINDOW_N = 8
    const val MIN_INTERVALS = 4
    const val NORMAL_TOL = 0.25
    const val MISSED_TOL = 0.15
    const val GAP_FACTOR = 2.5
    const val GAP_S = 2.0
    const val REANCHOR_IRREGULAR = 6
    const val SERIES_STEP_S = 5.0
    const val PROFILE_MIN_CONF = 0.3
    const val PROFILE_MAX_AGE_S = 5.0
    const val PROGRESS_BUCKET_M = 20.0
    // phone only
    const val LIVE_LOOKBACK_S = 30.0
    const val STEP_MAX_REPORT_LATENCY_MS = 1000L
}

/** One non-null series point (gaps are absent, never zero). */
data class CadencePoint(val tSeconds: Double, val spm: Double, val conf: Double)

/**
 * Pure Kotlin mirror of backend/cadence.py (CAD1 in 10_architecture.json). The server value is authoritative; this runs
 * for the live display and the golden tests. Times are float seconds since the run start so both sides see equal numbers.
 * [pausesMillis] ranges are inclusive: pass `a until b` for a pause [a, b).
 */
object CadenceEstimator {
    private class State(val m: Double, val conf: Double)
    private class Snap(val eventS: Double, val state: State?)

    private fun median(values: List<Double>): Double {
        val v = values.sorted(); val n = v.size
        return if (n % 2 == 1) v[n / 2] else (v[n / 2 - 1] + v[n / 2]) / 2.0
    }

    /** Same as Python round(x, digits): exact decimal value of the double, half-even. */
    private fun r(x: Double, digits: Int): Double =
        java.math.BigDecimal(x).setScale(digits, java.math.RoundingMode.HALF_EVEN).toDouble()

    /** Steps 2-4 for one pause-free segment (sorted, distinct seconds). */
    private fun snapshots(steps: List<Double>): List<Snap> {
        val snaps = ArrayList<Snap>()
        val window = ArrayDeque<Pair<Double, Boolean>>()
        var irregular = 0
        var prevNormal = false
        val lo = 60.0 / CadenceConfig.MAX_SPM
        val hi = 60.0 / CadenceConfig.MIN_SPM
        fun add(v: Double, corrected: Boolean) { window.addLast(v to corrected); while (window.size > CadenceConfig.WINDOW_N) window.removeFirst() }
        fun medianM(): Double? = if (window.size >= CadenceConfig.MIN_INTERVALS) median(window.map { it.first }) else null

        for (i in 1 until steps.size - 1) {
            val d = steps[i] - steps[i - 1]
            val dNext = steps[i + 1] - steps[i]
            val m = medianM()
            if (d > CadenceConfig.GAP_S || (m != null && d > CadenceConfig.GAP_FACTOR * m)) {
                window.clear(); irregular = 0; prevNormal = false
            } else if (m == null) {
                if (d >= lo && d <= hi) { add(d, false); irregular = 0; prevNormal = true } else { irregular++; prevNormal = false }
            } else if (abs(d - m) <= CadenceConfig.NORMAL_TOL * m) {
                add(d, false); irregular = 0; prevNormal = true
            } else if (prevNormal && abs(d - 2 * m) <= CadenceConfig.MISSED_TOL * 2 * m && abs(dNext - m) <= CadenceConfig.NORMAL_TOL * m) {
                add(d / 2.0, true); add(d / 2.0, true); irregular = 0; prevNormal = false
            } else {
                irregular++; prevNormal = false
            }
            if (irregular >= CadenceConfig.REANCHOR_IRREGULAR) { window.clear(); irregular = 0 }
            val mm = medianM()
            if (mm == null) { snaps.add(Snap(steps[i + 1], null)); continue }
            val vals = window.map { it.first }
            val mean = vals.sum() / vals.size
            val cv = sqrt(vals.sumOf { (it - mean) * (it - mean) } / vals.size) / mean
            val corrected = window.count { it.second }.toDouble() / window.size
            snaps.add(Snap(steps[i + 1], State(mm, max(0.0, min(1.0, 1.0 - 2.0 * cv)) * (1.0 - 0.5 * corrected))))
        }
        return snaps
    }

    /** Segments of kept steps (step 1) with their snapshots. */
    private class Model(val segments: Map<Int, List<Double>>, val snaps: Map<Int, List<Snap>>, val pauses: List<LongRange>, val startMillis: Long) {
        fun segmentOf(ms: Long) = pauses.count { it.last + 1 <= ms }
        fun inPause(ms: Long) = pauses.any { ms in it }

        fun valueAt(tauMs: Long): CadencePoint? {
            if (inPause(tauMs)) return null
            val seg = segmentOf(tauMs)
            val steps = segments[seg] ?: return null
            val t = (tauMs - startMillis) / 1000.0
            val newest = steps.lastOrNull { it <= t } ?: return null
            if (t - newest > CadenceConfig.GAP_S) return null
            val s = snaps[seg]!!.lastOrNull { it.eventS <= t }?.state ?: return null
            return CadencePoint(t, r(60.0 / s.m, 1), r(s.conf, 2))
        }
    }

    private fun model(stepMillis: List<Long>, pauses: List<LongRange>, startMillis: Long, endMillis: Long): Model {
        val ps = pauses.sortedBy { it.first }
        val kept = stepMillis.filter { it in startMillis..endMillis && ps.none { p -> it in p } }.distinct().sorted()
        val segs = LinkedHashMap<Int, MutableList<Double>>()
        for (ms in kept) segs.getOrPut(ps.count { it.last + 1 <= ms }) { ArrayList() }.add((ms - startMillis) / 1000.0)
        return Model(segs, segs.mapValues { snapshots(it.value) }, ps, startMillis)
    }

    /** CAD1 series on the same grid and rounding as the server (t = k * SERIES_STEP_S since [startMillis]). */
    fun series(stepMillis: List<Long>, pausesMillis: List<LongRange>, startMillis: Long, endMillis: Long): List<CadencePoint> {
        val model = model(stepMillis, pausesMillis, startMillis, endMillis)
        val out = ArrayList<CadencePoint>()
        var k = 0
        while (k * CadenceConfig.SERIES_STEP_S <= (endMillis - startMillis) / 1000.0) {
            val tMs = startMillis + (k * CadenceConfig.SERIES_STEP_S * 1000).toLong()
            model.valueAt(tMs)?.let { out.add(CadencePoint(k * CadenceConfig.SERIES_STEP_S, it.spm, it.conf)) }
            k++
        }
        return out
    }

    /** CAD1 at one instant from the given (recent) steps; null = gap / warm-up. Live use passes the last LIVE_LOOKBACK_S of steps. */
    fun at(stepMillis: List<Long>, pausesMillis: List<LongRange>, atMillis: Long): CadencePoint? {
        val relevant = stepMillis.filter { it <= atMillis }
        if (relevant.isEmpty()) return null
        return model(relevant, pausesMillis, relevant.min(), atMillis).valueAt(atMillis)
    }
}
