package net.linspad.atlasphone.running

import net.linspad.atlasphone.mobile.model.RawHeartRate
import net.linspad.atlasphone.mobile.model.RawLocation
import net.linspad.atlasphone.running.metrics.RunMetrics
import net.linspad.atlasphone.running.recap.RecapBuilder
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Recovery samples never reach the running statistics; the HR series covers both phases. */
class RecapBuilderTest {
    private val start = 1_700_000_000_000L
    private val runEnd = start + 300_000L
    // 4 m/s north for 300 s of GPS (1.2 km), HR 150 while running and 120 for 3 minutes after the run end.
    private val locations = (0..300).map { t -> RawLocation(start + t * 1000L, 53.0 + t * 4.0 / 111194.9266, 10.0, 5f, null, null, null, null) }
    private val heartRates = (0..480).map { t -> RawHeartRate(start + t * 1000L, if (t <= 300) 150 else 120, null) }
    private val pauses = emptyList<PauseRecord>()

    @Test fun summaryAtRunEndExcludesTheRecoverySegment() {
        val atRunEnd = RunMetrics.summarize(locations, heartRates.filter { it.timestampMillis <= runEnd }, pauses, start, runEnd)
        val unfiltered = RunMetrics.summarize(locations, heartRates, pauses, start, runEnd)
        assertEquals(150.0, atRunEnd.avgHr!!, 1e-9)
        assertTrue("an unfiltered average would include the recovery readings", unfiltered.avgHr!! < 150.0)
        assertEquals(1200.0, atRunEnd.distanceM, 5.0)
        assertEquals(300.0, atRunEnd.elapsedS, 1e-9)
    }

    @Test fun recapSplitsAndMaxHrUseRunningSamplesOnlyAndHrSeriesCoversBothPhases() {
        val atFinishRun = RecapBuilder.build(locations, heartRates.filter { it.timestampMillis <= runEnd }, pauses, runEnd, null)
        val atTrainingEnd = RecapBuilder.build(locations, heartRates, pauses, runEnd, null)
        assertEquals(atFinishRun.splits, atTrainingEnd.splits)            // recovery does not change the running splits
        assertEquals(150, atFinishRun.maxHr); assertEquals(150, atTrainingEnd.maxHr)
        assertTrue(atFinishRun.splits.isNotEmpty() && atFinishRun.splits.all { it.avgHr == 150.0 })
        assertEquals(start + 300_000L, atFinishRun.hrSeries.last().tsMillis)
        assertEquals(start + 480_000L, atTrainingEnd.hrSeries.last().tsMillis)
        assertEquals(120, atTrainingEnd.hrSeries.last().bpm)
        assertNull(atTrainingEnd.standing)
    }

    @Test fun runWithoutHeartRateHasNoHrBlocks() {
        val r = RecapBuilder.build(locations, emptyList(), pauses, null, null)
        assertNull(r.maxHr); assertTrue(r.hrSeries.isEmpty()); assertTrue(r.splits.isNotEmpty())
        assertTrue(RecapBuilder.build(locations, listOf(RawHeartRate(start, 0, null)), pauses, null, null).hrSeries.isEmpty()) // 0 is no reading
    }
}
