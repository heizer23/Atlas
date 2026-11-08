package net.linspad.atlasphone.running

import net.linspad.atlasphone.mobile.model.CaptureSample
import net.linspad.atlasphone.mobile.model.Stream
import net.linspad.atlasphone.running.auth.PairingPayload
import net.linspad.atlasphone.running.net.AtlasClient
import net.linspad.atlasphone.running.net.AtlasResult
import net.linspad.atlasphone.running.net.HttpRequest
import net.linspad.atlasphone.running.net.HttpResponse
import net.linspad.atlasphone.running.net.HttpTransport
import net.linspad.atlasphone.running.net.StreamCountsLocal
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.IOException

/** Fake transport: records requests, answers with a scripted response (or throws). */
class FakeTransport(var respond: (HttpRequest) -> HttpResponse) : HttpTransport {
    val requests = mutableListOf<HttpRequest>()
    override fun execute(request: HttpRequest): HttpResponse { requests += request; return respond(request) }
}

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class AtlasClientTest {
    private val token = "tok-SECRET-abcdefghijklmnopqrstuvwxyz0123456789"
    private val base = "https://atlas.example.ts.net:8443"
    private fun ok(json: String) = HttpResponse(200, json)
    private fun client(t: HttpTransport, tokenProvider: () -> String? = { token }) = AtlasClient(base, tokenProvider, t)

    @Test fun httpBaseUrlIsRefused() {
        val e = assertThrows(IllegalArgumentException::class.java) { AtlasClient("http://atlas.example:8443", { token }, FakeTransport { ok("{}") }) }
        assertFalse(e.message!!.contains(token))
        AtlasClient(base, { token }, FakeTransport { ok("{}") }) // https is accepted
    }

    @Test fun bearerIsSentOnEverythingExceptPair() {
        val t = FakeTransport { r ->
            when {
                r.url.endsWith("/pair") -> ok("""{"device_id":"d","device_token":"t","device_name":"n"}""")
                r.url.endsWith("/prepared-runs") -> ok("""{"prepared_runs":[{"id":"p1","short_id":"ABC234","run_type":"continuous","title":"Easy","planned_for":null,"expires_at":"2030-01-01T00:00:00Z"}]}""")
                r.url.contains("/prepared-runs/") -> ok("""{"id":"p1","short_id":"ABC234","run_type":"continuous","title":null,"planned_for":"2030-01-01T10:00:00+00:00","expires_at":"2030-01-01T00:00:00Z"}""")
                r.url.endsWith("/begin") -> ok("""{"run_id":"r","status":"uploading","high_seq":{"location":0,"heart_rate":0},"contiguous_seq":7}""")
                r.url.endsWith("/samples") -> ok("""{"stored":1,"duplicates":0,"high_seq":{"location":1,"heart_rate":0},"contiguous_seq":1}""")
                else -> ok("""{"result":"complete","run_id":"r","verified_counts":{"location":1,"heart_rate":0},"missing_seq_ranges":[],"count_mismatch":[],"high_seq":{"location":1,"heart_rate":0},"contiguous_seq":1}""")
            }
        }
        val c = client(t)
        assertTrue(c.pair("ABCD2345", "Pixel") is AtlasResult.Success)
        val list = c.preparedRuns() as AtlasResult.Success
        assertEquals("Easy", list.value.single().title)
        assertEquals(1_893_456_000_000, list.value.single().expiresAtMillis)
        assertNotNull((c.preparedRun("p1") as AtlasResult.Success).value.plannedForMillis)
        assertEquals(7L, (c.begin("r", 1_700_000_000_000) as AtlasResult.Success).value.contiguousSeq)
        assertTrue(c.putSamples("r", listOf(CaptureSample("r", 1, Stream.LOCATION, 1, """{"timestamp":"2026-01-01T00:00:00.000Z"}"""))) is AtlasResult.Success)
        assertTrue(c.finish("r", finishedMeta(), StreamCountsLocal(1, 0), 1, 0) is AtlasResult.Success)

        for (req in t.requests) {
            assertTrue(req.url.startsWith("$base/api/runningtracker/native/"))
            if (req.url.endsWith("/pair")) assertNull("pair must not send Authorization", req.headers["Authorization"])
            else assertEquals("Bearer $token", req.headers["Authorization"])
        }
        assertEquals(listOf("POST", "GET", "GET", "POST", "PUT", "POST"), t.requests.map { it.method })
    }

    @Test fun streamNamesAreMappedAndPayloadIsUnchanged() {
        val t = FakeTransport { ok("""{"stored":2,"duplicates":0,"high_seq":{"location":1,"heart_rate":2},"contiguous_seq":2}""") }
        val loc = """{"type":"location.sample","timestamp":"2026-01-01T00:00:00.000Z","latitude":52.5,"speedMetersPerSecond":null}"""
        val hr = """{"type":"heartRate.sample","timestamp":"2026-01-01T00:00:01.000Z","bpm":150}"""
        client(t).putSamples("r", listOf(CaptureSample("r", 1, Stream.LOCATION, 0, loc), CaptureSample("r", 2, Stream.HEART_RATE, 1, hr)))
        val samples = JSONObject(t.requests.single().body!!).getJSONArray("samples")
        assertEquals("location", samples.getJSONObject(0).getString("stream"))
        assertEquals("heart_rate", samples.getJSONObject(1).getString("stream"))
        assertEquals(2L, samples.getJSONObject(1).getLong("seq"))
        assertTrue(samples.getJSONObject(0).getJSONObject("payload").isNull("speedMetersPerSecond")) // nullable fields stay null
        assertEquals(52.5, samples.getJSONObject(0).getJSONObject("payload").getDouble("latitude"), 0.0)
    }

    @Test fun finishBodyCarriesSummaryPausesAndCounts() {
        val t = FakeTransport { ok("""{"result":"incomplete","run_id":"r","verified_counts":{"location":1,"heart_rate":0},"missing_seq_ranges":[{"start":5,"end":8}],"count_mismatch":[{"stream":"heart_rate","expected":3,"stored":0}],"high_seq":{"location":1,"heart_rate":0},"contiguous_seq":4}""") }
        val r = client(t).finish("r", finishedMeta(), StreamCountsLocal(10, 3), 20, 2) as AtlasResult.Success
        assertFalse(r.value.complete)
        assertEquals(listOf(5L..8L), r.value.missingRanges)
        assertEquals(listOf("heart_rate"), r.value.mismatchedStreams)
        val body = JSONObject(t.requests.single().body!!)
        assertEquals(20, body.getInt("last_seq")); assertEquals(2, body.getInt("dropped"))
        assertEquals(10, body.getJSONObject("expected_counts").getInt("location"))
        assertEquals(3, body.getJSONObject("expected_counts").getInt("heart_rate"))
        assertEquals(1, body.getJSONArray("pauses").length()) // the open pause is not sent
        assertEquals(1800.0, body.getDouble("elapsed_s"), 0.0)
    }

    @Test fun statusCodesMapToResults() {
        fun call(status: Int, body: String = "{}") = client(FakeTransport { HttpResponse(status, body) }).begin("r", 0)
        assertEquals(AtlasResult.Unauthorized, call(401))
        assertEquals(AtlasResult.NotFound, call(404))
        assertTrue(call(503) is AtlasResult.ServerError)
        val rejected = call(409, """{"error":{"code":"RUN_NOT_UPLOADABLE","message":"Run is already complete.","detail":null,"request_id":"x"}}""") as AtlasResult.Rejected
        assertEquals("RUN_NOT_UPLOADABLE", rejected.code)
        assertTrue(call(200, "<html>not json</html>") is AtlasResult.ServerError)
        assertTrue(client(FakeTransport { throw IOException("boom $token") }).begin("r", 0) is AtlasResult.NetworkError)
    }

    @Test fun missingTokenIsUnauthorizedWithoutAnyRequest() {
        val t = FakeTransport { ok("{}") }
        assertEquals(AtlasResult.Unauthorized, client(t) { null }.preparedRuns())
        assertTrue(t.requests.isEmpty())
    }

    @Test fun errorsAndResultsNeverContainTheToken() {
        val io = client(FakeTransport { throw IOException("connect failed for $token") }).preparedRuns()
        assertFalse(io.toString().contains(token))
        val rejected = client(FakeTransport { HttpResponse(400, """{"error":{"code":"X","message":"bad"}}""") }).preparedRuns()
        assertFalse(rejected.toString().contains(token))
    }

    // ── PairingPayload (parser of the text/QR format built by src/pairingPayload.ts) ──

    @Test fun pairingPayloadParsing() {
        val full = PairingPayload.parse("ATLASRUN1|https://atlas.example.ts.net:8443|k7m2qx9a")!!
        assertEquals("https://atlas.example.ts.net:8443", full.baseUrl); assertEquals("K7M2QX9A", full.code)
        assertEquals("K7M2QX9A", PairingPayload.parse("  k7m2qx9a ")!!.code)
        assertNull(PairingPayload.parse("k7m2qx9a")!!.baseUrl)
        assertNull(PairingPayload.parse("ATLASRUN1|http://atlas.example:8443|K7M2QX9A"))  // cleartext refused
        assertNull(PairingPayload.parse("ATLASRUN1|https://atlas.example|SHORT"))
        assertNull(PairingPayload.parse("ATLASRUN2|https://atlas.example|K7M2QX9A"))       // unknown prefix
        assertNull(PairingPayload.parse("ATLASRUN1|https://a|K7M2QX9A|extra"))
        assertNull(PairingPayload.parse("O0I1L0O1"))                                       // ambiguous characters are not in the alphabet
        assertNull(PairingPayload.parse(""))
        assertEquals("ATLASRUN1", PairingPayload.PREFIX)
    }

    private fun finishedMeta() = RunMeta(
        "r", RunState.PENDING_UPLOAD, null, null, 1_700_000_000_000, 1_700_001_800_000,
        listOf(PauseRecord(1_700_000_100_000, 1_700_000_160_000, 100.0, 160.0), PauseRecord(1_700_001_700_000, null, 1700.0, null)),
        RunSummary(1800.0, 1740.0, 5000.0, 348.0, 150.0), 0, null, false,
    )
}
