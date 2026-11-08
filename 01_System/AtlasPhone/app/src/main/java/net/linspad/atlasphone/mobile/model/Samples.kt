package net.linspad.atlasphone.mobile.model

import org.json.JSONArray
import org.json.JSONObject
import java.time.Instant
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter

/** A GPS fix as delivered by the location module, before it is assigned to a capture. */
data class RawLocation(
    val timestampMillis: Long,
    val latitude: Double,
    val longitude: Double,
    val accuracyMeters: Float?,
    val speedMetersPerSecond: Float?,
    val altitudeMeters: Double?,
    val bearingDegrees: Float?,
)

/** A heart-rate notification as delivered by the heart-rate module (timestamp = arrival on the phone). */
data class RawHeartRate(
    val timestampMillis: Long,
    val bpm: Int,
    val rrIntervalsMs: List<Int>?,
)

enum class Stream(val wireName: String) {
    LOCATION("location.sample"),
    HEART_RATE("heartRate.sample"),
}

/**
 * A sample that belongs to a capture: `sequence` is unique and strictly increasing within the capture
 * (shared by both streams, so interleaving can be reconstructed), `json` is the public payload.
 */
data class CaptureSample(
    val captureId: String,
    val sequence: Long,
    val stream: Stream,
    val timestampMillis: Long,
    val json: String,
)

/** Public payload format (see Sprint01_MobilePlatform/00_draft.md): SI units, ISO-8601 UTC, nullable gaps. */
object SampleJson {
    private val ISO = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'").withZone(ZoneOffset.UTC)

    fun iso(millis: Long): String = ISO.format(Instant.ofEpochMilli(millis))

    fun location(raw: RawLocation, captureId: String?, sequence: Long?): JSONObject = JSONObject()
        .put("type", Stream.LOCATION.wireName)
        .put("captureId", captureId ?: JSONObject.NULL)
        .put("sequence", sequence ?: JSONObject.NULL)
        .put("timestamp", iso(raw.timestampMillis))
        .put("latitude", raw.latitude)
        .put("longitude", raw.longitude)
        .put("accuracyMeters", raw.accuracyMeters?.toDouble() ?: JSONObject.NULL)
        .put("speedMetersPerSecond", raw.speedMetersPerSecond?.toDouble() ?: JSONObject.NULL)
        .put("altitudeMeters", raw.altitudeMeters ?: JSONObject.NULL)
        .put("bearingDegrees", raw.bearingDegrees?.toDouble() ?: JSONObject.NULL)

    fun heartRate(raw: RawHeartRate, captureId: String?, sequence: Long?): JSONObject = JSONObject()
        .put("type", Stream.HEART_RATE.wireName)
        .put("captureId", captureId ?: JSONObject.NULL)
        .put("sequence", sequence ?: JSONObject.NULL)
        .put("timestamp", iso(raw.timestampMillis))
        .put("bpm", raw.bpm)
        .put("rrIntervalsMs", raw.rrIntervalsMs?.let { JSONArray(it) } ?: JSONObject.NULL)
        .put("source", "bluetooth")
}
