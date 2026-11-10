package net.linspad.atlasphone.running.metrics

import net.linspad.atlasphone.mobile.model.RawHeartRate
import net.linspad.atlasphone.mobile.model.RawLocation
import net.linspad.atlasphone.running.PauseRecord
import net.linspad.atlasphone.running.RunSummary
import kotlin.math.asin
import kotlin.math.cos
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sin
import kotlin.math.sqrt

/**
 * Algorithm A1 (algo_version 1), pure Kotlin. Same steps and constants as backend/metrics.py and backend/config.py;
 * parity is enforced by 03_Application/RunningTracker/tests/fixtures/metrics_golden.json (RunMetricsTest).
 * Raw samples are never modified. Step numbers refer to invariant A1 in 10_architecture.json.
 */
object A1 {
    const val ACCURACY_MAX_M = 30.0
    const val MIN_STEP_M = 1.0
    const val MAX_SPEED_MPS = 12.0
    const val SMOOTHING_WINDOW_S = 10.0
    const val SPLIT_DISTANCE_M = 1000.0
    const val PARTIAL_SPLIT_MIN_M = 10.0
    const val EARTH_RADIUS_M = 6_371_000.0
    /** Live display only (not part of A1): a pace older than this is not shown. */
    const val LIVE_PACE_STALE_MS = 15_000L
    /** Live display only: a heart rate older than this is "no signal", not the last value. */
    const val LIVE_HR_STALE_MS = 10_000L
    /** Live display only: window and minimum span of the rolling average pace. */
    const val ROLLING_PACE_WINDOW_S = 120.0
    const val ROLLING_PACE_MIN_S = 20.0
    const val ROLLING_PACE_MIN_M = 20.0
}

data class SplitInfo(
    val km: Int,
    val distanceM: Double,
    val durationS: Double,
    val paceSPerKm: Double,
    val avgHr: Double?,
    val partial: Boolean,
)

/** Values shown while recording. */
data class LiveMetrics(
    val distanceM: Double,
    val currentPaceSPerKm: Double?,
    val avgPaceSPerKm: Double?,
    val movingS: Double,
    val elapsedS: Double,
    val currentHr: Int?,
    val avgHr: Double?,
    val lastAccuracyM: Float?,
    /** Average pace over the last 2 minutes of moving time (live display only). */
    val rollingPaceSPerKm: Double? = null,
)

fun haversineM(lat1: Double, lon1: Double, lat2: Double, lon2: Double): Double {
    val p1 = Math.toRadians(lat1)
    val p2 = Math.toRadians(lat2)
    val dPhi = p2 - p1
    val dLambda = Math.toRadians(lon2 - lon1)
    val a = sin(dPhi / 2) * sin(dPhi / 2) + cos(p1) * cos(p2) * sin(dLambda / 2) * sin(dLambda / 2)
    return 2 * A1.EARTH_RADIUS_M * asin(min(1.0, sqrt(a)))
}

/**
 * Streaming form of A1 for the live screen; [RunMetrics.summarize] feeds the same accumulator from stored samples.
 * Pauses are a list of intervals [start, end) (the last one may be open): fixes inside are ignored, the first usable fix
 * after a pause is a new anchor and adds no distance.
 */
class RunMetricsAccumulator(private val startedAtMillis: Long, initialPauses: List<PauseRecord> = emptyList()) {
    private class Point(val moving: Double, val dist: Double, val segment: Int, val tsMillis: Long)
    private class Anchor(val lat: Double, val lon: Double, val tsMillis: Long, val nanos: Long?, val segment: Int)

    private val pauses = initialPauses.toMutableList()
    private val points = ArrayList<Point>()
    private val hr = ArrayList<Pair<Long, Int>>() // (timestamp, bpm) with bpm >= 1 outside pauses
    private var anchor: Anchor? = null
    private var distance = 0.0
    private var lastAccuracy: Float? = null
    private var hrSum = 0.0

    fun pause(atMillis: Long) {
        if (pauses.isNotEmpty() && pauses.last().endedAtMillis == null) return // already paused
        pauses.add(PauseRecord(atMillis, null, 0.0, null))
    }

    fun resume(atMillis: Long) {
        val last = pauses.lastOrNull() ?: return
        if (last.endedAtMillis == null) pauses[pauses.lastIndex] = last.copy(endedAtMillis = atMillis)
    }

