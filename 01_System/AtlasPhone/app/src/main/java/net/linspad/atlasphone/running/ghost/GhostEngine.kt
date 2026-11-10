package net.linspad.atlasphone.running.ghost

import net.linspad.atlasphone.running.PauseRecord
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.hypot
import kotlin.math.max
import kotlin.math.min

/**
 * Ghost engine, pure Kotlin, no I/O. Same definitions and constants as `backend/ghost.py` (PROGRESS_ALGO_VERSION 1);
 * parity is enforced by `ghost_golden.json` (comparison) and `ghost_progress_golden.json` (route progress), asserted by
 * pytest and by GhostEngineTest.
 *
 * - Progress: metres ALONG the reference route, not GPS-travelled distance.
 * - Time basis: MOVING time (seconds since start minus manual pauses).
 * - Sign convention: timeGapS = myT - ghostT(at my progress), NEGATIVE = ahead.
 *   leadM = myS - ghostS(at my time), POSITIVE = ahead. Unknown values are null, never fabricated.
 */
object GhostConfig {
    const val MAX_SPEED_MPS = 12.0
    const val OFF_COURSE_M = 50.0
    const val BACK_TOLERANCE_M = 25.0
    const val FORWARD_SLACK_M = 40.0
    const val START_WINDOW_M = 250.0
    const val ACCURACY_MAX_M = 30.0
    /** Live-only (not in the Python reference): this many unmatched fixes in a row suspend the comparison. */
    const val SUSPEND_AFTER_OFF_COURSE = 3
    /** Live-only: no matched fix for this long means GPS is lost and the comparison is suspended. */
    const val GPS_LOST_MS = 10_000L
}

private const val METRES_PER_DEG = PI / 180.0 * 6_371_000.0

class Projection(val progressM: Double, val distanceM: Double)

/** Projects (lat, lon) onto the route polyline in a local flat plane, restricted to a progress window. */
class RouteProjector(points: List<RoutePoint>) {
    private val cum = DoubleArray(points.size) { points[it].cumM }
    private val lat0 = Math.toRadians(points[0].lat)
    private val xs = DoubleArray(points.size) { points[it].lon * METRES_PER_DEG * cos(lat0) }
    private val ys = DoubleArray(points.size) { points[it].lat * METRES_PER_DEG }
    val length: Double = cum.last()

    private fun firstAtLeast(v: Double): Int {
        var lo = 0; var hi = cum.size
        while (lo < hi) { val mid = (lo + hi) ushr 1; if (cum[mid] < v) lo = mid + 1 else hi = mid }
        return lo
    }

    fun project(lat: Double, lon: Double, sLo: Double, sHi: Double): Projection? {
        val px = lon * METRES_PER_DEG * cos(lat0)
        val py = lat * METRES_PER_DEG
        var best: Projection? = null
        var i = max(0, firstAtLeast(sLo) - 1)
        while (i < cum.size - 1) {
            if (cum[i] > sHi) break
            val ax = xs[i]; val ay = ys[i]
            val dx = xs[i + 1] - ax; val dy = ys[i + 1] - ay
            val seg2 = dx * dx + dy * dy
            val segLen = cum[i + 1] - cum[i]
            // Only the part of the segment inside the progress window is a candidate (a fix far ahead is never snapped).
            val uLo = if (segLen <= 0) 0.0 else max(0.0, (sLo - cum[i]) / segLen)
            val uHi = if (segLen <= 0) 1.0 else min(1.0, (sHi - cum[i]) / segLen)
            if (uLo <= uHi) {
                var u = if (seg2 == 0.0) 0.0 else ((px - ax) * dx + (py - ay) * dy) / seg2
                u = max(uLo, min(uHi, u))
                val d = hypot(px - (ax + u * dx), py - (ay + u * dy))
                if (best == null || d < best.distanceM) best = Projection(cum[i] + u * segLen, d)
            }
            i++
        }
        return best
    }
}

/** Moving time = seconds since start minus completed manual pauses; fixes inside a pause have no moving time. */
class MovingClock(private val startedAtMillis: Long) {
    fun inPause(tsMillis: Long, pauses: List<PauseRecord>) =
        pauses.any { tsMillis >= it.startedAtMillis && (it.endedAtMillis == null || tsMillis < it.endedAtMillis) }

    fun movingS(tsMillis: Long, pauses: List<PauseRecord>): Double {
        val paused = pauses.filter { it.endedAtMillis != null && it.endedAtMillis <= tsMillis }
            .sumOf { (it.endedAtMillis!! - it.startedAtMillis) / 1000.0 }
        return (tsMillis - startedAtMillis) / 1000.0 - paused
    }
}

sealed interface Match {
    data class Matched(val movingS: Double, val progressM: Double) : Match
    data object OffCourse : Match
    /** Not used for progress (poor accuracy). */
    data object Ignored : Match
}

/** Streaming route matching with movement continuity (monotonic progress, window limited by plausible speed). */
class ProgressTracker(private val projector: RouteProjector) {
    var lastProgressM: Double? = null; private set
    var lastMovingS: Double? = null; private set
    var matched = 0; private set
    var offCourse = 0; private set
    var consecutiveOffCourse = 0; private set

    val referenceLengthM: Double get() = projector.length

