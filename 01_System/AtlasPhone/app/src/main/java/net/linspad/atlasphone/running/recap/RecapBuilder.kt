package net.linspad.atlasphone.running.recap

import net.linspad.atlasphone.mobile.model.RawHeartRate
import net.linspad.atlasphone.mobile.model.RawLocation
import net.linspad.atlasphone.running.PauseRecord
import net.linspad.atlasphone.running.hr.HrConfig
import net.linspad.atlasphone.running.hr.HrPoint
import net.linspad.atlasphone.running.metrics.RunMetrics

/** Pure assembly of [RecapData] (flow step build_recap). */
object RecapBuilder {
    /**
     * Splits and max HR use only samples at or before [runFinishedAtMillis] (all when null); the HR series covers every
     * given reading (bpm >= 1) as the mean per RECAP_BUCKET_S. [standing] is passed through unchanged.
     */
    fun build(
        locations: List<RawLocation>, heartRates: List<RawHeartRate>, pauses: List<PauseRecord>,
        runFinishedAtMillis: Long?, standing: FinishStanding?,
    ): RecapData {
        val cut = runFinishedAtMillis ?: Long.MAX_VALUE
        val runLocations = locations.filter { it.timestampMillis <= cut }
        val runHr = heartRates.filter { it.timestampMillis <= cut }
        val splits = RunMetrics.splits(runLocations, runHr, pauses)
        val maxHr = runHr.map { it.bpm }.filter { it >= 1 }.maxOrNull()
        val bucketMs = (HrConfig.RECAP_BUCKET_S * 1000).toLong()
        val series = heartRates.filter { it.bpm >= 1 }.groupBy { it.timestampMillis / bucketMs }.toSortedMap()
            .map { (bucket, v) -> HrPoint(bucket * bucketMs, Math.round(v.sumOf { it.bpm }.toDouble() / v.size).toInt()) }
        return RecapData(standing, splits, maxHr, series)
    }
}