    private fun inPause(ts: Long) = pauses.any { ts >= it.startedAtMillis && (it.endedAtMillis == null || ts < it.endedAtMillis) }
    private fun segmentOf(ts: Long) = pauses.count { it.endedAtMillis != null && it.endedAtMillis <= ts }
    private fun movingOf(ts: Long): Double {
        val paused = pauses.filter { it.endedAtMillis != null && it.endedAtMillis <= ts }.sumOf { (it.endedAtMillis!! - it.startedAtMillis) / 1000.0 }
        return (ts - startedAtMillis) / 1000.0 - paused
    }

    /** A1 steps 1-3 for one fix (ignored while paused). */
    fun addFix(fix: RawLocation) {
        lastAccuracy = fix.accuracyMeters
        val acc = fix.accuracyMeters ?: return
        if (acc.toDouble() > A1.ACCURACY_MAX_M) return
        val ts = fix.timestampMillis
        if (inPause(ts)) return
        val seg = segmentOf(ts)
        val a = anchor
        if (a == null || a.segment != seg) {
            anchor = Anchor(fix.latitude, fix.longitude, ts, fix.elapsedRealtimeNanos, seg)
            points.add(Point(movingOf(ts), distance, seg, ts))
            return
        }
        val d = haversineM(a.lat, a.lon, fix.latitude, fix.longitude)
        if (d < A1.MIN_STEP_M) return
        val nanos = fix.elapsedRealtimeNanos
        val dt = if (nanos != null && a.nanos != null && nanos - a.nanos > 0) (nanos - a.nanos) / 1e9 else (ts - a.tsMillis) / 1000.0
        if (dt <= 0 || d / dt > A1.MAX_SPEED_MPS) return
        distance += d
        anchor = Anchor(fix.latitude, fix.longitude, ts, nanos, seg)
        points.add(Point(movingOf(ts), distance, seg, ts))
    }

    /** A1 step 7 input: heart rate outside pauses, bpm >= 1. */
    fun addHeartRate(sample: RawHeartRate) {
        if (sample.bpm < 1 || inPause(sample.timestampMillis)) return
        hr.add(sample.timestampMillis to sample.bpm)
        hrSum += sample.bpm
    }

    val distanceM: Double get() = distance
    val avgHr: Double? get() = if (hr.isEmpty()) null else hrSum / hr.size

    /** A1 step 5 at accepted point [i]. */
    private fun paceAt(i: Int): Double? {
        val p = points[i]
        val threshold = p.moving - A1.SMOOTHING_WINDOW_S
        var lo = i
        while (lo > 0 && points[lo - 1].segment == p.segment && points[lo - 1].moving >= threshold) lo--
        if (lo >= i) return null
        val q = points[lo]
        return if (p.dist - q.dist >= 1.0) (p.moving - q.moving) / (p.dist - q.dist) * 1000.0 else null
    }

    /** Average pace over the last [A1.ROLLING_PACE_WINDOW_S] of moving time ending at the newest accepted point. */
    private fun rollingPace(): Double? {
        val last = points.lastOrNull() ?: return null
        val threshold = last.moving - A1.ROLLING_PACE_WINDOW_S
        var lo = points.lastIndex
        while (lo > 0 && points[lo - 1].moving >= threshold) lo--
        val first = points[lo]
        val dt = last.moving - first.moving; val dd = last.dist - first.dist
        return if (dt >= A1.ROLLING_PACE_MIN_S && dd >= A1.ROLLING_PACE_MIN_M) dt / dd * 1000.0 else null
    }

    fun snapshot(nowMillis: Long): LiveMetrics {
        val elapsed = max(0.0, (nowMillis - startedAtMillis) / 1000.0)
        val paused = pauses.sumOf { p ->
            val end = min(p.endedAtMillis ?: nowMillis, nowMillis)
            max(0L, end - p.startedAtMillis) / 1000.0
        }
        val moving = max(0.0, elapsed - paused)
        val openPause = pauses.lastOrNull()?.endedAtMillis == null && pauses.isNotEmpty()
        val last = points.lastOrNull()
        val fresh = !(last == null || openPause || nowMillis - last.tsMillis > A1.LIVE_PACE_STALE_MS)
        val current = if (fresh) paceAt(points.lastIndex) else null
        val rolling = if (fresh) rollingPace() else null
        val lastHr = hr.lastOrNull()?.takeIf { nowMillis - it.first <= A1.LIVE_HR_STALE_MS }
        return LiveMetrics(
            distanceM = distance, currentPaceSPerKm = current,
            avgPaceSPerKm = if (distance > 0 && moving > 0) moving / (distance / 1000.0) else null,
            movingS = moving, elapsedS = elapsed, currentHr = lastHr?.second, avgHr = avgHr, lastAccuracyM = lastAccuracy, rollingPaceSPerKm = rolling,
        )
    }

