package net.linspad.atlasphone.running

import net.linspad.atlasphone.mobile.model.RawHeartRate
import net.linspad.atlasphone.mobile.model.RawLocation
import org.json.JSONArray
import org.json.JSONObject
import java.time.Instant

/** Lifecycle: PREPARED -> RECORDING <-> PAUSED -> COMPLETED_LOCAL -> PENDING_UPLOAD -> SYNCED (see [RunLifecycle]). */
enum class RunState { PREPARED, RECORDING, PAUSED, COMPLETED_LOCAL, PENDING_UPLOAD, SYNCED }

/** One manual pause; open while [endedAtMillis] is null. Offsets are seconds on the phone's monotonic clock since run start. */
data class PauseRecord(
    val startedAtMillis: Long,
    val endedAtMillis: Long?,
    val startedElapsedS: Double,
    val endedElapsedS: Double?,
)

/** Initial stats computed on the phone with RunMetrics (the server recomputes authoritative series and splits). */
data class RunSummary(
    val elapsedS: Double,
    val movingS: Double,
    val distanceM: Double,
    val avgPaceSPerKm: Double?,
    val avgHr: Double?,
)

/**
 * Persisted in CaptureStore.run_meta; run id == capture id == server run id.
 * [uploadCursor] is the server's contiguous_seq as last reported; [needsRepair] means the server answered 401.
 */
data class RunMeta(
    val captureId: String,
    val state: RunState,
    val preparedShortId: String?,
    val title: String?,
    val startedAtMillis: Long,
    val finishedAtMillis: Long?,
    val pauses: List<PauseRecord>,
    val summary: RunSummary?,
    val uploadCursor: Long,
    val lastError: String?,
    val needsRepair: Boolean,
    val routeId: String? = null,
    val ghostRunId: String? = null,
) {
    fun toJson(): String = JSONObject()
        .put("captureId", captureId)
        .put("state", state.name)
        .put("preparedShortId", preparedShortId ?: JSONObject.NULL)
        .put("title", title ?: JSONObject.NULL)
        .put("startedAtMillis", startedAtMillis)
        .put("finishedAtMillis", finishedAtMillis ?: JSONObject.NULL)
        .put("pauses", JSONArray(pauses.map { p ->
            JSONObject()
                .put("startedAtMillis", p.startedAtMillis)
                .put("endedAtMillis", p.endedAtMillis ?: JSONObject.NULL)
                .put("startedElapsedS", p.startedElapsedS)
                .put("endedElapsedS", p.endedElapsedS ?: JSONObject.NULL)
        }))
        .put("summary", summary?.let {
            JSONObject()
                .put("elapsedS", it.elapsedS).put("movingS", it.movingS).put("distanceM", it.distanceM)
                .put("avgPaceSPerKm", it.avgPaceSPerKm ?: JSONObject.NULL).put("avgHr", it.avgHr ?: JSONObject.NULL)
        } ?: JSONObject.NULL)
        .put("uploadCursor", uploadCursor)
        .put("lastError", lastError ?: JSONObject.NULL)
        .put("needsRepair", needsRepair)
        .put("routeId", routeId ?: JSONObject.NULL)
        .put("ghostRunId", ghostRunId ?: JSONObject.NULL)
        .toString()

    companion object {
        fun fromJson(json: String): RunMeta {
            val o = JSONObject(json)
            fun JSONObject.optStr(k: String): String? = if (isNull(k)) null else getString(k)
            fun JSONObject.optD(k: String): Double? = if (isNull(k)) null else getDouble(k)
            fun JSONObject.optL(k: String): Long? = if (isNull(k)) null else getLong(k)
            val pauses = o.getJSONArray("pauses").let { a ->
                (0 until a.length()).map { i ->
                    val p = a.getJSONObject(i)
                    PauseRecord(p.getLong("startedAtMillis"), p.optL("endedAtMillis"), p.getDouble("startedElapsedS"), p.optD("endedElapsedS"))
                }
            }
            val summary = if (o.isNull("summary")) null else o.getJSONObject("summary").let {
                RunSummary(it.getDouble("elapsedS"), it.getDouble("movingS"), it.getDouble("distanceM"), it.optD("avgPaceSPerKm"), it.optD("avgHr"))
            }
            return RunMeta(
                captureId = o.getString("captureId"), state = RunState.valueOf(o.getString("state")),
                preparedShortId = o.optStr("preparedShortId"), title = o.optStr("title"),
                startedAtMillis = o.getLong("startedAtMillis"), finishedAtMillis = o.optL("finishedAtMillis"),
                pauses = pauses, summary = summary, uploadCursor = o.getLong("uploadCursor"),
                lastError = o.optStr("lastError"), needsRepair = o.getBoolean("needsRepair"),
                routeId = if (o.has("routeId")) o.optStr("routeId") else null,
                ghostRunId = if (o.has("ghostRunId")) o.optStr("ghostRunId") else null,
            )
        }
    }
}

/** Rebuilds raw samples from the public JSON payloads stored in the capture buffer (finish summary, recovery). */
object SampleDecoder {
    fun location(json: String): RawLocation? = runCatching {
        val o = JSONObject(json)
        fun d(k: String): Double? = if (o.isNull(k)) null else o.getDouble(k)
        RawLocation(
            timestampMillis = Instant.parse(o.getString("timestamp")).toEpochMilli(),
            latitude = o.getDouble("latitude"), longitude = o.getDouble("longitude"),
            accuracyMeters = d("accuracyMeters")?.toFloat(), speedMetersPerSecond = d("speedMetersPerSecond")?.toFloat(),
            altitudeMeters = d("altitudeMeters"), bearingDegrees = d("bearingDegrees")?.toFloat(),
            elapsedRealtimeNanos = if (o.isNull("elapsedRealtimeNanos")) null else o.getLong("elapsedRealtimeNanos"),
        )
    }.getOrNull()

    fun heartRate(json: String): RawHeartRate? = runCatching {
        val o = JSONObject(json)
        RawHeartRate(
            timestampMillis = Instant.parse(o.getString("timestamp")).toEpochMilli(), bpm = o.getInt("bpm"),
            rrIntervalsMs = null,
            elapsedRealtimeNanos = if (o.isNull("elapsedRealtimeNanos")) null else o.getLong("elapsedRealtimeNanos"),
        )
    }.getOrNull()
}
