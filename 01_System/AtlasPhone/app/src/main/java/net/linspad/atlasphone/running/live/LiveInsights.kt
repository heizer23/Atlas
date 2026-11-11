package net.linspad.atlasphone.running.live

import net.linspad.atlasphone.running.ghost.FieldMarker
import net.linspad.atlasphone.running.ghost.RoutePoint
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.atan2
import kotlin.math.exp
import kotlin.math.sin
import kotlin.math.cos
import kotlin.math.hypot
import kotlin.math.max
import kotlin.math.min

/**
 * Pure live-cockpit logic (no Android, no I/O): HR target zones, run category, ghost-gap momentum, smoothed pace and
 * history, and the local map model. Display-only: nothing here changes the recorded data or the A1 / ghost algorithms.
 */

// ── Target heart rate ────────────────────────────────────────────────────────

enum class HrZone { NO_SIGNAL, BELOW, NEAR, ABOVE }

object HrTarget {
    const val TOLERANCE_BPM = 5
    const val DEFAULT_BPM = 140
    const val MIN_BPM = 80
    const val MAX_BPM = 200

    /** NEAR = within ±[TOLERANCE_BPM] of the target. No signal (or no target) is its own state, never "near". */
    fun zone(hr: Int?, target: Int?): HrZone = when {
        hr == null || target == null -> HrZone.NO_SIGNAL
        hr < target - TOLERANCE_BPM -> HrZone.BELOW
        hr > target + TOLERANCE_BPM -> HrZone.ABOVE
        else -> HrZone.NEAR
    }

    /** Equivalent-effort category, e.g. "4 km · HR 140" (route length rounded to 0.5 km) or "HR 140" without a route. */
    fun category(targetBpm: Int?, routeDistanceM: Double?): String? {
        if (targetBpm == null) return null
        val hr = "HR $targetBpm"
        if (routeDistanceM == null || routeDistanceM <= 0) return hr
        val halfKm = Math.round(routeDistanceM / 500.0) / 2.0
        if (halfKm <= 0) return hr
        val km = if (halfKm % 1.0 == 0.0) "%d km".format(halfKm.toLong()) else "%.1f km".format(halfKm)
        return "$km · $hr"
    }
}

// ── Time series with a bounded history ───────────────────────────────────────

/** (x, y) samples, x non-decreasing; keeps at most [capacity] newest samples. */
class Series(private val capacity: Int = 900) {
    private val xs = ArrayList<Double>()
    private val ys = ArrayList<Double>()
    val size: Int get() = xs.size

    fun add(x: Double, y: Double) {
        if (xs.isNotEmpty() && x < xs.last()) return
        xs.add(x); ys.add(y)
        if (xs.size > capacity) { xs.removeAt(0); ys.removeAt(0) }
    }

    fun points(): List<Pair<Double, Double>> = xs.indices.map { xs[it] to ys[it] }
    fun lastX(): Double? = xs.lastOrNull()
    fun lastY(): Double? = ys.lastOrNull()

    /** Newest y whose x is at most [x]; null when the history does not reach back that far. */
    fun yAtOrBefore(x: Double): Double? {
        var best: Double? = null
        for (i in xs.indices) { if (xs[i] <= x) best = ys[i] else break }
        return best
    }
}

/**
 * Ghost lead history. The lead is metres ahead (+) / behind (-) at the same elapsed time. Momentum is how the lead
 * changed over the last [WINDOW_M] metres of route progress: positive = lead growing, negative = gap closing.
 */
class GapMomentum {
    private val byProgress = Series(1800)
    private val byTime = Series(1800)

    fun add(movingS: Double, progressM: Double, leadM: Double) {
        byProgress.add(progressM, leadM)
        byTime.add(movingS, leadM)
    }

    /** Lead change over the last 100 m; null until the runner has covered 100 m on the route since the first sample. */
    fun changeOver100m(): Double? {
        val s = byProgress.lastX() ?: return null
        val now = byProgress.lastY() ?: return null
        val then = byProgress.yAtOrBefore(s - WINDOW_M) ?: return null
        return now - then
    }

    /** The lead as it was about [SECONDS_BACK] s ago (for "50 m ahead → 45 m ahead"); null while the history is shorter. */
    fun leadSecondsAgo(): Double? {
        val t = byTime.lastX() ?: return null
        return byTime.yAtOrBefore(t - SECONDS_BACK)
    }

    companion object {
        const val WINDOW_M = 100.0
        const val SECONDS_BACK = 10.0
    }
}

/** Lead text for one value: "50 m ahead" / "12 m behind" / "level". */
fun leadText(leadM: Double): String {
    val m = Math.round(Math.abs(leadM))
    return if (m == 0L) "level" else if (leadM > 0) "$m m ahead" else "$m m behind"
}

/** "50 m ahead → 45 m ahead" once the rounded value changed since [previousM]; otherwise just the current text. */
fun leadTransition(previousM: Double?, nowM: Double): String {
    val now = leadText(nowM)
    if (previousM == null) return now
    val before = leadText(previousM)
    return if (before == now) now else "$before → $now"
}

