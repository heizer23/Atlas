package net.linspad.atlasphone.running.net

import net.linspad.atlasphone.mobile.model.CaptureSample
import net.linspad.atlasphone.mobile.model.SampleJson
import net.linspad.atlasphone.mobile.model.Stream
import net.linspad.atlasphone.running.RunMeta
import net.linspad.atlasphone.running.ghost.GhostProfile
import net.linspad.atlasphone.running.ghost.RouteGeometry
import org.json.JSONArray
import org.json.JSONException
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

data class HttpRequest(val method: String, val url: String, val headers: Map<String, String>, val body: String?)
data class HttpResponse(val status: Int, val body: String)

/** Transport seam: tests inject a fake. Implementations throw [IOException] on network failure and never log. */
interface HttpTransport {
    fun execute(request: HttpRequest): HttpResponse
}

/** HttpURLConnection implementation; connect 10 s / read 30 s. Does not log URLs, headers or bodies. */
class UrlConnectionTransport : HttpTransport {
    override fun execute(request: HttpRequest): HttpResponse {
        val conn = URL(request.url).openConnection() as HttpURLConnection
        try {
            conn.requestMethod = request.method
            conn.connectTimeout = 10_000
            conn.readTimeout = 30_000
            request.headers.forEach { (k, v) -> conn.setRequestProperty(k, v) }
            if (request.body != null) {
                conn.doOutput = true
                conn.outputStream.use { it.write(request.body.toByteArray(Charsets.UTF_8)) }
            }
            val status = conn.responseCode
            val stream = if (status >= 400) conn.errorStream else conn.inputStream
            val body = stream?.use { it.readBytes().toString(Charsets.UTF_8) } ?: ""
            return HttpResponse(status, body)
        } finally {
            conn.disconnect()
        }
    }
}

sealed interface AtlasResult<out T> {
    data class Success<T>(val value: T) : AtlasResult<T>
    /** 401: missing, unknown or revoked token. The phone shows "re-pair". */
    data object Unauthorized : AtlasResult<Nothing>
    data object NotFound : AtlasResult<Nothing>
    /** Other 4xx; [code] and [message] are the server's ApiError fields (never contain secrets). */
    data class Rejected(val status: Int, val code: String?, val message: String) : AtlasResult<Nothing>
    data class ServerError(val status: Int) : AtlasResult<Nothing>
    data class NetworkError(val message: String) : AtlasResult<Nothing>
}

data class PairResult(val deviceId: String, val deviceToken: String, val deviceName: String)
data class PreparedRun(
    val id: String, val shortId: String, val title: String?, val plannedForMillis: Long?, val expiresAtMillis: Long,
    val routeId: String? = null, val ghostRunId: String? = null,
)
data class StreamCountsLocal(val location: Long, val heartRate: Long)
data class BeginResult(val status: String, val contiguousSeq: Long)
data class SamplesResult(val stored: Int, val duplicates: Int, val contiguousSeq: Long)
data class FinishResult(
    val complete: Boolean,
    val missingRanges: List<LongRange>,
    val mismatchedStreams: List<String>,
    val contiguousSeq: Long,
)

/**
 * HTTPS client for the RunningTracker native endpoints (/api/runningtracker/native/...).
 * Refuses non-https base URLs (N1); sends `Authorization: Bearer <token>` on every call except pair;
 * never logs headers, bodies or tokens, and puts none into exception messages.
 */