    /** A1 step 6: per-km splits plus a final partial split (>= 10 m). */
    fun splits(): List<SplitInfo> {
        if (points.isEmpty()) return emptyList()
        fun splitHr(t0: Double, t1: Double, inclusiveEnd: Boolean): Double? {
            val vals = hr.filter { (ts, _) ->
                val m = movingOf(ts)
                m >= t0 && (if (inclusiveEnd) m <= t1 else m < t1)
            }.map { it.second }
            return if (vals.isEmpty()) null else vals.sum().toDouble() / vals.size
        }
        val out = ArrayList<SplitInfo>()
        var tPrev = points[0].moving
        var k = 1
        for (i in 0 until points.size - 1) {
            val a = points[i]
            val b = points[i + 1]
            while (b.dist > a.dist && a.dist < k * A1.SPLIT_DISTANCE_M && k * A1.SPLIT_DISTANCE_M <= b.dist) {
                val tCross = a.moving + (k * A1.SPLIT_DISTANCE_M - a.dist) / (b.dist - a.dist) * (b.moving - a.moving)
                val duration = tCross - tPrev
                out.add(SplitInfo(k, A1.SPLIT_DISTANCE_M, duration, duration, splitHr(tPrev, tCross, false), false))
                tPrev = tCross
                k++
            }
        }
        val remainder = distance - (k - 1) * A1.SPLIT_DISTANCE_M
        if (remainder >= A1.PARTIAL_SPLIT_MIN_M) {
            val tEnd = points.last().moving
            val duration = tEnd - tPrev
            out.add(SplitInfo(k, remainder, duration, duration / remainder * 1000.0, splitHr(tPrev, tEnd, true), true))
        }
        return out
    }
}

object RunMetrics {
    private fun replay(
        locations: List<RawLocation>, heartRates: List<RawHeartRate>, pauses: List<PauseRecord>,
        originMillis: Long, closeOpenPausesAt: Long?,
    ): RunMetricsAccumulator {
        val closed = pauses.map { if (it.endedAtMillis == null && closeOpenPausesAt != null) it.copy(endedAtMillis = closeOpenPausesAt) else it }
        return RunMetricsAccumulator(originMillis, closed).also { acc ->
            locations.forEach(acc::addFix)
            heartRates.forEach(acc::addHeartRate)
        }
    }

    /**
     * Batch A1 for finish and recovery: rebuilds the state from stored samples (in sequence order).
     * Elapsed/moving here come from wall timestamps; the controller replaces them with monotonic durations when it has them.
     */
    fun summarize(
        locations: List<RawLocation>, heartRates: List<RawHeartRate>, pauses: List<PauseRecord>,
        startedAtMillis: Long, finishedAtMillis: Long,
    ): RunSummary {
        val acc = replay(locations, heartRates, pauses, startedAtMillis, finishedAtMillis)
        val elapsed = max(0.0, (finishedAtMillis - startedAtMillis) / 1000.0)
        val paused = pauses.sumOf { p ->
            val end = min(p.endedAtMillis ?: finishedAtMillis, finishedAtMillis)
            max(0L, end - p.startedAtMillis) / 1000.0
        }
        val moving = max(0.0, elapsed - paused)
        val d = acc.distanceM
        return RunSummary(elapsed, moving, d, if (d > 0 && moving > 0) moving / (d / 1000.0) else null, acc.avgHr)
    }

    /** Per-km splits; the moving-time origin is the first fix (only differences matter). */
    fun splits(locations: List<RawLocation>, heartRates: List<RawHeartRate>, pauses: List<PauseRecord>): List<SplitInfo> {
        val origin = locations.firstOrNull()?.timestampMillis ?: return emptyList()
        return replay(locations, heartRates, pauses, origin, null).splits()
    }
}
