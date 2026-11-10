package net.linspad.atlasphone.running.live

import net.linspad.atlasphone.running.ghost.RoutePoint
import kotlin.math.PI
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

/** Metres east/north of the runner. */
data class MapXY(val east: Double, val north: Double)

/**
 * Local map around the runner (runner at the origin). [route] is the route window near the runner; [ghost] is the
 * ghost's position, clamped to the view edge when it is further than [radiusM] ([ghostClamped]).
 */
class LocalMapView(
    val route: List<MapXY>,
    val runner: MapXY,
    val ghost: MapXY?,
    val ghostClamped: Boolean,
    val radiusM: Double,
)

object LocalMap {
    const val MIN_RADIUS_M = 120.0
    const val MAX_RADIUS_M = 400.0
    /** Route shown behind and ahead of the runner (progress metres). */
    const val BEHIND_M = 150.0
    const val AHEAD_M = 300.0

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

    private fun xy(p: RoutePoint, origin: RoutePoint): MapXY {
        val k = cos(Math.toRadians(origin.lat))
        return MapXY((p.lon - origin.lon) * METRES_PER_DEG * k, (p.lat - origin.lat) * METRES_PER_DEG)
    }

    fun build(points: List<RoutePoint>, runnerProgressM: Double, ghostProgressM: Double?): LocalMapView {
        val me = pointAt(points, runnerProgressM)
        val window = points.filter { it.cumM >= runnerProgressM - BEHIND_M && it.cumM <= runnerProgressM + AHEAD_M }
        // Vertices outside the window are replaced by interpolated end points so the line starts and ends cleanly.
        val line = ArrayList<MapXY>()
        line.add(xy(pointAt(points, runnerProgressM - BEHIND_M), me))
        window.forEach { line.add(xy(it, me)) }
        line.add(xy(pointAt(points, runnerProgressM + AHEAD_M), me))

        val ghostRaw = ghostProgressM?.let { xy(pointAt(points, it), me) }
        val dist = ghostRaw?.let { hypot(it.east, it.north) }
        val radius = if (dist == null) MIN_RADIUS_M else min(MAX_RADIUS_M, max(MIN_RADIUS_M, dist * 1.25))
        val clamped = dist != null && dist > radius * 0.92
        val ghost = if (ghostRaw == null || dist == null) null
        else if (clamped) MapXY(ghostRaw.east / dist * radius * 0.92, ghostRaw.north / dist * radius * 0.92)
        else ghostRaw
        return LocalMapView(line, MapXY(0.0, 0.0), ghost, clamped, radius)
    }
}