class AtlasClient(
    baseUrl: String,
    private val tokenProvider: () -> String?,
    private val transport: HttpTransport,
) {
    private val base: String

    init {
        require(baseUrl.startsWith("https://")) { "Atlas base URL must use https" }
        base = baseUrl.trimEnd('/') + "/api/runningtracker/native"
    }

    fun pair(code: String, deviceName: String): AtlasResult<PairResult> =
        call("POST", "/pair", JSONObject().put("code", code).put("device_name", deviceName), authenticated = false) {
            PairResult(it.getString("device_id"), it.getString("device_token"), it.getString("device_name"))
        }

    fun preparedRuns(): AtlasResult<List<PreparedRun>> = call("GET", "/prepared-runs", null) { o ->
        val a = o.getJSONArray("prepared_runs")
        (0 until a.length()).map { parsePrepared(a.getJSONObject(it)) }
    }

    fun preparedRun(id: String): AtlasResult<PreparedRun> = call("GET", "/prepared-runs/$id", null) { parsePrepared(it) }

    /** Reference route for offline use. */
    fun route(routeId: String): AtlasResult<RouteGeometry> = call("GET", "/routes/$routeId", null) { RouteGeometry.fromJson(it) }

    /** Ghost profile (moving time, progress, heart rate) of a completed run on its route. */
    fun ghostProfile(runId: String): AtlasResult<GhostProfile> = call("GET", "/runs/$runId/ghost-profile", null) { GhostProfile.fromJson(it) }

    fun begin(runId: String, startedAtMillis: Long): AtlasResult<BeginResult> =
        call("POST", "/runs/$runId/begin", JSONObject().put("run_type", "continuous").put("started_at", SampleJson.iso(startedAtMillis))) {
            BeginResult(it.getString("status"), it.getLong("contiguous_seq"))
        }

    /** Stream names are mapped to the server's `location` / `heart_rate`; the payload is the stored JSON unchanged. */
    fun putSamples(runId: String, samples: List<CaptureSample>): AtlasResult<SamplesResult> {
        val arr = JSONArray()
        samples.forEach { s ->
            arr.put(JSONObject().put("stream", if (s.stream == Stream.LOCATION) "location" else "heart_rate")
                .put("seq", s.sequence).put("payload", JSONObject(s.json)))
        }
        return call("PUT", "/runs/$runId/samples", JSONObject().put("samples", arr)) {
            SamplesResult(it.getInt("stored"), it.getInt("duplicates"), it.getLong("contiguous_seq"))
        }
    }

    fun finish(runId: String, meta: RunMeta, counts: StreamCountsLocal, lastSeq: Long, dropped: Long): AtlasResult<FinishResult> {
        val summary = meta.summary ?: return AtlasResult.Rejected(0, null, "run has no summary")
        val finishedAt = meta.finishedAtMillis ?: return AtlasResult.Rejected(0, null, "run has no finish time")
        val pauses = JSONArray()
        meta.pauses.filter { it.endedAtMillis != null }.forEach { p ->
            pauses.put(JSONObject()
                .put("started_at", SampleJson.iso(p.startedAtMillis)).put("ended_at", SampleJson.iso(p.endedAtMillis!!))
                .put("started_elapsed_s", p.startedElapsedS).put("ended_elapsed_s", p.endedElapsedS ?: p.startedElapsedS))
        }
        val body = JSONObject()
            .put("finished_at", SampleJson.iso(finishedAt))
            .put("elapsed_s", summary.elapsedS).put("moving_s", summary.movingS).put("distance_m", summary.distanceM)
            .put("last_seq", lastSeq)
            .put("expected_counts", JSONObject().put("location", counts.location).put("heart_rate", counts.heartRate))
            .put("pauses", pauses).put("dropped", dropped)
        return call("POST", "/runs/$runId/finish", body) { o ->
            val ranges = o.getJSONArray("missing_seq_ranges").let { a -> (0 until a.length()).map { a.getJSONObject(it).let { r -> r.getLong("start")..r.getLong("end") } } }
            val mismatched = o.getJSONArray("count_mismatch").let { a -> (0 until a.length()).map { a.getJSONObject(it).getString("stream") } }
            FinishResult(o.getString("result") == "complete", ranges, mismatched, o.getLong("contiguous_seq"))
        }
    }

    private fun parsePrepared(o: JSONObject) = PreparedRun(
        id = o.getString("id"), shortId = o.getString("short_id"),
        title = if (o.isNull("title")) null else o.getString("title"),
        plannedForMillis = if (o.isNull("planned_for")) null else millis(o.getString("planned_for")),
        expiresAtMillis = millis(o.getString("expires_at")),
        routeId = if (o.isNull("route_id")) null else o.optString("route_id", "").ifEmpty { null },
        ghostRunId = if (o.isNull("ghost_run_id")) null else o.optString("ghost_run_id", "").ifEmpty { null },
    )

    /** ISO-8601 with "Z" or an offset. */
    private fun millis(iso: String) = java.time.OffsetDateTime.parse(iso).toInstant().toEpochMilli()

    private fun <T> call(method: String, path: String, body: JSONObject?, authenticated: Boolean = true, parse: (JSONObject) -> T): AtlasResult<T> {
        val headers = mutableMapOf("Content-Type" to "application/json", "Accept" to "application/json")
        if (authenticated) {
            val token = tokenProvider() ?: return AtlasResult.Unauthorized
            headers["Authorization"] = "Bearer $token"
        }
        val response = try {
            transport.execute(HttpRequest(method, base + path, headers, body?.toString()))
        } catch (e: IOException) {
            return AtlasResult.NetworkError("network error (${e.javaClass.simpleName})")
        }
        val status = response.status
        return when {
            status in 200..299 -> try {
                AtlasResult.Success(parse(JSONObject(response.body)))
            } catch (e: JSONException) {
                AtlasResult.ServerError(status)
            }
            status == 401 -> AtlasResult.Unauthorized
            status == 404 -> AtlasResult.NotFound
            status >= 500 -> AtlasResult.ServerError(status)
            else -> {
                val err = runCatching { JSONObject(response.body).getJSONObject("error") }.getOrNull()
                AtlasResult.Rejected(status, err?.optString("code"), err?.optString("message") ?: "request rejected")
            }
        }
    }
}
