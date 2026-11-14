package net.linspad.atlasphone.running.recap

import net.linspad.atlasphone.running.ghost.FieldRanking
import net.linspad.atlasphone.running.ghost.GhostComparison
import net.linspad.atlasphone.running.ghost.GhostConfig
import net.linspad.atlasphone.running.ghost.GhostProfile
import kotlin.math.abs

/** Pure ST1 computation; [FieldRanking] and [GhostComparison] are used unchanged. */
object FinishStandings {
    private fun duration(p: GhostProfile) = p.points.last().t

    /**
     * [field] may include [main]; it is deduplicated by run id. (my moving time, my progress) = the last matched fix.
     * Profile durations have the idle start trimmed while [myMovingS] is untrimmed, so the comparison is conservative.
     */
    fun compute(
        main: GhostProfile, field: List<GhostProfile>, previousRunId: String?,
        myMovingS: Double, myProgressM: Double, routeLengthM: Double,
    ): FinishStanding {
        val everyone = (listOf(main) + field).distinctBy { it.runId }
        val completed = myProgressM >= routeLengthM - GhostConfig.BACK_TOLERANCE_M
        // Ties favour the runner: only strictly faster / further ghosts count.
        val ahead = if (completed) everyone.count { duration(it) < myMovingS }
        else everyone.count { GhostComparison.progressNow(it, myMovingS) > myProgressM }
        val position = 1 + ahead
        val mainDuration = duration(main)
        val reading = if (completed) null else GhostComparison.compare(main, myMovingS, myProgressM)
        val rivalBeaten = if (completed) mainDuration > myMovingS else (reading?.leadM ?: 0.0) > 0
        val rivalMargin = if (completed) abs(mainDuration - myMovingS) else reading?.timeGapS?.let { abs(it) }
        val previous = previousRunId?.let { id -> everyone.firstOrNull { it.runId == id } }
        return FinishStanding(
            position = position, fieldSize = everyone.size, overtaken = everyone.size - (position - 1),
            routeCompleted = completed, routeTimeS = if (completed) myMovingS else null,
            rivalBeaten = rivalBeaten, rivalMarginS = rivalMargin, rivalTimeS = mainDuration,
            personalRecord = completed && everyone.isNotEmpty() && position == 1,
            previousRunRank = previousRunId?.let { FieldRanking.ranks(everyone)[it] },
            beatPreviousRun = if (completed && previous != null) duration(previous) > myMovingS else null,
        )
    }
}