    fun addFix(movingS: Double, lat: Double, lon: Double, accuracyM: Double?): Match {
        if (accuracyM != null && accuracyM > GhostConfig.ACCURACY_MAX_M) return Match.Ignored
        val prevS = lastProgressM
        val window = if (prevS == null) 0.0 to GhostConfig.START_WINDOW_M else {
            val dt = max(0.0, movingS - (lastMovingS ?: movingS))
            max(0.0, prevS - GhostConfig.BACK_TOLERANCE_M) to min(projector.length, prevS + GhostConfig.MAX_SPEED_MPS * dt + GhostConfig.FORWARD_SLACK_M)
        }
        val hit = projector.project(lat, lon, window.first, window.second)
        if (hit == null || hit.distanceM > GhostConfig.OFF_COURSE_M) {
            offCourse++; consecutiveOffCourse++
            return Match.OffCourse
        }
        val s = if (prevS == null) hit.progressM else max(prevS, hit.progressM) // progress never goes backwards
        matched++; consecutiveOffCourse = 0
        lastProgressM = s; lastMovingS = movingS
        return Match.Matched(movingS, s)
    }
}

/** The four live values plus context. Everything the ghost cannot answer is null. */
data class GhostReading(
    val timeGapS: Double?,
    val leadM: Double?,
    val ghostHrAtPosition: Double?,
    val ghostHrAtTime: Double?,
    val ghostFinished: Boolean,
    /** Where the ghost is on the route now (metres along the route); the end of the route once it has finished. */
    val ghostProgressM: Double? = null,
)

object GhostComparison {
    private fun bisectLeft(xs: List<Double>, x: Double): Int {
        var lo = 0; var hi = xs.size
        while (lo < hi) { val mid = (lo + hi) ushr 1; if (xs[mid] < x) lo = mid + 1 else hi = mid }
        return lo
    }

    private fun interp(xs: List<Double>, ys: List<Double?>, x: Double): Double? {
        if (xs.isEmpty() || x < xs.first() || x > xs.last()) return null
        val i = bisectLeft(xs, x)
        if (xs[i] == x) return ys[i]
        val y0 = ys[i - 1]; val y1 = ys[i]
        if (y0 == null || y1 == null) return null
        return y0 + (y1 - y0) * (x - xs[i - 1]) / (xs[i] - xs[i - 1])
    }

    fun timeAtProgress(p: GhostProfile, s: Double): Double? {
        val ss = p.points.map { it.s }
        if (s < ss.first() || s > ss.last()) return null
        val i = bisectLeft(ss, s)
        if (ss[i] == s) return p.points[i].t // flat parts: earliest time
        val a = p.points[i - 1]; val b = p.points[i]
        return a.t + (b.t - a.t) * (s - a.s) / (b.s - a.s)
    }

    fun progressAtTime(p: GhostProfile, t: Double): Double? = interp(p.points.map { it.t }, p.points.map { it.s }, t)
    fun hrAtTime(p: GhostProfile, t: Double): Double? = interp(p.points.map { it.t }, p.points.map { it.hr }, t)
    fun hrAtProgress(p: GhostProfile, s: Double): Double? = timeAtProgress(p, s)?.let { hrAtTime(p, it) }

    fun compare(p: GhostProfile, myT: Double, myS: Double): GhostReading {
        val last = p.points.last()
        val finished = myT > last.t
        val ghostT = timeAtProgress(p, myS)
        val ghostS = if (finished) last.s else progressAtTime(p, myT) // a finished ghost stays at the end
        return GhostReading(
            timeGapS = ghostT?.let { myT - it },
            leadM = ghostS?.let { myS - it },
            ghostHrAtPosition = hrAtProgress(p, myS),
            ghostHrAtTime = hrAtTime(p, myT),
            ghostFinished = finished,
            ghostProgressM = ghostS,
        )
    }
}

enum class GhostStatus {
    /** No fix matched the route start yet: go to the start of the route. */
    WAITING_FOR_START,
    ON_COURSE,
    /** Several fixes in a row are away from the route: comparison suspended instead of showing a false gap. */
    OFF_COURSE,
    /** No usable fix for a while: comparison suspended. */
    GPS_LOST,
}

/** What the screen renders. [reading] is non-null only while [status] is ON_COURSE. */
data class GhostLive(
    val status: GhostStatus, val routeName: String, val reading: GhostReading?, val progressM: Double?, val routeLengthM: Double,
    /** The route polyline for the local map (shared, not copied). */
    val route: List<RoutePoint> = emptyList(),
)

/**
 * One ghost race: feeds fixes through the tracker using the run's moving clock and answers the live comparison from the
 * last matched fix (so values are exact for that fix, at most about a second old). Fixes inside a manual pause are ignored.
 */
class GhostSession(
    private val route: RouteGeometry,
    private val profile: GhostProfile,
    startedAtMillis: Long,
) {
    private val tracker = ProgressTracker(RouteProjector(route.points))
    private val clock = MovingClock(startedAtMillis)
    private var lastFixMillis: Long? = null

    fun addFix(tsMillis: Long, lat: Double, lon: Double, accuracyM: Double?, pauses: List<PauseRecord>) {
        if (clock.inPause(tsMillis, pauses)) return
        lastFixMillis = tsMillis
        tracker.addFix(clock.movingS(tsMillis, pauses), lat, lon, accuracyM)
    }

    fun snapshot(nowMillis: Long): GhostLive {
        val s = tracker.lastProgressM; val t = tracker.lastMovingS
        val len = route.referenceDistanceM
        if (s == null || t == null) return GhostLive(GhostStatus.WAITING_FOR_START, route.name, null, null, len, route.points)
        if (tracker.consecutiveOffCourse >= GhostConfig.SUSPEND_AFTER_OFF_COURSE) return GhostLive(GhostStatus.OFF_COURSE, route.name, null, s, len, route.points)
        val seen = lastFixMillis
        if (seen == null || nowMillis - seen > GhostConfig.GPS_LOST_MS) return GhostLive(GhostStatus.GPS_LOST, route.name, null, s, len, route.points)
        return GhostLive(GhostStatus.ON_COURSE, route.name, GhostComparison.compare(profile, t, s), s, len, route.points)
    }
}
