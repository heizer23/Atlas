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
) {
    companion object { val EMPTY = LiveTrends(null, null, emptyList(), emptyList(), emptyList(), null, null) }
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
        )
    }
}