enum class Trend { CLOSING, WIDENING, STEADY }

/** Closing/widening for the lead change over 100 m, with a ±[STEADY_M] m dead band so GPS noise does not flip it. */
fun trendOf(changeOver100m: Double?, aheadNow: Boolean): Trend? {
    val c = changeOver100m ?: return null
    if (Math.abs(c) <= STEADY_M) return Trend.STEADY
    // Lead is signed (+ ahead). A growing lead is "widening" for the runner who is ahead and "closing" when behind.
    val leadGrows = c > 0
    return if (leadGrows == aheadNow) Trend.WIDENING else Trend.CLOSING
}

const val STEADY_M = 2.0

// ── Pace smoothing ───────────────────────────────────────────────────────────

/** Exponential smoothing of the live pace (s/km) on top of the A1 10 s window; a gap in the data restarts it. */
class PaceSmoother(private val alpha: Double = 0.3) {
    private var value: Double? = null
    fun update(raw: Double?): Double? {
        if (raw == null || raw.isNaN() || raw.isInfinite()) { value = null; return null }
        val prev = value
        val next = if (prev == null) raw else prev + alpha * (raw - prev)
        value = next
        return next
    }
}

// ── Local map ────────────────────────────────────────────────────────────────

/** Metres to the right / up of the runner on the screen (the map is heading-up). */
data class MapXY(val east: Double, val north: Double)

/** A kilometre mark on the route ([km] = distance along the route, e.g. 3.0) at its screen position. */
class KmMark(val km: Double, val at: MapXY)

/**
 * Heading-up map model around the runner (runner at the origin). The screen is [radiusM] metres to either side of the
 * runner; [aheadM] / [behindM] are how far it reaches up / down (they depend on the screen aspect). [route] is the route
 * window, [markers] and [kmMarks] only what falls inside the screen: anything outside is not drawn.
 */
class LocalMapView(
    val route: List<MapXY>,
    val runner: MapXY,
    val markers: List<MapMarker>,
    val radiusM: Double,
    val aheadM: Double,
    val behindM: Double,
    val kmMarks: List<KmMark>,
)

/** A field runner on the map: [rank] by finishing time (the screen draws 1-9 as digits, others as dots). */
class MapMarker(val rank: Int, val at: MapXY, val isMain: Boolean)

object LocalMap {
    const val MIN_RADIUS_M = 120.0
    const val MAX_RADIUS_M = 400.0
    const val BEARING_LOOKAHEAD_M = 40.0
    /** The runner sits at 68% of the screen height: this share of the height is ahead of them, the rest behind. */
    private const val AHEAD_SHARE = 0.68
    /** Route metres drawn per screen metre (the route winds, so its length exceeds the straight distance). */
    private const val ROUTE_SLACK = 1.6
    /** Share of the half width / reach inside which a marker is drawn (keeps the marker body on screen). */
    private const val EDGE = 0.92
    /** The raced ghost may use this share of the reach before the map zooms out for it. */
    private const val COMFORT = 0.8

    private const val METRES_PER_DEG = PI / 180.0 * 6_371_000.0

    /** Interpolated position at [progressM] along the route. */
    fun pointAt(points: List<RoutePoint>, progressM: Double): RoutePoint {
        val s = progressM.coerceIn(points.first().cumM, points.last().cumM)
        var i = 1
        while (i < points.size - 1 && points[i].cumM < s) i++
        val a = points[i - 1]; val b = points[i]
        val len = b.cumM - a.cumM
        val u = if (len <= 0) 0.0 else ((s - a.cumM) / len).coerceIn(0.0, 1.0)
        return RoutePoint(a.lat + (b.lat - a.lat) * u, a.lon + (b.lon - a.lon) * u, s)
    }

    /** Direction of the route at [progressM], degrees clockwise from north (looks [BEARING_LOOKAHEAD_M] ahead, or back at the end). */
    fun routeBearingDeg(points: List<RoutePoint>, progressM: Double): Double {
        val end = points.last().cumM
        val (a, b) = if (progressM + BEARING_LOOKAHEAD_M <= end) pointAt(points, progressM) to pointAt(points, progressM + BEARING_LOOKAHEAD_M)
        else pointAt(points, end - BEARING_LOOKAHEAD_M) to pointAt(points, end)
        val d = xy(b, a, 0.0)
        return Math.toDegrees(atan2(d.east, d.north))
    }

    /** Metres east/north of [origin], rotated so that [headingDeg] (clockwise from north) points up on the screen. */
    private fun xy(p: RoutePoint, origin: RoutePoint, headingDeg: Double): MapXY {
        val k = cos(Math.toRadians(origin.lat))
        val e = (p.lon - origin.lon) * METRES_PER_DEG * k
        val n = (p.lat - origin.lat) * METRES_PER_DEG
        val h = Math.toRadians(headingDeg)
        return MapXY(e * cos(h) - n * sin(h), e * sin(h) + n * cos(h))
    }

