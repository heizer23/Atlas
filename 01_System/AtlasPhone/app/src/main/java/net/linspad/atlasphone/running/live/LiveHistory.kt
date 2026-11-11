package net.linspad.atlasphone.running.live

import net.linspad.atlasphone.running.ghost.GhostLive
import net.linspad.atlasphone.running.ghost.GhostStatus
import net.linspad.atlasphone.running.metrics.LiveMetrics

/** What the cockpit shows beyond the raw [LiveMetrics]. Series x = moving seconds. Everything unknown is null / empty. */
class LiveTrends(
    val smoothedPaceSPerKm: Double?,
    val rollingPaceSPerKm: Double?,
    val paceSeries: List<Pair<Double, Double>>,
    val hrSeries: List<Pair<Double, Double>>,
    /** The ghost's HR at the position you were at, same x axis as [hrSeries]. */
    val ghostHrSeries: List<Pair<Double, Double>>,
    val leadChange100mM: Double?,
    val leadSecondsAgoM: Double?,
    /** Your heart rate along the route (progress metres, bpm), 20 m buckets; only the part already run. */
    val hrByProgress: List<Pair<Double, Double>> = emptyList(),
    /** Change of the time gap to the ghost over the last ~25 s: negative = gaining / lead growing. Null until measurable. */
    val gapChangeS: Double? = null,
) {
    companion object { val EMPTY = LiveTrends(null, null, emptyList(), emptyList(), emptyList(), null, null) }
}

/**
 * Rolling change of the time gap (display only). Compares the gap now with the gap from [MIN_AGE_S] to [WINDOW_S]
 * seconds ago, so a short wobble does not flip the arrow.
 */
class GapTrend {
    private val ts = ArrayList<Double>()
    private val gaps = ArrayList<Double>()

    fun add(t: Double, gapS: Double) {
        ts.add(t); gaps.add(gapS)
        while (ts.size > 1 && ts.first() < t - WINDOW_S) { ts.removeAt(0); gaps.removeAt(0) }
    }

    fun change(): Double? {
        if (ts.isEmpty()) return null
        val now = ts.last()
        val i = ts.indexOfLast { it <= now - MIN_AGE_S }
        return if (i < 0) null else gaps.last() - gaps[i]
    }

    companion object {
        const val MIN_AGE_S = 20.0; const val WINDOW_S = 30.0
        /** Gap changes under this many seconds count as steady. */
        const val STEADY_S = 1.5
    }
}

/**
 * In-memory live history of one run, fed about once a second while recording (not while paused). Lost with the process on
 * purpose: it only feeds the display; the recorded samples are the source of truth.
 */
class LiveHistory(private val windowS: Double = 600.0) {
    private val smoother = PaceSmoother()
    private val pace = Series()
    private val hr = Series()
    private val ghostHr = Series()
    private val momentum = GapMomentum()
    private val gapTrend = GapTrend()
    private val hrByProgress = HrByDistance.Accumulator()
    private var rolling: Double? = null

    fun record(m: LiveMetrics, ghost: GhostLive?) {
        val t = m.movingS
        rolling = m.rollingPaceSPerKm
        lastSmoothed = smoother.update(m.currentPaceSPerKm)
        lastSmoothed?.let { pace.add(t, it) }
        m.currentHr?.let { hr.add(t, it.toDouble()) }
        val r = ghost?.reading
        if (ghost != null && ghost.status == GhostStatus.ON_COURSE && r != null) {
            val s = ghost.progressM
            if (s != null && r.leadM != null) momentum.add(t, s, r.leadM)
            r.ghostHrAtPosition?.let { ghostHr.add(t, it) }
            r.timeGapS?.let { gapTrend.add(t, it) }
            if (s != null) m.currentHr?.let { hrByProgress.add(s, it.toDouble()) }
        }
        lastT = t
    }

    private var lastSmoothed: Double? = null
    private var lastT = 0.0

    fun snapshot(): LiveTrends {
        val from = lastT - windowS
        fun recent(s: Series) = s.points().filter { it.first >= from }
        return LiveTrends(
            smoothedPaceSPerKm = lastSmoothed,
            rollingPaceSPerKm = rolling,
            paceSeries = recent(pace), hrSeries = recent(hr), ghostHrSeries = recent(ghostHr),
            leadChange100mM = momentum.changeOver100m(), leadSecondsAgoM = momentum.leadSecondsAgo(),
            hrByProgress = hrByProgress.snapshot(), gapChangeS = gapTrend.change(),
        )
    }
}
