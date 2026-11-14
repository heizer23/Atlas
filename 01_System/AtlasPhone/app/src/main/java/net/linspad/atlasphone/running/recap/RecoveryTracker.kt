package net.linspad.atlasphone.running.recap

import net.linspad.atlasphone.running.hr.HrPoint
import net.linspad.atlasphone.running.metrics.A1

/** What RecoveryScreen renders; [points] are raw readings from runFinishedAt - END_BEFORE_S on (smoothed by the UI per HR2). */
data class RecoveryLive(
    val secondsSinceRunEnd: Double, val summary: RecoverySummary, val points: List<HrPoint>, val lastHr: Int?, val reminderDue: Boolean,
)

/**
 * Live accumulator of the recovery phase: the only consumer of HR samples while in RECOVERY (the running accumulator no
 * longer receives them). Pure; the clock is passed in. [seed] = stored readings with ts >= runFinishedAt - END_BEFORE_S.
 */
class RecoveryTracker(private val runFinishedAtMillis: Long, seed: List<HrPoint>) {
    private val points = ArrayList(seed)

    /** Readings with bpm < 1 are kept raw; HR1 decides validity later. */
    fun addHeartRate(point: HrPoint) {
        if (points.isNotEmpty() && point.tsMillis <= points.last().tsMillis) return // already seeded from the capture / out of order
        points.add(point)
    }

    fun snapshot(nowMillis: Long): RecoveryLive {
        val last = points.lastOrNull { it.bpm >= 1 }?.takeIf { nowMillis - it.tsMillis <= A1.LIVE_HR_STALE_MS }
        return RecoveryLive(
            secondsSinceRunEnd = ((nowMillis - runFinishedAtMillis) / 1000.0).coerceAtLeast(0.0),
            summary = RecoveryMetrics.compute(points, runFinishedAtMillis, nowMillis),
            points = points.toList(), lastHr = last?.bpm,
            reminderDue = nowMillis - runFinishedAtMillis >= RecoveryConfig.REMINDER_MS,
        )
    }
}