    /**
     * [headingDeg]: the direction that points to the top of the map (0 = north up). [aspect] = screen height / width.
     * The zoom follows the raced ghost (it stays in view up to [MAX_RADIUS_M]); other runners simply drop off the screen.
     */
    fun build(points: List<RoutePoint>, runnerProgressM: Double, field: List<FieldMarker>, headingDeg: Double = 0.0, aspect: Double = 1.0): LocalMapView {
        val me = pointAt(points, runnerProgressM)
        val placed = field.map { it to xy(pointAt(points, it.progressM), me, headingDeg) }
        val main = placed.firstOrNull { it.first.isMain }?.second
        val radius = if (main == null) MIN_RADIUS_M else {
            val needed = max(
                abs(main.east) / COMFORT,
                if (main.north >= 0) main.north / (AHEAD_SHARE * 2 * aspect * COMFORT) else -main.north / ((1 - AHEAD_SHARE) * 2 * aspect * COMFORT),
            )
            min(MAX_RADIUS_M, max(MIN_RADIUS_M, needed))
        }
        val ahead = AHEAD_SHARE * 2 * aspect * radius
        val behind = (1 - AHEAD_SHARE) * 2 * aspect * radius
        fun inside(p: MapXY) = abs(p.east) <= radius * EDGE && p.north <= ahead * EDGE && p.north >= -behind * EDGE

        val from = runnerProgressM - behind * ROUTE_SLACK
        val to = runnerProgressM + ahead * ROUTE_SLACK
        // Vertices outside the window are replaced by interpolated end points so the line starts and ends cleanly.
        val line = ArrayList<MapXY>()
        line.add(xy(pointAt(points, from), me, headingDeg))
        points.filter { it.cumM > from && it.cumM < to }.forEach { line.add(xy(it, me, headingDeg)) }
        line.add(xy(pointAt(points, to), me, headingDeg))

        val markers = placed.filter { inside(it.second) }.map { MapMarker(it.first.rank, it.second, it.first.isMain) }
        val km = ArrayList<KmMark>()
        var k = Math.ceil(max(from, 1.0) / 1000.0).toInt()
        while (k * 1000.0 <= min(to, points.last().cumM)) {
            val at = xy(pointAt(points, k * 1000.0), me, headingDeg)
            if (inside(at)) km.add(KmMark(k.toDouble(), at))
            k++
        }
        return LocalMapView(line, MapXY(0.0, 0.0), markers, radius, ahead, behind, km)
    }
}

/** Heart rate along the route (x = progress metres) for the distance-aligned comparison graph. */
object HrByDistance {
    const val STEP_M = 20.0

    /** Folds (progress, bpm) points into [STEP_M] buckets (mean progress, mean bpm), ordered by progress. */
    class Accumulator {
        private val buckets = java.util.TreeMap<Int, DoubleArray>()      // index -> [sum s, sum hr, n]
        fun add(progressM: Double, bpm: Double) {
            val b = buckets.getOrPut((progressM / STEP_M).toInt()) { DoubleArray(3) }
            b[0] += progressM; b[1] += bpm; b[2] += 1.0
        }
        fun snapshot(): List<Pair<Double, Double>> = buckets.values.map { it[0] / it[2] to it[1] / it[2] }
    }

    fun bucket(points: List<Pair<Double, Double>>): List<Pair<Double, Double>> =
        Accumulator().also { acc -> points.forEach { acc.add(it.first, it.second) } }.snapshot()

    /** The bpm axis: [lo, hi] on multiples of 10 covering all values and [target], at least [MIN_SPAN] wide. */
    fun axis(values: List<Double>, target: Double?): Pair<Int, Int> {
        val all = values + listOfNotNull(target)
        if (all.isEmpty()) return 120 to 170
        var lo = Math.floor(all.min() / 10.0).toInt() * 10
        var hi = Math.ceil(all.max() / 10.0).toInt() * 10
        while (hi - lo < MIN_SPAN) { if (hi - lo < MIN_SPAN) hi += 10; if (hi - lo < MIN_SPAN) lo -= 10 }
        return lo to hi
    }
    const val MIN_SPAN = 40
}

/**
 * Slow low-pass on a compass angle so the rotating map does not jiggle. Moves along the shortest arc with time constant
 * [tauS] and ignores target changes smaller than [deadbandDeg]. [angleDeg] is continuous (not wrapped to 0..360), so it can
 * be animated without a jump when the heading crosses north.
 */
class HeadingSmoother(private val tauS: Double = 5.0, private val deadbandDeg: Double = 4.0) {
    var angleDeg: Double = 0.0; private set
    private var started = false

    fun update(targetDeg: Double, dtS: Double): Double {
        if (!started) { angleDeg = targetDeg; started = true; return angleDeg }
        var diff = (targetDeg - angleDeg) % 360.0
        if (diff > 180.0) diff -= 360.0 else if (diff < -180.0) diff += 360.0
        if (Math.abs(diff) >= deadbandDeg) angleDeg += diff * (1.0 - exp(-dtS.coerceAtLeast(0.0) / tauS))
        return angleDeg
    }
}
