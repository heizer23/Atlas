package net.linspad.atlasphone.running.recap

import net.linspad.atlasphone.running.hr.HrPoint
import net.linspad.atlasphone.running.metrics.SplitInfo
import org.json.JSONArray
import org.json.JSONObject

private fun JSONObject.optD(k: String): Double? = if (isNull(k)) null else getDouble(k)
private fun JSONObject.optI(k: String): Int? = if (isNull(k)) null else getInt(k)

/** HRR1 scalars; every value is null when not computable (never 0). Positive hrr = drop in bpm. */
data class RecoverySummary(val hrEnd: Double?, val hr60: Double?, val hr120: Double?, val hrr60: Double?, val hrr120: Double?) {
    fun toJson(): JSONObject = JSONObject()
        .put("hrEnd", hrEnd ?: JSONObject.NULL).put("hr60", hr60 ?: JSONObject.NULL).put("hr120", hr120 ?: JSONObject.NULL)
        .put("hrr60", hrr60 ?: JSONObject.NULL).put("hrr120", hrr120 ?: JSONObject.NULL)

    companion object {
        fun fromJson(o: JSONObject) = RecoverySummary(o.optD("hrEnd"), o.optD("hr60"), o.optD("hr120"), o.optD("hrr60"), o.optD("hrr120"))
    }
}

/** ST1 result persisted at Finish Run; displayed as position / (fieldSize + 1). */
data class FinishStanding(
    val position: Int, val fieldSize: Int, val overtaken: Int, val routeCompleted: Boolean, val routeTimeS: Double?,
    val rivalBeaten: Boolean, val rivalMarginS: Double?, val rivalTimeS: Double,
    val personalRecord: Boolean, val previousRunRank: Int?, val beatPreviousRun: Boolean?,
) {
    fun toJson(): JSONObject = JSONObject()
        .put("position", position).put("fieldSize", fieldSize).put("overtaken", overtaken).put("routeCompleted", routeCompleted)
        .put("routeTimeS", routeTimeS ?: JSONObject.NULL).put("rivalBeaten", rivalBeaten)
        .put("rivalMarginS", rivalMarginS ?: JSONObject.NULL).put("rivalTimeS", rivalTimeS)
        .put("personalRecord", personalRecord).put("previousRunRank", previousRunRank ?: JSONObject.NULL)
        .put("beatPreviousRun", beatPreviousRun ?: JSONObject.NULL)

    companion object {
        fun fromJson(o: JSONObject) = FinishStanding(
            o.getInt("position"), o.getInt("fieldSize"), o.getInt("overtaken"), o.getBoolean("routeCompleted"), o.optD("routeTimeS"),
            o.getBoolean("rivalBeaten"), o.optD("rivalMarginS"), o.getDouble("rivalTimeS"),
            o.getBoolean("personalRecord"), o.optI("previousRunRank"), if (o.isNull("beatPreviousRun")) null else o.getBoolean("beatPreviousRun"),
        )
    }
}

/**
 * Everything the recap needs offline (local samples are purged after a verified sync): standing (null without ghost),
 * running-phase per-km splits and max HR, and a 1-second-bucket HR series over running + recovery (absolute timestamps).
 */
data class RecapData(val standing: FinishStanding?, val splits: List<SplitInfo>, val maxHr: Int?, val hrSeries: List<HrPoint>) {
    fun toJson(): JSONObject = JSONObject()
        .put("standing", standing?.toJson() ?: JSONObject.NULL)
        .put("splits", JSONArray(splits.map { s ->
            JSONObject().put("km", s.km).put("distanceM", s.distanceM).put("durationS", s.durationS)
                .put("paceSPerKm", s.paceSPerKm).put("avgHr", s.avgHr ?: JSONObject.NULL).put("partial", s.partial)
        }))
        .put("maxHr", maxHr ?: JSONObject.NULL)
        .put("hrSeries", JSONArray(hrSeries.map { JSONArray(listOf(it.tsMillis, it.bpm)) }))

    companion object {
        fun fromJson(o: JSONObject): RecapData {
            val sp = o.getJSONArray("splits")
            val hr = o.getJSONArray("hrSeries")
            return RecapData(
                if (o.isNull("standing")) null else FinishStanding.fromJson(o.getJSONObject("standing")),
                (0 until sp.length()).map { i ->
                    sp.getJSONObject(i).let { SplitInfo(it.getInt("km"), it.getDouble("distanceM"), it.getDouble("durationS"), it.getDouble("paceSPerKm"), it.optD("avgHr"), it.getBoolean("partial")) }
                },
                o.optI("maxHr"),
                (0 until hr.length()).map { i -> hr.getJSONArray(i).let { HrPoint(it.getLong(0), it.getInt(1)) } },
            )
        }
    }
}
